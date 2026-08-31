"""Seed independent default donor pipelines for existing organizations.

Downgrade removes only deterministic pipelines seeded by this migration and
retains any pipeline referenced by donor records.
"""

from uuid import UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

SEED_NAMESPACE = UUID("b679bd7a-5e57-4f77-8c62-5da3df67ca90")
ROLE_STAGE_TYPES = ["intake", "post_approval", "paused", "terminal"]

PIPELINES = {
    "egg_donor": {
        "qualification_stage_key": "ready_to_match",
        "conversion_stage_key": "matched",
        "stages": [
            ("new", "New", "#3B82F6", "intake"),
            ("contacted", "Contacted", "#06B6D4", "intake"),
            ("pre_screening", "Pre-Screening", "#8B5CF6", "intake"),
            ("application_submitted", "Application Submitted", "#A855F7", "intake"),
            ("medical_records_review", "Medical Records Review", "#F59E0B", "intake"),
            ("psychological_screening", "Psychological Screening", "#D97706", "intake"),
            ("ready_to_match", "Ready to Match", "#0EA5E9", "post_approval"),
            ("matched", "Matched", "#6366F1", "post_approval"),
            ("cycle_in_progress", "Cycle in Progress", "#14B8A6", "post_approval"),
            ("retrieval_complete", "Retrieval Complete", "#10B981", "post_approval"),
            ("on_hold", "On-Hold", "#B4536A", "paused"),
            ("disqualified", "Disqualified", "#EF4444", "terminal"),
            ("closed", "Closed", "#64748B", "terminal"),
        ],
    },
    "sperm_donor": {
        "qualification_stage_key": "available",
        "conversion_stage_key": "matched",
        "stages": [
            ("new", "New", "#3B82F6", "intake"),
            ("contacted", "Contacted", "#06B6D4", "intake"),
            ("pre_screening", "Pre-Screening", "#8B5CF6", "intake"),
            ("application_submitted", "Application Submitted", "#A855F7", "intake"),
            ("semen_analysis", "Semen Analysis", "#F59E0B", "intake"),
            (
                "medical_genetic_screening",
                "Medical & Genetic Screening",
                "#D97706",
                "intake",
            ),
            ("available", "Available", "#0EA5E9", "post_approval"),
            ("matched", "Matched", "#6366F1", "post_approval"),
            (
                "collection_in_progress",
                "Collection in Progress",
                "#14B8A6",
                "post_approval",
            ),
            ("donation_complete", "Donation Complete", "#10B981", "post_approval"),
            ("on_hold", "On-Hold", "#B4536A", "paused"),
            ("disqualified", "Disqualified", "#EF4444", "terminal"),
            ("closed", "Closed", "#64748B", "terminal"),
        ],
    },
}


def _pipeline_id(organization_id: UUID, entity_type: str) -> UUID:
    return uuid5(SEED_NAMESPACE, f"{organization_id}:{entity_type}")


def _stage_id(organization_id: UUID, entity_type: str, stage_key: str) -> UUID:
    return uuid5(SEED_NAMESPACE, f"{organization_id}:{entity_type}:{stage_key}")


def _feature_config(entity_type: str, definition: dict) -> dict:
    stage_keys = [stage[0] for stage in definition["stages"]]
    role_rule = {"stage_types": ROLE_STAGE_TYPES, "stage_keys": [], "capabilities": []}
    return {
        "schema_version": 1,
        "journey": {"phases": [], "milestones": []},
        "analytics": {
            "funnel_stage_keys": stage_keys,
            "performance_stage_keys": stage_keys,
            "qualification_stage_key": definition["qualification_stage_key"],
            "conversion_stage_key": definition["conversion_stage_key"],
        },
        "role_visibility": {"admin": role_rule, "developer": role_rule},
        "role_mutation": {"admin": role_rule, "developer": role_rule},
    }


def _stage_semantics(entity_type: str, stage_key: str) -> dict:
    qualification_key = PIPELINES[entity_type]["qualification_stage_key"]
    progressed_keys = {
        "matched",
        "cycle_in_progress",
        "retrieval_complete",
        "collection_in_progress",
        "donation_complete",
        "closed",
    }
    if stage_key in {"new", "contacted"}:
        integration_bucket = "intake"
    elif stage_key in {
        "pre_screening",
        "application_submitted",
        "medical_records_review",
        "psychological_screening",
        "semen_analysis",
        "medical_genetic_screening",
    }:
        integration_bucket = "qualified"
    elif stage_key == qualification_key or stage_key in progressed_keys:
        integration_bucket = "converted"
    elif stage_key == "disqualified":
        integration_bucket = "not_qualified"
    else:
        integration_bucket = "none"
    return {
        "capabilities": {
            "counts_as_contacted": stage_key not in {"new", "on_hold", "disqualified", "closed"},
            "eligible_for_matching": stage_key == qualification_key,
            "locks_match_state": stage_key in progressed_keys,
            "shows_pregnancy_tracking": False,
            "requires_delivery_details": False,
            "tracks_interview_outcome": False,
        },
        "pause_behavior": "none",
        "terminal_outcome": "disqualified" if stage_key == "disqualified" else "none",
        "integration_bucket": integration_bucket,
        "analytics_bucket": stage_key,
        "suggestion_profile_key": None,
        "requires_reason_on_enter": stage_key == "on_hold",
    }


def _seed_default_donor_pipelines(conn: sa.Connection) -> None:
    pipeline_insert = sa.text(
        """
        INSERT INTO pipelines (
            id, organization_id, entity_type, name, is_default, current_version, feature_config
        ) VALUES (
            :id, :organization_id, :entity_type, 'Default', TRUE, 1, :feature_config
        )
        """
    ).bindparams(sa.bindparam("feature_config", type_=postgresql.JSONB()))
    stage_insert = sa.text(
        """
        INSERT INTO pipeline_stages (
            id, pipeline_id, stage_key, slug, stage_type, label, color, "order",
            semantics, is_active, is_intake_stage
        ) VALUES (
            :id, :pipeline_id, :stage_key, :stage_key, :stage_type, :label, :color,
            :order, :semantics, TRUE, :is_intake_stage
        )
        """
    ).bindparams(sa.bindparam("semantics", type_=postgresql.JSONB()))

    organization_ids = list(conn.execute(sa.text("SELECT id FROM organizations")).scalars())
    for organization_id in organization_ids:
        for entity_type, definition in PIPELINES.items():
            default_exists = conn.execute(
                sa.text(
                    """
                    SELECT 1 FROM pipelines
                    WHERE organization_id = :organization_id
                      AND entity_type = :entity_type
                      AND is_default = TRUE
                    """
                ),
                {"organization_id": organization_id, "entity_type": entity_type},
            ).scalar_one_or_none()
            if default_exists:
                continue

            pipeline_id = _pipeline_id(organization_id, entity_type)
            conn.execute(
                pipeline_insert,
                {
                    "id": pipeline_id,
                    "organization_id": organization_id,
                    "entity_type": entity_type,
                    "feature_config": _feature_config(entity_type, definition),
                },
            )
            for order, (stage_key, label, color, stage_type) in enumerate(
                definition["stages"], start=1
            ):
                conn.execute(
                    stage_insert,
                    {
                        "id": _stage_id(organization_id, entity_type, stage_key),
                        "pipeline_id": pipeline_id,
                        "stage_key": stage_key,
                        "stage_type": stage_type,
                        "label": label,
                        "color": color,
                        "order": order,
                        "semantics": _stage_semantics(entity_type, stage_key),
                        "is_intake_stage": stage_type == "intake",
                    },
                )


def _remove_seeded_donor_pipelines(conn: sa.Connection) -> None:
    organization_ids = list(conn.execute(sa.text("SELECT id FROM organizations")).scalars())
    for organization_id in organization_ids:
        for entity_type in PIPELINES:
            pipeline_id = _pipeline_id(organization_id, entity_type)
            conn.execute(
                sa.text(
                    """
                    DELETE FROM pipelines p
                    WHERE p.id = :pipeline_id
                      AND p.organization_id = :organization_id
                      AND p.entity_type = :entity_type
                      AND NOT EXISTS (
                          SELECT 1
                          FROM donors d
                          JOIN pipeline_stages ps ON ps.id = d.stage_id
                          WHERE ps.pipeline_id = p.id
                      )
                    """
                ),
                {
                    "pipeline_id": pipeline_id,
                    "organization_id": organization_id,
                    "entity_type": entity_type,
                },
            )


def upgrade() -> None:
    _seed_default_donor_pipelines(op.get_bind())


def downgrade() -> None:
    _remove_seeded_donor_pipelines(op.get_bind())
