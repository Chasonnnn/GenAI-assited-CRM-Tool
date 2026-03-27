"""Default pipeline stage definitions and ordering."""

from __future__ import annotations

from dataclasses import dataclass

from app.utils.presentation import humanize_identifier

SURROGATE_PIPELINE_ENTITY = "surrogate"
INTENDED_PARENT_PIPELINE_ENTITY = "intended_parent"
VALID_PIPELINE_ENTITY_TYPES = {
    SURROGATE_PIPELINE_ENTITY,
    INTENDED_PARENT_PIPELINE_ENTITY,
}


SYSTEM_STAGE_LOCKED_FIELDS = (
    "slug",
    "label",
    "color",
    "order",
    "category",
    "stage_type",
    "semantics",
    "is_active",
    "delete",
    "duplicate",
)


@dataclass(frozen=True)
class ProtectedSystemStageDefinition:
    system_role: str
    lock_reason: str
    locked_fields: tuple[str, ...] = SYSTEM_STAGE_LOCKED_FIELDS


# Default stage colors (matching Surrogacy Force conventions)
SURROGATE_DEFAULT_COLORS = {
    # Stage A: Intake Pipeline (blues/greens)
    "new_unread": "#3B82F6",  # Blue
    "contacted": "#06B6D4",  # Cyan
    "pre_qualified": "#10B981",  # Green
    "interview_scheduled": "#A855F7",  # Purple
    "application_submitted": "#8B5CF6",  # Violet
    "under_review": "#F59E0B",  # Amber
    "approved": "#22C55E",  # Green
    "on_hold": "#B4536A",  # Muted brick
    "disqualified": "#EF4444",  # Red
    "lost": "#EF4444",  # Red
    # Stage B: Post-Approval (darker shades)
    "ready_to_match": "#0EA5E9",  # Sky
    "matched": "#6366F1",  # Indigo
    "medical_clearance_passed": "#14B8A6",  # Teal
    "legal_clearance_passed": "#059669",  # Emerald
    "transfer_cycle": "#0D9488",  # Teal
    "second_hcg_confirmed": "#10B981",  # Green
    "heartbeat_confirmed": "#22C55E",  # Green
    "ob_care_established": "#84CC16",  # Lime
    "anatomy_scanned": "#16A34A",  # Green
    "delivered": "#16A34A",  # Green (success)
}

INTENDED_PARENT_DEFAULT_COLORS = {
    "new": "#3B82F6",
    "ready_to_match": "#F59E0B",
    "matched": "#10B981",
    "delivered": "#14B8A6",
}

SURROGATE_STAGE_TYPE_MAP = {
    "new_unread": "intake",
    "contacted": "intake",
    "pre_qualified": "intake",
    "interview_scheduled": "intake",
    "application_submitted": "intake",
    "under_review": "intake",
    "approved": "intake",
    "on_hold": "paused",
    "ready_to_match": "post_approval",
    "matched": "post_approval",
    "medical_clearance_passed": "post_approval",
    "legal_clearance_passed": "post_approval",
    "transfer_cycle": "post_approval",
    "second_hcg_confirmed": "post_approval",
    "heartbeat_confirmed": "post_approval",
    "ob_care_established": "post_approval",
    "anatomy_scanned": "post_approval",
    "delivered": "post_approval",
    "lost": "terminal",
    "disqualified": "terminal",
}

INTENDED_PARENT_STAGE_TYPE_MAP = {
    "new": "intake",
    "ready_to_match": "post_approval",
    "matched": "post_approval",
    "delivered": "post_approval",
}

# Backward-compatible surrogate aggregate used by legacy generators and tests.
STAGE_TYPE_MAP = dict(SURROGATE_STAGE_TYPE_MAP)

SURROGATE_LABEL_OVERRIDES = {
    "on_hold": "On-Hold",
    "pre_qualified": "Pre-Qualified",
    "second_hcg_confirmed": "Second hCG confirmed",
    "ready_to_match": "Ready to Match",
    "transfer_cycle": "Transfer Cycle Initiated",
    "ob_care_established": "OB Care Established",
}

INTENDED_PARENT_LABEL_OVERRIDES = {
    "ready_to_match": "Ready to Match",
}

# Backward-compatible aggregate used by integrations/export code paths that only
# need a friendly label lookup and do not care about pipeline entity scoping.
LABEL_OVERRIDES = {
    **SURROGATE_LABEL_OVERRIDES,
    **INTENDED_PARENT_LABEL_OVERRIDES,
}

LEGACY_STAGE_KEY_ALIASES = {
    "qualified": "pre_qualified",
}

PROTECTED_SYSTEM_STAGES_BY_ENTITY = {
    SURROGATE_PIPELINE_ENTITY: {
        "new_unread": ProtectedSystemStageDefinition(
            system_role="intake_entry",
            lock_reason="This is a protected system stage used by platform workflows.",
        ),
        "approved": ProtectedSystemStageDefinition(
            system_role="approval_gate",
            lock_reason="This is a protected system stage used by platform workflows.",
        ),
        "ready_to_match": ProtectedSystemStageDefinition(
            system_role="handoff",
            lock_reason="This is a protected system stage used by platform workflows.",
        ),
        "matched": ProtectedSystemStageDefinition(
            system_role="matched",
            lock_reason="This is a protected system stage used by platform workflows.",
        ),
        "on_hold": ProtectedSystemStageDefinition(
            system_role="pause",
            lock_reason="This is a protected system stage used by platform workflows.",
        ),
        "delivered": ProtectedSystemStageDefinition(
            system_role="delivered",
            lock_reason="This is a protected system stage used by platform workflows.",
        ),
        "lost": ProtectedSystemStageDefinition(
            system_role="lost",
            lock_reason="This is a protected system stage used by platform workflows.",
        ),
        "disqualified": ProtectedSystemStageDefinition(
            system_role="disqualified",
            lock_reason="This is a protected system stage used by platform workflows.",
        ),
    },
    INTENDED_PARENT_PIPELINE_ENTITY: {
        "new": ProtectedSystemStageDefinition(
            system_role="intake_entry",
            lock_reason="This is a protected system stage used by platform workflows.",
        ),
        "ready_to_match": ProtectedSystemStageDefinition(
            system_role="handoff",
            lock_reason="This is a protected system stage used by platform workflows.",
        ),
        "matched": ProtectedSystemStageDefinition(
            system_role="matched",
            lock_reason="This is a protected system stage used by platform workflows.",
        ),
        "delivered": ProtectedSystemStageDefinition(
            system_role="delivered",
            lock_reason="This is a protected system stage used by platform workflows.",
        ),
    },
}

REQUIRED_SYSTEM_STAGE_KEYS_BY_ENTITY = {
    entity_type: set(stage_map.keys())
    for entity_type, stage_map in PROTECTED_SYSTEM_STAGES_BY_ENTITY.items()
}

DEFAULT_STAGE_ORDER_BY_ENTITY = {
    SURROGATE_PIPELINE_ENTITY: [
        "new_unread",
        "contacted",
        "pre_qualified",
        "application_submitted",
        "interview_scheduled",
        "under_review",
        "approved",
        "ready_to_match",
        "matched",
        "medical_clearance_passed",
        "legal_clearance_passed",
        "transfer_cycle",
        "second_hcg_confirmed",
        "heartbeat_confirmed",
        "ob_care_established",
        "anatomy_scanned",
        "delivered",
        "on_hold",
        "lost",
        "disqualified",
    ],
    INTENDED_PARENT_PIPELINE_ENTITY: [
        "new",
        "ready_to_match",
        "matched",
        "delivered",
    ],
}

# Backward-compatible export used by legacy surrogate-stage tests and callers.
DEFAULT_STAGE_ORDER = DEFAULT_STAGE_ORDER_BY_ENTITY[SURROGATE_PIPELINE_ENTITY]


def normalize_pipeline_entity_type(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in VALID_PIPELINE_ENTITY_TYPES:
        return normalized
    return SURROGATE_PIPELINE_ENTITY


def get_required_semantic_stage_keys(entity_type: str | None = None) -> set[str]:
    normalized_entity_type = normalize_pipeline_entity_type(entity_type)
    return get_protected_system_stage_keys(normalized_entity_type)


def canonicalize_stage_key(value: str | None) -> str:
    """Normalize old aliases to canonical immutable stage keys."""
    normalized = (value or "").strip().lower()
    return LEGACY_STAGE_KEY_ALIASES.get(normalized, normalized)


def get_protected_system_stage_keys(entity_type: str | None = None) -> set[str]:
    normalized_entity_type = normalize_pipeline_entity_type(entity_type)
    return {
        canonicalize_stage_key(stage_key)
        for stage_key in PROTECTED_SYSTEM_STAGES_BY_ENTITY[normalized_entity_type]
    }


def get_protected_system_stage_defs(entity_type: str | None = None) -> list[dict[str, object]]:
    normalized_entity_type = normalize_pipeline_entity_type(entity_type)
    protected_stage_keys = get_protected_system_stage_keys(normalized_entity_type)
    return [
        stage_def
        for stage_def in get_default_stage_defs(normalized_entity_type)
        if canonicalize_stage_key(stage_def.get("stage_key") or stage_def["slug"])
        in protected_stage_keys
    ]


def get_stage_protection(
    stage_key_or_slug: str | None,
    entity_type: str | None = None,
) -> ProtectedSystemStageDefinition | None:
    normalized_entity_type = normalize_pipeline_entity_type(entity_type)
    normalized_stage_key = canonicalize_stage_key(stage_key_or_slug)
    return PROTECTED_SYSTEM_STAGES_BY_ENTITY[normalized_entity_type].get(normalized_stage_key)


def get_stage_protection_metadata(
    stage_key_or_slug: str | None,
    entity_type: str | None = None,
) -> dict[str, object]:
    protection = get_stage_protection(stage_key_or_slug, entity_type)
    if not protection:
        return {
            "is_locked": False,
            "system_role": None,
            "lock_reason": None,
            "locked_fields": [],
        }
    return {
        "is_locked": True,
        "system_role": protection.system_role,
        "lock_reason": protection.lock_reason,
        "locked_fields": list(protection.locked_fields),
    }


def get_system_stage_key(
    entity_type: str | None,
    system_role: str | None,
) -> str | None:
    normalized_entity_type = normalize_pipeline_entity_type(entity_type)
    normalized_role = str(system_role or "").strip().lower()
    if not normalized_role:
        return None
    for stage_key, definition in PROTECTED_SYSTEM_STAGES_BY_ENTITY[normalized_entity_type].items():
        if definition.system_role == normalized_role:
            return stage_key
    return None


def is_required_system_stage(
    stage_key_or_slug: str | None,
    entity_type: str | None = None,
) -> bool:
    """Return whether a stage key/slug is reserved for system workflows."""
    return get_stage_protection(stage_key_or_slug, entity_type) is not None


def get_default_stage_defs(entity_type: str | None = None) -> list[dict[str, object]]:
    """Generate default pipeline stage definitions."""
    normalized_entity_type = normalize_pipeline_entity_type(entity_type)
    stage_order = DEFAULT_STAGE_ORDER_BY_ENTITY[normalized_entity_type]
    if normalized_entity_type == INTENDED_PARENT_PIPELINE_ENTITY:
        colors = INTENDED_PARENT_DEFAULT_COLORS
        stage_type_map = INTENDED_PARENT_STAGE_TYPE_MAP
        label_overrides = INTENDED_PARENT_LABEL_OVERRIDES
    else:
        colors = SURROGATE_DEFAULT_COLORS
        stage_type_map = SURROGATE_STAGE_TYPE_MAP
        label_overrides = SURROGATE_LABEL_OVERRIDES

    stages: list[dict[str, object]] = []
    for order, slug in enumerate(stage_order, start=1):
        stage_key = canonicalize_stage_key(slug)
        stages.append(
            {
                "slug": slug,
                "stage_key": stage_key,
                "label": label_overrides.get(slug, humanize_identifier(slug)),
                "color": colors.get(slug, "#6B7280"),
                "order": order,
                "stage_type": stage_type_map.get(slug, "intake"),
            }
        )
    return stages
