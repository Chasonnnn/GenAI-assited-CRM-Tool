from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.enums import TaskType
from app.db.models import EmailTemplate
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import compliance_service, email_service, task_service


def test_compliance_masking_and_redaction_helpers():
    assert compliance_service._mask_email("user@example.com") == "***@example.com"
    assert compliance_service._mask_phone("+1 (212) 555-1212") == "***-***-1212"
    assert compliance_service._mask_ip("192.168.10.20") == "192.168.x.x"
    assert compliance_service._mask_name("Jane Doe").startswith("J.")
    assert compliance_service._mask_id_last4("123-45-6789").endswith("6789")

    free_text = "Email jane@example.com phone 212-555-1212 ssn 123-45-6789 ip 10.1.2.3"
    redacted = compliance_service._redact_free_text(free_text)
    assert "***@example.com" in redacted
    assert "***-***-1212" in redacted
    assert "***-**-****" in redacted
    assert "10.1.x.x" in redacted

    payload = {
        "email": "jane@example.com",
        "created_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
        "details": {"phone": "212-555-1212"},
    }
    value = compliance_service._redact_value("details", payload, person_linked=True)
    assert value["email"] == "***@example.com"
    assert value["details"]["phone"].endswith("1212")

    assert compliance_service._csv_safe("=SUM(A1:A3)").startswith("'=")
    assert compliance_service._serialize_value({"a": 1}) == '{"a":1}'
    assert compliance_service._serialize_json_value(
        {"t": datetime(2026, 1, 2, tzinfo=timezone.utc)}
    )["t"].startswith("2026-01-02")


def test_compliance_build_export_rows_and_storage_helpers(monkeypatch, tmp_path, db, test_org):
    actor_id = uuid4()
    now = datetime.now(timezone.utc)
    logs = [
        SimpleNamespace(
            id=uuid4(),
            organization_id=test_org.id,
            event_type="settings_changed",
            actor_user_id=actor_id,
            target_type="surrogate",
            target_id=uuid4(),
            details={"email": "jane@example.com"},
            ip_address="10.0.0.1",
            user_agent="UA",
            request_id=uuid4(),
            prev_hash=None,
            entry_hash="hash-1",
            before_version_id=None,
            after_version_id=None,
            created_at=now,
        ),
        SimpleNamespace(
            id=uuid4(),
            organization_id=test_org.id,
            event_type="settings_changed",
            actor_user_id=actor_id,
            target_type="surrogate",
            target_id=uuid4(),
            details={"phone": "212-555-1212"},
            ip_address="10.0.0.2",
            user_agent="UA2",
            request_id=uuid4(),
            prev_hash="hash-1",
            entry_hash="hash-2",
            before_version_id=None,
            after_version_id=None,
            created_at=now,
        ),
    ]
    monkeypatch.setattr(
        compliance_service, "_resolve_actor_names", lambda _db, _logs: {actor_id: "Actor"}
    )
    rows, meta = compliance_service._build_export_rows(
        db, logs, redact_mode=compliance_service.REDACT_MODE_REDACTED
    )
    assert len(rows) == 2
    assert meta["chain_contiguous"] is True
    assert rows[0]["actor_name"].startswith("A.")

    monkeypatch.setattr(compliance_service.settings, "EXPORT_LOCAL_DIR", str(tmp_path))
    export_dir = compliance_service._ensure_local_export_dir(test_org.id)
    assert Path(export_dir).exists()

    monkeypatch.setattr(compliance_service, "find_spec", lambda name: None)
    with pytest.raises(RuntimeError, match="boto3 is required"):
        compliance_service._require_boto3()

    monkeypatch.setattr(compliance_service, "find_spec", lambda name: object())
    compliance_service._require_boto3()


def test_email_template_sanitization_and_lifecycle(monkeypatch, db, test_org, test_user):
    version_calls: list[dict] = []
    monkeypatch.setattr(
        "app.services.version_service.create_version",
        lambda **kwargs: (
            version_calls.append(kwargs)
            or SimpleNamespace(version=kwargs.get("payload", {}).get("version", 1))
        ),
    )
    monkeypatch.setattr(
        "app.services.version_service.check_version", lambda current, expected: None
    )

    cleaned = email_service.sanitize_template_html("<script>alert(1)</script><p><br></p>")
    assert "script" not in cleaned.lower()
    assert "&nbsp;" in cleaned
    assert (
        email_service._normalize_from_email("  Sender <sender@example.com> ")
        == "Sender <sender@example.com>"
    )
    with pytest.raises(ValueError, match="Invalid from_email"):
        email_service._normalize_from_email("bad-email")

    template = email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Lifecycle",
        subject="Subject",
        body="<p>Body</p>",
        from_email="sender@example.com",
        scope="org",
    )
    assert isinstance(template, EmailTemplate)

    updated = email_service.update_template(
        db=db,
        template=template,
        user_id=test_user.id,
        name="Lifecycle Updated",
        body="<p>Updated</p>",
        from_email="sender2@example.com",
        expected_version=template.current_version,
    )
    assert updated.name == "Lifecycle Updated"
    assert len(version_calls) >= 2


def test_task_service_state_paths(monkeypatch, db, test_org, test_user):
    sync_calls = {"sync": 0, "delete": 0, "pull": 0}

    monkeypatch.setattr(
        "app.services.google_tasks_sync_service.sync_platform_task_to_google",
        lambda *_args, **_kwargs: sync_calls.__setitem__("sync", sync_calls["sync"] + 1),
    )
    monkeypatch.setattr(
        "app.services.google_tasks_sync_service.delete_platform_task_from_google",
        lambda *_args, **_kwargs: sync_calls.__setitem__("delete", sync_calls["delete"] + 1),
    )
    monkeypatch.setattr(
        "app.services.google_tasks_sync_service.sync_google_tasks_for_user",
        lambda *_args, **_kwargs: sync_calls.__setitem__("pull", sync_calls["pull"] + 1),
    )

    data = TaskCreate(title="Call client", description="desc", task_type=TaskType.OTHER)
    task = task_service.create_task(db, test_org.id, test_user.id, data)
    assert task.id is not None
    assert sync_calls["sync"] == 1

    updated = task_service.update_task(
        db,
        task,
        TaskUpdate(title="Call client updated", description=None),
        actor_user_id=test_user.id,
    )
    assert updated.title == "Call client updated"

    completed = task_service.complete_task(db, task, test_user.id, commit=True)
    assert completed.is_completed is True
    uncompleted = task_service.uncomplete_task(db, task)
    assert uncompleted.is_completed is False

    # Best-effort helpers should never raise.
    task_service._delete_task_from_google_best_effort(db, task)
    task_service._pull_google_tasks_for_user_best_effort(db, test_user.id, test_org.id)
    assert sync_calls["delete"] == 1
    assert sync_calls["pull"] == 1

    assert task_service._coerce_task_type(None) == TaskType.OTHER
    assert task_service._coerce_task_type("unknown") == TaskType.OTHER

    with pytest.raises(ValueError, match="owner_type and owner_id"):
        task_service.update_task(
            db,
            task,
            TaskUpdate(owner_type="user", owner_id=None),
            actor_user_id=test_user.id,
        )
