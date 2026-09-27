"""Campaign audience filters and recipient previews."""

from copy import deepcopy
from uuid import UUID

from sqlalchemy import String, and_, any_, bindparam, case, func, or_
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from app.core.encryption import hash_email
from app.core.stage_definitions import (
    EGG_DONOR_PIPELINE_ENTITY,
    INTENDED_PARENT_PIPELINE_ENTITY,
    SPERM_DONOR_PIPELINE_ENTITY,
    SURROGATE_PIPELINE_ENTITY,
)
from app.db.models import (
    Campaign,
    Donor,
    EmailSuppression,
    IntendedParent,
    MessagingConsentState,
    MessagingContact,
    MessagingGlobalSuppression,
    Pipeline,
    PipelineStage,
    Surrogate,
)
from app.schemas.campaign import (
    CampaignPreviewResponse,
    FilterCriteria,
    RecipientPreview,
)
from app.services import campaign_access

DONOR_RECIPIENT_TYPES = {
    EGG_DONOR_PIPELINE_ENTITY: "egg",
    SPERM_DONOR_PIPELINE_ENTITY: "sperm",
}


RECIPIENT_PIPELINE_ENTITY_TYPES = {
    "case": SURROGATE_PIPELINE_ENTITY,
    "intended_parent": INTENDED_PARENT_PIPELINE_ENTITY,
    EGG_DONOR_PIPELINE_ENTITY: EGG_DONOR_PIPELINE_ENTITY,
    SPERM_DONOR_PIPELINE_ENTITY: SPERM_DONOR_PIPELINE_ENTITY,
}


DONOR_MESSAGING_UNAVAILABLE = (
    "Messaging campaigns are not available for donors until donor consent identities are linked"
)


def ensure_supported_campaign_channel(channel: str, recipient_type: str) -> None:
    if channel == "messaging" and recipient_type in DONOR_RECIPIENT_TYPES:
        raise ValueError(DONOR_MESSAGING_UNAVAILABLE)


def recipient_entity_model(recipient_type: str):
    if recipient_type == "case":
        return Surrogate
    if recipient_type == "intended_parent":
        return IntendedParent
    if recipient_type in DONOR_RECIPIENT_TYPES:
        return Donor
    raise ValueError(f"Unknown recipient type: {recipient_type}")


def normalize_filter_criteria(
    db: Session,
    org_id: UUID,
    recipient_type: str,
    criteria: dict | FilterCriteria | None,
) -> dict:
    """Persist stage filters in stage-id/key form so slug edits stay safe."""
    payload = (
        criteria.model_dump(mode="json")
        if isinstance(criteria, FilterCriteria)
        else deepcopy(criteria or {})
    )
    normalized = FilterCriteria.model_validate(payload).model_dump(mode="json", exclude_none=True)

    pipeline_entity_type = RECIPIENT_PIPELINE_ENTITY_TYPES.get(recipient_type)
    if pipeline_entity_type is None:
        return normalized

    from app.services import pipeline_service

    stage_ids: list[UUID] = []
    raw_stage_ids = normalized.get("stage_ids") or []
    donor_recipient = recipient_type in DONOR_RECIPIENT_TYPES
    parsed_stage_ids: list[UUID] = []
    for value in raw_stage_ids:
        try:
            parsed_stage_ids.append(UUID(str(value)))
        except ValueError:
            continue
    stage_by_id: dict[UUID, PipelineStage] = {}
    if parsed_stage_ids:
        query = (
            db.query(PipelineStage)
            .join(Pipeline, Pipeline.id == PipelineStage.pipeline_id)
            .filter(
                PipelineStage.id.in_(parsed_stage_ids),
                Pipeline.organization_id == org_id,
            )
        )
        if donor_recipient:
            query = query.filter(
                PipelineStage.is_active.is_(True),
                Pipeline.entity_type == pipeline_entity_type,
                Pipeline.is_default.is_(True),
            )
        stage_by_id = {stage.id: stage for stage in query.all()}
    for stage_id in parsed_stage_ids:
        stage = stage_by_id.get(stage_id)
        if donor_recipient and stage is None:
            raise ValueError(
                f"Stage filter not found in {recipient_type.replace('_', ' ')} pipeline"
            )
        if stage and stage.is_active and stage_id not in stage_ids:
            stage_ids.append(stage_id)

    stage_refs = [
        *[str(value) for value in normalized.get("stage_keys") or []],
        *[str(value) for value in normalized.get("stage_slugs") or []],
    ]
    default_pipeline_id = (
        db.query(Pipeline.id)
        .filter(
            Pipeline.organization_id == org_id,
            Pipeline.entity_type == pipeline_entity_type,
            Pipeline.is_default.is_(True),
        )
        .scalar()
    )
    if stage_refs and default_pipeline_id is None:
        default_pipeline_id = pipeline_service.get_or_create_default_pipeline(
            db, org_id, entity_type=pipeline_entity_type
        ).id
    resolved_stages = (
        pipeline_service.resolve_stages_bulk(db, org_id, default_pipeline_id, stage_refs)
        if stage_refs
        else []
    )
    for stage in resolved_stages:
        if stage is None:
            if donor_recipient:
                raise ValueError(
                    f"Stage filter not found in {recipient_type.replace('_', ' ')} pipeline"
                )
            continue
        stage_by_id[stage.id] = stage
        if stage.id not in stage_ids:
            stage_ids.append(stage.id)

    stage_keys: list[str] = []
    for stage_id in stage_ids:
        stage = stage_by_id.get(stage_id)
        if stage and stage.is_active and stage.stage_key and stage.stage_key not in stage_keys:
            stage_keys.append(stage.stage_key)

    normalized["stage_ids"] = [str(stage_id) for stage_id in stage_ids]
    normalized["stage_keys"] = stage_keys
    normalized.pop("stage_slugs", None)
    return normalized


def remap_campaign_stage_references(
    db: Session,
    org_id: UUID,
    campaign: Campaign,
    remap_by_key: dict[str, str | None],
) -> None:
    if campaign.recipient_type not in RECIPIENT_PIPELINE_ENTITY_TYPES:
        return

    from app.services import pipeline_service

    criteria = deepcopy(
        campaign.filter_criteria if isinstance(campaign.filter_criteria, dict) else {}
    )
    stage_keys: list[str] = []
    for stage_id in criteria.get("stage_ids") or []:
        try:
            stage_uuid = UUID(str(stage_id))
        except ValueError:
            continue
        stage = pipeline_service.get_stage_by_id(db, stage_uuid)
        if stage and stage.stage_key:
            replacement = remap_by_key.get(stage.stage_key, stage.stage_key)
            if replacement and replacement not in stage_keys:
                stage_keys.append(replacement)

    for value in criteria.get("stage_keys") or []:
        replacement = remap_by_key.get(str(value), str(value))
        if replacement and replacement not in stage_keys:
            stage_keys.append(replacement)

    for value in criteria.get("stage_slugs") or []:
        normalized_value = pipeline_service.normalize_stage_ref(str(value))
        replacement = remap_by_key.get(normalized_value, normalized_value)
        if replacement and replacement not in stage_keys:
            stage_keys.append(replacement)

    criteria["stage_keys"] = stage_keys
    criteria.pop("stage_slugs", None)
    campaign.filter_criteria = normalize_filter_criteria(
        db, org_id, campaign.recipient_type, criteria
    )


def build_recipient_query(
    db: Session,
    org_id: UUID,
    recipient_type: str,
    filter_criteria: dict,
    *,
    channel: str = "email",
    campaign=None,
    scope: str = "org",
    owner_user_id: UUID | None = None,
):
    """Build SQLAlchemy query for recipients based on filter criteria."""
    criteria = FilterCriteria(**filter_criteria) if filter_criteria else FilterCriteria()

    if recipient_type == "case":
        recipient_requirement = (
            and_(Surrogate.email.isnot(None), Surrogate.email != "")
            if channel == "email"
            else and_(Surrogate.phone.isnot(None), Surrogate.phone_hash.isnot(None))
        )
        query = db.query(Surrogate).filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            recipient_requirement,
        )

        if criteria.stage_ids:
            query = query.filter(Surrogate.stage_id.in_(criteria.stage_ids))

        stage_refs = []
        if criteria.stage_keys:
            stage_refs.extend(criteria.stage_keys)
        if criteria.stage_slugs:
            stage_refs.extend(criteria.stage_slugs)

        if stage_refs:
            from app.services import pipeline_service

            resolved_stage_ids = pipeline_service.get_stage_ids_by_keys_or_slugs(
                db, org_id, stage_refs
            )
            query = query.filter(Surrogate.stage_id.in_(resolved_stage_ids))

        if criteria.states:
            query = query.filter(Surrogate.state.in_(criteria.states))

        if criteria.created_after:
            query = query.filter(Surrogate.created_at >= criteria.created_after)

        if criteria.created_before:
            query = query.filter(Surrogate.created_at <= criteria.created_before)

        if criteria.source:
            query = query.filter(Surrogate.source == criteria.source)

        if criteria.is_priority is not None:
            query = query.filter(Surrogate.is_priority == criteria.is_priority)

        return campaign_access.apply_audience(
            db,
            query,
            org_id,
            recipient_type,
            campaign=campaign,
            scope=scope,
            owner_user_id=owner_user_id,
        )

    elif recipient_type == "intended_parent":
        recipient_requirement = (
            and_(IntendedParent.email.isnot(None), IntendedParent.email != "")
            if channel == "email"
            else and_(
                IntendedParent.phone.isnot(None),
                IntendedParent.phone_hash.isnot(None),
            )
        )
        query = db.query(IntendedParent).filter(
            IntendedParent.organization_id == org_id,
            recipient_requirement,
            IntendedParent.is_archived.is_(False),  # Exclude archived IPs
        )

        if criteria.stage_ids:
            query = query.filter(IntendedParent.stage_id.in_(criteria.stage_ids))

        stage_refs = []
        if criteria.stage_keys:
            stage_refs.extend(criteria.stage_keys)
        if criteria.stage_slugs:
            stage_refs.extend(criteria.stage_slugs)

        if stage_refs:
            from app.services import pipeline_service

            resolved_stage_ids = pipeline_service.get_stage_ids_by_keys_or_slugs(
                db,
                org_id,
                stage_refs,
                entity_type=INTENDED_PARENT_PIPELINE_ENTITY,
            )
            query = query.filter(IntendedParent.stage_id.in_(resolved_stage_ids))

        if criteria.created_after:
            query = query.filter(IntendedParent.created_at >= criteria.created_after)

        if criteria.created_before:
            query = query.filter(IntendedParent.created_at <= criteria.created_before)

        return campaign_access.apply_audience(
            db,
            query,
            org_id,
            recipient_type,
            campaign=campaign,
            scope=scope,
            owner_user_id=owner_user_id,
        )

    elif recipient_type in DONOR_RECIPIENT_TYPES:
        donor_type = DONOR_RECIPIENT_TYPES[recipient_type]
        recipient_requirement = (
            and_(Donor.email.isnot(None), Donor.email != "")
            if channel == "email"
            else and_(Donor.phone.isnot(None), Donor.phone_hash.isnot(None))
        )
        query = db.query(Donor).filter(
            Donor.organization_id == org_id,
            Donor.donor_type == donor_type,
            Donor.is_archived.is_(False),
            recipient_requirement,
        )

        if criteria.stage_ids:
            query = query.filter(Donor.stage_id.in_(criteria.stage_ids))

        stage_refs = [
            *(criteria.stage_keys or []),
            *(criteria.stage_slugs or []),
        ]
        if stage_refs:
            from app.services import pipeline_service

            default_pipeline_id = (
                db.query(Pipeline.id)
                .filter(
                    Pipeline.organization_id == org_id,
                    Pipeline.entity_type == recipient_type,
                    Pipeline.is_default.is_(True),
                )
                .scalar()
            )
            resolved_stage_ids = pipeline_service.get_stage_ids_by_keys_or_slugs(
                db,
                org_id,
                stage_refs,
                pipeline_id=default_pipeline_id,
                entity_type=recipient_type,
            )
            query = query.filter(Donor.stage_id.in_(resolved_stage_ids))

        if criteria.states:
            query = query.filter(Donor.state.in_(criteria.states))

        if criteria.created_after:
            query = query.filter(Donor.created_at >= criteria.created_after)

        if criteria.created_before:
            query = query.filter(Donor.created_at <= criteria.created_before)

        if criteria.source:
            query = query.filter(Donor.source == criteria.source)

        return campaign_access.apply_audience(
            db,
            query,
            org_id,
            recipient_type,
            campaign=campaign,
            scope=scope,
            owner_user_id=owner_user_id,
        )

    raise ValueError(f"Unknown recipient type: {recipient_type}")


def _messaging_contact_join_condition(org_id: UUID, recipient_type: str):
    if recipient_type == "case":
        return and_(
            MessagingContact.organization_id == org_id,
            or_(
                MessagingContact.surrogate_id == Surrogate.id,
                MessagingContact.phone_hash == Surrogate.phone_hash,
            ),
        )
    if recipient_type == "intended_parent":
        return and_(
            MessagingContact.organization_id == org_id,
            MessagingContact.phone_hash == IntendedParent.phone_hash,
        )
    if recipient_type in DONOR_RECIPIENT_TYPES:
        return and_(
            MessagingContact.organization_id == org_id,
            MessagingContact.phone_hash == Donor.phone_hash,
        )
    raise ValueError(f"Unknown recipient type: {recipient_type}")


def _messaging_recipient_rows_query(
    db: Session,
    *,
    org_id: UUID,
    recipient_type: str,
    filter_criteria: dict,
    campaign=None,
    scope: str = "org",
    owner_user_id: UUID | None = None,
):
    base = build_recipient_query(
        db,
        org_id,
        recipient_type,
        filter_criteria,
        channel="messaging",
        campaign=campaign,
        scope=scope,
        owner_user_id=owner_user_id,
    )
    return (
        base.add_entity(MessagingContact)
        .join(
            MessagingContact,
            _messaging_contact_join_condition(org_id, recipient_type),
        )
        .outerjoin(
            MessagingConsentState,
            and_(
                MessagingConsentState.organization_id == org_id,
                MessagingConsentState.contact_id == MessagingContact.id,
                MessagingConsentState.purpose == "promotional",
            ),
        )
        .outerjoin(
            MessagingGlobalSuppression,
            and_(
                MessagingGlobalSuppression.organization_id == org_id,
                MessagingGlobalSuppression.contact_id == MessagingContact.id,
            ),
        )
    )


def preview_recipients(
    db: Session,
    org_id: UUID,
    recipient_type: str,
    filter_criteria: dict,
    limit: int = 50,
    *,
    ignore_opt_out: bool = False,
    channel: str = "email",
    campaign=None,
    scope: str = "org",
    owner_user_id: UUID | None = None,
    viewer_session=None,
) -> CampaignPreviewResponse:
    """Preview recipients matching the filter criteria."""
    ensure_supported_campaign_channel(channel, recipient_type)
    viewer_filter = (
        campaign_access.viewer_entity_filter(db, viewer_session, org_id, recipient_type)
        if viewer_session is not None and campaign_access.enabled(db, org_id)
        else None
    )
    if channel == "messaging":
        if ignore_opt_out:
            raise ValueError("include_unsubscribed is not available for messaging campaigns")
        base_query = build_recipient_query(
            db,
            org_id,
            recipient_type,
            filter_criteria,
            channel="messaging",
            campaign=campaign,
            scope=scope,
            owner_user_id=owner_user_id,
        )
        if viewer_filter is not None:
            base_query = base_query.filter(viewer_filter)
        total_count = base_query.order_by(None).count()
        rows_query = _messaging_recipient_rows_query(
            db,
            org_id=org_id,
            recipient_type=recipient_type,
            filter_criteria=filter_criteria,
            campaign=campaign,
            scope=scope,
            owner_user_id=owner_user_id,
        )
        if viewer_filter is not None:
            rows_query = rows_query.filter(viewer_filter)
        globally_allowed = or_(
            MessagingGlobalSuppression.id.is_(None),
            MessagingGlobalSuppression.active.is_(False),
        )
        eligible_query = rows_query.filter(
            MessagingConsentState.status == "opted_in",
            globally_allowed,
        )
        explicitly_suppressed = (
            rows_query.filter(
                or_(
                    MessagingConsentState.status == "opted_out",
                    MessagingGlobalSuppression.active.is_(True),
                )
            )
            .order_by(None)
            .count()
        )
        eligible_entity_count = eligible_query.order_by(None).count()
        eligible_count = (
            eligible_query.with_entities(func.count(func.distinct(MessagingContact.id)))
            .order_by(None)
            .scalar()
            or 0
        )
        duplicate_count = max(eligible_entity_count - eligible_count, 0)
        samples: list[RecipientPreview] = []
        sampled_contact_ids: set[UUID] = set()
        rows = eligible_query.order_by(
            MessagingContact.phone_last4,
            MessagingContact.id,
        ).yield_per(max(limit, 1))
        for entity, contact in rows:
            if contact.id in sampled_contact_ids:
                continue
            sampled_contact_ids.add(contact.id)
            samples.append(
                RecipientPreview(
                    entity_type=recipient_type,
                    entity_id=entity.id,
                    phone_last4=contact.phone_last4,
                    name=entity.full_name,
                    stage=None,
                )
            )
            if len(samples) >= limit:
                break
        return CampaignPreviewResponse(
            total_count=total_count,
            eligible_count=eligible_count,
            suppressed_count=explicitly_suppressed + duplicate_count,
            unknown_consent_count=max(
                total_count - eligible_entity_count - explicitly_suppressed,
                0,
            ),
            sample_recipients=samples,
        )

    query = build_recipient_query(
        db,
        org_id,
        recipient_type,
        filter_criteria,
        channel="email",
        campaign=campaign,
        scope=scope,
        owner_user_id=owner_user_id,
    )

    if viewer_filter is not None:
        query = query.filter(viewer_filter)
    entity_model = recipient_entity_model(recipient_type)

    # Entity emails are encrypted at rest, so suppression matching happens on
    # the indexed email_hash column. Load and hash the org's suppression list,
    # then pass it as one PostgreSQL array bind so large lists do not exceed the
    # driver's bind-parameter limit. Counts still cover the whole filtered
    # audience without materializing every recipient.
    suppression_query = db.query(EmailSuppression.email).filter(
        EmailSuppression.organization_id == org_id
    )
    if ignore_opt_out:
        suppression_query = suppression_query.filter(EmailSuppression.reason != "opt_out")
    suppressed_hashes = list({hash_email(email) for (email,) in suppression_query if email})

    suppressed_hashes_param = bindparam(
        "suppressed_email_hashes",
        value=suppressed_hashes,
        type_=ARRAY(String(64)),
    )
    suppressed_condition = entity_model.email_hash == any_(suppressed_hashes_param)
    total_count, suppressed_count = (
        query.order_by(None)
        .with_entities(
            func.count(),
            func.coalesce(func.sum(case((suppressed_condition, 1), else_=0)), 0),
        )
        .one()
    )
    eligible_count = max(total_count - suppressed_count, 0)

    sample_entities = query.filter(~suppressed_condition).limit(limit).all()

    stage_labels: dict[UUID, str] = {}
    if recipient_type in RECIPIENT_PIPELINE_ENTITY_TYPES:
        stage_ids = {entity.stage_id for entity in sample_entities if entity.stage_id}
        if stage_ids:
            stage_rows = (
                db.query(PipelineStage.id, PipelineStage.label)
                .filter(PipelineStage.id.in_(stage_ids))
                .all()
            )
            stage_labels = {stage_id: label for stage_id, label in stage_rows}

    recipients = [
        RecipientPreview(
            entity_type=recipient_type,
            entity_id=entity.id,
            email=entity.email,
            name=entity.full_name,
            stage=stage_labels.get(entity.stage_id),
        )
        for entity in sample_entities
    ]

    return CampaignPreviewResponse(
        total_count=total_count,
        eligible_count=eligible_count,
        suppressed_count=suppressed_count,
        sample_recipients=recipients,
    )
