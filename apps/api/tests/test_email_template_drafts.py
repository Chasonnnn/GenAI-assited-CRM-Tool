from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import EmailTemplate, EmailTemplateDraft, Membership, Organization, User
from app.main import app
from app.services import (
    email_service,
    session_service,
    version_service,
)


@asynccontextmanager
async def authed_client_for_user(db, *, user: User, org_id: uuid.UUID, role: Role):
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
async def test_existing_template_draft_is_isolated_until_explicit_publish(
    authed_client,
    db,
    test_org,
    test_user,
):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Journey welcome",
        subject="Original subject",
        from_email="Journey Team <journey@example.com>",
        body="<p>Original body</p>",
        scope="org",
    )
    template_id = template.id
    original_created_at = template.created_at

    create_response = await authed_client.post(
        f"/email-template-drafts/from-template/{template.id}"
    )
    assert create_response.status_code == 200
    draft = create_response.json()
    assert draft["template_id"] == str(template.id)
    assert draft["base_version"] == 1
    assert draft["published_version"] == 1
    assert draft["revision"] == 1
    assert draft["is_stale"] is False

    update_response = await authed_client.patch(
        f"/email-template-drafts/{draft['id']}",
        json={
            "subject": "Draft subject",
            "body": "<p>Draft body</p>",
            "expected_revision": 1,
        },
    )
    assert update_response.status_code == 200
    updated_draft = update_response.json()
    assert updated_draft["revision"] == 2
    assert updated_draft["subject"] == "Draft subject"

    db.expire_all()
    still_published = db.get(EmailTemplate, template_id)
    assert still_published is not None
    assert still_published.subject == "Original subject"
    assert still_published.body == "<p>Original body</p>"
    assert still_published.current_version == 1

    publish_response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/publish",
        json={
            "expected_revision": 2,
            "expected_published_version": 1,
        },
    )
    assert publish_response.status_code == 200
    published = publish_response.json()
    assert published["id"] == str(template_id)
    assert published["subject"] == "Draft subject"
    assert published["body"] == "<p>Draft body</p>"
    assert published["current_version"] == 2
    assert published["scope"] == "org"
    assert published["created_at"] == original_created_at.isoformat().replace("+00:00", "Z")

    discarded_after_publish = await authed_client.get(
        f"/email-template-drafts/{draft['id']}"
    )
    assert discarded_after_publish.status_code == 404


@pytest.mark.asyncio
async def test_new_draft_is_not_visible_as_a_template_until_publish(
    authed_client,
    db,
    test_org,
):
    create_response = await authed_client.post(
        "/email-template-drafts",
        json={
            "name": "Document request",
            "subject": "Please upload {{document_name}}",
            "body": "<p>Hi {{first_name}}, please upload the requested document.</p>",
            "scope": "org",
        },
    )
    assert create_response.status_code == 201
    draft = create_response.json()
    assert draft["template_id"] is None
    assert draft["base_version"] == 0
    assert draft["published_version"] is None

    before_publish = await authed_client.get("/email-templates?scope=org")
    assert before_publish.status_code == 200
    assert "Document request" not in {item["name"] for item in before_publish.json()}
    assert (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.organization_id == test_org.id,
            EmailTemplate.name == "Document request",
        )
        .count()
        == 0
    )

    publish_response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/publish",
        json={
            "expected_revision": 1,
            "expected_published_version": None,
        },
    )
    assert publish_response.status_code == 200
    published = publish_response.json()
    assert published["name"] == "Document request"
    assert published["current_version"] == 1

    after_publish = await authed_client.get("/email-templates?scope=org")
    assert after_publish.status_code == 200
    assert "Document request" in {item["name"] for item in after_publish.json()}


@pytest.mark.asyncio
@pytest.mark.parametrize("version_encryption_key", ["", "not-a-fernet-key"])
async def test_publish_is_unavailable_with_unusable_version_history_encryption(
    authed_client,
    db,
    test_org,
    monkeypatch,
    version_encryption_key,
):
    create_response = await authed_client.post(
        "/email-template-drafts",
        json={
            "name": "Encryption guarded draft",
            "subject": "Draft remains isolated",
            "body": "<p>Never partially publish this draft.</p>",
            "scope": "org",
        },
    )
    assert create_response.status_code == 201
    draft = create_response.json()

    monkeypatch.setattr(
        version_service.settings,
        "VERSION_ENCRYPTION_KEY",
        version_encryption_key,
    )
    monkeypatch.setattr(version_service.settings, "META_ENCRYPTION_KEY", "")
    monkeypatch.setattr(version_service, "_fernet", None)

    publish_response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/publish",
        json={
            "expected_revision": 1,
            "expected_published_version": None,
        },
    )

    assert publish_response.status_code == 503
    assert publish_response.json() == {
        "detail": "Template publishing is temporarily unavailable"
    }
    assert (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.organization_id == test_org.id,
            EmailTemplate.name == "Encryption guarded draft",
        )
        .count()
        == 0
    )
    assert db.get(EmailTemplateDraft, uuid.UUID(draft["id"])) is not None


@pytest.mark.asyncio
async def test_stale_draft_cannot_overwrite_a_newer_published_template(
    authed_client,
    db,
    test_org,
    test_user,
):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Appointment reminder",
        subject="Original subject",
        body="<p>Original body</p>",
        scope="org",
    )
    draft_response = await authed_client.post(
        f"/email-template-drafts/from-template/{template.id}"
    )
    assert draft_response.status_code == 200
    draft = draft_response.json()

    email_service.update_template(
        db,
        template=template,
        user_id=test_user.id,
        subject="Published by another editor",
        expected_version=1,
    )

    draft_update = await authed_client.patch(
        f"/email-template-drafts/{draft['id']}",
        json={
            "subject": "Stale draft subject",
            "expected_revision": 1,
        },
    )
    assert draft_update.status_code == 200

    publish_response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/publish",
        json={
            "expected_revision": 2,
            "expected_published_version": 1,
        },
    )
    assert publish_response.status_code == 409
    assert "published template changed" in publish_response.text.lower()

    db.expire_all()
    still_published = db.get(EmailTemplate, template.id)
    assert still_published is not None
    assert still_published.subject == "Published by another editor"
    assert still_published.current_version == 2

    retained_draft = await authed_client.get(f"/email-template-drafts/{draft['id']}")
    assert retained_draft.status_code == 200
    assert retained_draft.json()["subject"] == "Stale draft subject"
    assert retained_draft.json()["is_stale"] is True
    assert retained_draft.json()["published_version"] == 2


@pytest.mark.asyncio
async def test_publishing_a_legacy_template_backfills_old_content_in_version_history(
    authed_client,
    db,
    test_org,
    test_user,
):
    legacy_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Legacy template",
        subject="Legacy subject",
        body="<p>Legacy body</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
        current_version=1,
    )
    db.add(legacy_template)
    db.commit()

    assert (
        version_service.get_version_history(
            db,
            test_org.id,
            "email_template",
            legacy_template.id,
        )
        == []
    )

    draft_response = await authed_client.post(
        f"/email-template-drafts/from-template/{legacy_template.id}"
    )
    draft = draft_response.json()
    update_response = await authed_client.patch(
        f"/email-template-drafts/{draft['id']}",
        json={
            "subject": "Modern subject",
            "body": "<p>Modern body</p>",
            "expected_revision": 1,
        },
    )
    assert update_response.status_code == 200

    publish_response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/publish",
        json={
            "expected_revision": 2,
            "expected_published_version": 1,
        },
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["current_version"] == 2

    versions = version_service.get_version_history(
        db,
        test_org.id,
        "email_template",
        legacy_template.id,
    )
    assert [version.version for version in versions] == [2, 1]
    assert version_service.decrypt_payload(versions[1].payload_encrypted) == {
        "name": "Legacy template",
        "subject": "Legacy subject",
        "from_email": None,
        "body": "<p>Legacy body</p>",
        "is_active": True,
    }
    assert version_service.decrypt_payload(versions[0].payload_encrypted)["subject"] == (
        "Modern subject"
    )


@pytest.mark.asyncio
async def test_subject_only_publish_preserves_legacy_body_and_from_bytes(
    authed_client,
    db,
    test_org,
    test_user,
):
    legacy_body = (
        '<table style="mso-table-lspace:0"><tr><td>'
        "<script>legacyRenderer()</script>{{ unknown_legacy_variable }}"
        "</td></tr></table>"
    )
    legacy_from = "  Legacy Sender <legacy@example.com>  "
    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Imported legacy",
        subject="Legacy subject",
        from_email=legacy_from,
        body=legacy_body,
        scope="org",
        owner_user_id=None,
        is_active=True,
        current_version=3,
    )
    db.add(template)
    db.commit()

    draft_response = await authed_client.post(
        f"/email-template-drafts/from-template/{template.id}"
    )
    assert draft_response.status_code == 200
    draft = draft_response.json()
    assert draft["body"] == legacy_body
    assert draft["from_email"] == legacy_from

    update_response = await authed_client.patch(
        f"/email-template-drafts/{draft['id']}",
        json={
            "subject": "Only the subject changed",
            "expected_revision": 1,
        },
    )
    assert update_response.status_code == 200
    publish_response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/publish",
        json={
            "expected_revision": 2,
            "expected_published_version": 3,
        },
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["current_version"] == 4

    db.expire_all()
    published = db.get(EmailTemplate, template.id)
    assert published is not None
    assert published.subject == "Only the subject changed"
    assert published.body == legacy_body
    assert published.from_email == legacy_from


@pytest.mark.asyncio
async def test_draft_conflicts_and_discard_never_create_or_overwrite_templates(
    authed_client,
    db,
    test_org,
):
    existing = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=None,
        name="Already published",
        subject="Existing",
        body="<p>Existing</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
        current_version=1,
    )
    db.add(existing)
    db.commit()

    draft_response = await authed_client.post(
        "/email-template-drafts",
        json={
            "name": "Already published",
            "subject": "Conflicting draft",
            "body": "<p>Draft</p>",
            "scope": "org",
        },
    )
    assert draft_response.status_code == 201
    draft = draft_response.json()

    stale_save = await authed_client.patch(
        f"/email-template-drafts/{draft['id']}",
        json={
            "subject": "Must not save",
            "expected_revision": 999,
        },
    )
    assert stale_save.status_code == 409

    duplicate_publish = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/publish",
        json={
            "expected_revision": 1,
            "expected_published_version": None,
        },
    )
    assert duplicate_publish.status_code == 409
    assert "already exists" in duplicate_publish.text

    retained = await authed_client.get(f"/email-template-drafts/{draft['id']}")
    assert retained.status_code == 200
    assert retained.json()["subject"] == "Conflicting draft"
    assert retained.json()["revision"] == 1

    stale_discard = await authed_client.delete(
        f"/email-template-drafts/{draft['id']}?expected_revision=999"
    )
    assert stale_discard.status_code == 409
    assert (
        await authed_client.get(f"/email-template-drafts/{draft['id']}")
    ).status_code == 200

    discard = await authed_client.delete(
        f"/email-template-drafts/{draft['id']}?expected_revision=1"
    )
    assert discard.status_code == 204
    assert (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.organization_id == test_org.id,
            EmailTemplate.name == "Already published",
        )
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_immediate_publish_returns_conflict_when_history_does_not_match_live_state(
    authed_client,
    db,
    test_org,
    test_user,
):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Conflicted history",
        subject="Versioned subject",
        body="<p>Versioned body</p>",
        scope="org",
    )
    template.subject = "Out-of-band subject"
    db.commit()

    response = await authed_client.patch(
        f"/email-templates/{template.id}",
        json={
            "subject": "Attempted overwrite",
            "expected_version": 1,
        },
    )
    assert response.status_code == 409
    assert "does not match its version history" in response.text

    db.expire_all()
    unchanged = db.get(EmailTemplate, template.id)
    assert unchanged is not None
    assert unchanged.subject == "Out-of-band subject"
    assert unchanged.current_version == 1


@pytest.mark.asyncio
async def test_drafts_are_not_visible_or_mutable_across_organizations(
    authed_client,
    db,
    test_org,
):
    create_response = await authed_client.post(
        "/email-template-drafts",
        json={
            "name": "Tenant private draft",
            "subject": "Org one",
            "body": "<p>Org one only</p>",
            "scope": "org",
        },
    )
    assert create_response.status_code == 201
    draft = create_response.json()

    other_org = Organization(
        id=uuid.uuid4(),
        name="Other organization",
        slug=f"other-{uuid.uuid4().hex[:8]}",
    )
    other_user = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Other developer",
        token_version=1,
        is_active=True,
    )
    db.add_all([other_org, other_user])
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=other_user.id,
            organization_id=other_org.id,
            role=Role.DEVELOPER,
        )
    )
    db.commit()

    async with authed_client_for_user(
        db,
        user=other_user,
        org_id=other_org.id,
        role=Role.DEVELOPER,
    ) as other_client:
        get_response = await other_client.get(f"/email-template-drafts/{draft['id']}")
        assert get_response.status_code == 404

        update_response = await other_client.patch(
            f"/email-template-drafts/{draft['id']}",
            json={
                "subject": "Cross-tenant overwrite",
                "expected_revision": 1,
            },
        )
        assert update_response.status_code == 404

        publish_response = await other_client.post(
            f"/email-template-drafts/{draft['id']}/publish",
            json={
                "expected_revision": 1,
                "expected_published_version": None,
            },
        )
        assert publish_response.status_code == 404

        restore_response = await other_client.post(
            f"/email-template-drafts/{draft['id']}/restore-version",
            json={"target_version": 1, "expected_revision": 1},
        )
        assert restore_response.status_code == 404

    retained = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.organization_id == test_org.id,
            EmailTemplate.name == "Tenant private draft",
        )
        .first()
    )
    assert retained is None


@pytest.mark.asyncio
async def test_restore_published_version_updates_only_the_existing_draft(
    authed_client,
    db,
    test_org,
    test_user,
):
    legacy_body = (
        '<table style="mso-table-lspace:0"><tr><td>'
        "<script>legacyRenderer()</script>{{ unknown_legacy_variable }}"
        "</td></tr></table>"
    )
    legacy_from = "  Legacy Sender <legacy@example.com>  "
    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Historical journey",
        subject="Historical subject",
        from_email=legacy_from,
        body=legacy_body,
        scope="org",
        owner_user_id=None,
        is_active=True,
        current_version=1,
    )
    db.add(template)
    db.commit()

    email_service.update_template(
        db,
        template=template,
        user_id=test_user.id,
        name="Current journey",
        subject="Current subject",
        from_email="Current Sender <current@example.com>",
        body="<p>Current body</p>",
        is_active=False,
        expected_version=1,
    )
    draft_response = await authed_client.post(f"/email-template-drafts/from-template/{template.id}")
    assert draft_response.status_code == 200
    draft = draft_response.json()
    updated_response = await authed_client.patch(
        f"/email-template-drafts/{draft['id']}",
        json={
            "subject": "Unpublished working subject",
            "expected_revision": 1,
        },
    )
    assert updated_response.status_code == 200

    draft_model = db.get(EmailTemplateDraft, uuid.UUID(draft["id"]))
    assert draft_model is not None
    draft_model.last_tested_revision = 2
    draft_model.last_tested_at = datetime.now(timezone.utc)
    db.commit()

    db.refresh(template)
    published_before = (
        template.name,
        template.subject,
        template.from_email,
        template.body,
        template.is_active,
        template.current_version,
        template.created_at,
        template.updated_at,
    )
    versions_before = [
        (
            version.id,
            version.version,
            version.payload_encrypted,
            version.checksum,
            version.created_by_user_id,
            version.comment,
            version.created_at,
        )
        for version in version_service.get_version_history(
            db,
            test_org.id,
            "email_template",
            template.id,
        )
    ]
    historical_payload = version_service.decrypt_payload(
        version_service.get_version(
            db,
            test_org.id,
            "email_template",
            template.id,
            1,
        ).payload_encrypted
    )

    response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/restore-version",
        json={"target_version": 1, "expected_revision": 2},
    )

    assert response.status_code == 200
    restored = response.json()
    assert {
        field: restored[field] for field in ("name", "subject", "from_email", "body", "is_active")
    } == historical_payload
    assert restored["body"] == legacy_body
    assert restored["from_email"] == legacy_from
    assert restored["revision"] == 3
    assert restored["base_version"] == 2
    assert restored["published_version"] == 2
    assert restored["is_stale"] is False
    assert restored["last_tested_revision"] is None
    assert restored["last_tested_at"] is None
    assert restored["updated_by_user_id"] == str(test_user.id)

    db.expire_all()
    published_after = db.get(EmailTemplate, template.id)
    assert published_after is not None
    assert (
        published_after.name,
        published_after.subject,
        published_after.from_email,
        published_after.body,
        published_after.is_active,
        published_after.current_version,
        published_after.created_at,
        published_after.updated_at,
    ) == published_before
    versions_after = [
        (
            version.id,
            version.version,
            version.payload_encrypted,
            version.checksum,
            version.created_by_user_id,
            version.comment,
            version.created_at,
        )
        for version in version_service.get_version_history(
            db,
            test_org.id,
            "email_template",
            template.id,
        )
    ]
    assert versions_after == versions_before


@pytest.mark.asyncio
async def test_restore_published_version_rejects_stale_draft_revision(
    authed_client,
    db,
    test_org,
    test_user,
):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Revision fence",
        subject="Published subject",
        body="<p>Published body</p>",
        scope="org",
    )
    draft_response = await authed_client.post(f"/email-template-drafts/from-template/{template.id}")
    draft = draft_response.json()
    update_response = await authed_client.patch(
        f"/email-template-drafts/{draft['id']}",
        json={"subject": "Working subject", "expected_revision": 1},
    )
    assert update_response.status_code == 200

    response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/restore-version",
        json={"target_version": 1, "expected_revision": 1},
    )

    assert response.status_code == 409
    retained = await authed_client.get(f"/email-template-drafts/{draft['id']}")
    assert retained.status_code == 200
    assert retained.json()["subject"] == "Working subject"
    assert retained.json()["revision"] == 2


@pytest.mark.asyncio
async def test_restore_published_version_requires_linked_draft_and_existing_history(
    authed_client,
    db,
    test_org,
    test_user,
):
    new_draft_response = await authed_client.post(
        "/email-template-drafts",
        json={
            "name": "Never published",
            "subject": "Draft only",
            "body": "<p>Draft only</p>",
            "scope": "org",
        },
    )
    new_draft = new_draft_response.json()
    unlinked_response = await authed_client.post(
        f"/email-template-drafts/{new_draft['id']}/restore-version",
        json={"target_version": 1, "expected_revision": 1},
    )
    assert unlinked_response.status_code == 422

    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Missing history target",
        subject="Published subject",
        body="<p>Published body</p>",
        scope="org",
    )
    linked_draft_response = await authed_client.post(
        f"/email-template-drafts/from-template/{template.id}"
    )
    linked_draft = linked_draft_response.json()
    missing_response = await authed_client.post(
        f"/email-template-drafts/{linked_draft['id']}/restore-version",
        json={"target_version": 999, "expected_revision": 1},
    )
    assert missing_response.status_code == 404


@pytest.mark.asyncio
async def test_restore_published_version_rejects_failed_integrity_check(
    authed_client,
    db,
    test_org,
    test_user,
):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Integrity fence",
        subject="Published subject",
        body="<p>Published body</p>",
        scope="org",
    )
    draft_response = await authed_client.post(f"/email-template-drafts/from-template/{template.id}")
    draft = draft_response.json()
    version = version_service.get_version(
        db,
        test_org.id,
        "email_template",
        template.id,
        1,
    )
    assert version is not None
    version.checksum = "0" * 64
    db.commit()

    response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/restore-version",
        json={"target_version": 1, "expected_revision": 1},
    )

    assert response.status_code == 422
    retained = await authed_client.get(f"/email-template-drafts/{draft['id']}")
    assert retained.status_code == 200
    assert retained.json()["revision"] == 1
