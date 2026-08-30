from datetime import UTC, datetime

from app.schemas.donor import DonorCreate


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
        meta_created_time=datetime.now(UTC),
    )
    db.add(lead)
    db.commit()

    data = analytics_meta_service.get_leads_by_form(db, test_org.id)
    assert data
    assert data[0]["form_external_id"] == "form_status"
    assert data[0]["mapping_status"] == "outdated"


def test_meta_form_performance_reports_exact_donor_conversion_type(db, test_org, test_user):
    from app.db.models import MetaForm, MetaLead
    from app.services import analytics_meta_service, donor_service

    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Analytics Egg Donor",
            email="analytics-egg@example.com",
        ),
    )
    form = MetaForm(
        organization_id=test_org.id,
        page_id="page_egg",
        form_external_id="form_egg",
        form_name="Egg Donor Form",
        mapping_status="mapped",
        lead_kind="egg_donor",
    )
    db.add(form)
    db.add_all(
        [
            MetaLead(
                organization_id=test_org.id,
                meta_lead_id="lead_egg_converted",
                meta_form_id="form_egg",
                meta_page_id="page_egg",
                meta_created_time=datetime.now(UTC),
                converted_donor_id=donor.id,
                is_converted=True,
            ),
            MetaLead(
                organization_id=test_org.id,
                meta_lead_id="lead_egg_pending",
                meta_form_id="form_egg",
                meta_page_id="page_egg",
                meta_created_time=datetime.now(UTC),
            ),
        ]
    )
    db.commit()

    item = analytics_meta_service.get_leads_by_form(db, test_org.id)[0]
    assert item["lead_kind"] == "egg_donor"
    assert item["lead_count"] == 2
    assert item["converted_count"] == 1
    assert item["surrogate_count"] == 0
    assert item["egg_donor_count"] == 1
    assert item["sperm_donor_count"] == 0
    assert item["conversion_rate"] == 50.0
