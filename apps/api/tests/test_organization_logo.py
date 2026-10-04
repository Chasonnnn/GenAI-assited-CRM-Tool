"""Organization branding media lifecycle and tenant authorization."""

import io
import random
from types import SimpleNamespace
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import CSRF_HEADER
from app.core.deps import get_db
from app.db.enums import JobType, Role
from app.db.models import AuditLog, Job, Membership, Organization, User
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.jobs.handlers import storage as storage_jobs
from app.main import app
from app.services import attachment_service, audit_service, org_logo_service, storage_client
from tests.test_journey import _authed_client_for_user

LOGO_PATH = "/settings/organization/logo"


def _image(format="PNG", size=(128, 64)):
    image = Image.new("RGB", size, "blue")
    # Only the middle square should survive the crop.
    if size == (128, 64):
        image.paste("red", (0, 0, 32, 64))
        image.paste("green", (96, 0, 128, 64))
    output = io.BytesIO()
    image.save(output, format=format)
    return output.getvalue()


@pytest.fixture
def logo_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_upload_replace_delete_logo(authed_client, db, test_org, logo_storage):
    test_org.signature_logo_url = "https://example.com/signature.png"
    db.commit()
    old_url = None
    for extension, format in [("png", "PNG"), ("jpg", "JPEG"), ("webp", "WEBP")]:
        response = await authed_client.post(
            LOGO_PATH, files={"file": (f"logo.{extension}", _image(format), f"image/{extension}")}
        )
        assert response.status_code == 200, response.text
        url = response.json()["logo_url"]
        assert url != old_url
        image_response = await authed_client.get(urlparse(url).path)
        assert image_response.status_code == 200
        assert image_response.headers["cross-origin-resource-policy"] == "cross-origin"
        with Image.open(io.BytesIO(image_response.content)) as image:
            assert image.size == (256, 256)
            red, green, blue = image.convert("RGB").getpixel((128, 128))
            assert blue > 240 and red < 15 and green < 15
            red, green, blue = image.convert("RGB").getpixel((16, 128))
            assert blue > 240 and red < 15 and green < 15
        assert len(image_response.content) <= 50 * 1024
        assert len(list(logo_storage.rglob("*.*"))) == 1
        if old_url:
            assert (await authed_client.get(urlparse(old_url).path)).status_code == 404
        for path in ["/settings/organization", "/settings/organization/signature"]:
            current = await authed_client.get(path)
            assert current.status_code == 200
            assert current.json()["logo_url"] == url
        assert (await authed_client.get("/auth/me")).json()["org_logo_url"] == url
        old_url = url

    response = await authed_client.delete(LOGO_PATH)
    assert response.status_code == 204
    assert response.content == b""
    assert (await authed_client.get(urlparse(old_url).path)).status_code == 404
    assert list(logo_storage.rglob("*.*")) == []
    db.refresh(test_org)
    assert test_org.logo_url is None
    assert test_org.signature_logo_url == "https://example.com/signature.png"
    assert (await authed_client.get("/auth/me")).json()["org_logo_url"] is None
    audits = db.query(AuditLog).filter_by(organization_id=test_org.id).all()
    actions = [
        entry.details["changes"]["action"]
        for entry in audits
        if entry.details and entry.details.get("area") == "logo"
    ]
    assert actions.count("uploaded") == 3
    assert actions.count("deleted") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "content", "error"),
    [
        ("logo.gif", _image("GIF"), "Invalid file type"),
        ("logo.png", _image("GIF"), "Invalid image file"),
        ("logo.png", b"not an image", "Invalid image file"),
        ("logo.jpg", b"x" * (1024 * 1024 + 1), "File too large"),
        ("logo.jpg", b"x" * (2 * 1024 * 1024), "File too large"),
        ("logo.png", _image(size=(63, 100)), "64x64"),
        ("logo.png", _image(size=(100, 63)), "64x64"),
    ],
    # Explicit IDs: raw upload bytes would put megabyte-long test names in the CI log.
    ids=[
        "unsupported-extension",
        "wrong-image-format",
        "not-an-image",
        "over-1mb",
        "2mb",
        "too-narrow",
        "too-short",
    ],
)
async def test_logo_rejects_invalid_upload_without_changing_current(
    authed_client, db, test_org, logo_storage, filename, content, error
):
    response = await authed_client.post(LOGO_PATH, files={"file": ("logo.png", _image())})
    original_url = response.json()["logo_url"]
    response = await authed_client.post(LOGO_PATH, files={"file": (filename, content)})
    assert response.status_code == 400
    assert error in response.json()["detail"]
    assert (await authed_client.get("/auth/me")).json()["org_logo_url"] == original_url
    assert len(list(logo_storage.rglob("*.*"))) == 1


@pytest.mark.asyncio
async def test_logo_rejects_output_over_50kb(authed_client, test_org, logo_storage):
    image = Image.frombytes("RGB", (256, 256), random.Random(7).randbytes(256 * 256 * 3))
    content = io.BytesIO()
    image.save(content, format="PNG")
    response = await authed_client.post(LOGO_PATH, files={"file": ("logo.png", content.getvalue())})
    assert response.status_code == 400
    assert response.json()["detail"] == "Image too complex to compress under 50KB"
    assert list(logo_storage.rglob("*.*")) == []
    assert (await authed_client.get("/auth/me")).json()["org_logo_url"] is None


@pytest.mark.asyncio
async def test_logo_audit_failure_rolls_back_and_removes_new_file(
    authed_client, db, test_org, test_user, logo_storage, monkeypatch
):
    from fastapi import HTTPException

    # Request rollback must not remove auth/organization fixtures in the outer transaction.
    connection = db.connection()

    def request_db():
        with Session(
            bind=connection, autoflush=False, join_transaction_mode="create_savepoint"
        ) as session:
            yield session

    monkeypatch.setitem(app.dependency_overrides, get_db, request_db)
    original = await authed_client.post(LOGO_PATH, files={"file": ("logo.png", _image())})
    assert original.status_code == 200, original.text
    original_url = original.json()["logo_url"]

    def fail_audit(**kwargs):
        raise HTTPException(status_code=503, detail="Audit unavailable")

    monkeypatch.setattr(audit_service, "log_settings_changed", fail_audit)
    response = await authed_client.post(LOGO_PATH, files={"file": ("logo.png", _image())})
    assert response.status_code == 503, response.text
    assert response.json()["detail"] == "Audit unavailable"
    current = await authed_client.get("/auth/me")
    assert current.status_code == 200, current.text
    assert current.json()["org_logo_url"] == original_url
    assert len(list(logo_storage.rglob("*.*"))) == 1
    response = await authed_client.delete(LOGO_PATH)
    assert response.status_code == 503, response.text
    assert response.json()["detail"] == "Audit unavailable"
    assert (await authed_client.get(urlparse(original_url).path)).status_code == 200
    current = await authed_client.get("/auth/me")
    assert current.status_code == 200, current.text
    assert current.json()["org_logo_url"] == original_url
    assert (
        db.query(Job)
        .filter_by(organization_id=test_org.id, job_type=JobType.STORAGE_DELETE.value)
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_logo_storage_failure_is_sanitized_and_delete_is_retryable(
    authed_client, db, test_org, logo_storage, monkeypatch
):
    from botocore.exceptions import ClientError

    original = await authed_client.post(LOGO_PATH, files={"file": ("logo.png", _image())})
    original_url = original.json()["logo_url"]

    def storage_failure(*args, **kwargs):
        raise ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "private-provider-details"}}, "PutObject"
        )

    with monkeypatch.context() as failing_storage:
        failing_storage.setattr(org_logo_service, "upload_logo_to_storage", storage_failure)
        failing_storage.setattr(org_logo_service, "delete_logo_from_storage", storage_failure)
        response = await authed_client.post(LOGO_PATH, files={"file": ("logo.png", _image())})
        assert response.status_code == 503
        assert response.json()["detail"] == "Logo storage unavailable"
        assert (await authed_client.get("/auth/me")).json()["org_logo_url"] == original_url
        response = await authed_client.delete(LOGO_PATH)
        assert response.status_code == 204
        assert (await authed_client.get("/auth/me")).json()["org_logo_url"] is None
        assert len(list(logo_storage.rglob("*.*"))) == 1

    job = (
        db.query(Job)
        .filter_by(organization_id=test_org.id, job_type=JobType.STORAGE_DELETE.value)
        .one()
    )
    foreign_job = SimpleNamespace(organization_id=uuid4(), payload=job.payload)
    with pytest.raises(ValueError, match="outside the job organization"):
        await storage_jobs.process_storage_delete(db, foreign_job)
    assert len(list(logo_storage.rglob("*.*"))) == 1
    await storage_jobs.process_storage_delete(db, job)
    assert list(logo_storage.rglob("*.*")) == []
    await storage_jobs.process_storage_delete(db, job)
    assert (await authed_client.delete(LOGO_PATH)).status_code == 204


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
async def test_logo_requires_settings_permission(
    authed_client, db, test_org, test_user, logo_storage, version
):
    if version == 2:
        db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    membership = db.query(Membership).filter_by(user_id=test_user.id).one()
    membership.role = Role.CASE_MANAGER.value
    db.commit()
    for path in [LOGO_PATH, "/settings/organization/signature/logo"]:
        response = await authed_client.post(path, files={"file": ("logo.png", _image())})
        assert response.status_code == 403
        assert response.json()["detail"] == "Missing permission: manage_org"
        response = await authed_client.delete(path)
        assert response.status_code == 403
        assert response.json()["detail"] == "Missing permission: manage_org"
    db.refresh(test_org)
    assert test_org.logo_url is None
    assert list(logo_storage.rglob("*.*")) == []


@pytest.mark.asyncio
async def test_logo_requires_csrf(authed_client, db, test_org, logo_storage):
    response = await authed_client.post(LOGO_PATH, files={"file": ("logo.png", _image())})
    url = response.json()["logo_url"]
    del authed_client.headers[CSRF_HEADER]
    response = await authed_client.post(LOGO_PATH, files={"file": ("logo.png", _image())})
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]
    response = await authed_client.delete(LOGO_PATH)
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]
    assert (await authed_client.get("/auth/me")).json()["org_logo_url"] == url
    assert len(list(logo_storage.rglob("*.*"))) == 1


@pytest.mark.asyncio
async def test_logo_is_scoped_to_membership(authed_client, db, test_org, logo_storage):
    other_org = Organization(name="Other Agency", slug=f"other-{uuid4().hex}")
    other_user = User(email=f"other-{uuid4().hex}@example.com", display_name="Other Admin")
    db.add_all([other_org, other_user])
    db.flush()
    db.add(Membership(organization_id=other_org.id, user_id=other_user.id, role=Role.ADMIN))
    db.commit()

    response = await authed_client.post(
        f"{LOGO_PATH}?org_id={other_org.id}",
        data={"organization_id": str(other_org.id)},
        files={"file": ("logo.png", _image())},
    )
    assert response.status_code == 200
    first_url = response.json()["logo_url"]
    db.refresh(test_org)
    first_stored_url = test_org.logo_url
    db.refresh(other_org)
    assert other_org.logo_url is None

    async with _authed_client_for_user(db, other_org.id, other_user, Role.ADMIN) as other_client:
        for path, key in [
            ("/settings/organization", "logo_url"),
            ("/settings/organization/signature", "logo_url"),
            ("/auth/me", "org_logo_url"),
        ]:
            response = await other_client.get(f"{path}?org_id={test_org.id}")
            assert response.status_code == 200
            assert response.json()[key] is None
            assert first_url not in response.text
        response = await other_client.post(
            f"{LOGO_PATH}?org_id={test_org.id}", files={"file": ("logo.png", _image())}
        )
        assert response.status_code == 200
        assert response.json()["logo_url"] != first_url
        response = await other_client.delete(f"{LOGO_PATH}?org_id={test_org.id}")
        assert response.status_code == 204
    db.refresh(test_org)
    assert test_org.logo_url == first_stored_url
    assert len(list(logo_storage.rglob("*.*"))) == 1


@pytest.mark.asyncio
async def test_logo_s3_storage_and_signed_auth_responses(authed_client, db, test_org, monkeypatch):
    objects = {}

    class Storage:
        def put_object(self, *, Bucket, Key, Body, ContentType):
            objects[Key] = Body

        def delete_object(self, *, Bucket, Key):
            del objects[Key]

    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "S3_BUCKET", "crm-attachments")
    monkeypatch.setattr(settings, "S3_PUBLIC_BASE_URL", "")
    monkeypatch.setattr(settings, "S3_URL_STYLE", "path")
    monkeypatch.setattr(storage_client, "get_s3_client", lambda: Storage())
    monkeypatch.setattr(
        attachment_service,
        "generate_signed_url",
        lambda key, expires_in_seconds=None: f"https://signed.example/{key}?signature=test",
    )
    for _ in range(2):
        response = await authed_client.post(LOGO_PATH, files={"file": ("logo.png", _image())})
        assert response.status_code == 200
        signed = response.json()["logo_url"]
        assert signed.startswith(f"https://signed.example/logos/{test_org.id}/")
        assert len(objects) == 1
        db.refresh(test_org)
        assert "signature=" not in test_org.logo_url
        for method, path, key in [
            ("GET", "/auth/me", "org_logo_url"),
            ("PATCH", "/auth/me", "org_logo_url"),
            ("GET", "/settings/organization", "logo_url"),
            ("GET", "/settings/organization/signature", "logo_url"),
        ]:
            response = await authed_client.request(
                method, path, **({"json": {}} if method == "PATCH" else {})
            )
            assert response.status_code == 200
            assert response.json()[key] == signed
    assert (await authed_client.delete(LOGO_PATH)).status_code == 204
    assert objects == {}
