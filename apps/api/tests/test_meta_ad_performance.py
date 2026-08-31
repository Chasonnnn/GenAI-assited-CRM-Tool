from datetime import UTC, datetime

from app.schemas.donor import DonorCreate
from app.schemas.surrogate import SurrogateCreate


def test_meta_ad_performance_breakdown(db, test_org, test_user):
    from app.db.models import MetaLead
    from app.services import analytics_meta_service, donor_service, surrogate_service

    surrogate = surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        data=SurrogateCreate(full_name="Lead One", email="lead1@example.com"),
    )
    egg_donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Egg Lead",
            email="egg-lead@example.com",
        ),
    )
    sperm_donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="sperm",
            full_name="Sperm Lead",
            email="sperm-lead@example.com",
        ),
    )

    now = datetime.now(UTC)
    leads = [
        MetaLead(
            organization_id=test_org.id,
            meta_lead_id="lead_ad_1",
            meta_form_id="form_1",
            meta_page_id="page_1",
            field_data_raw={"meta_ad_id": "ad_1"},
            meta_created_time=now,
            converted_surrogate_id=surrogate.id,
            is_converted=True,
        ),
        MetaLead(
            organization_id=test_org.id,
            meta_lead_id="lead_ad_1_b",
            meta_form_id="form_1",
            meta_page_id="page_1",
            field_data_raw={"meta_ad_id": "ad_1"},
            meta_created_time=now,
        ),
        MetaLead(
            organization_id=test_org.id,
            meta_lead_id="lead_ad_1_egg",
            meta_form_id="form_egg",
            meta_page_id="page_1",
            field_data_raw={"meta_ad_id": "ad_1"},
            meta_created_time=now,
            converted_donor_id=egg_donor.id,
            is_converted=True,
        ),
        MetaLead(
            organization_id=test_org.id,
            meta_lead_id="lead_ad_1_sperm",
            meta_form_id="form_sperm",
            meta_page_id="page_1",
            field_data_raw={"meta_ad_id": "ad_1"},
            meta_created_time=now,
            converted_donor_id=sperm_donor.id,
            is_converted=True,
        ),
        MetaLead(
            organization_id=test_org.id,
            meta_lead_id="lead_ad_2",
            meta_form_id="form_1",
            meta_page_id="page_1",
            field_data_raw={"meta_ad_id": "ad_2"},
            meta_created_time=now,
        ),
    ]
    db.add_all(leads)
    db.commit()

    result = analytics_meta_service.get_leads_by_ad(db, test_org.id)
    by_id = {item["ad_id"]: item for item in result}

    assert by_id["ad_1"]["lead_count"] == 4
    assert by_id["ad_1"]["surrogate_count"] == 1
    assert by_id["ad_1"]["egg_donor_count"] == 1
    assert by_id["ad_1"]["sperm_donor_count"] == 1
    assert by_id["ad_1"]["converted_count"] == 3
    assert by_id["ad_1"]["conversion_rate"] == 75.0
    assert by_id["ad_2"]["lead_count"] == 1
