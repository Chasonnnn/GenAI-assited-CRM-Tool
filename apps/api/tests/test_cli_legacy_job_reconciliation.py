"""Operator CLI contracts for legacy job-claim reconciliation."""

from datetime import datetime, timezone
import json
from types import SimpleNamespace
from uuid import UUID

from click.testing import CliRunner

import app.cli as cli_module
from app.cli import cli


def test_reconciliation_command_defaults_to_aggregate_only_dry_run(monkeypatch):
    job_id = UUID("91000000-0000-4000-8000-000000000001")
    org_id = UUID("92000000-0000-4000-8000-000000000001")
    evaluated_at = datetime(2026, 7, 25, 22, 44, tzinfo=timezone.utc)
    report = SimpleNamespace(
        mode="dry_run",
        fingerprint="a" * 64,
        count=1,
        decisions=(
            SimpleNamespace(
                job_id=job_id,
                organization_id=org_id,
                job_type="workflow_email",
                target_status="failed",
                reason_code="workflow_email_no_local_delivery_evidence",
                non_replayable=True,
            ),
        ),
        evaluated_at=evaluated_at,
    )
    calls: list[dict] = []

    class _Session:
        closed = False

        def close(self):
            self.closed = True

    db = _Session()

    def _reconcile(session, **kwargs):
        assert session is db
        calls.append(kwargs)
        return report

    monkeypatch.setattr(cli_module, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        cli_module,
        "legacy_job_reconciliation_service",
        SimpleNamespace(reconcile_legacy_running_jobs=_reconcile),
        raising=False,
    )

    result = CliRunner().invoke(
        cli,
        [
            "reconcile-legacy-job-claims",
            "--stale-before",
            "2026-07-24T00:00:00+00:00",
            "--evaluated-at",
            evaluated_at.isoformat(),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "stale_before": datetime(2026, 7, 24, tzinfo=timezone.utc),
            "apply": False,
            "evaluated_at": evaluated_at,
            "expected_count": None,
            "expected_fingerprint": None,
            "review_reason": None,
        }
    ]
    assert "mode=dry_run" in result.output
    assert "count=1" in result.output
    assert f"fingerprint={'a' * 64}" in result.output
    assert "workflow_email=1" in result.output
    assert "workflow_email_no_local_delivery_evidence=1" in result.output
    assert str(job_id) not in result.output
    assert str(org_id) not in result.output
    assert db.closed is True


def test_reconciliation_manifest_is_explicit_sanitized_dry_run_json(monkeypatch):
    job_id = UUID("91000000-0000-4000-8000-000000000001")
    org_id = UUID("92000000-0000-4000-8000-000000000001")
    stale_before = datetime(2026, 7, 24, tzinfo=timezone.utc)
    evaluated_at = datetime(2026, 7, 25, 22, 44, tzinfo=timezone.utc)
    run_at = datetime(2026, 5, 20, 5, 4, tzinfo=timezone.utc)
    fingerprint = "c" * 64
    report = SimpleNamespace(
        mode="dry_run",
        fingerprint=fingerprint,
        count=1,
        decisions=(
            SimpleNamespace(
                job_id=job_id,
                organization_id=org_id,
                job_type="workflow_email",
                run_at=run_at,
                attempts=2,
                evidence_flags={
                    "email_log_exists": True,
                    "email_log_has_provider_id": False,
                    "email_log_has_sent_at": False,
                },
                target_status="failed",
                reason_code="workflow_email_outcome_unknown",
                non_replayable=True,
                recipient_email="must-never-appear@example.test",
                payload={"secret": "must-never-appear"},
            ),
        ),
        evaluated_at=evaluated_at,
        applied_at=None,
    )

    class _Session:
        closed = False

        def close(self):
            self.closed = True

    db = _Session()
    monkeypatch.setattr(cli_module, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        cli_module,
        "legacy_job_reconciliation_service",
        SimpleNamespace(reconcile_legacy_running_jobs=lambda _db, **_kwargs: report),
        raising=False,
    )

    result = CliRunner().invoke(
        cli,
        [
            "reconcile-legacy-job-claims",
            "--stale-before",
            stale_before.isoformat(),
            "--evaluated-at",
            evaluated_at.isoformat(),
            "--manifest",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "schema_version": 1,
        "mode": "dry_run",
        "stale_before": stale_before.isoformat(),
        "evaluated_at": evaluated_at.isoformat(),
        "count": 1,
        "fingerprint": fingerprint,
        "decisions": [
            {
                "job_id": str(job_id),
                "organization_id": str(org_id),
                "job_type": "workflow_email",
                "run_at": run_at.isoformat(),
                "attempts": 2,
                "evidence_flags": {
                    "email_log_exists": True,
                    "email_log_has_provider_id": False,
                    "email_log_has_sent_at": False,
                },
                "target_status": "failed",
                "reason_code": "workflow_email_outcome_unknown",
                "non_replayable": True,
            }
        ],
    }
    assert "must-never-appear" not in result.output
    assert "must-never-appear@example.test" not in result.output
    assert db.closed is True


def test_reconciliation_manifest_is_rejected_on_apply_before_db_access(monkeypatch):
    opened = False

    def _open_session():
        nonlocal opened
        opened = True
        raise AssertionError("database must not open for invalid manifest apply")

    monkeypatch.setattr(cli_module, "SessionLocal", _open_session)
    result = CliRunner().invoke(
        cli,
        [
            "reconcile-legacy-job-claims",
            "--stale-before",
            "2026-07-24T00:00:00+00:00",
            "--apply",
            "--expected-count",
            "0",
            "--expected-fingerprint",
            "d" * 64,
            "--review-reason",
            "Approved production cutover",
            "--manifest",
        ],
    )

    assert result.exit_code != 0
    assert "--manifest is available only for dry runs" in result.output
    assert opened is False


def test_reconciliation_apply_is_rejected_before_db_access_without_review_contract(monkeypatch):
    opened = False

    def _open_session():
        nonlocal opened
        opened = True
        raise AssertionError("database must not open before apply options are validated")

    monkeypatch.setattr(cli_module, "SessionLocal", _open_session)

    result = CliRunner().invoke(
        cli,
        [
            "reconcile-legacy-job-claims",
            "--stale-before",
            "2026-07-24T00:00:00+00:00",
            "--apply",
        ],
    )

    assert result.exit_code != 0
    assert "--expected-count" in result.output
    assert "--expected-fingerprint" in result.output
    assert "--review-reason" in result.output
    assert opened is False


def test_reconciliation_apply_passes_the_exact_review_contract(monkeypatch):
    evaluated_at = datetime(2026, 7, 25, 22, 44, tzinfo=timezone.utc)
    fingerprint = "b" * 64
    report = SimpleNamespace(
        mode="apply",
        fingerprint=fingerprint,
        count=0,
        decisions=(),
        evaluated_at=evaluated_at,
    )
    calls: list[dict] = []

    class _Session:
        closed = False

        def close(self):
            self.closed = True

    db = _Session()

    def _reconcile(session, **kwargs):
        assert session is db
        calls.append(kwargs)
        return report

    monkeypatch.setattr(cli_module, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        cli_module,
        "legacy_job_reconciliation_service",
        SimpleNamespace(reconcile_legacy_running_jobs=_reconcile),
        raising=False,
    )

    result = CliRunner().invoke(
        cli,
        [
            "reconcile-legacy-job-claims",
            "--stale-before",
            "2026-07-24T00:00:00+00:00",
            "--evaluated-at",
            evaluated_at.isoformat(),
            "--apply",
            "--expected-count",
            "0",
            "--expected-fingerprint",
            f"  {fingerprint}  ",
            "--review-reason",
            "  Approved production cutover  ",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "stale_before": datetime(2026, 7, 24, tzinfo=timezone.utc),
            "apply": True,
            "evaluated_at": evaluated_at,
            "expected_count": 0,
            "expected_fingerprint": fingerprint,
            "review_reason": "Approved production cutover",
        }
    ]
    assert f"mode=apply count=0 fingerprint={fingerprint}" in result.output
    assert db.closed is True
