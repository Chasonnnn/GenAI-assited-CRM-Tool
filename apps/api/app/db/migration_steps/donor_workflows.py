"""Add required workflow subjects and execution subject context."""

import sqlalchemy as sa

from alembic import op


def upgrade() -> None:
    op.add_column(
        "automation_workflows",
        sa.Column("subject_type", sa.String(length=50), nullable=True),
    )
    op.execute(
        """
        UPDATE automation_workflows
        SET subject_type = CASE
            WHEN trigger_type = 'form_submitted' THEN 'form_submission'
            WHEN trigger_type = 'intake_lead_created' THEN 'intake_lead'
            WHEN trigger_type IN ('match_proposed', 'match_accepted', 'match_rejected')
                THEN 'match'
            WHEN trigger_type IN ('appointment_scheduled', 'appointment_completed')
                THEN 'appointment'
            ELSE 'surrogate'
        END
        """
    )
    op.alter_column(
        "automation_workflows",
        "subject_type",
        existing_type=sa.String(length=50),
        nullable=False,
        server_default=sa.text("'surrogate'"),
    )
    op.create_index(
        "idx_wf_org_subject",
        "automation_workflows",
        ["organization_id", "subject_type", "is_enabled"],
    )

    op.add_column(
        "workflow_executions",
        sa.Column("subject_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "workflow_executions",
        sa.Column("subject_id", sa.UUID(), nullable=True),
    )

    op.execute(
        """
        UPDATE workflow_executions
        SET subject_type = entity_type,
            subject_id = entity_id
        WHERE entity_type IN (
            'surrogate', 'form_submission', 'intake_lead', 'match', 'appointment'
        )
        """
    )
    op.execute(
        """
        UPDATE workflow_executions execution
        SET subject_type = 'surrogate',
            subject_id = task.surrogate_id
        FROM tasks task
        WHERE execution.entity_type = 'task'
          AND execution.entity_id = task.id
          AND task.surrogate_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE workflow_executions execution
        SET subject_type = donor.donor_type || '_donor',
            subject_id = task.donor_id
        FROM tasks task
        JOIN donors donor
          ON donor.id = task.donor_id
         AND donor.organization_id = task.organization_id
        WHERE execution.entity_type = 'task'
          AND execution.entity_id = task.id
          AND task.donor_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE workflow_executions execution
        SET subject_type = CASE
                WHEN note.entity_type = 'donor' THEN donor.donor_type || '_donor'
                ELSE 'surrogate'
            END,
            subject_id = note.entity_id
        FROM entity_notes note
        LEFT JOIN donors donor
          ON note.entity_type = 'donor'
         AND donor.id = note.entity_id
         AND donor.organization_id = note.organization_id
        WHERE execution.entity_type = 'note'
          AND execution.entity_id = note.id
          AND (
              note.entity_type = 'surrogate'
              OR (note.entity_type = 'donor' AND donor.id IS NOT NULL)
          )
        """
    )
    op.execute(
        """
        UPDATE workflow_executions execution
        SET subject_type = donor.donor_type || '_donor',
            subject_id = donor.id
        FROM donors donor
        WHERE execution.entity_type = 'document'
          AND execution.entity_id = donor.profile_photo_attachment_id
          AND donor.organization_id = execution.organization_id
        """
    )
    op.create_index(
        "idx_exec_subject",
        "workflow_executions",
        ["organization_id", "subject_type", "subject_id"],
    )


def downgrade() -> None:
    # Donor workflows and execution payloads are not meaningful without the
    # subject discriminator introduced by this revision.
    # Serialize worker claims and legal-hold creation through all destructive work.
    op.execute(
        """
        LOCK TABLE
            legal_holds,
            automation_workflows,
            workflow_executions,
            jobs,
            email_logs,
            email_deliveries
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
                          AND (
                              EXISTS (
                                  SELECT 1 FROM automation_workflows workflow
                                  WHERE workflow.organization_id = legal_hold.organization_id
                                    AND workflow.subject_type
                                        IN ('egg_donor', 'sperm_donor')
                              )
                              OR EXISTS (
                                  SELECT 1 FROM workflow_executions execution
                                  WHERE execution.organization_id = legal_hold.organization_id
                                    AND execution.subject_type
                                        IN ('egg_donor', 'sperm_donor')
                              )
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'donor'
                          AND EXISTS (
                              SELECT 1 FROM workflow_executions execution
                              WHERE execution.organization_id = legal_hold.organization_id
                                AND execution.subject_type
                                    IN ('egg_donor', 'sperm_donor')
                                AND execution.subject_id = legal_hold.entity_id
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'workflow_execution'
                          AND EXISTS (
                              SELECT 1 FROM workflow_executions execution
                              WHERE execution.organization_id = legal_hold.organization_id
                                AND execution.id = legal_hold.entity_id
                                AND execution.subject_type
                                    IN ('egg_donor', 'sperm_donor')
                          )
                      )
                      OR (
                          legal_hold.entity_type = 'task'
                          AND EXISTS (
                              SELECT 1 FROM workflow_executions execution
                              WHERE execution.organization_id = legal_hold.organization_id
                                AND execution.entity_type = 'task'
                                AND execution.entity_id = legal_hold.entity_id
                                AND execution.subject_type
                                    IN ('egg_donor', 'sperm_donor')
                          )
                      )
                      OR (
                          legal_hold.entity_type IN (
                              'form_submission',
                              'intake_lead',
                              'meta_lead'
                          )
                          AND EXISTS (
                              SELECT 1 FROM workflow_executions execution
                              WHERE execution.organization_id = legal_hold.organization_id
                                AND execution.entity_type = legal_hold.entity_type
                                AND execution.entity_id = legal_hold.entity_id
                                AND execution.subject_type
                                    IN ('egg_donor', 'sperm_donor')
                          )
                      )
                      OR (
                          legal_hold.entity_type IN ('entity_notes', 'entity_note', 'note')
                          AND EXISTS (
                              SELECT 1 FROM workflow_executions execution
                              WHERE execution.organization_id = legal_hold.organization_id
                                AND execution.entity_type = 'note'
                                AND execution.entity_id = legal_hold.entity_id
                                AND execution.subject_type
                                    IN ('egg_donor', 'sperm_donor')
                          )
                      )
                  )
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade donor workflows while donor data is under legal hold';
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM jobs job
                WHERE job.status = 'running'
                  AND (
                      (
                          job.job_type = 'workflow_email'
                          AND (
                              job.payload->>'subject_type' IN ('egg_donor', 'sperm_donor')
                              OR job.payload->>'workflow_execution_id' IN (
                                  SELECT id::text
                                  FROM workflow_executions
                                  WHERE subject_type IN ('egg_donor', 'sperm_donor')
                              )
                          )
                      )
                      OR (
                          job.job_type = 'workflow_resume'
                          AND job.payload->>'execution_id' IN (
                              SELECT id::text
                              FROM workflow_executions
                              WHERE subject_type IN ('egg_donor', 'sperm_donor')
                          )
                      )
                      OR (
                          job.job_type = 'notification'
                          AND job.payload->>'entity_type'
                              IN ('donor', 'egg_donor', 'sperm_donor')
                      )
                  )
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade donor workflows while donor jobs are running; '
                    'stop workers and retry';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM email_deliveries delivery
                JOIN email_logs email_log
                  ON email_log.id = delivery.email_log_id
                 AND email_log.organization_id = delivery.organization_id
                WHERE delivery.status = 'leased'
                  AND (
                      email_log.job_id IN (
                          SELECT job.id
                          FROM jobs job
                          WHERE job.job_type = 'workflow_email'
                            AND (
                                job.payload->>'subject_type'
                                    IN ('egg_donor', 'sperm_donor')
                                OR job.payload->>'workflow_execution_id' IN (
                                    SELECT id::text
                                    FROM workflow_executions
                                    WHERE subject_type IN ('egg_donor', 'sperm_donor')
                                )
                            )
                      )
                      OR (
                          email_log.source_type = 'workflow_job'
                          AND email_log.source_id IN (
                              SELECT job.id
                              FROM jobs job
                              WHERE job.job_type = 'workflow_email'
                                AND (
                                    job.payload->>'subject_type'
                                        IN ('egg_donor', 'sperm_donor')
                                    OR job.payload->>'workflow_execution_id' IN (
                                        SELECT id::text
                                        FROM workflow_executions
                                        WHERE subject_type
                                            IN ('egg_donor', 'sperm_donor')
                                    )
                                )
                          )
                      )
                  )
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade donor workflows while a donor email delivery is leased; '
                    'stop workers and retry';
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DELETE FROM email_logs
        WHERE job_id IN (
            SELECT job.id
            FROM jobs job
            WHERE job.job_type = 'workflow_email'
              AND (
                  job.payload->>'subject_type' IN ('egg_donor', 'sperm_donor')
                  OR job.payload->>'workflow_execution_id' IN (
                      SELECT id::text
                      FROM workflow_executions
                      WHERE subject_type IN ('egg_donor', 'sperm_donor')
                  )
              )
        )
        OR (
            source_type = 'workflow_job'
            AND source_id IN (
                SELECT job.id
                FROM jobs job
                WHERE job.job_type = 'workflow_email'
                  AND (
                      job.payload->>'subject_type' IN ('egg_donor', 'sperm_donor')
                      OR job.payload->>'workflow_execution_id' IN (
                          SELECT id::text
                          FROM workflow_executions
                          WHERE subject_type IN ('egg_donor', 'sperm_donor')
                      )
                  )
            )
        )
        """
    )
    op.execute(
        """
        DELETE FROM jobs job
        WHERE (
            job.job_type = 'workflow_email'
            AND (
                job.payload->>'subject_type' IN ('egg_donor', 'sperm_donor')
                OR job.payload->>'workflow_execution_id' IN (
                    SELECT id::text
                    FROM workflow_executions
                    WHERE subject_type IN ('egg_donor', 'sperm_donor')
                )
            )
        )
        OR (
            job.job_type = 'workflow_resume'
            AND job.payload->>'execution_id' IN (
                SELECT id::text
                FROM workflow_executions
                WHERE subject_type IN ('egg_donor', 'sperm_donor')
            )
        )
        OR (
            job.job_type = 'notification'
            AND job.payload->>'entity_type' IN ('donor', 'egg_donor', 'sperm_donor')
        )
        """
    )
    op.execute("DELETE FROM workflow_executions WHERE subject_type IN ('egg_donor', 'sperm_donor')")
    op.execute(
        "DELETE FROM automation_workflows WHERE subject_type IN ('egg_donor', 'sperm_donor')"
    )
    op.drop_index("idx_exec_subject", table_name="workflow_executions")
    op.drop_column("workflow_executions", "subject_id")
    op.drop_column("workflow_executions", "subject_type")

    op.drop_index("idx_wf_org_subject", table_name="automation_workflows")
    op.drop_column("automation_workflows", "subject_type")
