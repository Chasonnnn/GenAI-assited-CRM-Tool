"""Admin API contracts for messaging templates and outbound MMS media."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from urllib.parse import urlsplit

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import JobType, Role
from app.db.models import Job, Membership, MessageMediaAsset, TwilioSettings, User
from app.main import app
from app.services import session_service


@asynccontextmanager
async def _authed_client_for_role(db, organization_id, role: Role):
    user = User(
        id=uuid.uuid4(),
        email=f"messaging-content-{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Messaging Content User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=organization_id,
            role=role.value,
        )
    )
    db.flush()
    token = create_session_token(
        user_id=user.id,
        org_id=organization_id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=organization_id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    ) as client:
        yield client
    app.dependency_overrides.clear()


def _template_payload(**overrides):
    payload = {
        "name": "Application updates",
        "purpose": "operational",
        "body": "Your application has a new update.",
        "is_enrollment_confirmation": False,
        "content_classification": "no_phi",
    }
    payload.update(overrides)
    return payload


def _configure_phi(db, organization_id):
    approved_at = datetime(2026, 7, 31, 20, 0, tzinfo=UTC)
    db.add(
        TwilioSettings(
            organization_id=organization_id,
            phi_enabled=True,
            twilio_edition="hipaa_eligible",
            baa_verified_at=approved_at,
            compliance_approved_at=approved_at,
        )
    )
    db.commit()


async def test_template_admin_api_creates_versions_lists_gets_and_publishes(authed_client):
    created = await authed_client.post("/messaging/templates", json=_template_payload())
    assert created.status_code == 201
    first = created.json()
    assert first["version"] == 1
    assert first["status"] == "draft"

    versioned = await authed_client.post(
        f"/messaging/templates/{first['template_key']}/versions",
        json={"body": "Your application has a reviewed update."},
    )
    assert versioned.status_code == 201
    second = versioned.json()
    assert second["version"] == 2
    assert second["name"] == first["name"]

    original = await authed_client.get(f"/messaging/templates/{first['id']}")
    assert original.status_code == 200
    assert original.json()["body"] == first["body"]

    listed = await authed_client.get("/messaging/templates?purpose=operational&status=draft")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [second["id"], first["id"]]

    published = await authed_client.post(f"/messaging/templates/{second['id']}/publish")
    assert published.status_code == 200
    assert published.json()["status"] == "published"


async def test_template_mutations_require_csrf_and_admin_or_developer(
    authed_client,
    db,
    test_org,
):
    csrf_blocked = await authed_client.post(
        "/messaging/templates",
        json=_template_payload(),
        headers={CSRF_HEADER: ""},
    )
    assert csrf_blocked.status_code == 403

    async with _authed_client_for_role(db, test_org.id, Role.CASE_MANAGER) as client:
        role_blocked = await client.post("/messaging/templates", json=_template_payload())
    assert role_blocked.status_code == 403


async def test_phi_template_and_media_uploads_share_the_valid_settings_gate(
    authed_client,
    db,
    test_org,
):
    template_blocked = await authed_client.post(
        "/messaging/templates",
        json=_template_payload(content_classification="phi"),
    )
    media_blocked = await authed_client.post(
        "/messaging/media",
        data={"content_classification": "phi"},
        files=[("files", ("photo.gif", b"GIF89a-safe", "image/gif"))],
    )
    assert template_blocked.status_code == 400
    assert media_blocked.status_code == 400

    _configure_phi(db, test_org.id)
    template_allowed = await authed_client.post(
        "/messaging/templates",
        json=_template_payload(content_classification="phi"),
    )
    media_allowed = await authed_client.post(
        "/messaging/media",
        data={"content_classification": "phi"},
        files=[("files", ("photo.gif", b"GIF89a-safe", "image/gif"))],
    )
    assert template_allowed.status_code == 201
    assert media_allowed.status_code == 201
    assert media_allowed.json()[0]["content_classification"] == "phi"


async def test_media_upload_encrypts_filename_and_uses_scan_gated_signed_head_and_get(
    authed_client,
    db,
):
    original_filename = "candidate-private-name.gif"
    payload = b"GIF89a-safe-messaging-media"
    uploaded = await authed_client.post(
        "/messaging/media",
        data={"content_classification": "no_phi"},
        files=[("files", (original_filename, payload, "image/gif"))],
    )
    assert uploaded.status_code == 201
    asset_payload = uploaded.json()[0]
    assert asset_payload["original_filename"] == original_filename
    assert asset_payload["scan_status"] == "pending"
    assert "storage_key" not in asset_payload

    asset_id = uuid.UUID(asset_payload["id"])
    scan_job = db.query(Job).filter(Job.job_type == JobType.MESSAGE_MEDIA_SCAN.value).one()
    assert scan_job.payload == {"media_asset_id": str(asset_id)}
    raw_filename = db.execute(
        text("SELECT original_filename FROM message_media_assets WHERE id = :id"),
        {"id": asset_id},
    ).scalar_one()
    assert original_filename not in raw_filename

    pending_access = await authed_client.post(f"/messaging/media/{asset_id}/access")
    assert pending_access.status_code == 409

    asset = db.get(MessageMediaAsset, asset_id)
    asset.scan_status = "clean"
    db.commit()
    access = await authed_client.post(f"/messaging/media/{asset_id}/access")
    assert access.status_code == 200
    access_payload = access.json()
    assert original_filename not in access_payload["url"]
    signed = urlsplit(access_payload["url"])
    signed_path = f"{signed.path}?{signed.query}"

    head = await authed_client.head(signed_path)
    fetched = await authed_client.get(signed_path)
    assert head.status_code == 200
    assert fetched.status_code == 200
    assert head.content == b""
    assert fetched.content == payload
    assert head.headers["content-type"] == "image/gif"
    assert fetched.headers["content-type"] == "image/gif"
    assert head.headers["content-length"] == str(len(payload))
    assert "content-disposition" not in fetched.headers

    asset.scan_status = "quarantined"
    db.commit()
    quarantined = await authed_client.get(signed_path)
    assert quarantined.status_code == 404


async def test_media_upload_rejects_unsafe_types_and_more_than_ten_assets(authed_client):
    unsafe = await authed_client.post(
        "/messaging/media",
        data={"content_classification": "no_phi"},
        files=[("files", ("payload.png", b"not-a-png", "image/png"))],
    )
    assert unsafe.status_code == 400

    too_many_files = [
        ("files", (f"image-{index}.gif", f"GIF89a-{index}".encode(), "image/gif"))
        for index in range(11)
    ]
    too_many = await authed_client.post(
        "/messaging/media",
        data={"content_classification": "no_phi"},
        files=too_many_files,
    )
    assert too_many.status_code == 400
    assert "10" in too_many.json()["detail"]
