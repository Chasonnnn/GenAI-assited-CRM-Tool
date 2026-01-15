"""Rename cases to surrogates throughout the database.

Full rename of 'cases' to 'surrogates' across:
- Table names (9 case-prefixed tables)
- Column names (case_number, case_id FKs, case_owner_id_at_attempt)
- Indexes and constraints
- Triggers and functions
- Polymorphic entity_type values
- org_counters counter_type
- Notification preference columns
- Permission strings

Revision ID: 20260113_1100
Revises: 20260113_1000
Create Date: 2026-01-13
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260113_1100"
down_revision: Union[str, Sequence[str], None] = "20260113_1000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# =============================================================================
# Permission key mappings (explicit, no broad REPLACE)
# =============================================================================
PERMISSION_RENAMES = [
    ("view_cases", "view_surrogates"),
    ("edit_cases", "edit_surrogates"),
    ("delete_cases", "delete_surrogates"),
    ("view_post_approval_cases", "view_post_approval_surrogates"),
    ("change_case_status", "change_surrogate_status"),
    ("assign_cases", "assign_surrogates"),
    ("view_case_notes", "view_surrogate_notes"),
    ("edit_case_notes", "edit_surrogate_notes"),
    ("archive_cases", "archive_surrogates"),
    ("import_cases", "import_surrogates"),
]


def upgrade() -> None:
    """Upgrade: Rename cases to surrogates."""

    # =========================================================================
    # 1. Drop dependent indexes/constraints that reference old names
    #    (These will be recreated with new names after table renames)
    # =========================================================================

    # Drop indexes on cases table
    op.execute("DROP INDEX IF EXISTS idx_cases_stage")
    op.execute("DROP INDEX IF EXISTS idx_cases_org_stage")
    op.execute("DROP INDEX IF EXISTS idx_cases_org_owner")
    op.execute("DROP INDEX IF EXISTS idx_cases_org_status_label")
    op.execute("DROP INDEX IF EXISTS idx_cases_org_created")
    op.execute("DROP INDEX IF EXISTS idx_cases_org_updated")
    op.execute("DROP INDEX IF EXISTS idx_cases_org_active")
    op.execute("DROP INDEX IF EXISTS idx_cases_meta_ad")
    op.execute("DROP INDEX IF EXISTS idx_cases_meta_form")
    op.execute("DROP INDEX IF EXISTS ix_cases_search_vector")
    op.execute("DROP INDEX IF EXISTS idx_cases_org_phone_hash")
    op.execute("DROP INDEX IF EXISTS idx_cases_reminder_check")
    op.execute("DROP INDEX IF EXISTS uq_case_email_hash_active")

    # Drop indexes on related tables
    op.execute("DROP INDEX IF EXISTS idx_case_history_case")
    op.execute("DROP INDEX IF EXISTS idx_case_activity_case_time")
    op.execute("DROP INDEX IF EXISTS idx_contact_attempts_case")
    op.execute("DROP INDEX IF EXISTS idx_contact_attempts_org_pending")
    op.execute("DROP INDEX IF EXISTS idx_contact_attempts_case_owner")
    op.execute("DROP INDEX IF EXISTS idx_profile_overrides_case")
    op.execute("DROP INDEX IF EXISTS idx_profile_state_case")
    op.execute("DROP INDEX IF EXISTS idx_profile_hidden_case")
    op.execute("DROP INDEX IF EXISTS ix_case_interviews_case_id")

    # Drop indexes on FK tables (tasks, matches, etc.)
    op.execute("DROP INDEX IF EXISTS idx_email_logs_case")
    op.execute("DROP INDEX IF EXISTS idx_attachments_case")
    op.execute("DROP INDEX IF EXISTS idx_form_submission_tokens_case")
    op.execute("DROP INDEX IF EXISTS idx_form_submissions_case")
    op.execute("DROP INDEX IF EXISTS idx_appointments_case")
    op.execute("DROP INDEX IF EXISTS ix_zoom_meetings_case_id")
    op.execute("DROP INDEX IF EXISTS ix_matches_case_id")

    # Drop unique constraints
    op.execute("ALTER TABLE cases DROP CONSTRAINT IF EXISTS uq_case_number")
    op.execute(
        "ALTER TABLE case_profile_overrides DROP CONSTRAINT IF EXISTS uq_case_profile_override_field"
    )
    op.execute(
        "ALTER TABLE case_profile_states DROP CONSTRAINT IF EXISTS uq_case_profile_state_case"
    )
    op.execute(
        "ALTER TABLE case_profile_hidden_fields DROP CONSTRAINT IF EXISTS uq_case_profile_hidden_field"
    )
    op.execute("ALTER TABLE form_submissions DROP CONSTRAINT IF EXISTS uq_form_submission_case")

    # Drop search trigger
    op.execute("DROP TRIGGER IF EXISTS cases_search_vector_trigger ON cases")

    # =========================================================================
    # 2. Rename tables (9 case-prefixed tables)
    # =========================================================================

    op.execute("ALTER TABLE cases RENAME TO surrogates")
    op.execute("ALTER TABLE case_status_history RENAME TO surrogate_status_history")
    op.execute("ALTER TABLE case_activity_log RENAME TO surrogate_activity_log")
    op.execute("ALTER TABLE case_contact_attempts RENAME TO surrogate_contact_attempts")
    op.execute("ALTER TABLE case_imports RENAME TO surrogate_imports")
    op.execute("ALTER TABLE case_interviews RENAME TO surrogate_interviews")
    op.execute("ALTER TABLE case_profile_overrides RENAME TO surrogate_profile_overrides")
    op.execute("ALTER TABLE case_profile_states RENAME TO surrogate_profile_states")
    op.execute("ALTER TABLE case_profile_hidden_fields RENAME TO surrogate_profile_hidden_fields")

    # =========================================================================
    # 3. Rename columns
    # =========================================================================

    # Rename case_number to surrogate_number on surrogates table
    op.execute("ALTER TABLE surrogates RENAME COLUMN case_number TO surrogate_number")

    # Rename case_id to surrogate_id on tables that were renamed
    op.execute("ALTER TABLE surrogate_status_history RENAME COLUMN case_id TO surrogate_id")
    op.execute("ALTER TABLE surrogate_activity_log RENAME COLUMN case_id TO surrogate_id")
    op.execute("ALTER TABLE surrogate_contact_attempts RENAME COLUMN case_id TO surrogate_id")
    op.execute("ALTER TABLE surrogate_profile_overrides RENAME COLUMN case_id TO surrogate_id")
    op.execute("ALTER TABLE surrogate_profile_states RENAME COLUMN case_id TO surrogate_id")
    op.execute("ALTER TABLE surrogate_profile_hidden_fields RENAME COLUMN case_id TO surrogate_id")
    op.execute("ALTER TABLE surrogate_interviews RENAME COLUMN case_id TO surrogate_id")

    # Rename form_field_mappings.case_field to surrogate_field (if exists)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name = 'form_field_mappings' AND column_name = 'case_field') THEN
                EXECUTE 'ALTER TABLE form_field_mappings RENAME COLUMN case_field TO surrogate_field';
            END IF;
        END $$;
    """)

    # Update form_field_mappings unique constraint name
    op.execute("ALTER TABLE form_field_mappings DROP CONSTRAINT IF EXISTS uq_form_case_field")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'form_field_mappings'
                  AND constraint_name = 'uq_form_surrogate_field'
            ) THEN
                EXECUTE 'ALTER TABLE form_field_mappings ADD CONSTRAINT uq_form_surrogate_field UNIQUE (form_id, surrogate_field)';
            END IF;
        END $$;
    """)

    # Rename case_id to surrogate_id on FK tables (keep table names, if columns exist)
    fk_column_renames = [
        ("tasks", "case_id", "surrogate_id"),
        ("matches", "case_id", "surrogate_id"),
        ("attachments", "case_id", "surrogate_id"),
        ("email_logs", "case_id", "surrogate_id"),
        ("zoom_meetings", "case_id", "surrogate_id"),
        ("form_submission_tokens", "case_id", "surrogate_id"),
        ("form_submissions", "case_id", "surrogate_id"),
        ("appointments", "case_id", "surrogate_id"),
        ("meta_leads", "converted_case_id", "converted_surrogate_id"),
        ("surrogate_contact_attempts", "case_owner_id_at_attempt", "surrogate_owner_id_at_attempt"),
    ]

    for table_name, old_col, new_col in fk_column_renames:
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name = '{table_name}' AND column_name = '{old_col}') THEN
                    EXECUTE 'ALTER TABLE {table_name} RENAME COLUMN {old_col} TO {new_col}';
                END IF;
            END $$;
        """)

    # =========================================================================
    # 4. Update polymorphic entity_type values (only if tables exist)
    # =========================================================================

    # Helper to safely update entity_type only if table exists
    entity_type_updates = [
        ("entity_notes", "entity_type"),
        ("ai_conversations", "entity_type"),
        ("ai_entity_summaries", "entity_type"),
        ("workflow_executions", "entity_type"),
        ("entity_versions", "entity_type"),
        ("legal_holds", "entity_type"),
        ("data_retention_policies", "entity_type"),
        ("campaign_recipients", "entity_type"),
    ]

    for table_name, column_name in entity_type_updates:
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}') THEN
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = '{table_name}' AND column_name = '{column_name}') THEN
                        EXECUTE 'UPDATE {table_name} SET {column_name} = ''surrogate'' WHERE {column_name} = ''case''';
                    END IF;
                END IF;
            END $$;
        """)

    # =========================================================================
    # 5. Update org_counters counter_type
    # =========================================================================

    op.execute(
        "UPDATE org_counters SET counter_type = 'surrogate_number' WHERE counter_type = 'case_number'"
    )

    # =========================================================================
    # 6. Rename notification preference columns (if they exist)
    # =========================================================================

    notification_column_renames = [
        ("case_assigned", "surrogate_assigned"),
        ("case_status_changed", "surrogate_status_changed"),
        ("case_handoff", "surrogate_claim_available"),
    ]

    for old_col, new_col in notification_column_renames:
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name = 'user_notification_settings' AND column_name = '{old_col}') THEN
                    EXECUTE 'ALTER TABLE user_notification_settings RENAME COLUMN {old_col} TO {new_col}';
                END IF;
            END $$;
        """)

    # =========================================================================
    # 7. Update permission strings (explicit mapping)
    # =========================================================================

    for old_perm, new_perm in PERMISSION_RENAMES:
        op.execute(
            f"UPDATE role_permissions SET permission = '{new_perm}' WHERE permission = '{old_perm}'"
        )

    for old_perm, new_perm in PERMISSION_RENAMES:
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_permission_overrides') THEN
                    EXECUTE 'UPDATE user_permission_overrides SET permission = ''{new_perm}'' WHERE permission = ''{old_perm}''';
                END IF;
            END $$;
        """)

    # =========================================================================
    # 8. Recreate indexes with new names
    # =========================================================================

    # Indexes on surrogates table
    op.execute("CREATE INDEX idx_surrogates_stage ON surrogates (stage_id)")
    op.execute("CREATE INDEX idx_surrogates_org_stage ON surrogates (organization_id, stage_id)")
    op.execute(
        "CREATE INDEX idx_surrogates_org_owner ON surrogates (organization_id, owner_type, owner_id)"
    )
    op.execute(
        "CREATE INDEX idx_surrogates_org_status_label ON surrogates (organization_id, status_label)"
    )
    op.execute(
        "CREATE INDEX idx_surrogates_org_created ON surrogates (organization_id, created_at)"
    )
    op.execute(
        "CREATE INDEX idx_surrogates_org_updated ON surrogates (organization_id, updated_at)"
    )
    op.execute(
        "CREATE INDEX idx_surrogates_org_active ON surrogates (organization_id) WHERE is_archived = FALSE"
    )
    op.execute(
        "CREATE INDEX idx_surrogates_meta_ad ON surrogates (organization_id, meta_ad_external_id) WHERE meta_ad_external_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_surrogates_meta_form ON surrogates (organization_id, meta_form_id) WHERE meta_form_id IS NOT NULL"
    )
    op.execute("CREATE INDEX ix_surrogates_search_vector ON surrogates USING gin (search_vector)")
    op.execute(
        "CREATE INDEX idx_surrogates_org_phone_hash ON surrogates (organization_id, phone_hash)"
    )
    op.execute(
        "CREATE INDEX idx_surrogates_reminder_check ON surrogates (organization_id, owner_type, contact_status, stage_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_surrogate_email_hash_active ON surrogates (organization_id, email_hash) WHERE is_archived = FALSE"
    )

    # Indexes on related tables
    op.execute(
        "CREATE INDEX idx_surrogate_history_surrogate ON surrogate_status_history (surrogate_id, changed_at)"
    )
    op.execute(
        "CREATE INDEX idx_surrogate_activity_surrogate_time ON surrogate_activity_log (surrogate_id, created_at)"
    )
    op.execute(
        "CREATE INDEX idx_contact_attempts_surrogate ON surrogate_contact_attempts (surrogate_id, attempted_at)"
    )
    op.execute(
        "CREATE INDEX idx_contact_attempts_org_pending ON surrogate_contact_attempts (organization_id, outcome, attempted_at) WHERE outcome != 'reached'"
    )
    op.execute(
        "CREATE INDEX idx_contact_attempts_surrogate_owner ON surrogate_contact_attempts (surrogate_id, surrogate_owner_id_at_attempt, attempted_at)"
    )
    op.execute(
        "CREATE INDEX idx_profile_overrides_surrogate ON surrogate_profile_overrides (surrogate_id)"
    )
    op.execute(
        "CREATE INDEX idx_profile_state_surrogate ON surrogate_profile_states (surrogate_id)"
    )
    op.execute(
        "CREATE INDEX idx_profile_hidden_surrogate ON surrogate_profile_hidden_fields (surrogate_id)"
    )
    op.execute(
        "CREATE INDEX ix_surrogate_interviews_surrogate_id ON surrogate_interviews (surrogate_id)"
    )

    # Indexes on FK tables
    op.execute("CREATE INDEX idx_email_logs_surrogate ON email_logs (surrogate_id, created_at)")
    op.execute("CREATE INDEX idx_attachments_surrogate ON attachments (surrogate_id)")
    op.execute(
        "CREATE INDEX idx_form_submission_tokens_surrogate ON form_submission_tokens (surrogate_id)"
    )
    op.execute("CREATE INDEX idx_form_submissions_surrogate ON form_submissions (surrogate_id)")
    op.execute("CREATE INDEX idx_appointments_surrogate ON appointments (surrogate_id)")
    op.execute("CREATE INDEX ix_zoom_meetings_surrogate_id ON zoom_meetings (surrogate_id)")
    op.execute("CREATE INDEX ix_matches_surrogate_id ON matches (surrogate_id)")

    # =========================================================================
    # 9. Recreate unique constraints with new names
    # =========================================================================

    op.execute(
        "ALTER TABLE surrogates ADD CONSTRAINT uq_surrogate_number UNIQUE (organization_id, surrogate_number)"
    )
    op.execute(
        "ALTER TABLE surrogate_profile_overrides ADD CONSTRAINT uq_surrogate_profile_override_field UNIQUE (surrogate_id, field_key)"
    )
    op.execute(
        "ALTER TABLE surrogate_profile_states ADD CONSTRAINT uq_surrogate_profile_state_surrogate UNIQUE (surrogate_id)"
    )
    op.execute(
        "ALTER TABLE surrogate_profile_hidden_fields ADD CONSTRAINT uq_surrogate_profile_hidden_field UNIQUE (surrogate_id, field_key)"
    )
    op.execute(
        "ALTER TABLE form_submissions ADD CONSTRAINT uq_form_submission_surrogate UNIQUE (form_id, surrogate_id)"
    )

    # =========================================================================
    # 10. Rename and recreate the search vector trigger
    # =========================================================================

    # Drop the old trigger function (if exists) - PostgreSQL doesn't support ALTER FUNCTION IF EXISTS RENAME
    op.execute("DROP FUNCTION IF EXISTS cases_search_vector_update() CASCADE")

    # Update the trigger function body to reference the new table
    op.execute("""
        CREATE OR REPLACE FUNCTION surrogates_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.full_name, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.surrogate_number, '')), 'B');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
    """)

    # Create the trigger
    op.execute("""
        CREATE TRIGGER surrogates_search_vector_trigger
        BEFORE INSERT OR UPDATE ON surrogates
        FOR EACH ROW EXECUTE FUNCTION surrogates_search_vector_update()
    """)


def downgrade() -> None:
    """Downgrade: Revert surrogates back to cases."""

    # Drop new trigger
    op.execute("DROP TRIGGER IF EXISTS surrogates_search_vector_trigger ON surrogates")

    # Drop new indexes
    op.execute("DROP INDEX IF EXISTS idx_surrogates_stage")
    op.execute("DROP INDEX IF EXISTS idx_surrogates_org_stage")
    op.execute("DROP INDEX IF EXISTS idx_surrogates_org_owner")
    op.execute("DROP INDEX IF EXISTS idx_surrogates_org_status_label")
    op.execute("DROP INDEX IF EXISTS idx_surrogates_org_created")
    op.execute("DROP INDEX IF EXISTS idx_surrogates_org_updated")
    op.execute("DROP INDEX IF EXISTS idx_surrogates_org_active")
    op.execute("DROP INDEX IF EXISTS idx_surrogates_meta_ad")
    op.execute("DROP INDEX IF EXISTS idx_surrogates_meta_form")
    op.execute("DROP INDEX IF EXISTS ix_surrogates_search_vector")
    op.execute("DROP INDEX IF EXISTS idx_surrogates_org_phone_hash")
    op.execute("DROP INDEX IF EXISTS idx_surrogates_reminder_check")
    op.execute("DROP INDEX IF EXISTS uq_surrogate_email_hash_active")
    op.execute("DROP INDEX IF EXISTS idx_surrogate_history_surrogate")
    op.execute("DROP INDEX IF EXISTS idx_surrogate_activity_surrogate_time")
    op.execute("DROP INDEX IF EXISTS idx_contact_attempts_surrogate")
    op.execute("DROP INDEX IF EXISTS idx_contact_attempts_org_pending")
    op.execute("DROP INDEX IF EXISTS idx_contact_attempts_surrogate_owner")
    op.execute("DROP INDEX IF EXISTS idx_profile_overrides_surrogate")
    op.execute("DROP INDEX IF EXISTS idx_profile_state_surrogate")
    op.execute("DROP INDEX IF EXISTS idx_profile_hidden_surrogate")
    op.execute("DROP INDEX IF EXISTS ix_surrogate_interviews_surrogate_id")
    op.execute("DROP INDEX IF EXISTS idx_email_logs_surrogate")
    op.execute("DROP INDEX IF EXISTS idx_attachments_surrogate")
    op.execute("DROP INDEX IF EXISTS idx_form_submission_tokens_surrogate")
    op.execute("DROP INDEX IF EXISTS idx_form_submissions_surrogate")
    op.execute("DROP INDEX IF EXISTS idx_appointments_surrogate")
    op.execute("DROP INDEX IF EXISTS ix_zoom_meetings_surrogate_id")
    op.execute("DROP INDEX IF EXISTS ix_matches_surrogate_id")

    # Drop new constraints
    op.execute("ALTER TABLE surrogates DROP CONSTRAINT IF EXISTS uq_surrogate_number")
    op.execute(
        "ALTER TABLE surrogate_profile_overrides DROP CONSTRAINT IF EXISTS uq_surrogate_profile_override_field"
    )
    op.execute(
        "ALTER TABLE surrogate_profile_states DROP CONSTRAINT IF EXISTS uq_surrogate_profile_state_surrogate"
    )
    op.execute(
        "ALTER TABLE surrogate_profile_hidden_fields DROP CONSTRAINT IF EXISTS uq_surrogate_profile_hidden_field"
    )
    op.execute(
        "ALTER TABLE form_submissions DROP CONSTRAINT IF EXISTS uq_form_submission_surrogate"
    )

    # Revert permission strings
    for old_perm, new_perm in PERMISSION_RENAMES:
        op.execute(
            f"UPDATE role_permissions SET permission = '{old_perm}' WHERE permission = '{new_perm}'"
        )
    for old_perm, new_perm in PERMISSION_RENAMES:
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_permission_overrides') THEN
                    EXECUTE 'UPDATE user_permission_overrides SET permission = ''{old_perm}'' WHERE permission = ''{new_perm}''';
                END IF;
            END $$;
        """)

    # Revert notification preference columns (if they exist)
    notification_column_renames = [
        ("surrogate_assigned", "case_assigned"),
        ("surrogate_status_changed", "case_status_changed"),
        ("surrogate_claim_available", "case_handoff"),
    ]

    for old_col, new_col in notification_column_renames:
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name = 'user_notification_settings' AND column_name = '{old_col}') THEN
                    EXECUTE 'ALTER TABLE user_notification_settings RENAME COLUMN {old_col} TO {new_col}';
                END IF;
            END $$;
        """)

    # Revert org_counters
    op.execute(
        "UPDATE org_counters SET counter_type = 'case_number' WHERE counter_type = 'surrogate_number'"
    )

    # Revert entity_type values (only if tables exist)
    entity_type_updates = [
        ("entity_notes", "entity_type"),
        ("ai_conversations", "entity_type"),
        ("ai_entity_summaries", "entity_type"),
        ("workflow_executions", "entity_type"),
        ("entity_versions", "entity_type"),
        ("legal_holds", "entity_type"),
        ("data_retention_policies", "entity_type"),
        ("campaign_recipients", "entity_type"),
    ]

    for table_name, column_name in entity_type_updates:
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}') THEN
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = '{table_name}' AND column_name = '{column_name}') THEN
                        EXECUTE 'UPDATE {table_name} SET {column_name} = ''case'' WHERE {column_name} = ''surrogate''';
                    END IF;
                END IF;
            END $$;
        """)

    # Revert form_field_mappings surrogate_field back to case_field
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name = 'form_field_mappings' AND column_name = 'surrogate_field') THEN
                EXECUTE 'ALTER TABLE form_field_mappings RENAME COLUMN surrogate_field TO case_field';
            END IF;
        END $$;
    """)
    op.execute("ALTER TABLE form_field_mappings DROP CONSTRAINT IF EXISTS uq_form_surrogate_field")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'form_field_mappings'
                  AND constraint_name = 'uq_form_case_field'
            ) THEN
                EXECUTE 'ALTER TABLE form_field_mappings ADD CONSTRAINT uq_form_case_field UNIQUE (form_id, case_field)';
            END IF;
        END $$;
    """)

    # Revert column names on FK tables
    op.execute("ALTER TABLE meta_leads RENAME COLUMN converted_surrogate_id TO converted_case_id")
    op.execute("ALTER TABLE appointments RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE form_submissions RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE form_submission_tokens RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE zoom_meetings RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE email_logs RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE attachments RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE matches RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE tasks RENAME COLUMN surrogate_id TO case_id")

    # Revert surrogate_owner_id_at_attempt
    op.execute(
        "ALTER TABLE surrogate_contact_attempts RENAME COLUMN surrogate_owner_id_at_attempt TO case_owner_id_at_attempt"
    )

    # Revert column names on renamed tables
    op.execute("ALTER TABLE surrogate_interviews RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE surrogate_profile_hidden_fields RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE surrogate_profile_states RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE surrogate_profile_overrides RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE surrogate_contact_attempts RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE surrogate_activity_log RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE surrogate_status_history RENAME COLUMN surrogate_id TO case_id")
    op.execute("ALTER TABLE surrogates RENAME COLUMN surrogate_number TO case_number")

    # Revert table names
    op.execute("ALTER TABLE surrogate_profile_hidden_fields RENAME TO case_profile_hidden_fields")
    op.execute("ALTER TABLE surrogate_profile_states RENAME TO case_profile_states")
    op.execute("ALTER TABLE surrogate_profile_overrides RENAME TO case_profile_overrides")
    op.execute("ALTER TABLE surrogate_interviews RENAME TO case_interviews")
    op.execute("ALTER TABLE surrogate_imports RENAME TO case_imports")
    op.execute("ALTER TABLE surrogate_contact_attempts RENAME TO case_contact_attempts")
    op.execute("ALTER TABLE surrogate_activity_log RENAME TO case_activity_log")
    op.execute("ALTER TABLE surrogate_status_history RENAME TO case_status_history")
    op.execute("ALTER TABLE surrogates RENAME TO cases")

    # Recreate original indexes
    op.execute("CREATE INDEX idx_cases_stage ON cases (stage_id)")
    op.execute("CREATE INDEX idx_cases_org_stage ON cases (organization_id, stage_id)")
    op.execute("CREATE INDEX idx_cases_org_owner ON cases (organization_id, owner_type, owner_id)")
    op.execute("CREATE INDEX idx_cases_org_status_label ON cases (organization_id, status_label)")
    op.execute("CREATE INDEX idx_cases_org_created ON cases (organization_id, created_at)")
    op.execute("CREATE INDEX idx_cases_org_updated ON cases (organization_id, updated_at)")
    op.execute(
        "CREATE INDEX idx_cases_org_active ON cases (organization_id) WHERE is_archived = FALSE"
    )
    op.execute(
        "CREATE INDEX idx_cases_meta_ad ON cases (organization_id, meta_ad_external_id) WHERE meta_ad_external_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_cases_meta_form ON cases (organization_id, meta_form_id) WHERE meta_form_id IS NOT NULL"
    )
    op.execute("CREATE INDEX ix_cases_search_vector ON cases USING gin (search_vector)")
    op.execute("CREATE INDEX idx_cases_org_phone_hash ON cases (organization_id, phone_hash)")
    op.execute(
        "CREATE INDEX idx_cases_reminder_check ON cases (organization_id, owner_type, contact_status, stage_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_case_email_hash_active ON cases (organization_id, email_hash) WHERE is_archived = FALSE"
    )
    op.execute("CREATE INDEX idx_case_history_case ON case_status_history (case_id, changed_at)")
    op.execute(
        "CREATE INDEX idx_case_activity_case_time ON case_activity_log (case_id, created_at)"
    )
    op.execute(
        "CREATE INDEX idx_contact_attempts_case ON case_contact_attempts (case_id, attempted_at)"
    )
    op.execute(
        "CREATE INDEX idx_contact_attempts_org_pending ON case_contact_attempts (organization_id, outcome, attempted_at) WHERE outcome != 'reached'"
    )
    op.execute(
        "CREATE INDEX idx_contact_attempts_case_owner ON case_contact_attempts (case_id, case_owner_id_at_attempt, attempted_at)"
    )
    op.execute("CREATE INDEX idx_profile_overrides_case ON case_profile_overrides (case_id)")
    op.execute("CREATE INDEX idx_profile_state_case ON case_profile_states (case_id)")
    op.execute("CREATE INDEX idx_profile_hidden_case ON case_profile_hidden_fields (case_id)")
    op.execute("CREATE INDEX ix_case_interviews_case_id ON case_interviews (case_id)")
    op.execute("CREATE INDEX idx_email_logs_case ON email_logs (case_id, created_at)")
    op.execute("CREATE INDEX idx_attachments_case ON attachments (case_id)")
    op.execute("CREATE INDEX idx_form_submission_tokens_case ON form_submission_tokens (case_id)")
    op.execute("CREATE INDEX idx_form_submissions_case ON form_submissions (case_id)")
    op.execute("CREATE INDEX idx_appointments_case ON appointments (case_id)")
    op.execute("CREATE INDEX ix_zoom_meetings_case_id ON zoom_meetings (case_id)")
    op.execute("CREATE INDEX ix_matches_case_id ON matches (case_id)")

    # Recreate original constraints
    op.execute(
        "ALTER TABLE cases ADD CONSTRAINT uq_case_number UNIQUE (organization_id, case_number)"
    )
    op.execute(
        "ALTER TABLE case_profile_overrides ADD CONSTRAINT uq_case_profile_override_field UNIQUE (case_id, field_key)"
    )
    op.execute(
        "ALTER TABLE case_profile_states ADD CONSTRAINT uq_case_profile_state_case UNIQUE (case_id)"
    )
    op.execute(
        "ALTER TABLE case_profile_hidden_fields ADD CONSTRAINT uq_case_profile_hidden_field UNIQUE (case_id, field_key)"
    )
    op.execute(
        "ALTER TABLE form_submissions ADD CONSTRAINT uq_form_submission_case UNIQUE (form_id, case_id)"
    )

    # Rename trigger function back
    op.execute(
        "ALTER FUNCTION surrogates_search_vector_update() RENAME TO cases_search_vector_update"
    )

    # Recreate original trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION cases_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.full_name, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.case_number, '')), 'B');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER cases_search_vector_trigger
        BEFORE INSERT OR UPDATE ON cases
        FOR EACH ROW EXECUTE FUNCTION cases_search_vector_update()
    """)
