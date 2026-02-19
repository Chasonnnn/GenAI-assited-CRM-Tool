import uuid

import pytest

from app.core.config import settings
from app.db.models import MetaLead, MetaPageMapping, Organization


def _create_org(db, name: str) -> Organization:
    org = Organization(
        id=uuid.uuid4(),
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(org)
    db.flush()
    return org


@pytest.mark.asyncio
async def test_dev_meta_lead_alerts_are_org_scoped(client, db, test_org):
    other_org = _create_org(db, "Other Org")

    # Target org data
    db.add_all(
        [
            MetaLead(
                organization_id=test_org.id,
                meta_lead_id="org-a-fetch-failed",
                status="fetch_failed",
                fetch_error="request timeout",
            ),
            MetaLead(
                organization_id=test_org.id,
                meta_lead_id="org-a-convert-error",
                status="stored",
                conversion_error="validation failed",
            ),
            MetaLead(
                organization_id=test_org.id,
                meta_lead_id="org-a-ok",
                status="stored",
            ),
        ]
    )
    db.add_all(
        [
            MetaPageMapping(
                organization_id=test_org.id,
                page_id="page-org-a-problem",
                page_name="Org A Problem Page",
                last_error="meta token invalid",
            ),
            MetaPageMapping(
                organization_id=test_org.id,
                page_id="page-org-a-healthy",
                page_name="Org A Healthy Page",
            ),
        ]
    )

    # Other org data that must not be returned
    db.add_all(
        [
            MetaLead(
                organization_id=other_org.id,
                meta_lead_id="org-b-fetch-failed",
                status="fetch_failed",
                fetch_error="bad credentials",
            ),
            MetaPageMapping(
                organization_id=other_org.id,
                page_id="page-org-b-problem",
                page_name="Org B Problem Page",
                last_error="permission denied",
            ),
        ]
    )
    db.flush()

    response = await client.get(
        "/dev/meta-leads/alerts",
        params={"org_id": str(test_org.id), "limit": 50},
        headers={"X-Dev-Secret": settings.DEV_SECRET},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == {
        "total_leads": 3,
        "failed_leads": 1,
        "problem_pages": 1,
    }

    problem_lead_ids = {lead["meta_lead_id"] for lead in data["problem_leads"]}
    assert problem_lead_ids == {"org-a-fetch-failed", "org-a-convert-error"}
    assert "org-b-fetch-failed" not in problem_lead_ids

    problem_page_ids = {page["page_id"] for page in data["problem_pages"]}
    assert problem_page_ids == {"page-org-a-problem"}
    assert "page-org-b-problem" not in problem_page_ids


@pytest.mark.asyncio
async def test_dev_meta_leads_all_is_org_scoped_and_status_filtered(client, db, test_org):
    other_org = _create_org(db, "Other Org Two")

    db.add_all(
        [
            MetaLead(
                organization_id=test_org.id,
                meta_lead_id="org-a-received",
                status="received",
            ),
            MetaLead(
                organization_id=test_org.id,
                meta_lead_id="org-a-stored",
                status="stored",
            ),
            MetaLead(
                organization_id=other_org.id,
                meta_lead_id="org-b-received",
                status="received",
            ),
        ]
    )
    db.flush()

    response_all = await client.get(
        "/dev/meta-leads/all",
        params={"org_id": str(test_org.id), "limit": 100},
        headers={"X-Dev-Secret": settings.DEV_SECRET},
    )
    assert response_all.status_code == 200
    all_data = response_all.json()
    assert all_data["count"] == 2
    all_ids = {lead["meta_lead_id"] for lead in all_data["leads"]}
    assert all_ids == {"org-a-received", "org-a-stored"}
    assert "org-b-received" not in all_ids

    response_filtered = await client.get(
        "/dev/meta-leads/all",
        params={"org_id": str(test_org.id), "status": "received", "limit": 100},
        headers={"X-Dev-Secret": settings.DEV_SECRET},
    )
    assert response_filtered.status_code == 200
    filtered_data = response_filtered.json()
    assert filtered_data["count"] == 1
    assert [lead["meta_lead_id"] for lead in filtered_data["leads"]] == ["org-a-received"]
