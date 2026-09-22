"""Campaign worker execution and failed-recipient retries."""

import os
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.enums import CampaignRecipientStatus, CampaignStatus, EmailStatus
from app.db.models import (
    Campaign,
    CampaignRecipient,
    CampaignRun,
    Donor,
    IntendedParent,
    MessagingContact,
    Surrogate,
)
from app.services import (
    campaign_access,
    campaign_audience,
    campaign_content,
    campaign_delivery_service,
    campaign_suppression_service,
)

CAMPAIGN_SEND_BATCH_SIZE = int(os.getenv("CAMPAIGN_SEND_BATCH_SIZE", "200"))


def _load_existing_recipients(
    db: Session,
    run_id: UUID,
    entity_type: str,
    entity_ids: list[UUID],
) -> dict[UUID, CampaignRecipient]:
    if not entity_ids:
        return {}
    recipients = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.run_id == run_id,
            CampaignRecipient.entity_type == entity_type,
            CampaignRecipient.entity_id.in_(entity_ids),
        )
        .all()
    )
    return {recipient.entity_id: recipient for recipient in recipients}


def _campaign_run_result(
    run: CampaignRun,
    *,
    retried_count: int | None = None,
) -> dict:
    result = {
        "sent_count": run.sent_count,
        "delivered_count": run.delivered_count,
        "failed_count": run.failed_count,
        "skipped_count": run.skipped_count,
        "total_count": run.total_count,
    }
    if retried_count is not None:
        result["retried_count"] = retried_count
    return result


def _load_messaging_contacts_for_batch(
    db: Session,
    *,
    org_id: UUID,
    recipient_type: str,
    recipients: list,
) -> dict[UUID, MessagingContact]:
    entity_ids = [entity.id for entity in recipients]
    phone_hashes = [entity.phone_hash for entity in recipients if entity.phone_hash]
    if recipient_type == "case":
        contacts = (
            db.query(MessagingContact)
            .filter(
                MessagingContact.organization_id == org_id,
                or_(
                    MessagingContact.surrogate_id.in_(entity_ids),
                    MessagingContact.phone_hash.in_(phone_hashes),
                ),
            )
            .all()
        )
        by_surrogate = {
            contact.surrogate_id: contact
            for contact in contacts
            if contact.surrogate_id is not None
        }
    else:
        contacts = (
            db.query(MessagingContact)
            .filter(
                MessagingContact.organization_id == org_id,
                MessagingContact.phone_hash.in_(phone_hashes),
            )
            .all()
        )
        by_surrogate = {}
    by_phone = {contact.phone_hash: contact for contact in contacts}
    resolved: dict[UUID, MessagingContact] = {}
    for entity in recipients:
        linked_contact = by_surrogate.get(entity.id)
        if linked_contact is not None and linked_contact.phone_hash == entity.phone_hash:
            resolved[entity.id] = linked_contact
            continue
        fallback_contact = by_phone.get(entity.phone_hash)
        if fallback_contact is not None:
            resolved[entity.id] = fallback_contact
    return resolved


def _execute_messaging_campaign_run(
    db: Session,
    *,
    org_id: UUID,
    campaign: Campaign,
    run: CampaignRun,
) -> dict:
    from app.services import email_service, messaging_delivery_service

    campaign_audience.ensure_supported_campaign_channel(campaign.channel, campaign.recipient_type)
    if run.status == "completed":
        return _campaign_run_result(run)
    if run.message_template_version_id != campaign.message_template_version_id:
        raise ValueError("Campaign message template version does not match queued run")
    template = campaign_content.load_published_message_template(
        db,
        org_id=org_id,
        template_version_id=run.message_template_version_id,
    )

    campaign.status = CampaignStatus.SENDING.value
    run.status = "running"
    run.started_at = datetime.now(UTC)
    db.commit()

    recipient_query = campaign_audience.build_recipient_query(
        db,
        org_id,
        campaign.recipient_type,
        campaign.filter_criteria or {},
        channel="messaging",
        campaign=campaign,
    )
    entity_model = campaign_audience.recipient_entity_model(campaign.recipient_type)
    run.total_count = recipient_query.order_by(None).count()
    recipient_query = recipient_query.order_by(entity_model.phone_hash, entity_model.id)
    db.commit()

    batch_size = max(1, CAMPAIGN_SEND_BATCH_SIZE)
    buffer: list = []
    seen_contacts: set[UUID] = set()

    def _process_batch(batch: list) -> None:
        contacts_by_entity = _load_messaging_contacts_for_batch(
            db,
            org_id=org_id,
            recipient_type=campaign.recipient_type,
            recipients=batch,
        )
        existing_by_entity = _load_existing_recipients(
            db,
            run.id,
            campaign.recipient_type,
            [entity.id for entity in batch],
        )
        for entity in batch:
            existing = existing_by_entity.get(entity.id)
            if not campaign_access.recipient_allowed(db, campaign, run, entity.id):
                if existing is None:
                    existing = CampaignRecipient(
                        run_id=run.id,
                        entity_type=campaign.recipient_type,
                        entity_id=entity.id,
                        recipient_name=entity.full_name or "",
                    )
                    db.add(existing)
                existing.status = CampaignRecipientStatus.SKIPPED.value
                existing.skip_reason = "permission_revoked"
                existing.error = None
                continue
            contact = contacts_by_entity.get(entity.id)
            name = entity.full_name or getattr(entity, "first_name", "")
            if contact is None:
                if existing is None:
                    db.add(
                        CampaignRecipient(
                            run_id=run.id,
                            entity_type=campaign.recipient_type,
                            entity_id=entity.id,
                            recipient_email=None,
                            recipient_name=name,
                            status=CampaignRecipientStatus.SKIPPED.value,
                            skip_reason="consent_unknown",
                        )
                    )
                elif existing.message_delivery_id is None:
                    existing.status = CampaignRecipientStatus.SKIPPED.value
                    existing.skip_reason = "consent_unknown"
                continue

            if contact.id in seen_contacts:
                if existing is None:
                    db.add(
                        CampaignRecipient(
                            run_id=run.id,
                            entity_type=campaign.recipient_type,
                            entity_id=entity.id,
                            recipient_email=None,
                            recipient_phone_last4=contact.phone_last4,
                            recipient_name=name,
                            status=CampaignRecipientStatus.SKIPPED.value,
                            skip_reason="duplicate_phone",
                        )
                    )
                continue
            seen_contacts.add(contact.id)

            campaign_recipient = existing
            if campaign_recipient is None:
                campaign_recipient = CampaignRecipient(
                    run_id=run.id,
                    entity_type=campaign.recipient_type,
                    entity_id=entity.id,
                    recipient_email=None,
                    recipient_phone_last4=contact.phone_last4,
                    recipient_name=name,
                    status=CampaignRecipientStatus.PENDING.value,
                )
                db.add(campaign_recipient)
                db.flush()
            elif (
                campaign_recipient.message_delivery_id is not None
                or campaign_recipient.status
                in {
                    CampaignRecipientStatus.SENT.value,
                    CampaignRecipientStatus.DELIVERED.value,
                    CampaignRecipientStatus.SKIPPED.value,
                }
            ):
                continue

            variables = campaign_content.build_recipient_template_variables(
                db,
                campaign.recipient_type,
                entity,
            )
            _subject, body = email_service.render_template("", template.body, variables)
            try:
                delivery = messaging_delivery_service.materialize_delivery(
                    db,
                    organization_id=org_id,
                    contact_id=contact.id,
                    purpose="promotional",
                    body=body,
                    idempotency_key=(
                        f"campaign-message/{campaign_recipient.id}/"
                        f"v{campaign_recipient.send_revision}"
                    ),
                    source_type="campaign_recipient",
                    source_id=campaign_recipient.id,
                    template_version_id=template.id,
                    media_asset_ids=[],
                    is_enrollment_confirmation=template.is_enrollment_confirmation,
                    run_at=campaign.scheduled_at,
                )
            except (
                messaging_delivery_service.MessagingConsentBlocked,
                messaging_delivery_service.MessagingEnrollmentRequired,
                messaging_delivery_service.MessagingRouteNotReady,
            ) as exc:
                campaign_recipient.status = CampaignRecipientStatus.SKIPPED.value
                campaign_recipient.error = None
                campaign_recipient.skip_reason = str(exc)[:100]
            except Exception as exc:
                campaign_recipient.status = CampaignRecipientStatus.FAILED.value
                campaign_recipient.error = type(exc).__name__[:100]
                campaign_recipient.skip_reason = None
            else:
                campaign_recipient.message_delivery_id = delivery.id
                campaign_recipient.status = CampaignRecipientStatus.PENDING.value
                campaign_recipient.error = None
                campaign_recipient.skip_reason = None
            db.commit()

    for entity in recipient_query.execution_options(stream_results=True).yield_per(batch_size):
        buffer.append(entity)
        if len(buffer) >= batch_size:
            _process_batch(buffer)
            buffer = []
    if buffer:
        _process_batch(buffer)

    if not campaign_delivery_service.recompute_campaign_run_aggregates(
        db,
        organization_id=org_id,
        run_id=run.id,
        commit=True,
    ):
        raise RuntimeError("Campaign aggregate target is missing")
    return _campaign_run_result(run)


def execute_campaign_run(
    db: Session,
    org_id: UUID,
    campaign_id: UUID,
    run_id: UUID,
    actor_user_id: UUID | None = None,
) -> dict:
    """
    Execute a campaign run - send emails to all recipients.

    This is called by the worker for async processing.
    Recipients are filtered, emails are sent individually, and status is tracked.

    Returns:
        dict with sent_count, failed_count, skipped_count
    """
    from app.services import email_service, permission_policy_service

    permission_policy_service.lock_configuration(db, org_id)
    locked = campaign_delivery_service.lock_campaign_run_and_campaign(
        db,
        organization_id=org_id,
        run_id=run_id,
    )
    if locked is None:
        raise Exception(f"Campaign run {run_id} not found")
    run, campaign = locked
    if campaign.id != campaign_id:
        raise Exception(f"Campaign run {run_id} not found")
    if campaign.status == CampaignStatus.CANCELLED.value:
        return _campaign_run_result(run)

    campaign_audience.ensure_supported_campaign_channel(campaign.channel, campaign.recipient_type)

    if campaign.channel == "messaging":
        return _execute_messaging_campaign_run(
            db,
            org_id=org_id,
            campaign=campaign,
            run=run,
        )

    template = campaign_content.load_campaign_run_template(
        db,
        org_id=org_id,
        campaign=campaign,
        run=run,
    )

    from app.services import org_service

    org = org_service.get_org_by_id(db, org_id)
    portal_base_url = org_service.get_org_portal_base_url(org)

    if run.status == "completed":
        return _campaign_run_result(run)

    # Mark campaign as sending
    campaign.status = CampaignStatus.SENDING.value
    run.status = "running"
    run.started_at = datetime.now(UTC)
    db.commit()

    recipient_query = campaign_audience.build_recipient_query(
        db, org_id, campaign.recipient_type, campaign.filter_criteria or {}, campaign=campaign
    )
    entity_model = campaign_audience.recipient_entity_model(campaign.recipient_type)
    email_col = entity_model.email
    id_col = entity_model.id

    run.total_count = recipient_query.order_by(None).count()
    recipient_query = recipient_query.order_by(func.lower(email_col), id_col)
    db.commit()

    seen_emails: dict[str, str | None] = {}
    suppressed_emails = campaign_suppression_service.load_suppressed_emails(
        db, org_id, ignore_opt_out=bool(getattr(campaign, "include_unsubscribed", False))
    )

    def _mark_skipped(existing_recipient, reason, email, name, entity_id):
        if not existing_recipient:
            existing_recipient = CampaignRecipient(
                run_id=run_id,
                entity_type=campaign.recipient_type,
                entity_id=entity_id,
                recipient_email=email,
                recipient_name=name,
                status=CampaignRecipientStatus.SKIPPED.value,
                skip_reason=reason,
            )
            db.add(existing_recipient)
            return
        if existing_recipient.status not in (
            CampaignRecipientStatus.SENT.value,
            CampaignRecipientStatus.SKIPPED.value,
        ):
            existing_recipient.status = CampaignRecipientStatus.SKIPPED.value
            existing_recipient.skip_reason = reason

    batch_size = max(1, CAMPAIGN_SEND_BATCH_SIZE)
    recipients_buffer = []
    recipient_iter = recipient_query.execution_options(stream_results=True).yield_per(batch_size)

    def _finalize_cancelled():
        run.status = "failed"
        run.error_message = "cancelled"
        campaign.status = CampaignStatus.CANCELLED.value
        if not campaign_delivery_service.recompute_campaign_run_aggregates(
            db,
            organization_id=org_id,
            run_id=run_id,
            commit=True,
        ):
            raise RuntimeError("Campaign aggregate target is missing")

        return _campaign_run_result(run)

    def _is_cancelled() -> bool:
        db.refresh(campaign)
        return campaign.status == CampaignStatus.CANCELLED.value

    if _is_cancelled():
        return _finalize_cancelled()

    def _process_batch(batch):
        entity_ids = [recipient.id for recipient in batch]
        existing_by_entity = _load_existing_recipients(
            db,
            run_id,
            campaign.recipient_type,
            entity_ids,
        )

        for recipient in batch:
            email = recipient.email
            name = recipient.full_name or getattr(recipient, "first_name", "")
            entity_id = recipient.id

            if not email:
                continue

            email_norm = email.strip().lower()
            if not email_norm:
                continue

            existing = existing_by_entity.get(entity_id)

            if not campaign_access.recipient_allowed(db, campaign, run, entity_id):
                _mark_skipped(existing, "permission_revoked", email, name, entity_id)
                continue

            if email_norm in seen_emails:
                skip_reason = seen_emails[email_norm] or "duplicate_email"
                _mark_skipped(existing, skip_reason, email, name, entity_id)
                continue

            # Check suppression
            if email_norm in suppressed_emails:
                seen_emails[email_norm] = "suppressed"
                _mark_skipped(existing, "suppressed", email, name, entity_id)
                continue

            seen_emails[email_norm] = None

            # Build email from template with shared variable builder
            variables = campaign_content.build_recipient_template_variables(
                db,
                campaign.recipient_type,
                recipient,
            )

            from app.services import email_composition_service

            cleaned_body_template = email_composition_service.strip_legacy_unsubscribe_placeholders(
                template.body
            )
            subject, body = email_service.render_template(
                template.subject, cleaned_body_template, variables
            )

            body = email_composition_service.compose_template_email_html(
                db=db,
                org_id=org_id,
                recipient_email=email,
                rendered_body_html=body,
                scope="org",
                portal_base_url=portal_base_url,
            )
            donor_launch_snapshot = None
            if campaign.recipient_type in campaign_audience.DONOR_RECIPIENT_TYPES:
                donor_launch_snapshot = campaign_content.build_donor_launch_snapshot(
                    recipient_email=email,
                    recipient_name=name,
                    subject=subject,
                    body=body,
                )

            # Create recipient record
            cr = existing
            if not cr:
                from app.services import tracking_service

                cr = CampaignRecipient(
                    run_id=run_id,
                    entity_type=campaign.recipient_type,
                    entity_id=entity_id,
                    recipient_email=email,
                    recipient_name=name,
                    donor_launch_snapshot=donor_launch_snapshot,
                    status=CampaignRecipientStatus.PENDING.value,
                    tracking_token=tracking_service.generate_tracking_token(),
                )
                db.add(cr)
                db.flush()
            elif cr.status in (
                CampaignRecipientStatus.PENDING.value,
                CampaignRecipientStatus.SENT.value,
                CampaignRecipientStatus.DELIVERED.value,
                CampaignRecipientStatus.FAILED.value,
                CampaignRecipientStatus.SKIPPED.value,
            ):
                continue

            # Ensure tracking token exists (for retried sends)
            if not cr.tracking_token:
                from app.services import tracking_service

                cr.tracking_token = tracking_service.generate_tracking_token()

            if donor_launch_snapshot is not None and cr.donor_launch_snapshot is None:
                cr.donor_launch_snapshot = donor_launch_snapshot

            # Inject tracking pixel and wrap links
            # Skip internal tracking for Resend (uses webhooks instead)
            if run.email_provider == "resend":
                tracked_body = body  # No internal tracking for Resend
            else:
                from app.services import tracking_service

                tracked_body = tracking_service.prepare_email_for_tracking(body, cr.tracking_token)

            try:
                # Queue email (actual send happens in background job)
                email_log, _job = email_service.send_email(
                    db=db,
                    org_id=org_id,
                    template_id=template.template_id,
                    recipient_email=email,
                    subject=subject,
                    body=tracked_body,
                    surrogate_id=entity_id if campaign.recipient_type == "case" else None,
                    sender_user_id=actor_user_id,
                    commit=False,
                    ignore_opt_out=bool(getattr(campaign, "include_unsubscribed", False)),
                    idempotency_key=(f"campaign-recipient/{cr.id}/v{cr.send_revision}"),
                    source_type="campaign_recipient",
                    source_id=cr.id,
                    purpose="marketing",
                    from_email=template.from_email,
                )
                cr.email_log_id = email_log.id
                if email_log.status == EmailStatus.SKIPPED.value:
                    cr.status = CampaignRecipientStatus.SKIPPED.value
                    cr.error = None
                    cr.skip_reason = (email_log.error or "suppressed")[:100]
                    cr.external_message_id = None
                else:
                    cr.status = CampaignRecipientStatus.PENDING.value
            except Exception as e:
                cr.status = CampaignRecipientStatus.FAILED.value
                cr.error = str(e)[:500]

        db.commit()

    for recipient in recipient_iter:
        recipients_buffer.append(recipient)
        if len(recipients_buffer) >= batch_size:
            if _is_cancelled():
                return _finalize_cancelled()
            _process_batch(recipients_buffer)
            recipients_buffer = []
            if _is_cancelled():
                return _finalize_cancelled()

    if recipients_buffer:
        if _is_cancelled():
            return _finalize_cancelled()
        _process_batch(recipients_buffer)

    if not campaign_delivery_service.recompute_campaign_run_aggregates(
        db,
        organization_id=org_id,
        run_id=run_id,
        commit=True,
    ):
        raise RuntimeError("Campaign aggregate target is missing")

    return _campaign_run_result(run)


def retry_failed_campaign_run(
    db: Session,
    org_id: UUID,
    campaign_id: UUID,
    run_id: UUID,
    actor_user_id: UUID | None = None,
) -> dict:
    """Retry failed recipients for an existing campaign run."""
    from app.services import email_service, permission_policy_service

    permission_policy_service.lock_configuration(db, org_id)
    locked = campaign_delivery_service.lock_campaign_run_and_campaign(
        db,
        organization_id=org_id,
        run_id=run_id,
    )
    if locked is None:
        raise Exception(f"Campaign run {run_id} not found")
    run, campaign = locked
    if campaign.id != campaign_id:
        raise Exception(f"Campaign run {run_id} not found")
    if campaign.status == CampaignStatus.CANCELLED.value:
        return _campaign_run_result(run, retried_count=0)

    template = campaign_content.load_campaign_run_template(
        db,
        org_id=org_id,
        campaign=campaign,
        run=run,
    )

    from app.services import org_service

    org = org_service.get_org_by_id(db, org_id)
    portal_base_url = org_service.get_org_portal_base_url(org)

    failed_recipient_query = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.run_id == run_id,
            CampaignRecipient.entity_type == campaign.recipient_type,
            CampaignRecipient.status == CampaignRecipientStatus.FAILED.value,
        )
        .order_by(func.lower(CampaignRecipient.recipient_email), CampaignRecipient.id)
    )
    failed_recipients = failed_recipient_query.all()
    if not failed_recipients:
        return _campaign_run_result(run, retried_count=0)

    campaign.status = CampaignStatus.SENDING.value
    run.status = "running"
    db.commit()
    failed_recipients = failed_recipient_query.all()

    suppressed_emails = campaign_suppression_service.load_suppressed_emails(
        db, org_id, ignore_opt_out=bool(getattr(campaign, "include_unsubscribed", False))
    )
    seen_emails: dict[str, str | None] = {}
    retried_count = 0
    skipped_count = 0

    entity_ids = list(
        dict.fromkeys(
            recipient.entity_id
            for recipient in failed_recipients
            if recipient.entity_id is not None
        )
    )
    entities_by_id: dict[UUID, Surrogate | IntendedParent | Donor] = {}
    entity_batch_size = max(1, CAMPAIGN_SEND_BATCH_SIZE)
    for offset in range(0, len(entity_ids), entity_batch_size):
        entity_id_batch = entity_ids[offset : offset + entity_batch_size]
        if campaign.recipient_type == "case":
            entities = db.scalars(
                select(Surrogate).where(
                    Surrogate.organization_id == org_id,
                    Surrogate.id.in_(entity_id_batch),
                    Surrogate.is_archived.is_(False),
                )
            ).all()
        elif campaign.recipient_type == "intended_parent":
            entities = db.scalars(
                select(IntendedParent).where(
                    IntendedParent.organization_id == org_id,
                    IntendedParent.id.in_(entity_id_batch),
                    IntendedParent.is_archived.is_(False),
                )
            ).all()
        elif campaign.recipient_type in campaign_audience.DONOR_RECIPIENT_TYPES:
            entities = db.scalars(
                select(Donor).where(
                    Donor.organization_id == org_id,
                    Donor.id.in_(entity_id_batch),
                    Donor.donor_type
                    == campaign_audience.DONOR_RECIPIENT_TYPES[campaign.recipient_type],
                    Donor.is_archived.is_(False),
                )
            ).all()
        else:
            raise ValueError(f"Unknown recipient type: {campaign.recipient_type}")
        entities_by_id.update((entity.id, entity) for entity in entities)

    for recipient in failed_recipients:
        if not campaign_access.recipient_allowed(db, campaign, run, recipient.entity_id):
            recipient.status = CampaignRecipientStatus.SKIPPED.value
            recipient.skip_reason = "permission_revoked"
            recipient.error = None
            skipped_count += 1
            continue
        entity = entities_by_id.get(recipient.entity_id)

        if not entity:
            recipient.status = CampaignRecipientStatus.SKIPPED.value
            recipient.skip_reason = "missing_recipient"
            recipient.error = None
            recipient.external_message_id = None
            skipped_count += 1
            continue

        donor_launch_snapshot = None
        if campaign.recipient_type in campaign_audience.DONOR_RECIPIENT_TYPES:
            try:
                donor_launch_snapshot = campaign_content.parse_donor_launch_snapshot(
                    recipient.donor_launch_snapshot
                )
            except ValueError:
                recipient.error = "invalid_donor_launch_snapshot"
                recipient.skip_reason = None
                recipient.external_message_id = None
                continue

        email = (
            donor_launch_snapshot["recipient_email"]
            if donor_launch_snapshot is not None
            else getattr(entity, "email", None)
        )
        email_norm = email.strip().lower() if email else ""
        if not email_norm:
            recipient.status = CampaignRecipientStatus.SKIPPED.value
            recipient.skip_reason = "missing_recipient"
            recipient.error = None
            recipient.external_message_id = None
            skipped_count += 1
            continue

        if email_norm in seen_emails:
            recipient.status = CampaignRecipientStatus.SKIPPED.value
            recipient.skip_reason = seen_emails[email_norm] or "duplicate_email"
            recipient.error = None
            recipient.external_message_id = None
            skipped_count += 1
            continue

        if email_norm in suppressed_emails:
            seen_emails[email_norm] = "suppressed"
            recipient.status = CampaignRecipientStatus.SKIPPED.value
            recipient.skip_reason = "suppressed"
            recipient.error = None
            recipient.external_message_id = None
            skipped_count += 1
            continue

        seen_emails[email_norm] = None

        if donor_launch_snapshot is not None:
            recipient.recipient_email = donor_launch_snapshot["recipient_email"]
            recipient.recipient_name = donor_launch_snapshot["recipient_name"]
            subject = donor_launch_snapshot["subject"]
            body = donor_launch_snapshot["body"]
        else:
            recipient.recipient_email = email
            recipient.recipient_name = getattr(entity, "full_name", None) or ""

            variables = campaign_content.build_recipient_template_variables(
                db,
                campaign.recipient_type,
                entity,
            )

            from app.services import email_composition_service

            cleaned_body_template = email_composition_service.strip_legacy_unsubscribe_placeholders(
                template.body
            )
            subject, body = email_service.render_template(
                template.subject, cleaned_body_template, variables
            )

            body = email_composition_service.compose_template_email_html(
                db=db,
                org_id=org_id,
                recipient_email=email,
                rendered_body_html=body,
                scope="org",
                portal_base_url=portal_base_url,
            )
            if campaign.recipient_type in campaign_audience.DONOR_RECIPIENT_TYPES:
                recipient.donor_launch_snapshot = campaign_content.build_donor_launch_snapshot(
                    recipient_email=email,
                    recipient_name=recipient.recipient_name,
                    subject=subject,
                    body=body,
                )

        if run.email_provider == "resend":
            tracked_body = body
        else:
            from app.services import tracking_service

            if not recipient.tracking_token:
                recipient.tracking_token = tracking_service.generate_tracking_token()
            tracked_body = tracking_service.prepare_email_for_tracking(
                body, recipient.tracking_token
            )

        recipient.send_revision += 1
        recipient.external_message_id = None
        try:
            email_log, _job = email_service.send_email(
                db=db,
                org_id=org_id,
                template_id=template.template_id,
                recipient_email=email,
                subject=subject,
                body=tracked_body,
                surrogate_id=entity.id if campaign.recipient_type == "case" else None,
                sender_user_id=actor_user_id,
                commit=False,
                ignore_opt_out=bool(getattr(campaign, "include_unsubscribed", False)),
                idempotency_key=(f"campaign-recipient/{recipient.id}/v{recipient.send_revision}"),
                source_type="campaign_recipient",
                source_id=recipient.id,
                purpose="marketing",
                from_email=template.from_email,
            )
        except Exception as exc:
            recipient.status = CampaignRecipientStatus.FAILED.value
            recipient.error = str(exc)[:500]
            recipient.skip_reason = None
            recipient.external_message_id = None
            continue

        recipient.email_log_id = email_log.id
        if email_log.status == EmailStatus.SKIPPED.value:
            recipient.status = CampaignRecipientStatus.SKIPPED.value
            recipient.skip_reason = "suppressed"
            recipient.error = None
            recipient.external_message_id = None
            skipped_count += 1
            continue

        recipient.status = CampaignRecipientStatus.PENDING.value
        recipient.error = None
        recipient.skip_reason = None
        retried_count += 1

    if not campaign_delivery_service.recompute_campaign_run_aggregates(
        db,
        organization_id=org_id,
        run_id=run_id,
        commit=True,
    ):
        raise RuntimeError("Campaign aggregate target is missing")

    return _campaign_run_result(run, retried_count=retried_count)
