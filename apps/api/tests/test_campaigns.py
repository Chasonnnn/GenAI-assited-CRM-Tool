"""
Tests for Campaigns Module.

Tests the campaign model creation and service logic.
"""

import pytest
from uuid import uuid4


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def test_template(db, test_org):
    """Create a test email template."""
    from app.db.models import EmailTemplate
    
    template = EmailTemplate(
        id=uuid4(),
        organization_id=test_org.id,
        name="Test Campaign Template",
        subject="Hello {{full_name}}",
        body="<p>Test email body</p>",
        is_active=True,  # Correct field name
    )
    db.add(template)
    db.flush()
    return template


@pytest.fixture
def test_campaign(db, test_org, test_user, test_template):
    """Create a test campaign."""
    from app.db.models import Campaign
    
    campaign = Campaign(
        id=uuid4(),
        organization_id=test_org.id,
        name="Test Campaign",
        description="A test campaign",
        email_template_id=test_template.id,
        recipient_type="case",
        filter_criteria={"stage_id": str(uuid4())},
        status="draft",
        created_by_user_id=test_user.id,
    )
    db.add(campaign)
    db.flush()
    return campaign


# =============================================================================
# Campaign Model Tests
# =============================================================================

def test_campaign_model_creation(db, test_org, test_user, test_template):
    """Test Campaign model can be created with all fields."""
    from app.db.models import Campaign
    from datetime import datetime, timezone
    
    campaign = Campaign(
        id=uuid4(),
        organization_id=test_org.id,
        name="Full Campaign",
        description="Campaign with all fields",
        email_template_id=test_template.id,
        recipient_type="intended_parent",
        filter_criteria={"state": "TX", "tags": ["vip"]},
        scheduled_at=datetime.now(timezone.utc),
        status="scheduled",
        created_by_user_id=test_user.id,
    )
    db.add(campaign)
    db.flush()
    
    assert campaign.id is not None
    assert campaign.created_at is not None
    assert campaign.status == "scheduled"


def test_campaign_run_model(db, test_org, test_campaign):
    """Test CampaignRun model creation."""
    from app.db.models import CampaignRun
    from datetime import datetime, timezone
    
    run = CampaignRun(
        id=uuid4(),
        organization_id=test_org.id,  # Required field
        campaign_id=test_campaign.id,
        status="running",
        started_at=datetime.now(timezone.utc),
        total_count=100,
        sent_count=0,
        failed_count=0,
        skipped_count=0,
    )
    db.add(run)
    db.flush()
    
    assert run.id is not None
    assert run.status == "running"


def test_campaign_recipient_model(db, test_org, test_campaign):
    """Test CampaignRecipient model creation."""
    from app.db.models import CampaignRun, CampaignRecipient
    from datetime import datetime, timezone
    
    run = CampaignRun(
        id=uuid4(),
        organization_id=test_org.id,  # Required field
        campaign_id=test_campaign.id,
        status="running",
        started_at=datetime.now(timezone.utc),
        total_count=1,
        sent_count=0,
        failed_count=0,
        skipped_count=0,
    )
    db.add(run)
    db.flush()
    
    recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="case",
        entity_id=uuid4(),
        recipient_email="test@example.com",  # Correct field name
        status="pending",
    )
    db.add(recipient)
    db.flush()
    
    assert recipient.id is not None
    assert recipient.status == "pending"


def test_email_suppression_model(db, test_org):
    """Test EmailSuppression model creation."""
    from app.db.models import EmailSuppression
    
    suppression = EmailSuppression(
        id=uuid4(),
        organization_id=test_org.id,
        email="blocked@example.com",
        reason="opt_out",
    )
    db.add(suppression)
    db.flush()
    
    assert suppression.id is not None
    assert suppression.reason == "opt_out"


# =============================================================================
# Campaign Service Tests
# =============================================================================

def test_campaign_service_list(db, test_org, test_campaign):
    """Test campaign service list function."""
    from app.services import campaign_service
    
    campaigns, total = campaign_service.list_campaigns(db, test_org.id)
    
    assert total == 1
    assert len(campaigns) == 1
    assert campaigns[0].name == "Test Campaign"


def test_campaign_service_get(db, test_org, test_campaign):
    """Test campaign service get function."""
    from app.services import campaign_service
    
    campaign = campaign_service.get_campaign(db, test_org.id, test_campaign.id)
    
    assert campaign is not None
    assert campaign.name == "Test Campaign"


def test_campaign_service_create(db, test_org, test_user, test_template):
    """Test campaign service create function."""
    from app.services import campaign_service
    from app.schemas.campaign import CampaignCreate
    
    create_data = CampaignCreate(
        name="New Service Campaign",
        email_template_id=test_template.id,
        recipient_type="case",
        filter_criteria={},
    )
    
    campaign = campaign_service.create_campaign(
        db, test_org.id, test_user.id, create_data
    )
    
    assert campaign is not None
    assert campaign.name == "New Service Campaign"
    assert campaign.status == "draft"


def test_is_email_suppressed(db, test_org):
    """Test suppression checking function."""
    from app.services import campaign_service
    from app.db.models import EmailSuppression
    
    # Not suppressed yet
    assert campaign_service.is_email_suppressed(db, test_org.id, "test@example.com") is False
    
    # Add suppression
    suppression = EmailSuppression(
        id=uuid4(),
        organization_id=test_org.id,
        email="test@example.com",
        reason="bounced",
    )
    db.add(suppression)
    db.flush()
    
    # Now suppressed
    assert campaign_service.is_email_suppressed(db, test_org.id, "test@example.com") is True


def test_add_to_suppression(db, test_org, test_user):
    """Test adding email to suppression list."""
    from app.services import campaign_service
    
    result = campaign_service.add_to_suppression(
        db, test_org.id, "newsuppressed@example.com", "opt_out", test_user.id
    )
    
    assert result is not None
    assert result.email == "newsuppressed@example.com"
    assert result.reason == "opt_out"
