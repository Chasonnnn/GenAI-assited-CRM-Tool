"""Campaign management and execution authority boundaries."""

from app.db.enums import AuditEventType
from app.db.models import Campaign, CampaignRun
from app.services import audit_service


def get_policy_execution_snapshot(db, org_id) -> list[dict]:
    rows = (
        db.query(Campaign)
        .filter(
            Campaign.organization_id == org_id,
            Campaign.status.in_(("scheduled", "sending")),
        )
        .order_by(Campaign.id)
        .all()
    )
    return [
        {
            "item_type": "campaign",
            "id": str(row.id),
            "name": row.name,
            "status": row.status,
            "scope": row.scope,
            "updated_at": row.updated_at.isoformat(),
            "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
            "runs": [
                {"id": str(run.id), "status": run.status}
                for run in db.query(CampaignRun)
                .filter(
                    CampaignRun.organization_id == org_id,
                    CampaignRun.campaign_id == row.id,
                    CampaignRun.status == "running",
                )
                .order_by(CampaignRun.id)
                .all()
            ],
        }
        for row in rows
    ]


def apply_policy_execution_resolutions(db, org_id, actor_user_id, resolutions) -> None:
    from app.services import campaign_service

    for resolution in resolutions:
        item = resolution.model_dump() if hasattr(resolution, "model_dump") else resolution
        if item.get("item_type") != "campaign":
            continue
        if item.get("action") != "pause":
            raise ValueError("Unknown campaign migration resolution")
        if not campaign_service.cancel_campaign(db, org_id, item["id"]):
            raise ValueError("Campaign changed; refresh permission preview")
        audit_service.log_event(
            db,
            org_id=org_id,
            event_type=AuditEventType.SETTINGS_ORG_UPDATED,
            actor_user_id=actor_user_id,
            target_type="campaign",
            target_id=item["id"],
            details={"operation": "pause_for_permission_activation"},
        )


def enabled(db, org_id):
    from app.services import permission_policy_service

    return permission_policy_service.is_enabled(db, org_id)


def effective_permissions(db, session):
    from app.services import permission_service

    return permission_service.get_effective_permissions(
        db, session.org_id, session.user_id, session.role.value
    )


def _has(db, session, key, permissions=None):
    return key in (effective_permissions(db, session) if permissions is None else permissions)


def _administrator(session):
    from app.db.enums import Role

    return session.role in {Role.ADMIN, Role.DEVELOPER}


def _module(recipient_type):
    return {
        "case": "surrogates",
        "intended_parent": "intended_parents",
        "egg_donor": "donors",
        "sperm_donor": "donors",
    }[recipient_type]


def visible_filter(db, session):
    from sqlalchemy import and_, false, or_, true

    if not enabled(db, session.org_id):
        return true()
    from app.services.workflow_execution_authority import active_session

    actor = active_session(db, session.org_id, session.user_id)
    if actor is None:
        return false()
    permissions = effective_permissions(db, actor)
    if "view_campaigns" not in permissions:
        return false()
    recipient_types = [
        kind
        for kind in ("case", "intended_parent", "egg_donor", "sperm_donor")
        if "view_" + _module(kind) in permissions
    ]
    return and_(
        Campaign.organization_id == actor.org_id,
        Campaign.recipient_type.in_(recipient_types),
        true()
        if _administrator(actor)
        else or_(Campaign.scope == "org", Campaign.owner_user_id == actor.user_id),
    )


def viewer_entity_filter(db, session, org_id, recipient_type):
    """Limit a read to the viewer without changing the execution audience."""
    from sqlalchemy import false

    from app.services import record_scope_service
    from app.services.workflow_execution_authority import active_session

    if session is None or session.org_id != org_id:
        return false()
    actor = active_session(db, org_id, session.user_id)
    if actor is None or not _has(db, actor, "view_" + _module(recipient_type)):
        return false()
    kind = {
        "case": "surrogate",
        "intended_parent": "intended_parent",
        "egg_donor": "donor",
        "sperm_donor": "donor",
    }[recipient_type]
    return record_scope_service.build_visibility_filter(db, actor, kind)


def viewer_recipient_filter(db, session, org_id):
    """SQL predicate shared by recipient rows and aggregate counts."""
    from sqlalchemy import and_, false, or_, select

    from app.db.models import CampaignRecipient, Donor, IntendedParent, Surrogate
    from app.services import record_scope_service
    from app.services.workflow_execution_authority import active_session

    if session is None or session.org_id != org_id:
        return false()
    actor = active_session(db, org_id, session.user_id)
    if actor is None:
        return false()
    permissions = effective_permissions(db, actor)
    if "view_campaigns" not in permissions:
        return false()
    branches = []
    for kind, model, recipient_types in (
        ("surrogate", Surrogate, ("case",)),
        ("intended_parent", IntendedParent, ("intended_parent",)),
        ("donor", Donor, ("egg_donor", "sperm_donor")),
    ):
        if "view_" + _module(recipient_types[0]) not in permissions:
            continue
        visibility = record_scope_service.build_visibility_filter(db, actor, kind)
        for recipient_type in recipient_types:
            ids = select(model.id).where(visibility)
            if kind == "donor":
                ids = ids.where(
                    Donor.donor_type == ("egg" if recipient_type == "egg_donor" else "sperm")
                )
            branches.append(
                and_(
                    CampaignRecipient.entity_type == recipient_type,
                    CampaignRecipient.entity_id.in_(ids),
                )
            )
    return or_(*branches) if branches else false()


def can_view(db, session, campaign, *, permissions=None):
    permissions = effective_permissions(db, session) if permissions is None else permissions
    if campaign.organization_id != session.org_id:
        return False
    if not enabled(db, session.org_id):
        return _has(db, session, "view_email_templates", permissions)
    return (
        _has(db, session, "view_campaigns", permissions)
        and _has(db, session, "view_" + _module(campaign.recipient_type), permissions)
        and (
            campaign.scope == "org"
            or campaign.owner_user_id == session.user_id
            or _administrator(session)
        )
    )


def can_manage(db, session, campaign, action="edit", *, permissions=None):
    permissions = effective_permissions(db, session) if permissions is None else permissions
    if not can_view(db, session, campaign, permissions=permissions):
        return False
    if not enabled(db, session.org_id):
        return _has(db, session, "manage_email_templates", permissions)
    if not _has(
        db, session, "send_campaigns" if action == "send" else "edit_campaigns", permissions
    ):
        return False
    if campaign.scope == "org" and not _has(db, session, "manage_org_campaigns", permissions):
        return False
    return action != "send" or _has(
        db, session, "send_sms" if campaign.channel == "messaging" else "send_email", permissions
    )


def can_create(db, session, scope, *, permissions=None):
    permissions = effective_permissions(db, session) if permissions is None else permissions
    if not enabled(db, session.org_id):
        return scope == "org" and _has(db, session, "manage_email_templates", permissions)
    return _has(db, session, "edit_campaigns", permissions) and (
        scope == "personal" or _has(db, session, "manage_org_campaigns", permissions)
    )


def capabilities(db, session, campaign, *, permissions=None):
    if session is None:
        return {"can_edit": False, "can_send": False, "can_publish": False}
    permissions = effective_permissions(db, session) if permissions is None else permissions
    can_edit = can_manage(db, session, campaign, permissions=permissions)
    return {
        "can_edit": can_edit,
        "can_send": can_manage(db, session, campaign, "send", permissions=permissions),
        "can_publish": enabled(db, session.org_id)
        and campaign.scope == "personal"
        and can_edit
        and can_create(db, session, "org", permissions=permissions),
    }


def configuration_digest(campaign):
    import hashlib
    import json

    values = {
        key: getattr(campaign, key)
        for key in (
            "organization_id",
            "scope",
            "owner_user_id",
            "channel",
            "recipient_type",
            "filter_criteria",
            "email_template_id",
            "message_template_version_id",
            "include_unsubscribed",
        )
    }
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def authorize_send(db, campaign, actor_user_id):
    from datetime import UTC, datetime

    from app.services.workflow_execution_authority import active_session

    if not enabled(db, campaign.organization_id):
        return None
    actor = active_session(db, campaign.organization_id, actor_user_id)
    if actor is None or not can_manage(db, actor, campaign, "send"):
        raise ValueError("Missing permission to send this campaign")
    grant = {
        "version": 2,
        "organization_id": str(campaign.organization_id),
        "scope": campaign.scope,
        "owner_user_id": str(campaign.owner_user_id) if campaign.owner_user_id else None,
        "configuration_digest": configuration_digest(campaign),
        "authorized_by_user_id": str(actor_user_id),
        "authorized_at": datetime.now(UTC).isoformat(),
        "permissions": [
            "view_campaigns",
            "send_campaigns",
            "view_" + _module(campaign.recipient_type),
            "send_sms" if campaign.channel == "messaging" else "send_email",
        ],
    }
    campaign.execution_authority = grant if campaign.scope == "org" else None
    return grant


def run_authorized(db, campaign, run):
    if not enabled(db, campaign.organization_id):
        return True
    if run.organization_id != campaign.organization_id or run.campaign_id != campaign.id:
        return False
    grant = run.authority_snapshot
    if (
        not grant
        or grant.get("organization_id") != str(campaign.organization_id)
        or grant.get("scope") != campaign.scope
        or grant.get("configuration_digest") != configuration_digest(campaign)
    ):
        return False
    keys = {
        "view_campaigns",
        "send_campaigns",
        "view_" + _module(campaign.recipient_type),
        "send_sms" if campaign.channel == "messaging" else "send_email",
    }
    if campaign.scope == "org":
        return keys.issubset(set(grant.get("permissions", [])))
    from app.services.workflow_execution_authority import active_session

    owner = active_session(db, campaign.organization_id, campaign.owner_user_id)
    return (
        owner is not None
        and grant.get("owner_user_id") == str(owner.user_id)
        and keys.issubset(effective_permissions(db, owner))
    )


def apply_audience(
    db, query, org_id, recipient_type, *, campaign=None, scope="org", owner_user_id=None
):
    if not enabled(db, org_id):
        return query
    if campaign is not None:
        scope, owner_user_id = campaign.scope, campaign.owner_user_id
    if scope != "personal":
        return query
    from sqlalchemy import false

    from app.services import record_scope_service
    from app.services.workflow_execution_authority import active_session

    owner = active_session(db, org_id, owner_user_id)
    if owner is None or not _has(db, owner, "view_" + _module(recipient_type)):
        return query.filter(false())
    kind = {
        "case": "surrogate",
        "intended_parent": "intended_parent",
        "egg_donor": "donor",
        "sperm_donor": "donor",
    }[recipient_type]
    return query.filter(
        record_scope_service.build_visibility_filter(db, owner, kind, personal_only=True)
    )


def recipient_allowed(db, campaign, run, entity_id):
    if not enabled(db, campaign.organization_id):
        return True
    if not run_authorized(db, campaign, run):
        return False
    from app.services import campaign_service

    model = campaign_service._recipient_entity_model(campaign.recipient_type)
    return (
        campaign_service._build_recipient_query(
            db,
            campaign.organization_id,
            campaign.recipient_type,
            campaign.filter_criteria or {},
            channel=campaign.channel,
            campaign=campaign,
        )
        .filter(model.id == entity_id)
        .first()
        is not None
    )


def audit(db, campaign, actor_user_id, operation):
    if not enabled(db, campaign.organization_id):
        return
    audit_service.log_event(
        db,
        campaign.organization_id,
        AuditEventType.SETTINGS_ORG_UPDATED,
        actor_user_id=actor_user_id,
        target_type="campaign",
        target_id=campaign.id,
        details={
            "operation": operation,
            "scope": campaign.scope,
            "administrative_personal_access": campaign.scope == "personal"
            and campaign.owner_user_id != actor_user_id,
        },
    )


def validate_template_scope(db, campaign):
    if not enabled(db, campaign.organization_id) or campaign.channel != "email":
        return
    from app.db.models import EmailTemplate

    template = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.id == campaign.email_template_id,
            EmailTemplate.organization_id == campaign.organization_id,
        )
        .first()
    )
    if template is None or (
        template.scope == "personal"
        and (campaign.scope != "personal" or template.owner_user_id != campaign.owner_user_id)
    ):
        raise ValueError("Campaign template is outside its ownership scope")


def publish_campaign(db, campaign, actor_user_id):
    from copy import deepcopy

    from app.schemas.campaign import CampaignCreate
    from app.services import campaign_service, email_template_publication, permission_policy_service
    from app.services.workflow_execution_authority import active_session

    permission_policy_service.lock_configuration(db, campaign.organization_id)
    actor = active_session(db, campaign.organization_id, actor_user_id)
    if (
        not enabled(db, campaign.organization_id)
        or actor is None
        or campaign.scope != "personal"
        or not can_manage(db, actor, campaign)
        or not can_create(db, actor, "org")
    ):
        raise ValueError("Cannot publish this campaign")
    with db.begin_nested():
        template_id = campaign.email_template_id
        if campaign.channel == "email":
            validate_template_scope(db, campaign)
            template_id = email_template_publication.publish_template_to_org(
                db,
                org_id=campaign.organization_id,
                template_id=template_id,
                actor_user_id=actor_user_id,
            ).id
        base_name = campaign.name[:170] + " (Published)"
        name, counter = base_name, 1
        while (
            db.query(Campaign.id)
            .filter(
                Campaign.organization_id == campaign.organization_id,
                Campaign.scope == "org",
                Campaign.name == name,
            )
            .first()
        ):
            counter += 1
            name = f"{base_name} {counter}"
        published = campaign_service.create_campaign(
            db,
            campaign.organization_id,
            actor_user_id,
            CampaignCreate(
                name=name,
                description=campaign.description,
                scope="org",
                channel=campaign.channel,
                email_template_id=template_id,
                message_template_version_id=campaign.message_template_version_id,
                recipient_type=campaign.recipient_type,
                filter_criteria=deepcopy(campaign.filter_criteria),
                include_unsubscribed=campaign.include_unsubscribed,
            ),
        )
        proposer_id = campaign.proposed_by_user_id or campaign.owner_user_id
        from app.db.models import User

        proposer = db.get(User, proposer_id) if proposer_id else None
        published.proposed_by_user_id = proposer_id
        published.proposed_by_name = campaign.proposed_by_name or (
            proposer.display_name if proposer else None
        )
        audit(db, published, actor_user_id, "publish")
        audit(db, campaign, actor_user_id, "publish_source")
        db.flush()
    return published
