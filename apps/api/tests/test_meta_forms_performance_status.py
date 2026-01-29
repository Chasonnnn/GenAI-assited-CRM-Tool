from datetime import datetime, timezone


def test_meta_form_performance_includes_mapping_status(db, test_org):
    from app.db.models import MetaForm, MetaLead
    from app.services import analytics_meta_service

    form = MetaForm(
        organization_id=test_org.id,
        page_id="page_status",
        form_external_id="form_status",
        form_name="Status Form",
        mapping_status="outdated",
    )
    db.add(form)
    db.flush()

    lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_status",
        meta_form_id="form_status",
        meta_page_id="page_status",
        meta_created_time=datetime.now(timezone.utc),
    )
    db.add(lead)
    db.commit()

    data = analytics_meta_service.get_leads_by_form(db, test_org.id)
    assert data
    assert data[0]["form_external_id"] == "form_status"
    assert data[0]["mapping_status"] == "outdated"
