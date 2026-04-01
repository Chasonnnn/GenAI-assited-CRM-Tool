"""Shared Meta outbound stage semantics and deduplication helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.stage_definitions import canonicalize_stage_key

META_STATUS_INTAKE = "Intake"
META_STATUS_QUALIFIED = "Qualified/Converted"
META_STATUS_DISQUALIFIED = "Not qualified/Lost"
META_STATUS_LOST = "Lost"


def resolve_stage_bucket(stage_key: str | None, mapping: list[dict] | None = None) -> str | None:
    """Resolve the canonical outbound bucket for a stage key."""
    from app.services import zapier_settings_service

    return zapier_settings_service.resolve_meta_stage_bucket(stage_key, mapping)


def resolve_stage_dedupe_key(stage_key: str | None, mapping: list[dict] | None = None) -> str:
    """Return the bucket-scoped dedupe key used for Meta outbound events."""
    bucket = resolve_stage_bucket(stage_key, mapping)
    if bucket:
        return bucket

    normalized_stage_key = canonicalize_stage_key(stage_key)
    if normalized_stage_key:
        return normalized_stage_key

    return str(stage_key or "")


def build_stage_event_key(
    prefix: str,
    lead_id: str,
    stage_key: str | None,
    mapping: list[dict] | None = None,
) -> str:
    """Build a stable outbound event key scoped to the resolved Meta bucket."""
    return f"{prefix}:{lead_id}:{resolve_stage_dedupe_key(stage_key, mapping)}"


def map_bucket_to_meta_status(bucket: str | None) -> str | None:
    """Map a canonical outbound bucket to the Meta lead status label."""
    if bucket == "lost":
        return META_STATUS_LOST
    if bucket == "not_qualified":
        return META_STATUS_DISQUALIFIED
    if bucket in {"qualified", "converted"}:
        return META_STATUS_QUALIFIED
    if bucket == "intake":
        return META_STATUS_INTAKE
    return None


def map_stage_key_to_meta_status_for_org(
    db: Session,
    organization_id,
    stage_key: str | None,
) -> str | None:
    """Resolve the Meta lead status label for an org's current pipeline semantics."""
    from app.services import pipeline_semantics_service, pipeline_service

    if not stage_key:
        return None

    pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
    snapshot = pipeline_semantics_service.get_pipeline_semantics_snapshot(db, pipeline)
    normalized_stage_key = canonicalize_stage_key(stage_key) or str(stage_key)

    stage = snapshot.stage_by_key.get(normalized_stage_key)
    if not stage:
        stage = next(
            (snapshot_stage for snapshot_stage in snapshot.stages if snapshot_stage.slug == stage_key),
            None,
        )

    if stage:
        return map_bucket_to_meta_status(stage.semantics.integration_bucket)

    return map_bucket_to_meta_status(resolve_stage_bucket(stage_key))
