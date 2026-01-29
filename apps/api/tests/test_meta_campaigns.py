"""Tests for Meta campaign filter metadata."""

from app.schemas.surrogate import SurrogateCreate


def test_meta_campaigns_use_metadata_name(db, test_org, test_user):
    from app.services import analytics_meta_service, surrogate_service

    surrogate = surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        data=SurrogateCreate(full_name="Meta Lead", email="meta@example.com"),
    )
    surrogate.meta_ad_external_id = "ad_123"
    surrogate.import_metadata = {"meta_ad_name": "Meta Ad Name"}
    db.commit()

    campaigns = analytics_meta_service.get_campaigns(db, test_org.id)
    assert campaigns
    assert campaigns[0]["ad_id"] == "ad_123"
    assert campaigns[0]["ad_name"] == "Meta Ad Name"
