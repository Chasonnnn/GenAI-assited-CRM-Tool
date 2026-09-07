"""Attach work to exact cases and attempts without guessing historical ownership."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260905_1500_match_work"
down_revision = "20260905_1400_match_cases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    op.add_column("tasks", sa.Column("work_source", sa.String(20), nullable=True))
    for table in ("tasks", "entity_notes", "attachments"):
        op.add_column(table, sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column(table, sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_match_id", table, "matches", ["match_id"], ["id"], ondelete="RESTRICT"
        )
        op.create_foreign_key(
            f"fk_{table}_attempt_id",
            table,
            "match_attempts",
            ["attempt_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            f"fk_{table}_match_org",
            table,
            "matches",
            ["organization_id", "match_id"],
            ["organization_id", "id"],
        )
        op.create_foreign_key(
            f"fk_{table}_attempt_context",
            table,
            "match_attempts",
            ["organization_id", "match_id", "attempt_id"],
            ["organization_id", "match_id", "id"],
        )
        op.create_check_constraint(
            f"ck_{table}_attempt_match", table, "attempt_id IS NULL OR match_id IS NOT NULL"
        )
        op.create_index(
            f"idx_{table}_match_attempt", table, ["organization_id", "match_id", "attempt_id"]
        )
    op.add_column("entity_notes", sa.Column("work_source", sa.String(20), nullable=True))
    op.create_check_constraint(
        "ck_entity_notes_match_subject",
        "entity_notes",
        "match_id IS NULL OR (entity_type = 'match' AND entity_id = match_id)",
    )
    op.drop_constraint("ck_tasks_donor_subject_exclusive", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_donor_subject_exclusive",
        "tasks",
        "donor_id IS NULL OR (surrogate_id IS NULL AND (intended_parent_id IS NULL OR match_id IS NOT NULL))",
    )
    # A participant label on case work must describe a party of that exact case.
    # Historical rows keep NULL context; no pair- or date-based backfill is safe.
    op.execute("""
        CREATE FUNCTION validate_match_work_participants() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE case_row matches%ROWTYPE;
        BEGIN
            IF NEW.match_id IS NULL THEN RETURN NEW; END IF;
            SELECT * INTO case_row FROM matches WHERE id = NEW.match_id AND organization_id = NEW.organization_id;
            IF NOT FOUND THEN RAISE EXCEPTION 'Invalid match work context' USING ERRCODE = '23514'; END IF;
            IF TG_TABLE_NAME = 'tasks' THEN
                IF NEW.surrogate_id IS DISTINCT FROM case_row.surrogate_id
                   OR NEW.intended_parent_id IS DISTINCT FROM case_row.intended_parent_id
                   OR NEW.donor_id IS DISTINCT FROM case_row.donor_id THEN
                    RAISE EXCEPTION 'Task participants differ from match' USING ERRCODE = '23514';
                END IF;
            ELSE
                IF (NEW.surrogate_id IS NOT NULL AND NEW.surrogate_id IS DISTINCT FROM case_row.surrogate_id)
                   OR (NEW.intended_parent_id IS NOT NULL AND NEW.intended_parent_id IS DISTINCT FROM case_row.intended_parent_id)
                   OR (NEW.donor_id IS NOT NULL AND NEW.donor_id IS DISTINCT FROM case_row.donor_id) THEN
                    RAISE EXCEPTION 'File source is not a match participant' USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END $$
    """)
    for table in ("tasks", "attachments"):
        op.execute(
            f"CREATE TRIGGER {table}_match_participants BEFORE INSERT OR UPDATE OF organization_id, match_id, surrogate_id, intended_parent_id, donor_id ON {table} FOR EACH ROW EXECUTE FUNCTION validate_match_work_participants()"
        )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    # Acquire every affected table before any guard so later-table writes cannot
    # race a successful earlier check. Locks last through the destructive DDL.
    op.execute("LOCK TABLE attachments, entity_notes, tasks IN ACCESS EXCLUSIVE MODE")
    connection = op.get_bind()
    for table in ("tasks", "entity_notes", "attachments"):
        source_check = " OR work_source IS NOT NULL" if table != "attachments" else ""
        if connection.execute(
            sa.text(
                f"SELECT EXISTS(SELECT 1 FROM {table} WHERE match_id IS NOT NULL "
                f"OR attempt_id IS NOT NULL{source_check})"
            )
        ).scalar():
            raise RuntimeError("Case work exists; retain this schema and roll forward")
    for table in ("tasks", "attachments"):
        op.execute(f"DROP TRIGGER {table}_match_participants ON {table}")
    op.execute("DROP FUNCTION validate_match_work_participants()")
    op.drop_constraint("ck_tasks_donor_subject_exclusive", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_donor_subject_exclusive",
        "tasks",
        "donor_id IS NULL OR (surrogate_id IS NULL AND intended_parent_id IS NULL)",
    )
    op.drop_constraint("ck_entity_notes_match_subject", "entity_notes", type_="check")
    op.drop_column("entity_notes", "work_source")
    op.drop_column("tasks", "work_source")
    for table in ("tasks", "entity_notes", "attachments"):
        op.drop_index(f"idx_{table}_match_attempt", table_name=table)
        op.drop_constraint(f"ck_{table}_attempt_match", table, type_="check")
        for name in ("attempt_context", "match_org", "attempt_id", "match_id"):
            op.drop_constraint(f"fk_{table}_{name}", table, type_="foreignkey")
        op.drop_column(table, "attempt_id")
        op.drop_column(table, "match_id")
