from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.encryption import hash_email, hash_phone
from app.db.enums import Role
from app.routers import settings as settings_router
from app.schemas.auth import UserSession
from app.services import search_service


def test_settings_signature_validators_and_social_links():
    with pytest.raises(Exception):
        settings_router.SocialLinkItem(platform="Bad<script>", url="https://ok.example.com")

    with pytest.raises(Exception):
        settings_router.SocialLinkItem(platform="LinkedIn", url="http://not-https.example.com")

    links = [
        settings_router.SocialLinkItem(platform="LinkedIn", url="https://linkedin.com/company/acme"),
        settings_router.SocialLinkItem(platform="LinkedIn", url="https://linkedin.com/company/acme/"),
    ]
    update = settings_router.OrgSignatureUpdate(
        signature_template="modern",
        signature_primary_color="#00AAFF",
        signature_website="https://example.com",
        signature_social_links=links,
    )
    assert update.signature_template == "modern"
    assert update.signature_primary_color == "#00AAFF"
    assert len(update.signature_social_links or []) == 1

    with pytest.raises(Exception):
        settings_router.OrgSignatureUpdate(signature_template="invalid")
    with pytest.raises(Exception):
        settings_router.OrgSignatureUpdate(signature_primary_color="#GGHHII")
    with pytest.raises(Exception):
        settings_router.OrgSignatureUpdate(signature_website=" https://bad.example.com")


def test_settings_logo_local_storage_helpers(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_router, "_get_logo_storage_backend", lambda: "local")
    monkeypatch.setattr(settings_router, "_get_local_logo_path", lambda: str(tmp_path))

    logo_url = settings_router._upload_logo_to_storage(uuid4(), b"img-bytes", "png")
    assert logo_url.startswith(settings_router.LOCAL_LOGO_URL_PREFIX)

    storage_key = settings_router._extract_local_logo_storage_key(logo_url)
    assert storage_key is not None
    full_path = Path(tmp_path) / storage_key
    assert full_path.exists()

    settings_router._delete_logo_from_storage(logo_url)
    assert not full_path.exists()

    assert settings_router._extract_local_logo_storage_key("/static/logos/org/test.png") == "logos/org/test.png"
    assert settings_router._extract_local_logo_storage_key("https://cdn.example.com/file.png") is None


def test_settings_get_org_logo_local_guards(db, test_org, monkeypatch, tmp_path):
    monkeypatch.setattr(settings_router, "_get_local_logo_path", lambda: str(tmp_path))

    with pytest.raises(HTTPException) as exc:
        settings_router.get_org_logo_local("..\\evil.png", db=db)
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        settings_router.get_org_logo_local("../evil.png", db=db)
    assert exc.value.status_code == 404

    # Successful path
    storage_key = "logos/sample-org/logo.png"
    file_path = Path(tmp_path) / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"png")

    test_org.signature_logo_url = settings_router._build_local_logo_url(storage_key)
    db.add(test_org)
    db.commit()

    response = settings_router.get_org_logo_local(storage_key, db=db)
    assert str(file_path) in str(getattr(response, "path", ""))


def test_search_service_helpers():
    from app.db.models import PipelineStage, Surrogate

    email_hash, phone_hash = search_service._extract_hashes("person@example.com 5551234567")
    assert email_hash == hash_email("person@example.com 5551234567")
    assert phone_hash == hash_phone("person@example.com 5551234567")

    no_hashes = search_service._extract_hashes("abc")
    assert no_hashes == (None, None)

    normalized = search_service.normalize_entity_types("case,note,invalid,case,attachment")
    assert normalized == ["surrogate", "note", "attachment"]
    defaults = search_service.normalize_entity_types("invalid")
    assert defaults == ["surrogate", "note", "attachment", "intended_parent"]

    perms = {"view_surrogate_notes", "view_intended_parents"}
    assert search_service._user_can_view_notes(perms) is True
    assert search_service._user_can_view_intended_parents(perms) is True
    assert search_service._can_view_post_approval(perms) is False

    developer_filter = search_service._build_surrogate_access_filter(
        role=Role.DEVELOPER.value,
        user_id=uuid4(),
        can_view_post_approval=True,
        surrogate_table=Surrogate.__table__,
        stage_table=PipelineStage.__table__,
    )
    assert str(developer_filter).lower().startswith("true")


def test_search_global_search_for_session_orchestration(monkeypatch, db, test_org, test_user):
    captured = {"phi_logged": False}

    monkeypatch.setattr(
        "app.services.permission_service.get_effective_permissions",
        lambda **kwargs: {"view_surrogate_notes"},
    )
    monkeypatch.setattr(
        search_service,
        "global_search",
        lambda **kwargs: {"query": kwargs["query"], "total": 1, "results": [{"entity_type": "surrogate"}]},
    )
    monkeypatch.setattr(
        "app.services.phi_access_service.log_phi_access",
        lambda **kwargs: captured.__setitem__("phi_logged", True),
    )

    session = UserSession(
        user_id=test_user.id,
        org_id=test_org.id,
        role=Role.DEVELOPER,
        email=test_user.email,
        display_name=test_user.display_name,
        token_version=1,
        mfa_verified=True,
    )

    result = search_service.global_search_for_session(
        db=db,
        request=None,
        session=session,
        q="alpha",
        types="case",
        limit=10,
        offset=0,
    )
    assert result["total"] == 1
    assert captured["phi_logged"] is True
