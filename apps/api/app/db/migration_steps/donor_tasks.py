"""Add donor subject support to tasks."""

import sqlalchemy as sa

from alembic import op


def upgrade() -> None:
    op.add_column("tasks", sa.Column("donor_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_donor_id_donors",
        "tasks",
        "donors",
        ["donor_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_tasks_donor", "tasks", ["donor_id"])
    op.create_check_constraint(
        "ck_tasks_donor_subject_exclusive",
        "tasks",
        "donor_id IS NULL OR (surrogate_id IS NULL AND intended_parent_id IS NULL)",
    )


def downgrade() -> None:
    # Serialize legal-hold creation, Google sync/cleanup, and donor task writes
    # until this transaction has either failed closed or completed the downgrade.
    op.execute(
        """
        LOCK TABLE legal_holds, tasks, jobs, notifications
        IN EXCLUSIVE MODE
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM legal_holds legal_hold
                WHERE legal_hold.released_at IS NULL
                  AND (
                      (
                          legal_hold.entity_type IS NULL
                          AND EXISTS (
                              SELECT 1 FROM tasks task
                              WHERE task.organization_id = legal_hold.organization_id
                                AND task.donor_id IS NOT NULL
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'donor'
                          AND EXISTS (
                              SELECT 1 FROM tasks task
                              WHERE task.organization_id = legal_hold.organization_id
                                AND task.donor_id = legal_hold.entity_id
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'task'
                          AND EXISTS (
                              SELECT 1 FROM tasks task
                              WHERE task.organization_id = legal_hold.organization_id
                                AND task.id = legal_hold.entity_id
                                AND task.donor_id IS NOT NULL
                          )
                      )
                  )
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade donor tasks while donor data is under legal hold';
            END IF;
        END $$
        """
    )
    has_google_synced_donor_tasks = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS ("
            "SELECT 1 FROM tasks "
            "WHERE donor_id IS NOT NULL AND google_task_id IS NOT NULL"
            ")"
        )
    )
    if has_google_synced_donor_tasks:
        raise RuntimeError(
            "Cannot downgrade while Google-synced donor tasks remain; "
            "complete remote Google Task cleanup first"
        )

    has_unresolved_google_cleanup_jobs = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS ("
            "SELECT 1 FROM jobs "
            "WHERE job_type IN ("
            "'google_task_remote_delete', 'google_task_creation_reconcile'"
            ") "
            "AND status IN ('pending', 'running', 'failed')"
            ")"
        )
    )
    if has_unresolved_google_cleanup_jobs:
        raise RuntimeError(
            "Cannot downgrade while Google task cleanup jobs remain unresolved; "
            "creation recovery jobs must also be complete"
        )

    # The previous schema cannot represent donor-linked tasks. Removing them
    # prevents donor task content from becoming an unscoped generic task.
    op.execute(
        "DELETE FROM notifications "
        "WHERE entity_type = 'task' "
        "AND entity_id IN (SELECT id FROM tasks WHERE donor_id IS NOT NULL)"
    )
    op.execute("DELETE FROM tasks WHERE donor_id IS NOT NULL")
    op.drop_constraint(
        "ck_tasks_donor_subject_exclusive",
        "tasks",
        type_="check",
    )
    op.drop_index("idx_tasks_donor", table_name="tasks")
    op.drop_constraint("fk_tasks_donor_id_donors", "tasks", type_="foreignkey")
    op.drop_column("tasks", "donor_id")
