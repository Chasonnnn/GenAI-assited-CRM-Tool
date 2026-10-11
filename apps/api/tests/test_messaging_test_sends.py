"""Code-verified test phones, template test texts, and the template library API."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from starlette.datastructures import FormData

from app.core.encryption import hash_phone
from app.db.enums import Role
from app.db.models import (
    AutomationWorkflow,
    Campaign,
    MessageReconciliationCase,
    MessageTemplate,
    MessagingTestPhone,
    MessagingTestSend,
    Organization,
)
from app.services import (
    message_content_service,
    messaging_consent_service,
    messaging_test_send_service,
    twilio_settings_service,
    twilio_transport,
)
from tests.test_messaging_content_api import _authed_client_for_role

ACCOUNT_SID = "AC" + ("1" * 32)
SERVICE_SID = "MG" + ("3" * 32)
SENDER = "+14155550199"
TEST_PHONE = "+15125550142"
MESSAGE_SID = "SM" + ("4" * 32)


def _ready_route(db, organization_id, purpose="operational"):
    settings = twilio_settings_service.get_or_create_settings(db, organization_id)
    settings.enabled = True
    settings.account_sid_encrypted = twilio_settings_service.encrypt_credential(ACCOUNT_SID)
    settings.api_key_sid_encrypted = twilio_settings_service.encrypt_credential("SK" + "2" * 32)
    settings.api_secret_encrypted = twilio_settings_service.encrypt_credential("secret")
    settings.auth_token_encrypted = twilio_settings_service.encrypt_credential("auth-token")
    settings.legal_messaging_brand = "EWI Family Global"
    settings.operational_disclosure = "Operational SMS disclosure"
    settings.promotional_disclosure = "Promotional SMS disclosure"
    settings.sms_terms_url = "https://example.org/sms-terms"
    settings.privacy_policy_url = "https://example.org/privacy"
    settings.support_contact = "(512) 555-0100"
    settings.expected_frequency = "Msg frequency varies"
    route = next(item for item in settings.routes if item.purpose == purpose)
    route.enabled = True
    route.messaging_service_sid_encrypted = twilio_settings_service.encrypt_credential(SERVICE_SID)
    route.sender_phone_encrypted = twilio_settings_service.encrypt_credential(SENDER)
    route.sender_phone_hash = hash_phone(SENDER)
    route.sender_phone_last4 = SENDER[-4:]
    route.a2p_status = "approved"
    route.capability_evidence = {
        "provider": {
            "a2p_status": "VERIFIED",
            "inbound_webhook_matches": True,
            "checked_at": datetime.now(UTC).isoformat(),
            "settings_version": settings.current_version,
        }
    }
    db.commit()
    return route


@pytest.fixture
def sent(monkeypatch):
    """Capture texts instead of calling Twilio; the dispatch worker stays off."""
    monkeypatch.delenv("MESSAGING_DELIVERY_DISPATCH_ENABLED", raising=False)
    calls: list[dict] = []

    def fake_send(**kwargs):
        calls.append(kwargs)
        return twilio_transport.TwilioSendResult(
            success=True, message_sid=f"{MESSAGE_SID[:-2]}{len(calls):02d}", initial_status="queued"
        )

    monkeypatch.setattr(twilio_transport, "send_message", fake_send)
    return calls


def _code_from(call: dict) -> str:
    match = re.search(r"\b(\d{6})\b", call["body"])
    assert match is not None
    return match.group(1)


async def _verified_phone(client, sent) -> dict:
    added = await client.post(
        "/messaging/test-phones", json={"label": "My phone", "phone": "(512) 555-0142"}
    )
    assert added.status_code == 201, added.text
    verified = await client.post(
        f"/messaging/test-phones/{added.json()['id']}/verify", json={"code": _code_from(sent[-1])}
    )
    assert verified.status_code == 200, verified.text
    return verified.json()


async def _draft(client, **overrides) -> dict:
    payload = {
        "name": "Application received",
        "purpose": "operational",
        "body": "Hi {{first_name}}, {{org_name}} got your application. O'Brien & co.",
    }
    payload.update(overrides)
    created = await client.post("/messaging/templates", json=payload)
    assert created.status_code == 201, created.text
    return created.json()


async def test_adding_a_test_phone_texts_a_code_that_verifies_it(authed_client, db, test_org, sent):
    _ready_route(db, test_org.id)

    added = await authed_client.post(
        "/messaging/test-phones", json={"label": "My phone", "phone": "(512) 555-0142"}
    )

    assert added.status_code == 201, added.text
    phone = added.json()
    assert phone["phone_last4"] == "0142"
    assert phone["verified_at"] is None
    assert phone["created_by_name"] == "Test User"
    assert len(sent) == 1
    assert sent[0]["to"] == TEST_PHONE
    assert sent[0]["from_"] == SENDER
    assert sent[0]["body"].startswith("EWI Family Global: Your test phone code is ")
    code = _code_from(sent[0])
    stored = db.get(MessagingTestPhone, uuid.UUID(phone["id"]))
    assert stored.code_hash and code not in stored.code_hash

    wrong = "000000" if code != "000000" else "111111"
    rejected = await authed_client.post(
        f"/messaging/test-phones/{phone['id']}/verify", json={"code": wrong}
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "The code is not correct"

    verified = await authed_client.post(
        f"/messaging/test-phones/{phone['id']}/verify", json={"code": code}
    )
    assert verified.status_code == 200
    assert verified.json()["verified_at"] is not None
    listed = await authed_client.get("/messaging/test-phones")
    assert [item["id"] for item in listed.json()] == [phone["id"]]


async def test_a_code_stops_working_after_it_expires_or_after_five_wrong_tries(
    authed_client, db, test_org, sent
):
    _ready_route(db, test_org.id)
    phone = (
        await authed_client.post(
            "/messaging/test-phones", json={"label": "My phone", "phone": TEST_PHONE}
        )
    ).json()
    code = _code_from(sent[0])
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(messaging_test_send_service.MAX_CODE_ATTEMPTS):
        await authed_client.post(
            f"/messaging/test-phones/{phone['id']}/verify", json={"code": wrong}
        )

    locked = await authed_client.post(
        f"/messaging/test-phones/{phone['id']}/verify", json={"code": code}
    )
    assert locked.status_code == 400
    assert locked.json()["detail"] == "The code expired. Send a new code."

    resent = await authed_client.post(
        "/messaging/test-phones", json={"label": "My phone", "phone": TEST_PHONE}
    )
    assert resent.json()["id"] == phone["id"]
    stored = db.get(MessagingTestPhone, uuid.UUID(phone["id"]))
    stored.code_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    expired = await authed_client.post(
        f"/messaging/test-phones/{phone['id']}/verify", json={"code": _code_from(sent[-1])}
    )
    assert expired.status_code == 400


async def test_test_text_fills_sample_values_and_skips_consent_and_the_dispatch_worker(
    authed_client, db, test_org, sent
):
    _ready_route(db, test_org.id)
    phone = await _verified_phone(authed_client, sent)
    template = await _draft(authed_client)

    response = await authed_client.post(
        f"/messaging/templates/{template['id']}/test-sends", json={"test_phone_id": phone["id"]}
    )

    assert response.status_code == 201, response.text
    assert response.json()["provider_status"] == "queued"
    org_name = db.get(Organization, test_org.id).name
    assert sent[-1]["to"] == TEST_PHONE
    assert sent[-1]["body"] == f"Hi Jane, {org_name} got your application. O'Brien & co."
    record = db.get(MessagingTestSend, uuid.UUID(response.json()["id"]))
    assert record.kind == "template_test"
    assert record.template_id == uuid.UUID(template["id"])


async def test_test_text_requires_a_verified_phone(authed_client, db, test_org, sent):
    _ready_route(db, test_org.id)
    phone = (
        await authed_client.post(
            "/messaging/test-phones", json={"label": "My phone", "phone": TEST_PHONE}
        )
    ).json()
    template = await _draft(authed_client)

    response = await authed_client.post(
        f"/messaging/templates/{template['id']}/test-sends", json={"test_phone_id": phone["id"]}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Verify this test phone first"
    assert len(sent) == 1


async def test_test_text_respects_a_stop_from_the_test_phone(authed_client, db, test_org, sent):
    _ready_route(db, test_org.id)
    phone = await _verified_phone(authed_client, sent)
    template = await _draft(authed_client)
    messaging_consent_service.record_global_stop(
        db,
        organization_id=test_org.id,
        phone=TEST_PHONE,
        instruction_text="STOP",
        source="twilio_inbound",
        source_reference="SM-stop",
        occurred_at=datetime.now(UTC),
        idempotency_key="test-phone-stop",
        evidence_metadata={},
    )
    db.commit()

    listed = await authed_client.get("/messaging/test-phones")
    assert listed.json()[0]["stopped_purposes"] == ["operational", "promotional"]
    response = await authed_client.post(
        f"/messaging/templates/{template['id']}/test-sends", json={"test_phone_id": phone["id"]}
    )

    assert response.status_code == 400
    assert "STOP" in response.json()["detail"]
    assert len(sent) == 1


async def test_test_text_uses_the_route_of_the_template_purpose(authed_client, db, test_org, sent):
    _ready_route(db, test_org.id)
    phone = await _verified_phone(authed_client, sent)
    template = await _draft(authed_client, purpose="promotional")

    response = await authed_client.post(
        f"/messaging/templates/{template['id']}/test-sends", json={"test_phone_id": phone["id"]}
    )

    assert response.status_code == 400
    assert len(sent) == 1


async def test_test_phones_and_templates_stay_in_their_organization(
    authed_client, db, test_org, sent
):
    _ready_route(db, test_org.id)
    phone = await _verified_phone(authed_client, sent)
    template = await _draft(authed_client)
    other_org = Organization(
        id=uuid.uuid4(), name="Other agency", slug=f"other-{uuid.uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.commit()
    _ready_route(db, other_org.id)

    async with _authed_client_for_role(db, other_org.id, Role.ADMIN) as other:
        assert (await other.get("/messaging/test-phones")).json() == []
        foreign_send = await other.post(
            f"/messaging/templates/{template['id']}/test-sends",
            json={"test_phone_id": phone["id"]},
        )
        foreign_verify = await other.post(
            f"/messaging/test-phones/{phone['id']}/verify", json={"code": "123456"}
        )
        foreign_delete = await other.delete(f"/messaging/test-phones/{phone['id']}")

    assert foreign_send.status_code == 404
    assert foreign_verify.status_code == 404
    assert foreign_delete.status_code == 404
    assert db.get(MessagingTestPhone, uuid.UUID(phone["id"])) is not None
    assert len(sent) == 1


async def test_test_phone_endpoints_require_csrf_and_admin_or_developer(
    authed_client, db, test_org
):
    csrf_blocked = await authed_client.post(
        "/messaging/test-phones",
        json={"label": "My phone", "phone": TEST_PHONE},
        headers={"X-CSRF-Token": ""},
    )
    assert csrf_blocked.status_code == 403

    async with _authed_client_for_role(db, test_org.id, Role.CASE_MANAGER) as client:
        assert (await client.get("/messaging/test-phones")).status_code == 403


async def test_removing_a_test_phone_keeps_its_test_text_record(authed_client, db, test_org, sent):
    _ready_route(db, test_org.id)
    phone = await _verified_phone(authed_client, sent)

    removed = await authed_client.delete(f"/messaging/test-phones/{phone['id']}")

    assert removed.status_code == 204
    assert (await authed_client.get("/messaging/test-phones")).json() == []
    record = db.execute(select(MessagingTestSend)).scalars().one()
    assert record.kind == "verification_code"
    assert record.test_phone_id is None


def test_status_callbacks_update_a_test_text_without_moving_back(db, test_org, test_user):
    route = _ready_route(db, test_org.id)
    record = MessagingTestSend(
        organization_id=test_org.id,
        route_id=route.id,
        kind="template_test",
        provider_message_sid=MESSAGE_SID,
        provider_status="queued",
        sent_by_user_id=test_user.id,
    )
    db.add(record)
    db.commit()

    def apply(status):
        return messaging_test_send_service.record_status(
            db,
            organization_id=test_org.id,
            route_id=route.id,
            provider_message_sid=MESSAGE_SID,
            provider_status=status,
            error_code=None,
        )

    assert apply("delivered") is True
    assert apply("sent") is True
    assert record.provider_status == "delivered"
    assert (
        messaging_test_send_service.record_status(
            db,
            organization_id=test_org.id,
            route_id=route.id,
            provider_message_sid="SM" + "9" * 32,
            provider_status="delivered",
            error_code=None,
        )
        is False
    )


async def test_status_webhook_for_a_test_text_opens_no_reconciliation_case(
    client, db, test_org, test_user, monkeypatch
):
    from app.services.webhooks import twilio as twilio_webhooks

    route = _ready_route(db, test_org.id)
    db.add(
        MessagingTestSend(
            organization_id=test_org.id,
            route_id=route.id,
            kind="template_test",
            provider_message_sid=MESSAGE_SID,
            provider_status="queued",
            sent_by_user_id=test_user.id,
        )
    )
    db.commit()

    async def accept(request, *, route, suffix):
        return FormData(
            {"AccountSid": ACCOUNT_SID, "MessageSid": MESSAGE_SID, "MessageStatus": "delivered"}
        )

    monkeypatch.setattr(twilio_webhooks, "_validated_form", accept)
    monkeypatch.setattr(twilio_webhooks, "_assert_tenant_binding", lambda *args, **kwargs: None)

    response = await client.post(f"/webhooks/twilio/{route.webhook_id}/status")

    assert response.status_code == 200, response.text
    record = db.execute(select(MessagingTestSend)).scalars().one()
    assert record.provider_status == "delivered"
    assert db.execute(select(MessageReconciliationCase)).scalars().all() == []


async def test_a_draft_is_edited_in_place_and_a_published_version_is_not(authed_client):
    template = await _draft(authed_client)

    edited = await authed_client.patch(
        f"/messaging/templates/{template['id']}", json={"body": "Hi {{first_name}}."}
    )
    assert edited.status_code == 200
    assert edited.json()["version"] == 1
    assert edited.json()["body"] == "Hi {{first_name}}."

    published = await authed_client.post(f"/messaging/templates/{template['id']}/publish")
    assert published.status_code == 200
    locked = await authed_client.patch(
        f"/messaging/templates/{template['id']}", json={"body": "Changed"}
    )
    assert locked.status_code == 409


async def test_publishing_moves_workflows_to_the_new_version_and_usage_lists_them(
    authed_client, db, test_org, test_user
):
    first = await _draft(authed_client, name="Consultation reminder")
    await authed_client.post(f"/messaging/templates/{first['id']}/publish")
    workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name="Remind before consult",
        subject_type="surrogate",
        trigger_type="status_changed",
        actions=[
            {
                "action_type": "send_message",
                "purpose": "operational",
                "message_template_version_id": first["id"],
            }
        ],
        is_enabled=True,
    )
    unrelated = AutomationWorkflow(
        organization_id=test_org.id,
        name="Unrelated",
        subject_type="surrogate",
        trigger_type="status_changed",
        actions=[{"action_type": "send_notification", "title": "Hi"}],
        is_enabled=True,
    )
    promo = MessageTemplate(
        organization_id=test_org.id,
        template_key=uuid.uuid4(),
        version=1,
        name="Info session",
        purpose="promotional",
        body="Join our info session",
        content_hash="0" * 64,
        status="published",
    )
    db.add_all([workflow, unrelated, promo])
    db.flush()
    db.add(
        Campaign(
            organization_id=test_org.id,
            name="October info session",
            channel="messaging",
            message_template_version_id=promo.id,
            recipient_type="surrogate",
            filter_criteria={},
            created_by_user_id=test_user.id,
        )
    )
    db.commit()

    second = (
        await authed_client.post(
            f"/messaging/templates/{first['template_key']}/versions",
            json={"body": "Reminder: your call is soon."},
        )
    ).json()
    published = await authed_client.post(f"/messaging/templates/{second['id']}/publish")
    assert published.status_code == 200

    db.refresh(workflow)
    assert workflow.actions[0]["message_template_version_id"] == second["id"]
    usage = {
        item["template_key"]: item["uses"]
        for item in (await authed_client.get("/messaging/templates/usage")).json()
    }
    assert usage[first["template_key"]] == [
        {"kind": "workflow", "id": str(workflow.id), "name": "Remind before consult"}
    ]
    assert [use["name"] for use in usage[str(promo.template_key)]] == ["October info session"]


async def test_template_variables_list_sample_values(authed_client, db, test_org):
    response = await authed_client.get("/messaging/template-variables")

    assert response.status_code == 200
    samples = {item["name"]: item["sample"] for item in response.json()}
    assert samples["first_name"] == "Jane"
    assert samples["org_name"] == db.get(Organization, test_org.id).name


def test_text_bodies_are_not_html_escaped():
    assert (
        message_content_service.render_message_body(
            "Hi {{first_name}} {{unknown}}from {{org_name}}",
            {"first_name": "Ana & O'Brien", "org_name": "<EWI>"},
        )
        == "Hi Ana & O'Brien from <EWI>"
    )


async def test_test_phone_changes_wait_for_the_routers_audit_commit(
    authed_client, db, test_org, test_user, sent, monkeypatch
):
    """Successful service calls leave the commit to the router, which writes the audit first."""
    _ready_route(db, test_org.id)
    template = await _draft(authed_client)
    commits: list[str] = []
    real_commit = db.commit

    def service_call(name, call):
        # A commit flushes; the stand-in records the call and keeps that effect.
        monkeypatch.setattr(db, "commit", lambda: commits.append(name) or db.flush())
        try:
            return call()
        finally:
            monkeypatch.setattr(db, "commit", real_commit)
            real_commit()

    added = service_call(
        "add",
        lambda: messaging_test_send_service.add_test_phone(
            db, organization_id=test_org.id, user_id=test_user.id, label="Desk", phone=TEST_PHONE
        ),
    )
    phone_id = added.phone.id
    service_call(
        "verify",
        lambda: messaging_test_send_service.verify_test_phone(
            db, organization_id=test_org.id, test_phone_id=phone_id, code=_code_from(sent[-1])
        ),
    )
    service_call(
        "send",
        lambda: messaging_test_send_service.send_template_test(
            db,
            organization_id=test_org.id,
            user_id=test_user.id,
            template_id=uuid.UUID(template["id"]),
            test_phone_id=phone_id,
        ),
    )
    service_call(
        "remove",
        lambda: messaging_test_send_service.remove_test_phone(
            db, organization_id=test_org.id, test_phone_id=phone_id
        ),
    )

    assert commits == []
    assert db.get(MessagingTestPhone, phone_id) is None
    kinds = sorted(db.execute(select(MessagingTestSend.kind)).scalars())
    assert kinds == ["template_test", "verification_code"]
