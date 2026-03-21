"""Journey service - milestone status derivation for surrogate lifecycle.

This service is the single source of truth for journey milestone definitions
and status derivation. The frontend receives all milestone data from the API
and does not contain any milestone definitions.

Version 1 - Initial milestone mapping
"""

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.stage_definitions import canonicalize_stage_key
from app.db.models import (
    JourneyFeaturedImage,
    PipelineStage,
    Surrogate,
    SurrogateStatusHistory,
)
from app.services import attachment_service, pipeline_semantics_service


# Journey version for audit trails and export stability
JOURNEY_VERSION = 1

# Export variants for journey PDF
EXPORT_VARIANTS = {"internal", "client"}
CLIENT_EXPORT_START_MILESTONE = "match_confirmed"


def get_default_image_url(milestone_slug: str) -> str:
    """Build absolute URL for default milestone image from frontend public folder."""
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    return f"{frontend_url}/journey/defaults/{milestone_slug}.jpg"


@dataclass(frozen=True)
class MilestoneDefinition:
    """Static milestone definition."""

    slug: str
    label: str
    description: str
    mapped_stage_keys: tuple[str, ...]  # Canonical stage keys that map to this milestone
    is_soft: bool = False  # Soft milestones never become "current"


@dataclass(frozen=True)
class PhaseDefinition:
    """Static phase definition (visual grouping only)."""

    slug: str
    label: str
    milestone_slugs: tuple[str, ...]


@dataclass
class JourneyMilestone:
    """Runtime milestone with computed status."""

    slug: str
    label: str
    description: str
    status: Literal["completed", "current", "upcoming"]
    completed_at: datetime | None
    is_soft: bool
    default_image_url: str  # Absolute URL to default image in frontend public folder
    featured_image_url: str | None = None  # Signed URL to custom featured image
    featured_image_id: str | None = None  # Attachment ID if featured image is set


@dataclass
class JourneyPhase:
    """Runtime phase with milestones."""

    slug: str
    label: str
    milestones: list[JourneyMilestone]


@dataclass
class JourneyResponse:
    """Complete journey response."""

    surrogate_id: str
    surrogate_name: str
    journey_version: int
    is_terminal: bool
    terminal_message: str | None
    terminal_date: str | None  # ISO date
    phases: list[JourneyPhase]
    organization_name: str
    organization_logo_url: str | None


def _filter_phases_from_milestone(
    phases: list[JourneyPhase],
    start_milestone_slug: str,
) -> list[JourneyPhase]:
    started = False
    filtered_phases: list[JourneyPhase] = []

    for phase in phases:
        milestones: list[JourneyMilestone] = []
        for milestone in phase.milestones:
            if not started:
                if milestone.slug != start_milestone_slug:
                    continue
                started = True
            milestones.append(milestone)
        if milestones:
            filtered_phases.append(
                JourneyPhase(
                    slug=phase.slug,
                    label=phase.label,
                    milestones=milestones,
                )
            )
    return filtered_phases


def apply_export_variant(journey: JourneyResponse, variant: str | None) -> JourneyResponse:
    if variant != "client":
        return journey

    phases = _filter_phases_from_milestone(journey.phases, CLIENT_EXPORT_START_MILESTONE)
    return JourneyResponse(
        surrogate_id=journey.surrogate_id,
        surrogate_name="",
        journey_version=journey.journey_version,
        is_terminal=journey.is_terminal,
        terminal_message=journey.terminal_message,
        terminal_date=journey.terminal_date,
        phases=phases,
        organization_name=journey.organization_name,
        organization_logo_url=journey.organization_logo_url,
    )


def update_milestone_featured_image(
    db: Session,
    *,
    surrogate: Surrogate,
    milestone_slug: str,
    attachment_id: UUID | None,
    actor_user_id: UUID,
) -> UUID | None:
    """
    Upsert or clear a featured image for a journey milestone.

    Raises ValueError for invalid attachment or missing records.
    """
    from app.services import activity_service

    existing = (
        db.query(JourneyFeaturedImage)
        .filter(
            JourneyFeaturedImage.surrogate_id == surrogate.id,
            JourneyFeaturedImage.milestone_slug == milestone_slug,
            JourneyFeaturedImage.organization_id == surrogate.organization_id,
        )
        .first()
    )
    old_attachment_id = existing.attachment_id if existing else None

    if attachment_id is None:
        if existing:
            db.delete(existing)
            activity_service.log_journey_image_cleared(
                db=db,
                surrogate_id=surrogate.id,
                organization_id=surrogate.organization_id,
                actor_user_id=actor_user_id,
                milestone_slug=milestone_slug,
                old_attachment_id=old_attachment_id,
            )
            db.commit()
        return None

    attachment = attachment_service.get_attachment(
        db,
        surrogate.organization_id,
        attachment_id,
    )
    if not attachment or attachment.surrogate_id != surrogate.id:
        raise ValueError("Attachment not found")
    if attachment.scan_status in ("infected", "error"):
        raise ValueError("Attachment failed virus scan")
    if not attachment.content_type or not attachment.content_type.startswith("image/"):
        raise ValueError("Attachment must be an image")

    if existing:
        existing.attachment_id = attachment_id
        existing.updated_by_user_id = actor_user_id
    else:
        db.add(
            JourneyFeaturedImage(
                surrogate_id=surrogate.id,
                organization_id=surrogate.organization_id,
                milestone_slug=milestone_slug,
                attachment_id=attachment_id,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )

    activity_service.log_journey_image_set(
        db=db,
        surrogate_id=surrogate.id,
        organization_id=surrogate.organization_id,
        actor_user_id=actor_user_id,
        milestone_slug=milestone_slug,
        new_attachment_id=attachment_id,
        old_attachment_id=old_attachment_id,
    )
    db.commit()

    return attachment_id


def _get_milestone_for_stage(
    stage_key: str | None,
    pipeline_stages: dict[str, int],  # stage_key -> order
    milestones: list[MilestoneDefinition],
    stage_to_milestone: dict[str, str],
) -> str | None:
    """
    Get the milestone slug for a given stage key.

    Falls back to nearest prior milestone using pipeline order if stage is unknown.
    """
    if not stage_key:
        return None

    # Direct mapping
    if stage_key in stage_to_milestone:
        return stage_to_milestone[stage_key]

    # Unknown stage - fall back to nearest prior milestone by pipeline order
    stage_order = pipeline_stages.get(stage_key)
    if stage_order is None:
        return milestones[0].slug if milestones else None  # Default to first milestone

    # Find the highest-order stage that's mapped to a milestone and has order <= current
    best_milestone: str | None = None
    best_order = -1

    for mapped_stage, milestone_slug in stage_to_milestone.items():
        mapped_order = pipeline_stages.get(mapped_stage)
        if mapped_order is not None and mapped_order <= stage_order and mapped_order > best_order:
            best_order = mapped_order
            best_milestone = milestone_slug

    return best_milestone or (milestones[0].slug if milestones else None)


_LABEL_CLEANUP = re.compile(r"[^a-z0-9]+")


def _normalize_label_to_slug(label: str) -> str:
    return _LABEL_CLEANUP.sub("_", label.strip().lower()).strip("_")


def _get_completion_date_for_milestone(
    milestone_index: int,
    history: list[SurrogateStatusHistory],
    pipeline_stages: dict[str, int],  # stage_key -> order
    milestones: list[MilestoneDefinition],
) -> datetime | None:
    """
    Get the completion date for a milestone.

    A milestone is completed when the surrogate first enters a stage that maps
    to the next milestone (or any milestone beyond it).

    Date priority: effective_at → recorded_at → changed_at
    """
    if milestone_index >= len(milestones) - 1:
        # Last milestone (Delivery) - completed_at is the delivery entry date
        delivery_milestone = milestones[-1]
        for entry in history:
            if entry.to_stage_id:
                to_stage_key = getattr(entry, "_to_stage_key", None)
                if to_stage_key and to_stage_key in delivery_milestone.mapped_stage_keys:
                    return entry.effective_at or entry.recorded_at or entry.changed_at
        return None

    # For other milestones, completion date is when first entering next milestone
    next_milestone_index = milestone_index + 1

    # Collect all stage slugs that would indicate completion
    completion_stage_keys: set[str] = set()
    for i in range(next_milestone_index, len(milestones)):
        completion_stage_keys.update(milestones[i].mapped_stage_keys)

    # Find the earliest history entry that enters a completion stage
    earliest_date: datetime | None = None
    for entry in history:
        to_stage_key = getattr(entry, "_to_stage_key", None)
        if to_stage_key and to_stage_key in completion_stage_keys:
            entry_date = entry.effective_at or entry.recorded_at or entry.changed_at
            if entry_date and (earliest_date is None or entry_date < earliest_date):
                earliest_date = entry_date

    return earliest_date


def _build_journey_definitions(
    feature_config,
) -> tuple[
    list[MilestoneDefinition],
    list[PhaseDefinition],
    dict[str, MilestoneDefinition],
    dict[str, int],
    dict[str, str],
]:
    milestones = [
        MilestoneDefinition(
            slug=milestone.slug,
            label=milestone.label,
            description=milestone.description,
            mapped_stage_keys=tuple(milestone.mapped_stage_keys),
            is_soft=milestone.is_soft,
        )
        for milestone in feature_config.journey.milestones
    ]
    phases = [
        PhaseDefinition(
            slug=phase.slug,
            label=phase.label,
            milestone_slugs=tuple(phase.milestone_slugs),
        )
        for phase in feature_config.journey.phases
    ]
    milestone_by_slug = {milestone.slug: milestone for milestone in milestones}
    milestone_index_by_slug = {milestone.slug: index for index, milestone in enumerate(milestones)}
    stage_to_milestone: dict[str, str] = {}
    for milestone in milestones:
        for stage_key in milestone.mapped_stage_keys:
            stage_to_milestone[canonicalize_stage_key(stage_key)] = milestone.slug
    return milestones, phases, milestone_by_slug, milestone_index_by_slug, stage_to_milestone


def get_journey(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID,
) -> JourneyResponse | None:
    """
    Get the journey timeline for a surrogate.

    All status derivation happens here - frontend only renders the response.
    Uses a single query path with joins to avoid N+1.
    """
    # Single query with all required joins
    surrogate = (
        db.query(Surrogate)
        .options(
            joinedload(Surrogate.stage),
            joinedload(Surrogate.organization),
        )
        .filter(
            Surrogate.id == surrogate_id,
            Surrogate.organization_id == org_id,
        )
        .first()
    )

    if not surrogate:
        return None

    # Get organization info
    org = surrogate.organization
    org_name = org.name if org else "Unknown Organization"
    org_logo_url = org.logo_url if org and hasattr(org, "logo_url") else None

    # Get pipeline stages for order lookup (cached per request)
    pipeline_id = surrogate.stage.pipeline_id if surrogate.stage else None
    if not pipeline_id:
        # Get default pipeline
        from app.services import pipeline_service

        pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id, None)
        pipeline_id = pipeline.id

    stages = db.query(PipelineStage).filter(PipelineStage.pipeline_id == pipeline_id).all()
    pipeline_snapshot = pipeline_semantics_service.get_pipeline_semantics_snapshot(db, pipeline_id)
    feature_config = pipeline_snapshot.feature_config
    milestones, phases_defs, milestone_by_slug, milestone_index_by_slug, stage_to_milestone = (
        _build_journey_definitions(feature_config)
    )
    pipeline_stages: dict[str, int] = {
        stage.stage_key: stage.order for stage in pipeline_snapshot.stages
    }
    stage_id_to_key: dict[UUID, str] = {
        stage.id: stage.stage_key for stage in pipeline_snapshot.stages
    }
    terminal_stage_keys = {
        stage.stage_key
        for stage in pipeline_snapshot.stages
        if stage.semantics.terminal_outcome != "none"
    }
    delivery_stage_keys = {
        stage.stage_key
        for stage in pipeline_snapshot.stages
        if stage.semantics.capabilities.requires_delivery_details
    }
    label_to_key: dict[str, str] = {
        s.label.strip().lower(): canonicalize_stage_key(s.stage_key or s.slug)
        for s in stages
        if s.label
    }

    def resolve_label_stage_key(label: str | None) -> str | None:
        if not label:
            return None
        key = label.strip().lower()
        if key in label_to_key:
            return label_to_key[key]
        normalized = canonicalize_stage_key(_normalize_label_to_slug(label))
        if normalized in pipeline_stages:
            return normalized
        if normalized in stage_to_milestone:
            return normalized
        return None

    # Get status history with stage info (single query)
    history_entries = (
        db.query(SurrogateStatusHistory)
        .filter(
            SurrogateStatusHistory.surrogate_id == surrogate_id,
            SurrogateStatusHistory.organization_id == org_id,
        )
        .order_by(SurrogateStatusHistory.effective_at.asc())
        .all()
    )

    # Enrich history with stage slugs (avoiding N+1)
    for entry in history_entries:
        entry._to_stage_key = (
            stage_id_to_key.get(entry.to_stage_id) if entry.to_stage_id else None
        ) or resolve_label_stage_key(entry.to_label_snapshot)
        entry._from_stage_key = (
            stage_id_to_key.get(entry.from_stage_id) if entry.from_stage_id else None
        ) or resolve_label_stage_key(entry.from_label_snapshot)

    from app.services import surrogate_stage_context

    current_stage = surrogate_stage_context.get_stage_context(
        db,
        surrogate,
        current_stage=surrogate.stage,
    ).effective_stage

    # Determine current state
    current_stage_key = (
        canonicalize_stage_key(current_stage.stage_key or current_stage.slug)
        if current_stage
        else None
    )
    if not current_stage_key and surrogate.status_label:
        current_stage_key = resolve_label_stage_key(surrogate.status_label)
    is_terminal = current_stage_key in terminal_stage_keys

    # Get terminal info if applicable
    terminal_message: str | None = None
    terminal_date: str | None = None
    if is_terminal:
        terminal_message = "This journey ended before completion."
        terminal_entries = [
            entry for entry in history_entries if entry._to_stage_key in terminal_stage_keys
        ]
        if terminal_entries:
            terminal_entry = max(
                terminal_entries,
                key=lambda entry: (
                    entry.effective_at or entry.recorded_at or entry.changed_at or datetime.min
                ),
            )
            entry_date = (
                terminal_entry.effective_at
                or terminal_entry.recorded_at
                or terminal_entry.changed_at
            )
            if entry_date:
                terminal_date = entry_date.isoformat()

    # Determine current milestone
    journey_complete = current_stage_key in delivery_stage_keys
    current_milestone_slug: str | None = None
    if not is_terminal and not journey_complete and current_stage_key:
        current_milestone_slug = _get_milestone_for_stage(
            current_stage_key,
            pipeline_stages,
            milestones,
            stage_to_milestone,
        )

    delivery_completed_at = _get_completion_date_for_milestone(
        len(milestones) - 1, history_entries, pipeline_stages, milestones
    )

    # Load featured images for this surrogate
    featured_images = (
        db.query(JourneyFeaturedImage)
        .options(joinedload(JourneyFeaturedImage.attachment))
        .filter(
            JourneyFeaturedImage.surrogate_id == surrogate_id,
            JourneyFeaturedImage.organization_id == org_id,
        )
        .all()
    )

    # Build a map of milestone_slug -> (attachment_id, signed_url)
    featured_image_map: dict[str, tuple[str, str]] = {}
    for fi in featured_images:
        attachment = fi.attachment
        # Skip if attachment is deleted or quarantined
        if not attachment or attachment.deleted_at or attachment.quarantined:
            continue
        # Generate fresh signed URL
        signed_url = attachment_service.generate_signed_url(attachment.storage_key)
        if signed_url:
            if signed_url.startswith("/"):
                signed_url = f"{settings.API_BASE_URL.rstrip('/')}{signed_url}"
            featured_image_map[fi.milestone_slug] = (str(fi.attachment_id), signed_url)

    # Build milestones with statuses
    phases: list[JourneyPhase] = []

    for phase_def in phases_defs:
        phase_milestones: list[JourneyMilestone] = []

        for milestone_slug in phase_def.milestone_slugs:
            milestone_def = milestone_by_slug[milestone_slug]
            milestone_index = milestone_index_by_slug[milestone_slug]

            # Determine status
            completed_at = _get_completion_date_for_milestone(
                milestone_index, history_entries, pipeline_stages, milestones
            )
            is_completed = completed_at is not None

            if journey_complete:
                status: Literal["completed", "current", "upcoming"] = "completed"
                if milestone_def.is_soft and completed_at is None:
                    completed_at = delivery_completed_at
            elif is_terminal:
                if not is_completed:
                    continue
                status = "completed"
            elif is_completed:
                status = "completed"
            elif current_milestone_slug == milestone_def.slug and not milestone_def.is_soft:
                status = "current"
            else:
                status = "upcoming"

            # Get featured image info if set
            featured_info = featured_image_map.get(milestone_def.slug)
            featured_image_id = featured_info[0] if featured_info else None
            featured_image_url = featured_info[1] if featured_info else None

            phase_milestones.append(
                JourneyMilestone(
                    slug=milestone_def.slug,
                    label=milestone_def.label,
                    description=milestone_def.description,
                    status=status,
                    completed_at=completed_at,
                    is_soft=milestone_def.is_soft,
                    default_image_url=get_default_image_url(milestone_def.slug),
                    featured_image_url=featured_image_url,
                    featured_image_id=featured_image_id,
                )
            )

        # Only include phase if it has milestones (terminal journeys may have fewer)
        if phase_milestones:
            phases.append(
                JourneyPhase(
                    slug=phase_def.slug,
                    label=phase_def.label,
                    milestones=phase_milestones,
                )
            )

    return JourneyResponse(
        surrogate_id=str(surrogate_id),
        surrogate_name=surrogate.full_name,
        journey_version=JOURNEY_VERSION,
        is_terminal=is_terminal,
        terminal_message=terminal_message,
        terminal_date=terminal_date,
        phases=phases,
        organization_name=org_name,
        organization_logo_url=org_logo_url,
    )
