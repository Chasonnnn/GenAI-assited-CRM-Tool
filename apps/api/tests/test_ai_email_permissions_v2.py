"""Queued AI email delivery rechecks current v2 authority before provider I/O."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models import (
    AIActionApproval,
    EmailLog,
    EntityNote,
    Job,
    Membership,
    Organization,
    OrganizationPermissionPolicy,
    RolePermission,
    RoleRecordScope,
    Surrogate,
    User,
    UserPermissionOverride,
)
from app.db.session import SessionLocal
from app.services import ai_email_service, gmail_service, permission_policy_service
from tests.test_ai_action_transactions import committed_approval as committed_approval
from tests.test_ai_action_transactions import queued_email as queued_email

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.parametrize("committed_approval", ["send_email"], indirect=True),
]


@pytest.fixture
def queued_email_v2(db_engine, queued_email):
    seeded = queued_email
    with SessionLocal(bind=db_engine) as db:
        db.add(OrganizationPermissionPolicy(organization_id=seeded.session.org_id, version=2))
        membership = (
            db.query(Membership)
            .filter_by(organization_id=seeded.session.org_id, user_id=seeded.session.user_id)
            .one()
        )
        membership.role = "intake_specialist"
        db.add(
            RoleRecordScope(
                organization_id=seeded.session.org_id,
                role="intake_specialist",
                module="surrogates",
                assignment="assigned",
                phase="all",
            )
        )
        db.commit()
    return seeded


def _deny_role_permission(db, seeded, permission):
    db.add(
        RolePermission(
            organization_id=seeded.session.org_id,
            role="intake_specialist",
            permission=permission,
            is_granted=False,
        )
    )


@pytest.mark.parametrize(
    "change",
    [
        "send_revoked",
        "ai_disabled",
        "view_revoked",
        "scope_lost",
        "inactive_user",
        "inactive_member",
    ],
)
async def test_v2_email_delivery_rechecks_current_authority(
    db_engine, queued_email_v2, monkeypatch, change
):
    seeded = queued_email_v2
    calls = []

    async def send(**kwargs):
        calls.append(kwargs)
        return {"success": True, "message_id": "synthetic-receipt"}

    monkeypatch.setattr(gmail_service, "send_email", send)
    with SessionLocal(bind=db_engine) as db:
        if change in {"send_revoked", "view_revoked"}:
            _deny_role_permission(
                db, seeded, "send_email" if change == "send_revoked" else "view_surrogates"
            )
        elif change == "ai_disabled":
            db.get(Organization, seeded.session.org_id).ai_enabled = False
        elif change == "scope_lost":
            db.get(Surrogate, seeded.surrogate_id).owner_id = uuid4()
        elif change == "inactive_user":
            db.get(User, seeded.session.user_id).is_active = False
        else:
            db.query(Membership).filter_by(
                organization_id=seeded.session.org_id, user_id=seeded.session.user_id
            ).one().is_active = False
        db.commit()
        await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        assert calls == []
        assert db.get(AIActionApproval, seeded.approval_id).status == "failed"
        email = db.query(EmailLog).filter_by(job_id=seeded.job_id).one()
        assert email.status == "failed"
        assert db.query(EntityNote).filter_by(entity_id=seeded.surrogate_id).count() == 0


async def test_v2_email_delivery_does_not_require_record_edit_permission(
    db_engine, queued_email_v2, monkeypatch
):
    seeded = queued_email_v2
    calls = []

    async def send(**kwargs):
        calls.append(kwargs)
        return {"success": True, "message_id": "synthetic-receipt"}

    monkeypatch.setattr(gmail_service, "send_email", send)
    with SessionLocal(bind=db_engine) as db:
        _deny_role_permission(db, seeded, "edit_surrogates")
        db.commit()
        await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        assert len(calls) == 1
        assert db.get(AIActionApproval, seeded.approval_id).status == "executed"
        assert db.query(EmailLog).filter_by(job_id=seeded.job_id).one().status == "sent"
        assert db.query(EntityNote).filter_by(entity_id=seeded.surrogate_id).count() == 1


async def test_v2_email_delivery_rejects_foreign_job_binding(
    db_engine, queued_email_v2, monkeypatch
):
    seeded = queued_email_v2

    async def no_send(**kwargs):
        pytest.fail("Foreign organization job must not reach the provider")

    monkeypatch.setattr(gmail_service, "send_email", no_send)
    with SessionLocal(bind=db_engine) as db:
        job = db.get(Job, seeded.job_id)
        foreign_job = SimpleNamespace(id=job.id, organization_id=uuid4(), payload=job.payload)
        with pytest.raises(
            ValueError, match="Organization not found|not found in job organization"
        ):
            await ai_email_service.process_email(db, foreign_job)
        assert db.get(AIActionApproval, seeded.approval_id).status == "approved"
        assert db.query(EmailLog).filter_by(job_id=seeded.job_id).one().status == "pending"


async def test_activation_before_delivery_lock_uses_current_policy(
    db_engine, queued_email_v2, monkeypatch
):
    seeded = queued_email_v2
    calls = []
    lock = permission_policy_service.lock_configuration

    async def send(**kwargs):
        calls.append(kwargs)
        return {"success": True, "message_id": "synthetic-receipt"}

    def activate_before_lock(db, org_id):
        with SessionLocal(bind=db_engine) as activation:
            activation.get(OrganizationPermissionPolicy, org_id).version = 2
            activation.commit()
        lock(db, org_id)

    monkeypatch.setattr(gmail_service, "send_email", send)
    monkeypatch.setattr(permission_policy_service, "lock_configuration", activate_before_lock)
    with SessionLocal(bind=db_engine) as db:
        db.get(OrganizationPermissionPolicy, seeded.session.org_id).version = 1
        db.add(
            UserPermissionOverride(
                organization_id=seeded.session.org_id,
                user_id=seeded.session.user_id,
                permission="approve_ai_actions",
                override_type="grant",
            )
        )
        _deny_role_permission(db, seeded, "send_email")
        db.commit()
        await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        assert calls == []
        assert db.get(AIActionApproval, seeded.approval_id).status == "failed"


async def test_v2_uncertain_delivery_is_not_resent_after_authority_changes(
    db_engine, queued_email_v2, monkeypatch
):
    seeded = queued_email_v2
    calls = []

    async def send(**kwargs):
        calls.append(kwargs)
        raise TimeoutError("Synthetic provider uncertainty")

    monkeypatch.setattr(gmail_service, "send_email", send)
    with SessionLocal(bind=db_engine) as db:
        await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        _deny_role_permission(db, seeded, "send_email")
        db.get(Organization, seeded.session.org_id).ai_enabled = False
        db.commit()
        await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        assert len(calls) == 1
        assert db.get(AIActionApproval, seeded.approval_id).status == "delivery_unknown"
        assert db.query(EmailLog).filter_by(job_id=seeded.job_id).one().status == "unknown"
        assert db.query(EntityNote).filter_by(entity_id=seeded.surrogate_id).count() == 0


@pytest.mark.parametrize("denied_permission", ["send_email", "edit_surrogates"])
async def test_v1_email_delivery_preserves_legacy_permission_admission(
    db_engine, queued_email_v2, monkeypatch, denied_permission
):
    seeded = queued_email_v2
    calls = []

    async def send(**kwargs):
        calls.append(kwargs)
        return {"success": True, "message_id": "synthetic-receipt"}

    monkeypatch.setattr(gmail_service, "send_email", send)
    with SessionLocal(bind=db_engine) as db:
        db.get(OrganizationPermissionPolicy, seeded.session.org_id).version = 1
        db.add(
            UserPermissionOverride(
                organization_id=seeded.session.org_id,
                user_id=seeded.session.user_id,
                permission="approve_ai_actions",
                override_type="grant",
            )
        )
        _deny_role_permission(db, seeded, denied_permission)
        db.commit()
        await ai_email_service.process_email(db, db.get(Job, seeded.job_id))
        should_send = denied_permission == "send_email"
        assert len(calls) == int(should_send)
        assert db.get(AIActionApproval, seeded.approval_id).status == (
            "executed" if should_send else "failed"
        )
