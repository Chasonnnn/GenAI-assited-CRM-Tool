"""Default pipeline stage definitions and ordering."""

from __future__ import annotations


# Default stage colors (matching typical CRM conventions)
DEFAULT_COLORS = {
    # Stage A: Intake Pipeline (blues/greens)
    "new_unread": "#3B82F6",  # Blue
    "contacted": "#06B6D4",  # Cyan
    "qualified": "#10B981",  # Green
    "interview_scheduled": "#A855F7",  # Purple
    "application_submitted": "#8B5CF6",  # Violet
    "under_review": "#F59E0B",  # Amber
    "approved": "#22C55E",  # Green
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

STAGE_TYPE_MAP = {
    "new_unread": "intake",
    "contacted": "intake",
    "qualified": "intake",
    "interview_scheduled": "intake",
    "application_submitted": "intake",
    "under_review": "intake",
    "approved": "intake",
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

DEFAULT_STAGE_ORDER = [
    "new_unread",
    "contacted",
    "qualified",
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
    "lost",
    "disqualified",
    "delivered",
]


def get_default_stage_defs() -> list[dict[str, object]]:
    """Generate default pipeline stage definitions."""
    stages: list[dict[str, object]] = []
    for order, slug in enumerate(DEFAULT_STAGE_ORDER, start=1):
        stages.append(
            {
                "slug": slug,
                "label": slug.replace("_", " ").title(),
                "color": DEFAULT_COLORS.get(slug, "#6B7280"),
                "order": order,
                "stage_type": STAGE_TYPE_MAP.get(slug, "intake"),
            }
        )
    return stages
