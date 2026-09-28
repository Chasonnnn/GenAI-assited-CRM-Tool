"""Donor intake review: canonical source, lifecycle, linking, applications, and recovery."""

import uuid

import pytest

from app.core.config import settings
from app.db.models import AutomationWorkflow, Donor, FormSubmission, IntakeLead
from app.services import alert_service, workflow_triggers
from tests.test_hosted_donor_forms import _create_donor_form, _submit_donor_form


@pytest.fixture(autouse=True)
def _local_unscanned_storage(monkeypatch, tmp_path):
    from app.core.rate_limit import limiter

    limiter.reset()
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False, raising=False)


def _disable_generated_routing(db, form_id: str) -> None:
    db.query(AutomationWorkflow).filter(
        AutomationWorkflow.system_key == f"shared_intake_routing:{form_id}"
    ).update({AutomationWorkflow.is_enabled: False})
    db.commit()


async def _manual_submission(client, db, *, kind="egg_donor", email="review@example.com"):
    form_id, slug = await _create_donor_form(client, lead_kind=kind)
    _disable_generated_routing(db, form_id)
    response = await _submit_donor_form(client, slug=slug, email=email)
    assert response.status_code == 200, response.text
    return form_id, slug, db.get(FormSubmission, uuid.UUID(response.json()["id"]))


async def _create_lead_and_promote(client, submission_id, *, source="hosted_form"):
    resolved = await client.post(
        f"/forms/submissions/{submission_id}/match/resolve",
        json={"create_intake_lead": True},
    )
    assert resolved.status_code == 200, resolved.text
    lead_id = resolved.json()["submission"]["intake_lead_id"]
    promoted = await client.post(f"/forms/intake-leads/{lead_id}/promote", json={"source": source})
    return lead_id, promoted


@pytest.mark.asyncio
async def test_manual_donor_intake_uses_canonical_website_source(authed_client, db):
    _, _, submission = await _manual_submission(authed_client, db)

    lead_id, promoted = await _create_lead_and_promote(authed_client, submission.id)
    assert promoted.status_code == 200, promoted.text

    lead = db.get(IntakeLead, uuid.UUID(lead_id))
    assert lead.source == "website"
    assert lead.source_metadata["source"] == "manual_review_resolution"
    donor = db.get(Donor, uuid.UUID(promoted.json()["donor_id"]))
    assert donor.source == "website"


@pytest.mark.asyncio
async def test_retry_created_donor_lead_uses_canonical_website_source(authed_client, db):
    _, _, submission = await _manual_submission(authed_client, db)
    submission.match_status = "ambiguous_review"
    submission.match_reason = "donor_no_deterministic_match"
    db.commit()

    retried = await authed_client.post(
        f"/forms/submissions/{submission.id}/match/retry",
        json={
            "unlink_surrogate": False,
            "rerun_auto_match": True,
            "create_intake_lead_if_unmatched": True,
        },
    )
    assert retried.status_code == 200, retried.text
    lead = db.get(IntakeLead, uuid.UUID(retried.json()["submission"]["intake_lead_id"]))
    assert lead.source == "website"
    assert lead.source_metadata["source"] == "manual_retry_resolution"


@pytest.mark.asyncio
async def test_hosted_promotion_alerts_when_donor_side_effects_fail(
    authed_client, db, test_org, monkeypatch, caplog
):
    _, _, submission = await _manual_submission(authed_client, db, email="alerts@example.com")
    alerts: list[dict] = []

    def fail(*_args, **_kwargs):
        raise RuntimeError("synthetic failure for alerts@example.com")

    monkeypatch.setattr(workflow_triggers, "trigger_donor_created", fail)
    monkeypatch.setattr(workflow_triggers, "trigger_document_uploaded", fail)
    monkeypatch.setattr(
        alert_service, "record_alert_isolated", lambda **kwargs: alerts.append(kwargs)
    )

    _, promoted = await _create_lead_and_promote(authed_client, submission.id)

    assert promoted.status_code == 200, promoted.text
    assert db.get(Donor, uuid.UUID(promoted.json()["donor_id"])) is not None
    assert sorted(alert["integration_key"] for alert in alerts) == [
        "donor_created",
        "donor_document_uploaded",
    ]
    assert all(alert["org_id"] == test_org.id for alert in alerts)
    assert "alerts@example.com" not in caplog.text
    assert all("alerts@example.com" not in (alert.get("message") or "") for alert in alerts)
