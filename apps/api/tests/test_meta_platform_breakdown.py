from datetime import datetime, timezone


def test_meta_platform_breakdown_counts(db, test_org):
    from app.db.models import MetaLead
    from app.services import analytics_meta_service

    now = datetime.now(timezone.utc)
    leads = [
        MetaLead(
            organization_id=test_org.id,
            meta_lead_id="lead_fb",
            meta_form_id="form_1",
            meta_page_id="page_1",
            field_data_raw={"meta_platform": "facebook"},
            meta_created_time=now,
        ),
        MetaLead(
            organization_id=test_org.id,
            meta_lead_id="lead_ig",
            meta_form_id="form_1",
            meta_page_id="page_1",
            field_data_raw={"platform": "instagram"},
            meta_created_time=now,
        ),
        MetaLead(
            organization_id=test_org.id,
            meta_lead_id="lead_unknown",
            meta_form_id="form_1",
            meta_page_id="page_1",
            field_data_raw={},
            meta_created_time=now,
        ),
    ]
    db.add_all(leads)
    db.commit()

    result = analytics_meta_service.get_meta_platform_breakdown(db, test_org.id)
    counts = {item["platform"]: item["lead_count"] for item in result}

    assert counts.get("facebook") == 1
    assert counts.get("instagram") == 1
    assert counts.get("Unknown") == 1
