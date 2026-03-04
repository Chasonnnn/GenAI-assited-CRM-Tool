from __future__ import annotations


import pytest

from app.services import import_service


def _column_mappings() -> list[import_service.ColumnMapping]:
    return [
        import_service.ColumnMapping(
            csv_column="full_name",
            surrogate_field="full_name",
            transformation=None,
            action="map",
        ),
        import_service.ColumnMapping(
            csv_column="email",
            surrogate_field="email",
            transformation=None,
            action="map",
        ),
    ]


def test_submit_for_approval_and_approve_flow(db, test_org, test_user):
    import_record = import_service.create_import_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="approval.csv",
        total_rows=1,
        file_content=b"full_name,email\nA,a@example.com\n",
        status="pending",
    )

    submitted = import_service.submit_for_approval(
        db=db,
        org_id=test_org.id,
        import_id=import_record.id,
        column_mappings=_column_mappings(),
        dedup_stats={"duplicate_emails_db": 0},
        unknown_column_behavior="metadata",
        backdate_created_at=True,
        default_source="manual",
        validation_mode=import_service.VALIDATION_MODE_DROP_FIELDS,
    )
    assert submitted.status == "awaiting_approval"
    assert submitted.column_mapping_snapshot is not None
    assert submitted.default_source == "manual"
    assert submitted.validation_mode == import_service.VALIDATION_MODE_DROP_FIELDS

    approved = import_service.approve_import(
        db=db,
        org_id=test_org.id,
        import_id=import_record.id,
        approved_by_user_id=test_user.id,
    )
    assert approved.status == "approved"
    assert approved.approved_by_user_id == test_user.id
    assert approved.approved_at is not None


def test_reject_and_cancel_import_flow(db, test_org, test_user):
    rejectable = import_service.create_import_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="reject.csv",
        total_rows=1,
        file_content=b"full_name,email\nA,a@example.com\n",
        status="awaiting_approval",
    )
    rejected = import_service.reject_import(
        db=db,
        org_id=test_org.id,
        import_id=rejectable.id,
        rejected_by_user_id=test_user.id,
        reason="Missing required columns",
    )
    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "Missing required columns"
    assert rejected.completed_at is not None

    cancellable = import_service.create_import_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="cancel.csv",
        total_rows=1,
        file_content=b"full_name,email\nA,a@example.com\n",
        status="pending",
    )
    cancelled = import_service.cancel_import(
        db=db,
        org_id=test_org.id,
        import_id=cancellable.id,
    )
    assert cancelled.status == "cancelled"
    assert cancelled.file_content is None
    assert cancelled.completed_at is not None


def test_queue_import_job_and_retry_guardrails(db, test_org, test_user):
    approved = import_service.create_import_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="queued.csv",
        total_rows=1,
        file_content=b"full_name,email\nA,a@example.com\n",
        status="approved",
    )
    job, already_queued = import_service.queue_import_job(db, test_org.id, approved)
    assert already_queued is False
    assert job.payload["import_id"] == str(approved.id)

    again, already_queued_second = import_service.queue_import_job(db, test_org.id, approved)
    assert already_queued_second is True
    assert again.id == job.id

    approved.status = "cancelled"
    db.add(approved)
    db.commit()
    with pytest.raises(ValueError):
        import_service.queue_import_job(db, test_org.id, approved)


def test_run_import_execution_and_inline_retry_paths(db, test_org, test_user, monkeypatch):
    import_record = import_service.create_import_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="run.csv",
        total_rows=1,
        file_content=b"full_name,email\nA,a@example.com\n",
        status="approved",
    )

    called = {"execute_import": 0, "execute_import_with_mappings": 0}

    def _fake_execute_import(**_kwargs):
        called["execute_import"] += 1
        return import_service.ImportResult()

    def _fake_execute_import_with_mappings(**_kwargs):
        called["execute_import_with_mappings"] += 1
        return import_service.ImportResult()

    monkeypatch.setattr(import_service, "execute_import", _fake_execute_import)
    monkeypatch.setattr(import_service, "execute_import_with_mappings", _fake_execute_import_with_mappings)

    import_service.run_import_execution(
        db=db,
        org_id=test_org.id,
        import_record=import_record,
        use_mappings=False,
    )
    db.refresh(import_record)
    assert called["execute_import"] == 1
    assert import_record.file_content is None

    inline_record = import_service.create_import_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="inline.csv",
        total_rows=1,
        file_content=b"full_name,email\nA,a@example.com\n",
        status="approved",
    )

    inline_called = {"count": 0}

    def _fake_run_import_execution(**_kwargs):
        inline_called["count"] += 1

    monkeypatch.setattr(import_service, "run_import_execution", _fake_run_import_execution)
    returned = import_service.run_import_inline(
        db=db,
        org_id=test_org.id,
        import_id=inline_record.id,
        dedupe_action="skip",
    )
    assert inline_called["count"] == 1
    assert returned.id == inline_record.id
