from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from io import BytesIO
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pypdf import PdfReader, PdfWriter

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.encryption import hash_email
from app.core.security import create_session_token
from app.db.enums import FormStatus, FormSubmissionStatus, Role
from app.db.models import Form, FormSubmission, Membership, Organization, Surrogate, User
from app.main import app
from app.services import form_submission_service, pdf_export_service, session_service
from app.utils.normalization import normalize_email


def _make_single_page_pdf(width: int, height: int) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=height)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _create_surrogate(db, org_id, user_id, stage, *, suffix: str) -> Surrogate:
    email = normalize_email(f"surrogate-export-{suffix}@example.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name="Export Candidate",
        email=email,
        email_hash=hash_email(email),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def _create_form(db, org_id, user_id, *, name: str, schema: dict) -> Form:
    form = Form(
        id=uuid.uuid4(),
        organization_id=org_id,
        name=name,
        status=FormStatus.PUBLISHED.value,
        schema_json=schema,
        published_schema_json=schema,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(form)
    db.flush()
    return form


def _create_submission(
    db,
    org_id,
    form_id,
    surrogate_id,
    *,
    submitted_at: datetime,
    full_name: str,
) -> FormSubmission:
    schema = {
        "pages": [
            {
                "title": "Basics",
                "fields": [
                    {
                        "key": "full_name",
                        "label": "Full Name",
                        "type": "text",
                        "required": True,
                    }
                ],
            }
        ]
    }
    submission = FormSubmission(
        id=uuid.uuid4(),
        organization_id=org_id,
        form_id=form_id,
        surrogate_id=surrogate_id,
        status=FormSubmissionStatus.PENDING_REVIEW.value,
        answers_json={"full_name": full_name},
        schema_snapshot=schema,
        submitted_at=submitted_at,
    )
    db.add(submission)
    db.flush()
    return submission


@asynccontextmanager
async def _authed_client_for_user(db, org_id, user, role):
    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=org_id,
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


@pytest.mark.asyncio
async def test_surrogate_export_requires_auth(client, db, test_org, test_user, default_stage):
    surrogate = _create_surrogate(
        db,
        test_org.id,
        test_user.id,
        default_stage,
        suffix=uuid.uuid4().hex[:8],
    )

    response = await client.get(f"/surrogates/{surrogate.id}/export")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_surrogate_export_cross_org_hidden(authed_client, db, test_org, test_user, default_stage):
    surrogate = _create_surrogate(
        db,
        test_org.id,
        test_user.id,
        default_stage,
        suffix=uuid.uuid4().hex[:8],
    )

    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Org",
        slug=f"other-org-{uuid.uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()

    other_user = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Other User",
        token_version=1,
        is_active=True,
    )
    db.add(other_user)
    db.flush()

    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=other_user.id,
            organization_id=other_org.id,
            role=Role.DEVELOPER,
        )
    )
    db.flush()

    async with _authed_client_for_user(db, other_org.id, other_user, Role.DEVELOPER) as other_client:
        response = await other_client.get(f"/surrogates/{surrogate.id}/export")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_surrogate_export_no_submission_sets_header_false(
    authed_client, db, test_org, test_user, default_stage, monkeypatch
):
    surrogate = _create_surrogate(
        db,
        test_org.id,
        test_user.id,
        default_stage,
        suffix=uuid.uuid4().hex[:8],
    )

    monkeypatch.setattr(
        pdf_export_service,
        "export_surrogate_packet_pdf",
        lambda **_kwargs: (b"%PDF-1.7\noverview", False),
    )

    response = await authed_client.get(f"/surrogates/{surrogate.id}/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers.get("x-includes-application") == "false"
    assert response.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_surrogate_export_with_submission_sets_header_true(
    authed_client, db, test_org, test_user, default_stage, monkeypatch
):
    surrogate = _create_surrogate(
        db,
        test_org.id,
        test_user.id,
        default_stage,
        suffix=uuid.uuid4().hex[:8],
    )

    monkeypatch.setattr(
        pdf_export_service,
        "export_surrogate_packet_pdf",
        lambda **_kwargs: (b"%PDF-1.7\ncombined", True),
    )

    response = await authed_client.get(f"/surrogates/{surrogate.id}/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers.get("x-includes-application") == "true"
    assert response.content.startswith(b"%PDF")


def test_merge_pdf_bytes_combines_pages_in_order():
    pdf_a = _make_single_page_pdf(111, 222)
    pdf_b = _make_single_page_pdf(333, 444)

    merged = pdf_export_service._merge_pdf_bytes([pdf_a, pdf_b])
    reader = PdfReader(BytesIO(merged))

    assert len(reader.pages) == 2
    assert float(reader.pages[0].mediabox.width) == 111
    assert float(reader.pages[0].mediabox.height) == 222
    assert float(reader.pages[1].mediabox.width) == 333
    assert float(reader.pages[1].mediabox.height) == 444


def test_export_surrogate_packet_pdf_returns_overview_only_when_no_submission(
    db, test_org, test_user, default_stage, monkeypatch
):
    surrogate = _create_surrogate(
        db,
        test_org.id,
        test_user.id,
        default_stage,
        suffix=uuid.uuid4().hex[:8],
    )
    overview_pdf = _make_single_page_pdf(500, 500)

    async def fake_render_url_to_pdf(*_args, **_kwargs):
        return overview_pdf

    monkeypatch.setattr(pdf_export_service, "_render_url_to_pdf", fake_render_url_to_pdf)
    monkeypatch.setattr(
        pdf_export_service,
        "export_submission_pdf",
        lambda **_kwargs: pytest.fail("application export should not be called"),
    )
    monkeypatch.setattr(pdf_export_service.settings, "FRONTEND_URL", "http://localhost:3000")

    packet_pdf, includes_application = pdf_export_service.export_surrogate_packet_pdf(
        db=db,
        org_id=test_org.id,
        surrogate_id=surrogate.id,
        surrogate_name=surrogate.full_name,
        org_name=test_org.name,
    )

    assert includes_application is False
    assert packet_pdf == overview_pdf


def test_export_surrogate_packet_pdf_uses_latest_submission_for_multi_form(
    db, test_org, test_user, default_stage, monkeypatch
):
    surrogate = _create_surrogate(
        db,
        test_org.id,
        test_user.id,
        default_stage,
        suffix=uuid.uuid4().hex[:8],
    )
    schema = {
        "pages": [
            {
                "title": "Basics",
                "fields": [{"key": "full_name", "label": "Full Name", "type": "text"}],
            }
        ]
    }
    first_form = _create_form(
        db,
        test_org.id,
        test_user.id,
        name="First Form",
        schema=schema,
    )
    second_form = _create_form(
        db,
        test_org.id,
        test_user.id,
        name="Second Form",
        schema=schema,
    )

    now = datetime.now(timezone.utc)
    first_submission = _create_submission(
        db,
        test_org.id,
        first_form.id,
        surrogate.id,
        submitted_at=now - timedelta(days=2),
        full_name="Older",
    )
    second_submission = _create_submission(
        db,
        test_org.id,
        second_form.id,
        surrogate.id,
        submitted_at=now - timedelta(days=1),
        full_name="Newer",
    )

    overview_pdf = _make_single_page_pdf(210, 297)
    application_pdf = _make_single_page_pdf(612, 792)
    captured_submission_id: dict[str, uuid.UUID] = {}

    async def fake_render_url_to_pdf(*_args, **_kwargs):
        return overview_pdf

    def fake_export_submission_pdf(**kwargs):
        captured_submission_id["value"] = kwargs["submission_id"]
        return application_pdf

    monkeypatch.setattr(pdf_export_service, "_render_url_to_pdf", fake_render_url_to_pdf)
    monkeypatch.setattr(pdf_export_service, "export_submission_pdf", fake_export_submission_pdf)
    monkeypatch.setattr(pdf_export_service.settings, "FRONTEND_URL", "http://localhost:3000")

    packet_pdf, includes_application = pdf_export_service.export_surrogate_packet_pdf(
        db=db,
        org_id=test_org.id,
        surrogate_id=surrogate.id,
        surrogate_name=surrogate.full_name,
        org_name=test_org.name,
    )

    reader = PdfReader(BytesIO(packet_pdf))
    assert includes_application is True
    assert captured_submission_id["value"] == second_submission.id
    assert captured_submission_id["value"] != first_submission.id
    assert len(reader.pages) == 2
    assert float(reader.pages[0].mediabox.width) == 210
    assert float(reader.pages[1].mediabox.width) == 612


def test_get_latest_submission_for_surrogate_returns_none_when_missing(db, test_org):
    result = form_submission_service.get_latest_submission_for_surrogate(
        db=db,
        org_id=test_org.id,
        surrogate_id=uuid.uuid4(),
    )
    assert result is None
