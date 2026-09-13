"""Campaign reader scope never changes durable organization execution authority."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.encryption import hash_email
from app.db.models import (
    Campaign,
    CampaignRecipient,
    CampaignRun,
    Donor,
    EmailSuppression,
    EmailTemplate,
    IntendedParent,
    Membership,
    Organization,
    RoleRecordScope,
    Surrogate,
)
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.services import campaign_service, pipeline_service
from app.services.workflow_execution_authority import active_session


@pytest.fixture(params=["case", "egg_donor", "sperm_donor", "intended_parent"])
def audience(db, test_org, test_user, request):
    recipient_type = request.param
    kind = "surrogate" if recipient_type == "case" else recipient_type
    module = {
        "case": "surrogates",
        "egg_donor": "donors",
        "sperm_donor": "donors",
        "intended_parent": "intended_parents",
    }[recipient_type]
    member = db.query(Membership).filter_by(organization_id=test_org.id, user_id=test_user.id).one()
    member.role = "operations"
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.add(
        RoleRecordScope(
            organization_id=test_org.id,
            role="operations",
            module=module,
            assignment="assigned",
            phase="all",
        )
    )
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id, entity_type=kind)
    stage = min((row for row in pipeline.stages if row.is_active), key=lambda row: row.order)
    records = []
    for index in range(3):
        email = f"audience-{uuid4().hex}@example.com"
        fields = dict(
            organization_id=test_org.id,
            full_name=f"Recipient {index}",
            email=email,
            email_hash=hash_email(email),
            stage_id=stage.id,
            owner_type="user",
            owner_id=test_user.id if index != 2 else uuid4(),
        )
        if recipient_type == "case":
            record = Surrogate(
                **fields, surrogate_number=f"S{10001 + index}", status_label=stage.label
            )
        elif recipient_type == "intended_parent":
            record = IntendedParent(
                **fields, intended_parent_number=f"I{10001 + index}", status=stage.stage_key
            )
        else:
            record = Donor(
                **fields,
                donor_number=f"D{10001 + index}",
                donor_type="egg" if recipient_type == "egg_donor" else "sperm",
            )
        db.add(record)
        records.append(record)
    template = EmailTemplate(
        organization_id=test_org.id,
        scope="org",
        name="Viewer scope",
        subject="Hello",
        body="<p>Hello</p>",
    )
    db.add(template)
    db.flush()
    campaign = Campaign(
        organization_id=test_org.id,
        name="Organization campaign",
        scope="org",
        email_template_id=template.id,
        recipient_type=recipient_type,
        filter_criteria={},
        created_by_user_id=test_user.id,
    )
    db.add(campaign)
    db.flush()
    run = CampaignRun(
        organization_id=test_org.id,
        campaign_id=campaign.id,
        total_count=99,
        sent_count=90,
        delivered_count=80,
        failed_count=9,
        opened_count=70,
        clicked_count=60,
        skipped_count=50,
        status="completed",
    )
    db.add(run)
    db.flush()
    now = datetime.now(UTC)
    recipients = []
    for index, record in enumerate(records):
        row = CampaignRecipient(
            run_id=run.id,
            entity_type=recipient_type,
            entity_id=record.id,
            recipient_name=record.full_name,
            recipient_email=record.email,
            status="sent" if index == 0 else "failed" if index == 1 else "delivered",
            created_at=now + timedelta(seconds=index),
            opened_at=now if index != 1 else None,
            clicked_at=now if index == 2 else None,
        )
        db.add(row)
        recipients.append(row)
    db.flush()
    return SimpleNamespace(
        org=test_org,
        user=test_user,
        member=member,
        campaign=campaign,
        run=run,
        records=records,
        recipients=recipients,
        recipient_type=recipient_type,
    )


@pytest.mark.asyncio
async def test_preview_filters_before_sampling_and_counts_only_visible_audience(
    db, audience, authed_client
):
    a = audience
    db.add(EmailSuppression(organization_id=a.org.id, email=a.records[1].email, reason="opt_out"))
    db.flush()
    response = await authed_client.get(f"/campaigns/{a.campaign.id}/preview?limit=1")
    assert response.status_code == 200, response.text
    assert response.json()["total_count"] == 2
    assert response.json()["eligible_count"] == 1
    assert response.json()["suppressed_count"] == 1
    assert [row["entity_id"] for row in response.json()["sample_recipients"]] == [
        str(a.records[0].id)
    ]
    unsaved = await authed_client.post(
        "/campaigns/preview-filters?limit=1",
        json={"scope": "org", "recipient_type": a.recipient_type},
    )
    assert unsaved.status_code == 200, unsaved.text
    assert unsaved.json() == response.json()
    # The execution query still contains the complete organization audience.
    execution = campaign_service._build_recipient_query(
        db, a.org.id, a.recipient_type, {}, campaign=a.campaign
    )
    assert execution.count() == 3


@pytest.mark.asyncio
async def test_run_rows_and_all_count_surfaces_follow_viewer_scope(db, audience, authed_client):
    a = audience
    response = await authed_client.get(
        f"/campaigns/{a.campaign.id}/runs/{a.run.id}/recipients?limit=1"
    )
    assert response.status_code == 200, response.text
    assert [row["entity_id"] for row in response.json()] == [str(a.records[1].id)]
    page2 = await authed_client.get(
        f"/campaigns/{a.campaign.id}/runs/{a.run.id}/recipients?limit=1&offset=1"
    )
    assert [row["entity_id"] for row in page2.json()] == [str(a.records[0].id)]
    denied_status = await authed_client.get(
        f"/campaigns/{a.campaign.id}/runs/{a.run.id}/recipients?status=delivered"
    )
    assert denied_status.json() == []
    for path, is_list in (
        (f"/campaigns/{a.campaign.id}/runs", True),
        (f"/campaigns/{a.campaign.id}/runs/{a.run.id}", False),
        (f"/campaigns/{a.campaign.id}", False),
        ("/campaigns", True),
    ):
        result = await authed_client.get(path)
        assert result.status_code == 200, result.text
        row = result.json()[0] if is_list else result.json()
        assert row.get("total_count", row.get("total_recipients")) == 2
        assert row["sent_count"] == 1
        assert row["delivered_count"] == 0
        assert row["failed_count"] == 1
        assert row["opened_count"] == 1
        assert row["clicked_count"] == 0
    db.refresh(a.run)
    assert a.run.total_count == 99
    assert a.run.sent_count == 90


def test_viewer_service_rejects_other_org_or_inactive_membership(db, audience):
    a = audience
    session = active_session(db, a.org.id, a.user.id)
    a.member.is_active = False
    db.flush()
    rows, total = campaign_service.list_campaigns(db, a.org.id, viewer_session=session)
    assert rows == [] and total == 0
    a.member.is_active = True
    other = Organization(name="Other", slug=f"other-{uuid4().hex}")
    db.add(other)
    db.flush()
    session.org_id = other.id
    # A viewer session cannot be applied to a different organization argument.
    rows, total = campaign_service.list_campaigns(db, a.org.id, viewer_session=session)
    assert rows == [] and total == 0


def test_run_statistics_batch_query_and_recipient_tenant_boundary(db, audience):
    from sqlalchemy import event

    a = audience
    viewer = active_session(db, a.org.id, a.user.id)
    second_run = CampaignRun(organization_id=a.org.id, campaign_id=a.campaign.id, total_count=30)
    db.add(second_run)
    db.flush()
    db.add(
        CampaignRecipient(
            run_id=second_run.id,
            entity_type=a.recipient_type,
            entity_id=a.records[0].id,
            status="sent",
        )
    )
    other = Organization(name="Foreign record", slug=f"other-{uuid4().hex}")
    db.add(other)
    db.flush()
    # An inconsistent historic recipient must not become visible just because
    # its record now claims the viewer as owner.
    a.records[2].organization_id = other.id
    a.records[2].owner_id = a.user.id
    db.flush()
    statements = []

    def record_query(_connection, _cursor, statement, _parameters, _context, _many):
        if "from campaign_recipients join campaign_runs" in " ".join(statement.lower().split()):
            statements.append(statement)

    connection = db.connection()
    event.listen(connection, "before_cursor_execute", record_query)
    try:
        counts = campaign_service.viewer_run_statistics(
            db, a.org.id, [a.run.id, second_run.id], viewer
        )
    finally:
        event.remove(connection, "before_cursor_execute", record_query)
    assert len(statements) == 1
    assert counts[a.run.id]["total_count"] == 2
    assert counts[second_run.id]["total_count"] == 1
    assert counts[a.run.id]["delivered_count"] == 0
    rows = campaign_service.list_run_recipients(
        db, a.run.id, org_id=a.org.id, viewer_session=viewer
    )
    assert {row.entity_id for row in rows} == {record.id for record in a.records[:2]}
    a.member.is_active = False
    db.flush()
    assert (
        campaign_service.list_run_recipients(db, a.run.id, org_id=a.org.id, viewer_session=viewer)
        == []
    )
    assert campaign_service.viewer_run_statistics(db, a.org.id, [a.run.id], viewer) == {}
