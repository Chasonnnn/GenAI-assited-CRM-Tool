"""Organization-scoped projections and non-composer messaging inbox actions."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.db.models import IntakeLead, MetaLead, Surrogate, TwilioRoute
from app.db.models.messaging import (
    MessagingConsentEvidence,
    MessagingConsentState,
    MessagingContact,
    MessagingGlobalSuppression,
)
from app.db.models.messaging_delivery import (
    MessageDelivery,
    MessageDeliveryAttempt,
    MessageMediaAsset,
    MessageMediaLink,
    MessageReconciliationCase,
    MessageWebhookEvent,
    MessagingConversation,
    MessagingMessage,
)
from app.schemas.messaging_inbox import (
    MessagingConsentEventRead,
    MessagingConversationDetail,
    MessagingConversationListResponse,
    MessagingConversationSummary,
    MessagingDeliveryAttemptRead,
    MessagingDeliveryRead,
    MessagingDeliveryStatusEventRead,
    MessagingLinkedEntityRead,
    MessagingMediaRead,
    MessagingMessageRead,
    MessagingReconciliationCaseRead,
)


class MessagingInboxNotFound(LookupError):
    """Requested inbox object is absent from the active organization."""


class MessagingInboxEntityNotFound(LookupError):
    """Requested CRM link target is absent from the active organization."""


class MessagingInboxLinkConflict(ValueError):
    """A contact is already linked to a different entity of the same type."""


class MessagingInboxVersionConflict(ValueError):
    """A reconciliation action used a stale optimistic version."""


def _masked_phone(contact: MessagingContact) -> str:
    return f"••• ••• {contact.phone_last4}"


def _route_label(purpose: str) -> str:
    return "Operational route" if purpose == "operational" else "Promotional route"


def _entity_label_maps(
    db: Session,
    *,
    organization_id: uuid.UUID,
    contacts: Iterable[MessagingContact],
) -> dict[str, dict[uuid.UUID, str]]:
    contacts = list(contacts)
    surrogate_ids = {item.surrogate_id for item in contacts if item.surrogate_id}
    intake_ids = {item.intake_lead_id for item in contacts if item.intake_lead_id}
    meta_ids = {item.meta_lead_id for item in contacts if item.meta_lead_id}

    surrogate_labels = (
        {
            item.id: f"{item.surrogate_number} · {item.full_name}"
            for item in db.scalars(
                select(Surrogate).where(
                    Surrogate.organization_id == organization_id,
                    Surrogate.id.in_(surrogate_ids),
                )
            ).all()
        }
        if surrogate_ids
        else {}
    )
    intake_labels = (
        {
            item.id: item.full_name
            for item in db.scalars(
                select(IntakeLead).where(
                    IntakeLead.organization_id == organization_id,
                    IntakeLead.id.in_(intake_ids),
                )
            ).all()
        }
        if intake_ids
        else {}
    )
    meta_labels: dict[uuid.UUID, str] = {}
    if meta_ids:
        for item in db.scalars(
            select(MetaLead).where(
                MetaLead.organization_id == organization_id,
                MetaLead.id.in_(meta_ids),
            )
        ).all():
            data = item.field_data or {}
            name = str(data.get("full_name") or "").strip()
            meta_labels[item.id] = name or f"Meta lead {item.meta_lead_id[-8:]}"
    return {
        "surrogate": surrogate_labels,
        "intake_lead": intake_labels,
        "meta_lead": meta_labels,
    }


def _linked_entities(
    contact: MessagingContact,
    labels: dict[str, dict[uuid.UUID, str]],
) -> list[MessagingLinkedEntityRead]:
    result: list[MessagingLinkedEntityRead] = []
    for entity_type, entity_id in (
        ("surrogate", contact.surrogate_id),
        ("intake_lead", contact.intake_lead_id),
        ("meta_lead", contact.meta_lead_id),
    ):
        if entity_id is None:
            continue
        label = labels[entity_type].get(entity_id)
        if label is None:
            continue
        result.append(
            MessagingLinkedEntityRead(
                entity_type=entity_type,
                entity_id=entity_id,
                label=label,
            )
        )
    return result


def _summary(
    *,
    conversation: MessagingConversation,
    contact: MessagingContact,
    route: TwilioRoute,
    labels: dict[str, dict[uuid.UUID, str]],
    last_message: MessagingMessage | None,
) -> MessagingConversationSummary:
    linked = _linked_entities(contact, labels)
    preview = None
    if last_message is not None:
        normalized = " ".join(last_message.body.split())
        preview = normalized[:120] or None
    return MessagingConversationSummary(
        id=conversation.id,
        contact_id=contact.id,
        masked_phone=_masked_phone(contact),
        purpose=route.purpose,
        route_id=route.id,
        route_label=_route_label(route.purpose),
        unread_count=conversation.unread_count,
        unlinked=not linked,
        linked_entities=linked,
        last_message_at=conversation.last_message_at,
        last_message_direction=last_message.direction if last_message else None,
        last_message_preview=preview,
    )


def _conversation_rows(
    db: Session,
    *,
    organization_id: uuid.UUID,
    unread: bool | None,
    unlinked: bool | None,
    purpose: str | None,
    surrogate_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[tuple[MessagingConversation, MessagingContact, TwilioRoute]], int]:
    filters = [MessagingConversation.organization_id == organization_id]
    if unread is True:
        filters.append(MessagingConversation.unread_count > 0)
    elif unread is False:
        filters.append(MessagingConversation.unread_count == 0)
    if unlinked is True:
        filters.extend(
            [
                MessagingContact.surrogate_id.is_(None),
                MessagingContact.intake_lead_id.is_(None),
                MessagingContact.meta_lead_id.is_(None),
            ]
        )
    elif unlinked is False:
        filters.append(
            or_(
                MessagingContact.surrogate_id.is_not(None),
                MessagingContact.intake_lead_id.is_not(None),
                MessagingContact.meta_lead_id.is_not(None),
            )
        )
    if purpose:
        filters.append(TwilioRoute.purpose == purpose)
    if surrogate_id:
        filters.append(MessagingContact.surrogate_id == surrogate_id)

    base = (
        select(MessagingConversation, MessagingContact, TwilioRoute)
        .join(MessagingContact, MessagingContact.id == MessagingConversation.contact_id)
        .join(TwilioRoute, TwilioRoute.id == MessagingConversation.route_id)
        .where(*filters)
    )
    total = db.scalar(
        select(func.count())
        .select_from(MessagingConversation)
        .join(MessagingContact, MessagingContact.id == MessagingConversation.contact_id)
        .join(TwilioRoute, TwilioRoute.id == MessagingConversation.route_id)
        .where(*filters)
    ) or 0
    rows = list(
        db.execute(
            base.order_by(
                MessagingConversation.last_message_at.desc().nullslast(),
                MessagingConversation.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).tuples()
    )
    return rows, int(total)


def _last_messages(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_ids: list[uuid.UUID],
) -> dict[uuid.UUID, MessagingMessage]:
    if not conversation_ids:
        return {}
    messages = db.scalars(
        select(MessagingMessage)
        .where(
            MessagingMessage.organization_id == organization_id,
            MessagingMessage.conversation_id.in_(conversation_ids),
        )
        .distinct(MessagingMessage.conversation_id)
        .order_by(
            MessagingMessage.conversation_id,
            MessagingMessage.created_at.desc(),
            MessagingMessage.id.desc(),
        )
    ).all()
    return {item.conversation_id: item for item in messages}


def list_conversations(
    db: Session,
    *,
    organization_id: uuid.UUID,
    unread: bool | None,
    unlinked: bool | None,
    purpose: str | None,
    limit: int,
    offset: int,
) -> MessagingConversationListResponse:
    if purpose not in {None, "operational", "promotional"}:
        raise ValueError("Purpose must be operational or promotional")
    rows, total = _conversation_rows(
        db,
        organization_id=organization_id,
        unread=unread,
        unlinked=unlinked,
        purpose=purpose,
        surrogate_id=None,
        limit=limit,
        offset=offset,
    )
    contacts = [contact for _, contact, _ in rows]
    labels = _entity_label_maps(
        db,
        organization_id=organization_id,
        contacts=contacts,
    )
    last_by_conversation = _last_messages(
        db,
        organization_id=organization_id,
        conversation_ids=[conversation.id for conversation, _, _ in rows],
    )
    return MessagingConversationListResponse(
        items=[
            _summary(
                conversation=conversation,
                contact=contact,
                route=route,
                labels=labels,
                last_message=last_by_conversation.get(conversation.id),
            )
            for conversation, contact, route in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


def list_candidate_conversations(
    db: Session,
    *,
    organization_id: uuid.UUID,
    surrogate_id: uuid.UUID,
    limit: int,
    offset: int,
) -> MessagingConversationListResponse:
    exists = db.scalar(
        select(Surrogate.id).where(
            Surrogate.id == surrogate_id,
            Surrogate.organization_id == organization_id,
        )
    )
    if exists is None:
        raise MessagingInboxEntityNotFound("Candidate was not found in this organization")
    rows, total = _conversation_rows(
        db,
        organization_id=organization_id,
        unread=None,
        unlinked=False,
        purpose=None,
        surrogate_id=surrogate_id,
        limit=limit,
        offset=offset,
    )
    contacts = [contact for _, contact, _ in rows]
    labels = _entity_label_maps(
        db,
        organization_id=organization_id,
        contacts=contacts,
    )
    last_by_conversation = _last_messages(
        db,
        organization_id=organization_id,
        conversation_ids=[conversation.id for conversation, _, _ in rows],
    )
    return MessagingConversationListResponse(
        items=[
            _summary(
                conversation=conversation,
                contact=contact,
                route=route,
                labels=labels,
                last_message=last_by_conversation.get(conversation.id),
            )
            for conversation, contact, route in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


def _get_conversation_row(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> tuple[MessagingConversation, MessagingContact, TwilioRoute]:
    row = db.execute(
        select(MessagingConversation, MessagingContact, TwilioRoute)
        .join(MessagingContact, MessagingContact.id == MessagingConversation.contact_id)
        .join(TwilioRoute, TwilioRoute.id == MessagingConversation.route_id)
        .where(
            MessagingConversation.organization_id == organization_id,
            MessagingConversation.id == conversation_id,
            MessagingContact.organization_id == organization_id,
            TwilioRoute.organization_id == organization_id,
        )
    ).one_or_none()
    if row is None:
        raise MessagingInboxNotFound("Conversation not found")
    return row._tuple()


def _media_by_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    message_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[MessagingMediaRead]]:
    result: dict[uuid.UUID, list[MessagingMediaRead]] = {item: [] for item in message_ids}
    if not message_ids:
        return result
    rows = db.execute(
        select(MessageMediaLink, MessageMediaAsset)
        .join(MessageMediaAsset, MessageMediaAsset.id == MessageMediaLink.media_asset_id)
        .where(
            MessageMediaLink.organization_id == organization_id,
            MessageMediaLink.message_id.in_(message_ids),
            MessageMediaAsset.organization_id == organization_id,
        )
        .order_by(MessageMediaLink.message_id, MessageMediaLink.position)
    ).all()
    for link, asset in rows:
        result.setdefault(link.message_id, []).append(
            MessagingMediaRead(
                id=asset.id,
                filename=asset.original_filename,
                content_type=asset.content_type,
                byte_size=asset.byte_size,
                scan_status=asset.scan_status,
                provider_deleted=(
                    link.provider_deleted_at is not None
                    or asset.provider_deleted_at is not None
                ),
                quarantined=asset.scan_status == "quarantined",
            )
        )
    return result


def _deliveries_by_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    messages: list[MessagingMessage],
) -> tuple[dict[uuid.UUID, MessagingDeliveryRead], list[uuid.UUID], list[uuid.UUID]]:
    message_ids = [item.id for item in messages]
    if not message_ids:
        return {}, [], []
    deliveries = db.scalars(
        select(MessageDelivery)
        .where(
            MessageDelivery.organization_id == organization_id,
            MessageDelivery.message_id.in_(message_ids),
        )
        .order_by(MessageDelivery.created_at)
    ).all()
    delivery_ids = [item.id for item in deliveries]
    attempts_by_delivery: dict[uuid.UUID, list[MessagingDeliveryAttemptRead]] = {
        item: [] for item in delivery_ids
    }
    if delivery_ids:
        for attempt in db.scalars(
            select(MessageDeliveryAttempt)
            .where(
                MessageDeliveryAttempt.organization_id == organization_id,
                MessageDeliveryAttempt.delivery_id.in_(delivery_ids),
            )
            .order_by(
                MessageDeliveryAttempt.delivery_id,
                MessageDeliveryAttempt.attempt_number,
            )
        ).all():
            attempts_by_delivery[attempt.delivery_id].append(
                MessagingDeliveryAttemptRead(
                    id=attempt.id,
                    attempt_number=attempt.attempt_number,
                    outcome=attempt.outcome,
                    started_at=attempt.started_at,
                    completed_at=attempt.completed_at,
                    provider_http_status=attempt.provider_http_status,
                    error_type=attempt.error_type,
                    error_message=attempt.error_message,
                )
            )

    provider_sids = [item.provider_message_sid for item in messages if item.provider_message_sid]
    events_by_sid: dict[str, list[MessagingDeliveryStatusEventRead]] = {}
    webhook_ids: list[uuid.UUID] = []
    if provider_sids:
        events = db.scalars(
            select(MessageWebhookEvent)
            .where(
                MessageWebhookEvent.organization_id == organization_id,
                MessageWebhookEvent.event_type == "status",
                MessageWebhookEvent.provider_message_sid.in_(provider_sids),
            )
            .order_by(MessageWebhookEvent.received_at)
        ).all()
        for event in events:
            webhook_ids.append(event.id)
            events_by_sid.setdefault(event.provider_message_sid, []).append(
                MessagingDeliveryStatusEventRead(
                    id=event.id,
                    status=event.provider_status,
                    received_at=event.received_at,
                )
            )

    message_by_id = {item.id: item for item in messages}
    projected: dict[uuid.UUID, MessagingDeliveryRead] = {}
    for delivery in deliveries:
        message = message_by_id[delivery.message_id]
        projected[delivery.message_id] = MessagingDeliveryRead(
            id=delivery.id,
            status=delivery.status,
            source_type=delivery.source_type,
            attempt_count=delivery.attempt_count,
            max_attempts=delivery.max_attempts,
            created_at=delivery.created_at,
            completed_at=delivery.completed_at,
            last_error_type=delivery.last_error_type,
            last_error=delivery.last_error,
            attempts=attempts_by_delivery.get(delivery.id, []),
            status_events=events_by_sid.get(message.provider_message_sid or "", []),
        )
    return projected, delivery_ids, webhook_ids


def _reconciliation_cases(
    db: Session,
    *,
    organization_id: uuid.UUID,
    delivery_ids: list[uuid.UUID],
    webhook_ids: list[uuid.UUID],
) -> list[MessagingReconciliationCaseRead]:
    conditions = []
    if delivery_ids:
        conditions.append(MessageReconciliationCase.delivery_id.in_(delivery_ids))
    if webhook_ids:
        conditions.append(MessageReconciliationCase.webhook_event_id.in_(webhook_ids))
    if not conditions:
        return []
    rows = db.scalars(
        select(MessageReconciliationCase)
        .where(
            MessageReconciliationCase.organization_id == organization_id,
            or_(*conditions),
        )
        .order_by(MessageReconciliationCase.detected_at.desc())
    ).all()
    return [
        MessagingReconciliationCaseRead(
            id=item.id,
            case_type=item.case_type,
            status=item.status,
            reason_code=item.reason_code,
            detected_at=item.detected_at,
            resolved_at=item.resolved_at,
            resolution_code=item.resolution_code,
            version=item.version,
        )
        for item in rows
    ]


def get_conversation(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> MessagingConversationDetail:
    conversation, contact, route = _get_conversation_row(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
    )
    labels = _entity_label_maps(
        db,
        organization_id=organization_id,
        contacts=[contact],
    )
    messages = list(
        db.scalars(
            select(MessagingMessage)
            .where(
                MessagingMessage.organization_id == organization_id,
                MessagingMessage.conversation_id == conversation_id,
            )
            .order_by(MessagingMessage.created_at, MessagingMessage.id)
        ).all()
    )
    media_by_message = _media_by_message(
        db,
        organization_id=organization_id,
        message_ids=[item.id for item in messages],
    )
    delivery_by_message, delivery_ids, webhook_ids = _deliveries_by_message(
        db,
        organization_id=organization_id,
        messages=messages,
    )
    consent_states = {
        item.purpose: item.status
        for item in db.scalars(
            select(MessagingConsentState).where(
                MessagingConsentState.organization_id == organization_id,
                MessagingConsentState.contact_id == contact.id,
            )
        ).all()
    }
    for purpose in ("operational", "promotional"):
        consent_states.setdefault(purpose, "unknown")
    suppression = db.scalar(
        select(MessagingGlobalSuppression).where(
            MessagingGlobalSuppression.organization_id == organization_id,
            MessagingGlobalSuppression.contact_id == contact.id,
        )
    )
    evidence = db.scalars(
        select(MessagingConsentEvidence)
        .where(
            MessagingConsentEvidence.organization_id == organization_id,
            MessagingConsentEvidence.contact_id == contact.id,
        )
        .order_by(MessagingConsentEvidence.occurred_at.desc())
    ).all()
    last_message = messages[-1] if messages else None
    summary = _summary(
        conversation=conversation,
        contact=contact,
        route=route,
        labels=labels,
        last_message=last_message,
    )
    return MessagingConversationDetail(
        **summary.model_dump(),
        consent_states=consent_states,
        global_suppression_active=bool(suppression and suppression.active),
        global_suppression_reason=suppression.reason if suppression else "none",
        messages=[
            MessagingMessageRead(
                id=message.id,
                direction=message.direction,
                purpose=message.purpose,
                body=message.body,
                provider_status=message.provider_status,
                is_unread=message.is_unread,
                created_at=message.created_at,
                media=media_by_message.get(message.id, []),
                delivery=delivery_by_message.get(message.id),
            )
            for message in messages
        ],
        consent_timeline=[
            MessagingConsentEventRead(
                id=item.id,
                purpose=item.purpose,
                action=item.action,
                source=item.source,
                occurred_at=item.occurred_at,
                instruction_text=item.instruction_text,
                disclosure_hash=item.disclosure_hash,
            )
            for item in evidence
        ],
        reconciliation_cases=_reconciliation_cases(
            db,
            organization_id=organization_id,
            delivery_ids=delivery_ids,
            webhook_ids=webhook_ids,
        ),
    )


def mark_conversation_read(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> MessagingConversationDetail:
    conversation, _contact, _route = _get_conversation_row(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
    )
    conversation.unread_count = 0

    # ⚡ Bolt: Replace N+1 iteration with a bulk update for better performance
    db.execute(
        update(MessagingMessage)
        .where(
            MessagingMessage.organization_id == organization_id,
            MessagingMessage.conversation_id == conversation_id,
            MessagingMessage.is_unread.is_(True),
        )
        .values(is_unread=False)
    )

    conversation.updated_at = datetime.now(UTC)
    db.commit()
    return get_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
    )


def link_conversation(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
) -> MessagingConversationDetail:
    _conversation, contact, _route = _get_conversation_row(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
    )
    targets = {
        "surrogate": (Surrogate, "surrogate_id"),
        "intake_lead": (IntakeLead, "intake_lead_id"),
        "meta_lead": (MetaLead, "meta_lead_id"),
    }
    target = targets.get(entity_type)
    if target is None:
        raise ValueError("Unsupported messaging entity type")
    model, attribute = target
    exists = db.scalar(
        select(model.id).where(
            model.id == entity_id,
            model.organization_id == organization_id,
        )
    )
    if exists is None:
        raise MessagingInboxEntityNotFound("Link target was not found in this organization")
    current = getattr(contact, attribute)
    if current is not None and current != entity_id:
        raise MessagingInboxLinkConflict(
            f"Conversation is already linked to a different {entity_type.replace('_', ' ')}"
        )
    setattr(contact, attribute, entity_id)
    contact.updated_at = datetime.now(UTC)
    db.commit()
    return get_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
    )


def update_reconciliation_case(
    db: Session,
    *,
    organization_id: uuid.UUID,
    case_id: uuid.UUID,
    expected_version: int,
    action: str,
    resolution_code: str,
) -> MessagingReconciliationCaseRead:
    if action not in {"resolve", "dismiss"}:
        raise ValueError("Action must be resolve or dismiss")
    resolution_code = resolution_code.strip()
    if not resolution_code:
        raise ValueError("Resolution code is required")
    case = db.scalar(
        select(MessageReconciliationCase)
        .where(
            MessageReconciliationCase.organization_id == organization_id,
            MessageReconciliationCase.id == case_id,
        )
        .with_for_update()
    )
    if case is None:
        raise MessagingInboxNotFound("Reconciliation case not found")
    if case.version != expected_version:
        raise MessagingInboxVersionConflict("Reconciliation case changed; refresh and retry")
    case.status = "resolved" if action == "resolve" else "dismissed"
    case.resolution_code = resolution_code
    case.resolved_at = datetime.now(UTC)
    case.version += 1
    db.commit()
    return MessagingReconciliationCaseRead(
        id=case.id,
        case_type=case.case_type,
        status=case.status,
        reason_code=case.reason_code,
        detected_at=case.detected_at,
        resolved_at=case.resolved_at,
        resolution_code=case.resolution_code,
        version=case.version,
    )
