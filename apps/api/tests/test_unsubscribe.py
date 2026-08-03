"""Tests for email unsubscribe flow."""

import base64
import hashlib
import hmac
import json
import time

import pytest


def test_generated_unsubscribe_token_is_opaque_and_database_resolved(db, test_org):
    from app.db.models import UnsubscribeToken
    from app.services import unsubscribe_service

    email = "private.person@example.com"
    token = unsubscribe_service.generate_unsubscribe_token(
        db,
        org_id=test_org.id,
        email=email,
    )

    assert token.startswith("u2_")
    assert email not in token
    assert str(test_org.id) not in token
    assert unsubscribe_service.parse_unsubscribe_token(db, token) == (test_org.id, email)

    record = db.query(UnsubscribeToken).one()
    assert record.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in record.token_hash
    assert record.organization_id == test_org.id
    assert record.consumed_at is not None

    # Prove this is no longer the legacy base64 JSON envelope that exposed PII
    # directly in Cloud Run request URLs.
    with pytest.raises((ValueError, UnicodeDecodeError, json.JSONDecodeError)):
        payload = token.split(".", 1)[0]
        padding = "=" * (-len(payload) % 4)
        json.loads(base64.urlsafe_b64decode(payload + padding).decode("utf-8"))


@pytest.mark.asyncio
async def test_unsubscribe_endpoint_adds_suppression(client, db, test_org):
    from app.db.enums import SuppressionReason
    from app.db.models import EmailSuppression
    from app.services import campaign_service, unsubscribe_service

    token = unsubscribe_service.generate_unsubscribe_token(
        db,
        org_id=test_org.id,
        email="User@Example.com",
    )

    resp = await client.get(f"/email/unsubscribe/{token}")
    assert resp.status_code == 200

    assert campaign_service.is_email_suppressed(
        db,
        test_org.id,
        "user@example.com",
    )
    suppression = (
        db.query(EmailSuppression)
        .filter(
            EmailSuppression.organization_id == test_org.id,
            EmailSuppression.email == "user@example.com",
        )
        .first()
    )
    assert suppression is not None
    assert suppression.reason == SuppressionReason.OPT_OUT.value


@pytest.mark.asyncio
async def test_one_click_unsubscribe_post_adds_suppression(client, db, test_org):
    from app.services import campaign_service, unsubscribe_service

    token = unsubscribe_service.generate_unsubscribe_token(
        db,
        org_id=test_org.id,
        email="one-click@example.com",
    )

    response = await client.post(
        f"/email/unsubscribe/{token}",
        content="List-Unsubscribe=One-Click",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    assert campaign_service.is_email_suppressed(
        db,
        test_org.id,
        "one-click@example.com",
    )


@pytest.mark.asyncio
async def test_unsubscribe_endpoint_handles_invalid_token(client, db, test_org):
    from app.services import campaign_service

    resp = await client.get("/email/unsubscribe/invalid-token")
    assert resp.status_code == 200

    assert (
        campaign_service.is_email_suppressed(
            db,
            test_org.id,
            "user@example.com",
        )
        is False
    )


def test_build_list_unsubscribe_headers_use_one_click_and_portal_domain(db, test_org):
    from app.services import org_service, unsubscribe_service

    org = org_service.get_org_by_id(db, test_org.id)
    base = org_service.get_org_portal_base_url(org)
    headers = unsubscribe_service.build_list_unsubscribe_headers(
        db,
        org_id=test_org.id,
        email="user@example.com",
        base_url=base,
    )

    list_unsub = headers.get("List-Unsubscribe") or ""
    assert list_unsub.startswith(f"<{base}/email/unsubscribe/")
    assert list_unsub.endswith("/one-click>")
    assert headers.get("List-Unsubscribe-Post") == "List-Unsubscribe=One-Click"


@pytest.mark.asyncio
async def test_consumed_unsubscribe_token_remains_idempotent(client, db, test_org):
    from app.db.models import EmailSuppression, UnsubscribeToken
    from app.services import unsubscribe_service

    token = unsubscribe_service.generate_unsubscribe_token(
        db,
        org_id=test_org.id,
        email="repeat@example.com",
    )

    first = await client.get(f"/email/unsubscribe/{token}")
    consumed_at = db.query(UnsubscribeToken).one().consumed_at
    second = await client.post(
        f"/email/unsubscribe/{token}",
        content="List-Unsubscribe=One-Click",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert first.status_code == second.status_code == 200
    assert consumed_at is not None
    assert db.query(UnsubscribeToken).one().consumed_at == consumed_at
    assert (
        db.query(EmailSuppression)
        .filter(
            EmailSuppression.organization_id == test_org.id,
            EmailSuppression.email == "repeat@example.com",
        )
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_legacy_unsubscribe_token_remains_compatible(client, db, test_org):
    from app.core.config import settings
    from app.services import campaign_service

    payload = {
        "v": 1,
        "org_id": str(test_org.id),
        "email": "legacy@example.com",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(
        hmac.new(
            settings.jwt_secrets[0].encode(),
            payload_b64.encode(),
            hashlib.sha256,
        ).digest()
    ).decode().rstrip("=")

    response = await client.get(f"/email/unsubscribe/{payload_b64}.{signature}")

    assert response.status_code == 200
    assert campaign_service.is_email_suppressed(
        db,
        test_org.id,
        "legacy@example.com",
    )
