from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from app.db.enums import Role
from app.db.models import Membership, OrgInvite, Organization, User


class _SessionProxy:
    """Keep shared pytest DB session open when CLI closes SessionLocal."""

    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def close(self) -> None:
        return None


@pytest.fixture
def _cli_db(monkeypatch, db):
    from app import cli as cli_module

    monkeypatch.setattr(cli_module, "SessionLocal", lambda: _SessionProxy(db))
    return cli_module


@pytest.fixture
def _echo_log(monkeypatch, _cli_db):
    messages: list[str] = []
    monkeypatch.setattr(_cli_db.click, "echo", lambda msg="": messages.append(str(msg)))
    return messages


def _create_org(db, slug: str = "acme", name: str = "Acme") -> Organization:
    org = Organization(id=uuid4(), slug=slug, name=name)
    db.add(org)
    db.flush()
    return org


def _create_user_with_membership(
    db,
    *,
    org: Organization,
    email: str,
    role: Role,
) -> User:
    user = User(
        id=uuid4(),
        email=email,
        display_name="Test User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid4(),
            user_id=user.id,
            organization_id=org.id,
            role=role,
            is_active=True,
        )
    )
    db.flush()
    return user


def test_cli_create_org_rejects_invalid_slug(monkeypatch, _cli_db, _echo_log):
    monkeypatch.setattr(
        _cli_db.org_service, "validate_slug", lambda _slug: (_ for _ in ()).throw(ValueError("bad"))
    )
    _cli_db.create_org.callback(
        name="Acme Corp",
        slug="bad slug",
        admin_email="admin@example.com",
        developer_email=None,
    )
    assert any("Invalid slug" in line for line in _echo_log)


def test_cli_create_org_rejects_existing_slug(db, _cli_db, _echo_log):
    _create_org(db, slug="acme")
    db.commit()

    _cli_db.create_org.callback(
        name="Acme Corp",
        slug="acme",
        admin_email="admin@example.com",
        developer_email=None,
    )
    assert any("already exists" in line for line in _echo_log)


def test_cli_create_org_admin_equals_developer(monkeypatch, db, _cli_db):
    def _fake_create_org(session, name: str, slug: str):
        return _create_org(session, slug=slug, name=name)

    monkeypatch.setattr(_cli_db.org_service, "create_org", _fake_create_org)
    monkeypatch.setattr(
        _cli_db.org_service, "get_org_portal_base_url", lambda _org: "https://acme.test"
    )

    _cli_db.create_org.callback(
        name="Acme Corp",
        slug="acme",
        admin_email="dev@example.com",
        developer_email="dev@example.com",
    )

    org = db.query(Organization).filter(Organization.slug == "acme").one()
    invites = db.query(OrgInvite).filter(OrgInvite.organization_id == org.id).all()
    assert len(invites) == 1
    assert invites[0].email == "dev@example.com"
    assert invites[0].role == Role.DEVELOPER.value


def test_cli_create_org_success_with_developer_invite(monkeypatch, db, _cli_db):
    def _fake_create_org(session, name: str, slug: str):
        return _create_org(session, slug=slug, name=name)

    monkeypatch.setattr(_cli_db.org_service, "create_org", _fake_create_org)
    monkeypatch.setattr(
        _cli_db.org_service, "get_org_portal_base_url", lambda _org: "https://acme.test"
    )

    _cli_db.create_org.callback(
        name="Acme Corp",
        slug="acme",
        admin_email="admin@example.com",
        developer_email="dev@example.com",
    )

    org = db.query(Organization).filter(Organization.slug == "acme").one()
    invites = (
        db.query(OrgInvite)
        .filter(OrgInvite.organization_id == org.id)
        .order_by(OrgInvite.email.asc())
        .all()
    )
    assert [invite.email for invite in invites] == ["admin@example.com", "dev@example.com"]
    assert {invite.role for invite in invites} == {Role.ADMIN.value, Role.DEVELOPER.value}


def test_cli_promote_to_developer_not_found(_cli_db, _echo_log):
    _cli_db.promote_to_developer.callback(email="missing@example.com", org_slug=None)
    assert any("User not found" in line for line in _echo_log)


def test_cli_promote_to_developer_success(db, _cli_db):
    org = _create_org(db, slug="acme")
    user = _create_user_with_membership(
        db,
        org=org,
        email="member@example.com",
        role=Role.ADMIN,
    )
    db.commit()

    _cli_db.promote_to_developer.callback(email="member@example.com", org_slug="acme")

    membership = db.query(Membership).filter(Membership.user_id == user.id).one()
    assert membership.role == Role.DEVELOPER.value


def test_cli_revoke_sessions_updates_token_version(db, _cli_db):
    org = _create_org(db, slug="acme")
    user = _create_user_with_membership(
        db,
        org=org,
        email="session@example.com",
        role=Role.DEVELOPER,
    )
    old_version = user.token_version
    db.commit()

    _cli_db.revoke_sessions.callback(email=user.email)
    db.refresh(user)
    assert user.token_version == old_version + 1


def test_cli_update_meta_page_token_rejects_missing_encryption(monkeypatch, _cli_db, _echo_log):
    monkeypatch.setattr(
        _cli_db, "SessionLocal", lambda: (_ for _ in ()).throw(AssertionError("should not open DB"))
    )
    from app import cli as cli_module
    from app.core import encryption

    monkeypatch.setattr(encryption, "is_encryption_configured", lambda: False)
    cli_module.update_meta_page_token.callback(
        page_id="p1",
        access_token="token",
        org_slug="acme",
        page_name=None,
        expires_days=60,
    )
    assert any("META_ENCRYPTION_KEY not configured" in line for line in _echo_log)


def test_cli_update_meta_page_token_create_and_update(monkeypatch, db, _cli_db):
    from app.db.models import MetaPageMapping
    from app.core import encryption

    org = _create_org(db, slug="acme")
    db.commit()

    monkeypatch.setattr(encryption, "is_encryption_configured", lambda: True)
    monkeypatch.setattr(encryption, "encrypt_token", lambda token: f"enc:{token}")

    _cli_db.update_meta_page_token.callback(
        page_id="page-123",
        access_token="first-token",
        org_slug="acme",
        page_name="First Name",
        expires_days=7,
    )
    created = db.query(MetaPageMapping).filter(MetaPageMapping.page_id == "page-123").one()
    assert created.organization_id == org.id
    assert created.access_token_encrypted == "enc:first-token"
    assert created.page_name == "First Name"

    _cli_db.update_meta_page_token.callback(
        page_id="page-123",
        access_token="second-token",
        org_slug="acme",
        page_name="Renamed Page",
        expires_days=30,
    )
    updated = db.query(MetaPageMapping).filter(MetaPageMapping.page_id == "page-123").one()
    assert updated.access_token_encrypted == "enc:second-token"
    assert updated.page_name == "Renamed Page"


def test_cli_deactivate_meta_page(monkeypatch, db, _cli_db):
    from app.db.models import MetaPageMapping

    org = _create_org(db, slug="acme")
    mapping = MetaPageMapping(
        id=uuid4(),
        organization_id=org.id,
        page_id="page-123",
        page_name="Page",
        access_token_encrypted="enc:token",
        token_expires_at=datetime.now(timezone.utc),
        is_active=True,
    )
    db.add(mapping)
    db.commit()

    _cli_db.deactivate_meta_page.callback(page_id="missing")
    db.refresh(mapping)
    assert mapping.is_active is True

    _cli_db.deactivate_meta_page.callback(page_id="page-123")
    db.refresh(mapping)
    assert mapping.is_active is False


def test_cli_backfill_permissions(monkeypatch, db, _cli_db):
    acme = _create_org(db, slug="acme")
    beta = _create_org(db, slug="beta")
    db.commit()

    created: list[uuid.UUID] = []

    def _seed_role_defaults(session, org_id):
        created.append(org_id)
        return 3

    from app.services import permission_service

    monkeypatch.setattr(permission_service, "seed_role_defaults", _seed_role_defaults)
    _cli_db.backfill_permissions.callback(dry_run=False)
    assert acme.id in created
    assert beta.id in created


def _create_orphaned_matched_records(db, *, org: Organization, user: User):
    from app.db.enums import IntendedParentStatus
    from app.schemas.surrogate import SurrogateCreate
    from app.services import ip_service, pipeline_service, surrogate_service

    pipeline = pipeline_service.get_or_create_default_pipeline(db, org.id, user.id)
    matched_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "matched")
    ready_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "ready_to_match")
    assert matched_stage is not None
    assert ready_stage is not None

    surrogate = surrogate_service.create_surrogate(
        db,
        org.id,
        user.id,
        SurrogateCreate(
            full_name="Orphaned Matched Surrogate",
            email="orphaned-surrogate@example.com",
        ),
    )
    intended_parent = ip_service.create_intended_parent(
        db,
        org.id,
        user.id,
        full_name="Orphaned Matched IP",
        email="orphaned-ip@example.com",
    )

    surrogate.stage_id = matched_stage.id
    surrogate.status_label = matched_stage.label
    intended_parent.status = IntendedParentStatus.MATCHED.value
    db.commit()

    return surrogate, intended_parent, matched_stage, ready_stage


def test_cli_repair_matched_without_match_dry_run_reports_without_mutating(db, _cli_db, _echo_log):
    from app.db.enums import IntendedParentStatus

    org = _create_org(db, slug="acme")
    user = _create_user_with_membership(
        db,
        org=org,
        email="repair-preview@example.com",
        role=Role.DEVELOPER,
    )
    surrogate, intended_parent, matched_stage, _ = _create_orphaned_matched_records(
        db,
        org=org,
        user=user,
    )

    _cli_db.repair_matched_without_match.callback(org_slug="acme", apply=False)

    db.refresh(surrogate)
    db.refresh(intended_parent)
    assert surrogate.stage_id == matched_stage.id
    assert intended_parent.status == IntendedParentStatus.MATCHED.value
    assert any("DRY RUN" in line for line in _echo_log)
    assert any("Found 1 orphaned matched surrogate(s)" in line for line in _echo_log)
    assert any("Found 1 orphaned matched intended parent(s)" in line for line in _echo_log)


def test_cli_repair_matched_without_match_apply_resets_entities_and_records_history(
    db, _cli_db, _echo_log
):
    from app.db.enums import IntendedParentStatus
    from app.db.models import IntendedParentStatusHistory, SurrogateStatusHistory

    org = _create_org(db, slug="acme")
    user = _create_user_with_membership(
        db,
        org=org,
        email="repair-apply@example.com",
        role=Role.DEVELOPER,
    )
    surrogate, intended_parent, _, ready_stage = _create_orphaned_matched_records(
        db,
        org=org,
        user=user,
    )

    _cli_db.repair_matched_without_match.callback(org_slug="acme", apply=True)

    db.refresh(surrogate)
    db.refresh(intended_parent)
    assert surrogate.stage_id == ready_stage.id
    assert surrogate.status_label == ready_stage.label
    assert intended_parent.status == IntendedParentStatus.READY_TO_MATCH.value

    surrogate_history = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id == surrogate.id)
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    assert surrogate_history is not None
    assert surrogate_history.to_stage_id == ready_stage.id
    assert surrogate_history.reason == "Repair orphaned matched record without accepted Match"

    ip_history = (
        db.query(IntendedParentStatusHistory)
        .filter(IntendedParentStatusHistory.intended_parent_id == intended_parent.id)
        .order_by(IntendedParentStatusHistory.recorded_at.desc())
        .first()
    )
    assert ip_history is not None
    assert ip_history.new_status == IntendedParentStatus.READY_TO_MATCH.value
    assert ip_history.reason == "Repair orphaned matched record without accepted Match"

    assert any(
        "Repaired 1 orphaned matched surrogate(s) and 1 intended parent(s)" in line
        for line in _echo_log
    )


def test_cli_replay_failed_jobs_paths(monkeypatch, _cli_db, _echo_log):
    fake_jobs = [
        SimpleNamespace(id=uuid4(), job_type="meta_form_sync", attempts=2, max_attempts=5),
        SimpleNamespace(id=uuid4(), job_type="gmail_sync", attempts=1, max_attempts=3),
    ]

    monkeypatch.setattr(
        _cli_db.job_service, "list_dead_letter_jobs", lambda *args, **kwargs: fake_jobs
    )
    monkeypatch.setattr(
        _cli_db.job_service, "replay_failed_jobs", lambda *args, **kwargs: fake_jobs[:1]
    )

    _cli_db.replay_failed_jobs_cli.callback(
        org_id="not-a-uuid",
        job_type=None,
        limit=5,
        reason="manual_retry",
        dry_run=False,
    )
    assert any("Invalid org UUID" in line for line in _echo_log)

    org_id = str(uuid4())
    _cli_db.replay_failed_jobs_cli.callback(
        org_id=org_id,
        job_type=None,
        limit=5,
        reason="manual_retry",
        dry_run=True,
    )
    assert any("Dry run complete" in line for line in _echo_log)

    _cli_db.replay_failed_jobs_cli.callback(
        org_id=org_id,
        job_type=None,
        limit=5,
        reason="manual_retry",
        dry_run=False,
    )
    assert any("Replayed 1 failed job(s)" in line for line in _echo_log)


def test_transcript_storage_inline_and_offloaded(monkeypatch):
    from app.services import transcript_storage_service as svc

    uploaded: dict[str, bytes] = {}
    monkeypatch.setattr(
        svc, "_upload_file", lambda key, content: uploaded.__setitem__(key, content)
    )

    interview_id = uuid4()

    html_inline = "<p>small</p>"
    inline = svc.store_transcript(interview_id, 1, html_inline, "small")
    assert inline == (html_inline, "small", None)

    large_html = "x" * (svc.OFFLOAD_THRESHOLD_BYTES + 100)
    html_db, text_db, storage_key = svc.store_transcript(interview_id, 2, large_html, "large")
    assert html_db is None
    assert text_db == "large"
    assert storage_key == f"transcripts/{interview_id}/v2.json"
    assert storage_key in uploaded


def test_transcript_storage_load_and_delete_paths(monkeypatch):
    from app.services import transcript_storage_service as svc

    payload = {"html": "<p>loaded</p>", "text": "fallback"}
    monkeypatch.setattr(svc, "_download_file", lambda _key: json.dumps(payload).encode("utf-8"))
    assert svc.load_transcript(None, None, "transcripts/1/v1.json") == ("<p>loaded</p>", "fallback")

    monkeypatch.setattr(
        svc, "_download_file", lambda _key: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    assert svc.load_transcript(None, "text-only", "transcripts/1/v1.json") == (None, "text-only")

    monkeypatch.setattr(svc, "_delete_file", lambda _key: None)
    assert svc.delete_transcript("transcripts/1/v1.json") is True
    monkeypatch.setattr(
        svc, "_delete_file", lambda _key: (_ for _ in ()).throw(RuntimeError("fail"))
    )
    assert svc.delete_transcript("transcripts/1/v1.json") is False
    assert svc.delete_transcript("") is False


def test_transcript_storage_local_backend_roundtrip(monkeypatch, tmp_path):
    from app.services import transcript_storage_service as svc

    monkeypatch.setattr(svc, "_get_storage_backend", lambda: "local")
    monkeypatch.setattr(svc, "_get_local_storage_path", lambda: str(tmp_path))

    key = "transcripts/abc/v1.json"
    content = b'{"ok":true}'
    svc._upload_file(key, content)
    assert svc._download_file(key) == content

    svc._delete_file(key)
    with pytest.raises(FileNotFoundError):
        svc._download_file(key)


def test_transcript_storage_s3_backend_paths(monkeypatch):
    from app.services import transcript_storage_service as svc

    calls: list[tuple[str, dict]] = []

    class _S3:
        def put_object(self, **kwargs):
            calls.append(("put", kwargs))

        def get_object(self, **kwargs):
            calls.append(("get", kwargs))
            return {"Body": SimpleNamespace(read=lambda: b'{"html":"h","text":"t"}')}

        def delete_object(self, **kwargs):
            calls.append(("delete", kwargs))
            return None

        def list_objects_v2(self, **kwargs):
            calls.append(("list", kwargs))
            return {
                "Contents": [
                    {"Key": "transcripts/x/v1.json"},
                    {"Key": "transcripts/x/v2.json"},
                    {"Key": "transcripts/x/not-a-version"},
                ]
            }

    monkeypatch.setattr(svc, "_get_storage_backend", lambda: "s3")
    monkeypatch.setattr(svc, "_get_s3_client", lambda: _S3())
    monkeypatch.setattr(svc, "_get_bucket", lambda: "bucket")

    svc._upload_file("transcripts/x/v1.json", b"abc")
    assert svc._download_file("transcripts/x/v1.json")
    svc._delete_file("transcripts/x/v1.json")
    deleted = svc.cleanup_old_versions(
        uuid.UUID("00000000-0000-0000-0000-0000000000aa"), keep_versions=[2]
    )
    assert deleted == 1
    assert any(call[0] == "put" for call in calls)
    assert any(call[0] == "delete" for call in calls)


def test_transcript_storage_s3_download_no_such_key(monkeypatch):
    from app.services import transcript_storage_service as svc

    class _S3:
        def get_object(self, **kwargs):
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

    monkeypatch.setattr(svc, "_get_storage_backend", lambda: "s3")
    monkeypatch.setattr(svc, "_get_s3_client", lambda: _S3())
    monkeypatch.setattr(svc, "_get_bucket", lambda: "bucket")

    with pytest.raises(FileNotFoundError):
        svc._download_file("transcripts/missing/v1.json")


def test_transcript_storage_local_cleanup_versions(monkeypatch, tmp_path):
    from app.services import transcript_storage_service as svc

    interview_id = uuid4()
    root = tmp_path / "transcripts" / str(interview_id)
    os.makedirs(root, exist_ok=True)
    (root / "v1.json").write_text("{}")
    (root / "v2.json").write_text("{}")
    (root / "junk.txt").write_text("{}")

    monkeypatch.setattr(svc, "_get_storage_backend", lambda: "local")
    monkeypatch.setattr(svc, "_get_local_storage_path", lambda: str(tmp_path))

    deleted = svc.cleanup_old_versions(interview_id, keep_versions=[2])
    assert deleted == 1
    assert (root / "v2.json").exists()
    assert not (root / "v1.json").exists()
