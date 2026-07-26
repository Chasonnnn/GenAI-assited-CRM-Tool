"""Operator CLI contracts for spacing-only template recovery."""

import json
from types import SimpleNamespace
from uuid import UUID

from click.testing import CliRunner

import app.cli as cli_module
from app.cli import cli


TEMPLATE_ID = UUID("392d2938-69a0-4840-8e4e-acd84e6064d1")
ORGANIZATION_ID = UUID("92000000-0000-4000-8000-000000000001")


class _Session:
    closed = False

    def close(self):
        self.closed = True


def _plan(**overrides):
    values = {
        "template_id": TEMPLATE_ID,
        "organization_id": ORGANIZATION_ID,
        "current_version": 2,
        "target_version": 1,
        "current_body_sha256": "a" * 64,
        "target_body_sha256": "b" * 64,
        "current_blank_line_count": 0,
        "target_blank_line_count": 3,
        "visible_text_equal": True,
        "variable_tokens_equal": True,
        "structural_content_equal": True,
        "eligible": True,
        "current_body": "must-never-appear",
        "target_body": "must-never-appear",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_template_spacing_recovery_defaults_to_sanitized_dry_run(monkeypatch):
    db = _Session()
    calls: list[dict] = []

    def _build(session, **kwargs):
        assert session is db
        calls.append(kwargs)
        return _plan()

    monkeypatch.setattr(cli_module, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        cli_module,
        "template_blank_line_recovery_service",
        SimpleNamespace(build_recovery_plan=_build),
        raising=False,
    )

    result = CliRunner().invoke(
        cli,
        [
            "recover-template-blank-lines",
            "--organization-id",
            str(ORGANIZATION_ID),
            "--template-id",
            str(TEMPLATE_ID),
            "--target-version",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "organization_id": ORGANIZATION_ID,
            "template_id": TEMPLATE_ID,
            "target_version": 1,
        }
    ]
    assert json.loads(result.output) == {
        "schema_version": 1,
        "mode": "dry_run",
        "template_id": str(TEMPLATE_ID),
        "current_version": 2,
        "target_version": 1,
        "current_body_sha256": "a" * 64,
        "target_body_sha256": "b" * 64,
        "current_blank_line_count": 0,
        "target_blank_line_count": 3,
        "visible_text_equal": True,
        "variable_tokens_equal": True,
        "structural_content_equal": True,
        "eligible": True,
    }
    assert "organization_id" not in result.output
    assert "must-never-appear" not in result.output
    assert db.closed is True


def test_template_spacing_recovery_apply_requires_exact_review_before_db_access(
    monkeypatch,
):
    opened = False

    def _open_session():
        nonlocal opened
        opened = True
        raise AssertionError("database must not open before review options are validated")

    monkeypatch.setattr(cli_module, "SessionLocal", _open_session)

    result = CliRunner().invoke(
        cli,
        [
            "recover-template-blank-lines",
            "--organization-id",
            str(ORGANIZATION_ID),
            "--template-id",
            str(TEMPLATE_ID),
            "--target-version",
            "1",
            "--apply",
        ],
    )

    assert result.exit_code != 0
    assert "--expected-current-version" in result.output
    assert "--expected-current-body-sha256" in result.output
    assert "--expected-target-body-sha256" in result.output
    assert "--review-reason" in result.output
    assert opened is False


def test_template_spacing_recovery_dry_run_rejects_approval_options(monkeypatch):
    opened = False

    def _open_session():
        nonlocal opened
        opened = True
        raise AssertionError("database must not open for invalid dry run")

    monkeypatch.setattr(cli_module, "SessionLocal", _open_session)

    result = CliRunner().invoke(
        cli,
        [
            "recover-template-blank-lines",
            "--organization-id",
            str(ORGANIZATION_ID),
            "--template-id",
            str(TEMPLATE_ID),
            "--target-version",
            "1",
            "--expected-current-version",
            "2",
        ],
    )

    assert result.exit_code != 0
    assert "approval options require --apply" in result.output
    assert opened is False


def test_template_spacing_recovery_apply_passes_exact_review_contract(monkeypatch):
    db = _Session()
    calls: list[dict] = []
    recovered = SimpleNamespace(id=TEMPLATE_ID, current_version=3)

    def _apply(session, **kwargs):
        assert session is db
        calls.append(kwargs)
        return recovered

    monkeypatch.setattr(cli_module, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        cli_module,
        "template_blank_line_recovery_service",
        SimpleNamespace(apply_recovery_plan=_apply),
        raising=False,
    )

    result = CliRunner().invoke(
        cli,
        [
            "recover-template-blank-lines",
            "--organization-id",
            str(ORGANIZATION_ID),
            "--template-id",
            str(TEMPLATE_ID),
            "--target-version",
            "1",
            "--apply",
            "--expected-current-version",
            "2",
            "--expected-current-body-sha256",
            f"  {'a' * 64}  ",
            "--expected-target-body-sha256",
            f"  {'b' * 64}  ",
            "--review-reason",
            "  Recover spacing lost during Studio publish  ",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "organization_id": ORGANIZATION_ID,
            "template_id": TEMPLATE_ID,
            "target_version": 1,
            "expected_current_version": 2,
            "expected_current_body_sha256": "a" * 64,
            "expected_target_body_sha256": "b" * 64,
            "review_reason": "Recover spacing lost during Studio publish",
        }
    ]
    assert json.loads(result.output) == {
        "schema_version": 1,
        "mode": "apply",
        "template_id": str(TEMPLATE_ID),
        "new_version": 3,
    }
    assert db.closed is True
