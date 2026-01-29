"""
Tests for Campaigns Module.

Tests the campaign model creation and service logic.
"""

from uuid import uuid4

import pytest

from app.core.encryption import hash_email
from app.utils.normalization import normalize_email


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


def _configure_resend_provider(db, org_id):
    """Configure org-level Resend settings for campaign sends."""
    from app.services import resend_settings_service

    resend_settings_service.get_or_create_resend_settings(db, org_id, org_id)
    resend_settings_service.update_resend_settings(
        db,
        org_id,
        org_id,
        email_provider="resend",
        api_key="re_test_key",
        from_email="no-reply@example.com",
        verified_domain="example.com",
    )


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

    campaign = campaign_service.create_campaign(db, test_org.id, test_user.id, create_data)

    assert campaign is not None
    assert campaign.name == "New Service Campaign"
    assert campaign.status == "draft"


def test_campaign_preview_filters_intended_parent_status(db, test_org):
    from app.db.enums import IntendedParentStatus
    from app.db.models import IntendedParent
    from app.services import campaign_service

    email_new = normalize_email("ip.new@example.com")
    email_matched = normalize_email("ip.matched@example.com")

    ip_new = IntendedParent(
        id=uuid4(),
        organization_id=test_org.id,
        intended_parent_number="I10001",
        full_name="IP New",
        email=email_new,
        email_hash=hash_email(email_new),
        status=IntendedParentStatus.NEW.value,
    )
    ip_matched = IntendedParent(
        id=uuid4(),
        organization_id=test_org.id,
        intended_parent_number="I10002",
        full_name="IP Matched",
        email=email_matched,
        email_hash=hash_email(email_matched),
        status=IntendedParentStatus.MATCHED.value,
    )
    db.add_all([ip_new, ip_matched])
    db.flush()

    preview = campaign_service.preview_recipients(
        db,
        test_org.id,
        "intended_parent",
        {"stage_slugs": [IntendedParentStatus.MATCHED.value]},
    )

    assert preview.total_count == 1
    assert preview.sample_recipients[0].entity_id == ip_matched.id


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


# =============================================================================
# Job Type Tests
# =============================================================================


def test_campaign_send_job_type_exists():
    """CAMPAIGN_SEND should exist in JobType enum."""
    from app.db.enums import JobType

    # This was the critical bug - job type was missing
    assert hasattr(JobType, "CAMPAIGN_SEND")
    assert JobType.CAMPAIGN_SEND.value == "campaign_send"


def test_campaign_send_job_creation(db, test_org, test_user, test_campaign):
    """Enqueuing campaign send should create a job with correct type."""
    from app.services import campaign_service
    from app.db.models import Job
    from app.db.enums import JobType

    _configure_resend_provider(db, test_org.id)

    # Enqueue campaign
    message, run_id, scheduled_at = campaign_service.enqueue_campaign_send(
        db=db,
        org_id=test_org.id,
        campaign_id=test_campaign.id,
        user_id=test_user.id,
        send_now=True,
    )

    assert run_id is not None
    assert "queued" in message.lower()

    # Verify job was created with correct type
    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.CAMPAIGN_SEND.value,
        )
        .first()
    )

    assert job is not None
    assert job.payload["campaign_id"] == str(test_campaign.id)
    assert job.payload["run_id"] == str(run_id)


def test_campaign_send_job_scheduled_run_at(db, test_org, test_user, test_campaign):
    """Scheduled campaigns should create a job with run_at set to scheduled_at."""
    from datetime import datetime, timezone, timedelta
    from app.services import campaign_service
    from app.db.models import Job
    from app.db.enums import JobType

    _configure_resend_provider(db, test_org.id)

    scheduled_at = datetime.now(timezone.utc) + timedelta(hours=2)
    test_campaign.scheduled_at = scheduled_at
    db.flush()

    message, run_id, returned_scheduled = campaign_service.enqueue_campaign_send(
        db=db,
        org_id=test_org.id,
        campaign_id=test_campaign.id,
        user_id=test_user.id,
        send_now=False,
    )

    assert run_id is not None
    assert "scheduled" in message.lower()
    assert returned_scheduled == scheduled_at

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.CAMPAIGN_SEND.value,
        )
        .first()
    )

    assert job is not None
    assert job.payload["campaign_id"] == str(test_campaign.id)
    assert job.payload["run_id"] == str(run_id)
    assert job.run_at.replace(tzinfo=None) == scheduled_at.replace(tzinfo=None)


def test_campaign_send_requires_scheduled_at_when_send_now_false(
    db, test_org, test_user, test_campaign
):
    """send_now=False should require campaign.scheduled_at."""
    from app.services import campaign_service

    _configure_resend_provider(db, test_org.id)

    with pytest.raises(ValueError, match="scheduled_at"):
        campaign_service.enqueue_campaign_send(
            db=db,
            org_id=test_org.id,
            campaign_id=test_campaign.id,
            user_id=test_user.id,
            send_now=False,
        )


# =============================================================================
# Campaign Execution Tests
# =============================================================================


def test_execute_campaign_run_function_exists():
    """execute_campaign_run function should exist."""
    from app.services import campaign_service

    assert hasattr(campaign_service, "execute_campaign_run")
    assert callable(campaign_service.execute_campaign_run)


def test_execute_campaign_run_with_no_recipients(db, test_org, test_user, test_template):
    """Executing campaign with no matching recipients should complete without errors."""
    from app.services import campaign_service
    from app.schemas.campaign import CampaignCreate
    from app.db.models import CampaignRun
    from uuid import uuid4

    # Create campaign with filter that matches nothing
    create_data = CampaignCreate(
        name="Empty Campaign",
        email_template_id=test_template.id,
        recipient_type="case",
        filter_criteria={"stage_ids": [str(uuid4())]},  # Non-existent stage
    )

    campaign = campaign_service.create_campaign(db, test_org.id, test_user.id, create_data)

    # Create a run
    run = CampaignRun(
        id=uuid4(),
        organization_id=test_org.id,
        campaign_id=campaign.id,
        status="pending",
        total_count=0,
        sent_count=0,
        failed_count=0,
        skipped_count=0,
    )
    db.add(run)
    db.flush()

    # Execute
    result = campaign_service.execute_campaign_run(
        db=db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run.id,
    )

    assert result["sent_count"] == 0
    assert result["failed_count"] == 0
    assert result["total_count"] == 0


def test_campaign_run_skips_existing_recipient(
    db, test_org, test_user, test_template, default_stage
):
    """Runs should be idempotent when a recipient already exists."""
    from app.db.models import Surrogate, CampaignRun, CampaignRecipient
    from app.schemas.campaign import CampaignCreate
    from app.services import campaign_service

    normalized_email = normalize_email("idempotent@example.com")
    case = Surrogate(
        id=uuid4(),
        organization_id=test_org.id,
        stage_id=default_stage.id,
        full_name="Case One",
        status_label=default_stage.label,
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        source="manual",
        surrogate_number=f"S{uuid4().int % 90000 + 10000:05d}",
        owner_type="user",
        owner_id=test_user.id,
    )
    db.add(case)
    db.flush()

    create_data = CampaignCreate(
        name="Idempotent Campaign",
        email_template_id=test_template.id,
        recipient_type="case",
        filter_criteria={"stage_ids": [str(default_stage.id)]},
    )
    campaign = campaign_service.create_campaign(db, test_org.id, test_user.id, create_data)

    run = CampaignRun(
        id=uuid4(),
        organization_id=test_org.id,
        campaign_id=campaign.id,
        status="pending",
        total_count=0,
        sent_count=0,
        failed_count=0,
        skipped_count=0,
    )
    db.add(run)
    db.flush()

    existing = CampaignRecipient(
        run_id=run.id,
        entity_type="case",
        entity_id=case.id,
        recipient_email=case.email,
        recipient_name=case.full_name,
        status="sent",
    )
    db.add(existing)
    db.flush()

    result = campaign_service.execute_campaign_run(
        db=db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run.id,
    )

    assert result["total_count"] == 1


@pytest.mark.parametrize("status", ["pending", "failed"])
def test_campaign_run_skips_existing_recipient_on_retry(
    db, test_org, test_user, test_template, default_stage, monkeypatch, status
):
    """Retry should not requeue pending/failed recipients without explicit retry action."""
    from app.db.models import Surrogate, CampaignRun, CampaignRecipient
    from app.schemas.campaign import CampaignCreate
    from app.services import campaign_service, email_service

    normalized_email = normalize_email(f"{status}-retry@example.com")
    case = Surrogate(
        id=uuid4(),
        organization_id=test_org.id,
        stage_id=default_stage.id,
        full_name="Case Retry",
        status_label=default_stage.label,
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        source="manual",
        surrogate_number=f"S{uuid4().int % 90000 + 10000:05d}",
        owner_type="user",
        owner_id=test_user.id,
    )
    db.add(case)
    db.flush()

    create_data = CampaignCreate(
        name="Retry Campaign",
        email_template_id=test_template.id,
        recipient_type="case",
        filter_criteria={"stage_ids": [str(default_stage.id)]},
    )
    campaign = campaign_service.create_campaign(db, test_org.id, test_user.id, create_data)

    run = CampaignRun(
        id=uuid4(),
        organization_id=test_org.id,
        campaign_id=campaign.id,
        status="pending",
        total_count=0,
        sent_count=0,
        failed_count=0,
        skipped_count=0,
    )
    db.add(run)
    db.flush()

    existing = CampaignRecipient(
        run_id=run.id,
        entity_type="case",
        entity_id=case.id,
        recipient_email=case.email,
        recipient_name=case.full_name,
        status=status,
    )
    db.add(existing)
    db.flush()

    def should_not_send(*args, **kwargs):
        raise AssertionError("send_email should not be called for existing recipients")

    monkeypatch.setattr(email_service, "send_email", should_not_send)

    result = campaign_service.execute_campaign_run(
        db=db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run.id,
    )

    assert result["total_count"] == 1


def test_campaign_response_uses_display_name(db, test_org, test_user, test_template):
    """Campaign response should use User.display_name (no User.full_name field)."""
    from app.db.models import Campaign
    from app.routers.campaigns import _campaign_to_response

    campaign = Campaign(
        id=uuid4(),
        organization_id=test_org.id,
        name="Display Name Campaign",
        description="Test campaign response serialization",
        email_template_id=test_template.id,
        recipient_type="case",
        filter_criteria={"stage_id": str(uuid4())},
        status="draft",
        created_by_user_id=test_user.id,
    )
    db.add(campaign)
    db.flush()

    response = _campaign_to_response(db, campaign)
    assert response.created_by_name == test_user.display_name


@pytest.mark.asyncio
async def test_preview_filters_invalid_stage_ids_returns_422(authed_client):
    response = await authed_client.post(
        "/campaigns/preview-filters",
        json={
            "recipient_type": "case",
            "filter_criteria": {"stage_ids": ["not-a-uuid"]},
        },
    )

    assert response.status_code == 422


def test_execute_campaign_run_streams_recipients(
    db, test_org, test_user, test_template, monkeypatch
):
    """Execute should stream recipients without calling .all()."""
    from types import SimpleNamespace
    from uuid import uuid4

    from app.db.models import CampaignRun
    from app.schemas.campaign import CampaignCreate
    from app.services import campaign_service, email_service

    class FakeQuery:
        def __init__(self, recipients):
            self._recipients = recipients

        def count(self):
            return len(self._recipients)

        def order_by(self, *args, **kwargs):
            return self

        def yield_per(self, *args, **kwargs):
            return self

        def execution_options(self, **kwargs):
            return self

        def options(self, *args, **kwargs):
            return self

        def all(self):
            raise AssertionError("execute_campaign_run should not call .all()")

        def __iter__(self):
            return iter(self._recipients)

    create_data = CampaignCreate(
        name="Streamed Campaign",
        email_template_id=test_template.id,
        recipient_type="case",
        filter_criteria={},
    )
    campaign = campaign_service.create_campaign(db, test_org.id, test_user.id, create_data)

    run = CampaignRun(
        id=uuid4(),
        organization_id=test_org.id,
        campaign_id=campaign.id,
        status="pending",
        total_count=0,
        sent_count=0,
        failed_count=0,
        skipped_count=0,
    )
    db.add(run)
    db.flush()

    recipient = SimpleNamespace(
        id=uuid4(),
        organization_id=test_org.id,
        email="stream@example.com",
        full_name="Stream Recipient",
        first_name="Stream",
        owner_type=None,
        owner_id=None,
        stage_id=None,
    )

    monkeypatch.setattr(
        campaign_service,
        "_build_recipient_query",
        lambda *args, **kwargs: FakeQuery([recipient]),
    )

    def fake_build_variables(*args, **kwargs):
        return {"first_name": "Stream", "full_name": "Stream Recipient", "email": "stream@example.com"}

    monkeypatch.setattr(email_service, "build_surrogate_template_variables", fake_build_variables)

    def fake_send_email(*args, **kwargs):
        return SimpleNamespace(id=uuid4()), None

    monkeypatch.setattr(email_service, "send_email", fake_send_email)

    result = campaign_service.execute_campaign_run(
        db=db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run.id,
    )

    assert result["total_count"] == 1


def test_execute_campaign_run_uses_bulk_suppression(
    db, test_org, test_user, test_template, monkeypatch
):
    """Execute should not call per-recipient suppression checks."""
    from types import SimpleNamespace
    from uuid import uuid4

    from app.db.models import CampaignRun
    from app.schemas.campaign import CampaignCreate
    from app.services import campaign_service, email_service

    class FakeQuery:
        def __init__(self, recipients):
            self._recipients = recipients

        def count(self):
            return len(self._recipients)

        def order_by(self, *args, **kwargs):
            return self

        def yield_per(self, *args, **kwargs):
            return self

        def execution_options(self, **kwargs):
            return self

        def options(self, *args, **kwargs):
            return self

        def __iter__(self):
            return iter(self._recipients)

    create_data = CampaignCreate(
        name="Bulk Suppression Campaign",
        email_template_id=test_template.id,
        recipient_type="case",
        filter_criteria={},
    )
    campaign = campaign_service.create_campaign(db, test_org.id, test_user.id, create_data)

    run = CampaignRun(
        id=uuid4(),
        organization_id=test_org.id,
        campaign_id=campaign.id,
        status="pending",
        total_count=0,
        sent_count=0,
        failed_count=0,
        skipped_count=0,
    )
    db.add(run)
    db.flush()

    recipient = SimpleNamespace(
        id=uuid4(),
        organization_id=test_org.id,
        email="bulk@example.com",
        full_name="Bulk Recipient",
        first_name="Bulk",
        owner_type=None,
        owner_id=None,
        stage_id=None,
    )

    monkeypatch.setattr(
        campaign_service,
        "_build_recipient_query",
        lambda *args, **kwargs: FakeQuery([recipient]),
    )

    def fake_build_variables(*args, **kwargs):
        return {"first_name": "Bulk", "full_name": "Bulk Recipient", "email": "bulk@example.com"}

    monkeypatch.setattr(email_service, "build_surrogate_template_variables", fake_build_variables)

    def fake_send_email(*args, **kwargs):
        return SimpleNamespace(id=uuid4()), None

    monkeypatch.setattr(email_service, "send_email", fake_send_email)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Per-recipient suppression check should not be called")

    monkeypatch.setattr(campaign_service, "is_email_suppressed", fail_if_called)

    result = campaign_service.execute_campaign_run(
        db=db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run.id,
    )

    assert result["total_count"] == 1
