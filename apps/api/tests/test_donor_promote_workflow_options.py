"""Surrogate-only promotion options must not block workflow donor promotion."""

from uuid import uuid4

import pytest

from app.core.config import settings
from app.db.models import Donor, Form
from app.services import form_intake_service, workflow_service
from app.services.workflow_engine_adapters import DefaultWorkflowDomainAdapter
from tests.test_donor_intake_routing import _submission


@pytest.fixture
def donor_storage(monkeypatch, tmp_path):
    from app.core.rate_limit import limiter

    limiter.reset()
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options",
    [
        {"assign_to_user": True, "is_priority": True},
        {"assign_to_user": False, "is_priority": False},
    ],
)
async def test_workflow_promotion_ignores_surrogate_options_for_donor_leads(
    authed_client, db, test_org, donor_storage, options
):
    submission = await _submission(authed_client, db, kind="sperm_donor")
    form_intake_service.auto_match_submission(db, submission=submission)
    _, lead = form_intake_service.create_intake_lead_for_submission(
        db, submission=submission, user_id=None, source="website", auto_promote=False
    )

    result = DefaultWorkflowDomainAdapter().execute_action(
        db,
        {"action_type": "promote_intake_lead", **options},
        lead,
        "intake_lead",
        event_id=uuid4(),
        depth=1,
    )

    assert result["success"] is True, result
    donor = db.get(Donor, lead.promoted_donor_id)
    assert donor is not None
    assert (donor.organization_id, donor.donor_type) == (test_org.id, "sperm")


def test_workflow_options_report_form_lead_kinds(db, test_org, test_user):
    forms = {}
    for lead_kind in ("surrogate", "egg_donor"):
        form = Form(
            id=uuid4(),
            organization_id=test_org.id,
            name=f"{lead_kind} options form",
            status="published",
            purpose="other",
            lead_kind=lead_kind,
            schema_json={"pages": []},
            published_schema_json={"pages": []},
            created_by_user_id=test_user.id,
        )
        db.add(form)
        forms[lead_kind] = form
    db.flush()

    options = workflow_service.get_workflow_options(
        db,
        test_org.id,
        user_id=test_user.id,
        subject_type="surrogate",
        include_donor_forms=True,
    )

    lead_kinds = {item["id"]: item["lead_kind"] for item in options.forms}
    assert lead_kinds[str(forms["surrogate"].id)] == "surrogate"
    assert lead_kinds[str(forms["egg_donor"].id)] == "egg_donor"
