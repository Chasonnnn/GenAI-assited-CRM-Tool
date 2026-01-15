"""Update pipeline stages for the surrogacy CRM.

Stage changes:
- Rename: followup_scheduled → interview_scheduled
- Rename: pending_match → ready_to_match
- Rename: meds_started → medical_clearance_passed
- Rename: embryo_transferred → transfer_cycle
- Remove: applied (migrate to application_submitted)
- Remove: pending_handoff (migrate to approved)
- Remove: exam_passed (migrate to medical_clearance_passed)
- Add: legal_clearance_passed, second_hcg_confirmed, heartbeat_confirmed,
       ob_care_established, anatomy_scanned

All operations filter to default pipelines only.

Also:
- Bootstrap "Surrogate Pool" queue per org with case_manager+ members
- Purge pipeline versions
- Update automation workflow stage slugs

Revision ID: 20260113_1130
Revises: 20260113_1100
Create Date: 2026-01-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260113_1130"
down_revision: Union[str, Sequence[str], None] = "20260113_1100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# =============================================================================
# Stage slug rename mappings
# =============================================================================
STAGE_RENAMES = [
    ("followup_scheduled", "interview_scheduled", "Interview Scheduled"),
    ("pending_match", "ready_to_match", "Ready To Match"),
    ("meds_started", "medical_clearance_passed", "Medical Clearance Passed"),
    ("embryo_transferred", "transfer_cycle", "Transfer Cycle"),
]

# Stages to remove with their migration targets
# (old_slug, target_slug)
STAGES_TO_REMOVE = [
    ("applied", "application_submitted"),
    ("pending_handoff", "approved"),
    ("exam_passed", "medical_clearance_passed"),
]

# New stages to add (in order after existing stages)
NEW_STAGES = [
    {
        "slug": "legal_clearance_passed",
        "label": "Legal Clearance Passed",
        "color": "#F59E0B",  # Amber
        "stage_type": "post_approval",
        "after_slug": "medical_clearance_passed",
    },
    {
        "slug": "second_hcg_confirmed",
        "label": "Second HCG Confirmed",
        "color": "#14B8A6",  # Teal
        "stage_type": "post_approval",
        "after_slug": "transfer_cycle",
    },
    {
        "slug": "heartbeat_confirmed",
        "label": "Heartbeat Confirmed",
        "color": "#22C55E",  # Green
        "stage_type": "post_approval",
        "after_slug": "second_hcg_confirmed",
    },
    {
        "slug": "ob_care_established",
        "label": "OB Care Established",
        "color": "#0EA5E9",  # Sky
        "stage_type": "post_approval",
        "after_slug": "heartbeat_confirmed",
    },
    {
        "slug": "anatomy_scanned",
        "label": "Anatomy Scanned",
        "color": "#6366F1",  # Indigo
        "stage_type": "post_approval",
        "after_slug": "ob_care_established",
    },
]

# Workflow stage slug updates (old -> new)
WORKFLOW_STAGE_UPDATES = {
    "followup_scheduled": "interview_scheduled",
    "pending_match": "ready_to_match",
    "meds_started": "medical_clearance_passed",
    "embryo_transferred": "transfer_cycle",
    "applied": "application_submitted",
    "pending_handoff": "approved",
    "exam_passed": "medical_clearance_passed",
}


def _table_exists(conn, table_name: str) -> bool:
    return sa.inspect(conn).has_table(table_name)


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(conn)
    if not inspector.has_table(table_name):
        return False
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    """Upgrade: Update pipeline stages."""
    conn = op.get_bind()

    # =========================================================================
    # 1. Rename stage slugs and labels (default pipelines only)
    # =========================================================================

    for old_slug, new_slug, new_label in STAGE_RENAMES:
        op.execute(f"""
            UPDATE pipeline_stages
            SET slug = '{new_slug}',
                label = '{new_label}',
                updated_at = NOW()
            WHERE slug = '{old_slug}'
              AND pipeline_id IN (SELECT id FROM pipelines WHERE is_default = true)
        """)

    # =========================================================================
    # 2. Migrate surrogates off removed stages to target stages
    #    Match target stage by pipeline_id to avoid cross-pipeline issues
    # =========================================================================

    for old_slug, target_slug in STAGES_TO_REMOVE:
        # Migrate surrogates: update stage_id to target stage in same pipeline
        op.execute(f"""
            UPDATE surrogates s
            SET stage_id = target.id,
                status_label = target.label,
                updated_at = NOW()
            FROM pipeline_stages old_stage
            JOIN pipeline_stages target ON target.pipeline_id = old_stage.pipeline_id
                                        AND target.slug = '{target_slug}'
            WHERE s.stage_id = old_stage.id
              AND old_stage.slug = '{old_slug}'
              AND old_stage.pipeline_id IN (SELECT id FROM pipelines WHERE is_default = true)
        """)

    # =========================================================================
    # 3. Remap surrogate_status_history FK references
    #    Match by pipeline_id (no cross-pipeline mismatches)
    # =========================================================================

    for old_slug, target_slug in STAGES_TO_REMOVE:
        # Update from_stage_id references
        op.execute(f"""
            UPDATE surrogate_status_history h
            SET from_stage_id = target.id
            FROM pipeline_stages old_stage
            JOIN pipeline_stages target ON target.pipeline_id = old_stage.pipeline_id
                                        AND target.slug = '{target_slug}'
            WHERE h.from_stage_id = old_stage.id
              AND old_stage.slug = '{old_slug}'
              AND old_stage.pipeline_id IN (SELECT id FROM pipelines WHERE is_default = true)
        """)

        # Update to_stage_id references
        op.execute(f"""
            UPDATE surrogate_status_history h
            SET to_stage_id = target.id
            FROM pipeline_stages old_stage
            JOIN pipeline_stages target ON target.pipeline_id = old_stage.pipeline_id
                                        AND target.slug = '{target_slug}'
            WHERE h.to_stage_id = old_stage.id
              AND old_stage.slug = '{old_slug}'
              AND old_stage.pipeline_id IN (SELECT id FROM pipelines WHERE is_default = true)
        """)

    # =========================================================================
    # 4. Delete removed stages (default pipelines only)
    # =========================================================================

    for old_slug, _ in STAGES_TO_REMOVE:
        op.execute(f"""
            DELETE FROM pipeline_stages
            WHERE slug = '{old_slug}'
              AND pipeline_id IN (SELECT id FROM pipelines WHERE is_default = true)
        """)

    # =========================================================================
    # 5. Insert new stages (default pipelines only)
    # =========================================================================

    for stage in NEW_STAGES:
        slug = stage["slug"]
        label = stage["label"]
        color = stage["color"]
        stage_type = stage["stage_type"]
        after_slug = stage["after_slug"]

        # Insert new stage with order = after_slug's order + 0.5 (will normalize later)
        # Using a subquery to get the correct pipeline_id and order
        op.execute(f"""
            INSERT INTO pipeline_stages (
                id, pipeline_id, slug, label, color, stage_type,
                is_intake_stage, is_active, "order", created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                after_stage.pipeline_id,
                '{slug}',
                '{label}',
                '{color}',
                '{stage_type}',
                false,
                true,
                after_stage."order" + 1,
                NOW(),
                NOW()
            FROM pipeline_stages after_stage
            WHERE after_stage.slug = '{after_slug}'
              AND after_stage.pipeline_id IN (SELECT id FROM pipelines WHERE is_default = true)
              AND NOT EXISTS (
                  SELECT 1 FROM pipeline_stages existing
                  WHERE existing.pipeline_id = after_stage.pipeline_id
                    AND existing.slug = '{slug}'
              )
        """)

    # =========================================================================
    # 6. Normalize stage order (1, 2, 3, ...)
    # =========================================================================

    op.execute("""
        WITH ordered AS (
            SELECT id, pipeline_id,
                   ROW_NUMBER() OVER (PARTITION BY pipeline_id ORDER BY "order") as new_order
            FROM pipeline_stages
            WHERE is_active = true
              AND pipeline_id IN (SELECT id FROM pipelines WHERE is_default = true)
        )
        UPDATE pipeline_stages ps
        SET "order" = ordered.new_order
        FROM ordered
        WHERE ps.id = ordered.id
    """)

    # =========================================================================
    # 7. Update automation workflow stage slugs
    # =========================================================================

    # Update trigger_config stage slugs in automation_workflows (JSONB)
    for old_slug, new_slug in WORKFLOW_STAGE_UPDATES.items():
        # Update stage_slugs array in trigger_config
        op.execute(f"""
            UPDATE automation_workflows
            SET trigger_config = jsonb_set(
                trigger_config,
                '{{stage_slugs}}',
                (
                    SELECT jsonb_agg(
                        to_jsonb(
                            CASE WHEN elem = '{old_slug}' THEN '{new_slug}' ELSE elem END
                        )
                    )
                    FROM jsonb_array_elements_text(trigger_config->'stage_slugs') elem
                )
            )
            WHERE trigger_config->'stage_slugs' IS NOT NULL
              AND trigger_config->'stage_slugs' @> '["{old_slug}"]'::jsonb
              AND organization_id IN (
                  SELECT organization_id FROM pipelines WHERE is_default = true
              )
        """)

        # Update from_stage_slug in trigger_config
        op.execute(f"""
            UPDATE automation_workflows
            SET trigger_config = jsonb_set(trigger_config, '{{from_stage_slug}}', '"{new_slug}"')
            WHERE trigger_config->>'from_stage_slug' = '{old_slug}'
              AND organization_id IN (
                  SELECT organization_id FROM pipelines WHERE is_default = true
              )
        """)

        # Update to_stage_slug in trigger_config
        op.execute(f"""
            UPDATE automation_workflows
            SET trigger_config = jsonb_set(trigger_config, '{{to_stage_slug}}', '"{new_slug}"')
            WHERE trigger_config->>'to_stage_slug' = '{old_slug}'
              AND organization_id IN (
                  SELECT organization_id FROM pipelines WHERE is_default = true
              )
        """)

    # Update campaign criteria stage_slugs (JSONB)
    if _column_exists(conn, "campaigns", "criteria"):
        for old_slug, new_slug in WORKFLOW_STAGE_UPDATES.items():
            op.execute(f"""
                UPDATE campaigns
                SET criteria = jsonb_set(
                    criteria,
                    '{{stage_slugs}}',
                    (
                        SELECT jsonb_agg(
                            to_jsonb(
                                CASE WHEN elem = '{old_slug}' THEN '{new_slug}' ELSE elem END
                            )
                        )
                        FROM jsonb_array_elements_text(criteria->'stage_slugs') elem
                    )
                )
                WHERE criteria->'stage_slugs' IS NOT NULL
                  AND criteria->'stage_slugs' @> '["{old_slug}"]'::jsonb
            """)

    # Convert workflow trigger_config from slugs to stage IDs (default pipelines only)
    op.execute("""
        UPDATE automation_workflows w
        SET trigger_config = jsonb_strip_nulls(
            (w.trigger_config - 'to_stage_slug' - 'from_stage_slug') ||
            jsonb_build_object(
                'to_stage_id', to_stage.id::text,
                'from_stage_id', from_stage.id::text
            )
        )
        FROM pipelines p
        LEFT JOIN pipeline_stages to_stage
            ON to_stage.pipeline_id = p.id
            AND to_stage.slug = w.trigger_config->>'to_stage_slug'
        LEFT JOIN pipeline_stages from_stage
            ON from_stage.pipeline_id = p.id
            AND from_stage.slug = w.trigger_config->>'from_stage_slug'
        WHERE w.organization_id = p.organization_id
          AND p.is_default = true
          AND (w.trigger_config ? 'to_stage_slug' OR w.trigger_config ? 'from_stage_slug')
    """)

    # =========================================================================
    # 8. Purge pipeline versions and analytics snapshots
    # =========================================================================

    # Delete all entity_versions for pipelines (will regenerate)
    if _table_exists(conn, "entity_versions"):
        op.execute("""
            DELETE FROM entity_versions
            WHERE entity_type = 'pipeline'
        """)

    # Reset pipeline current_version to 1
    op.execute("""
        UPDATE pipelines SET current_version = 1, updated_at = NOW()
    """)

    # Clear analytics snapshots (will regenerate)
    if _table_exists(conn, "analytics_snapshots"):
        op.execute("""
            DELETE FROM analytics_snapshots
            WHERE snapshot_type IN ('pipeline', 'stage')
        """)

    # =========================================================================
    # 9. Bootstrap "Surrogate Pool" queue per org with case_manager+ members
    # =========================================================================

    # Create "Surrogate Pool" queue for each org (if not exists)
    op.execute("""
        INSERT INTO queues (id, organization_id, name, description, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            o.id,
            'Surrogate Pool',
            'Default queue for approved surrogates awaiting case manager claim',
            NOW(),
            NOW()
        FROM organizations o
        WHERE NOT EXISTS (
            SELECT 1 FROM queues q
            WHERE q.organization_id = o.id AND q.name = 'Surrogate Pool'
        )
    """)

    # Add all case_manager, admin, developer users to the Surrogate Pool queue
    op.execute("""
        INSERT INTO queue_members (id, queue_id, user_id, created_at)
        SELECT
            gen_random_uuid(),
            q.id,
            m.user_id,
            NOW()
        FROM queues q
        JOIN memberships m ON m.organization_id = q.organization_id
        WHERE q.name = 'Surrogate Pool'
          AND m.role IN ('case_manager', 'admin', 'developer')
          AND m.is_active = true
          AND NOT EXISTS (
              SELECT 1 FROM queue_members qm
              WHERE qm.queue_id = q.id AND qm.user_id = m.user_id
          )
    """)


def downgrade() -> None:
    """Downgrade: Revert pipeline stage changes."""

    # Remove Surrogate Pool queue members and queues
    op.execute("""
        DELETE FROM queue_members
        WHERE queue_id IN (SELECT id FROM queues WHERE name = 'Surrogate Pool')
    """)

    op.execute("""
        DELETE FROM queues WHERE name = 'Surrogate Pool'
    """)

    # Remove new stages
    for stage in NEW_STAGES:
        op.execute(f"""
            DELETE FROM pipeline_stages
            WHERE slug = '{stage["slug"]}'
              AND pipeline_id IN (SELECT id FROM pipelines WHERE is_default = true)
        """)

    # Revert stage renames
    for old_slug, new_slug, _ in STAGE_RENAMES:
        old_label = old_slug.replace("_", " ").title()
        op.execute(f"""
            UPDATE pipeline_stages
            SET slug = '{old_slug}',
                label = '{old_label}',
                updated_at = NOW()
            WHERE slug = '{new_slug}'
              AND pipeline_id IN (SELECT id FROM pipelines WHERE is_default = true)
        """)

    # Re-add removed stages (basic recreation)
    removed_stages_data = [
        ("applied", "Applied", "#84CC16", "intake"),
        ("pending_handoff", "Pending Handoff", "#F97316", "intake"),
        ("exam_passed", "Exam Passed", "#059669", "post_approval"),
    ]

    for slug, label, color, stage_type in removed_stages_data:
        is_intake = "true" if stage_type == "intake" else "false"
        op.execute(f"""
            INSERT INTO pipeline_stages (
                id, pipeline_id, slug, label, color, stage_type,
                is_intake_stage, is_active, "order", created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                p.id,
                '{slug}',
                '{label}',
                '{color}',
                '{stage_type}',
                {is_intake},
                true,
                100,  -- High order, will need manual reordering
                NOW(),
                NOW()
            FROM pipelines p
            WHERE p.is_default = true
              AND NOT EXISTS (
                  SELECT 1 FROM pipeline_stages existing
                  WHERE existing.pipeline_id = p.id AND existing.slug = '{slug}'
              )
        """)

    # Re-normalize stage order
    op.execute("""
        WITH ordered AS (
            SELECT id, pipeline_id,
                   ROW_NUMBER() OVER (PARTITION BY pipeline_id ORDER BY "order") as new_order
            FROM pipeline_stages
            WHERE is_active = true
              AND pipeline_id IN (SELECT id FROM pipelines WHERE is_default = true)
        )
        UPDATE pipeline_stages ps
        SET "order" = ordered.new_order
        FROM ordered
        WHERE ps.id = ordered.id
    """)

    # Revert workflow stage slug updates
    for old_slug, new_slug in WORKFLOW_STAGE_UPDATES.items():
        op.execute(f"""
            UPDATE automation_workflows
            SET trigger_config = jsonb_set(
                trigger_config,
                '{{stage_slugs}}',
                (
                    SELECT jsonb_agg(
                        to_jsonb(
                            CASE WHEN elem = '{new_slug}' THEN '{old_slug}' ELSE elem END
                        )
                    )
                    FROM jsonb_array_elements_text(trigger_config->'stage_slugs') elem
                )
            )
            WHERE trigger_config->'stage_slugs' IS NOT NULL
              AND trigger_config->'stage_slugs' @> '["{new_slug}"]'::jsonb
        """)

        op.execute(f"""
            UPDATE automation_workflows
            SET trigger_config = jsonb_set(trigger_config, '{{from_stage}}', '"{old_slug}"')
            WHERE trigger_config->>'from_stage' = '{new_slug}'
        """)

        op.execute(f"""
            UPDATE automation_workflows
            SET trigger_config = jsonb_set(trigger_config, '{{to_stage}}', '"{old_slug}"')
            WHERE trigger_config->>'to_stage' = '{new_slug}'
        """)

    # Note: Cannot fully restore surrogate stage assignments or history
    # as the original stage IDs are deleted. Manual intervention needed.
