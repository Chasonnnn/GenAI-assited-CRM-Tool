"""
Tests for case statistics endpoint with period comparisons.

Tests the /surrogates/stats endpoint including:
- Basic stats (total, by_status, this_week, new_leads_24h)
- Period comparisons (last_week, new_leads_prev_24h, percentage changes)
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.encryption import hash_email
from app.db.enums import ContactStatus
from app.db.models import Surrogate, PipelineStage, Pipeline
from app.services import surrogate_service
from app.utils.normalization import normalize_email


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def stats_pipeline(db, test_org):
    """Create pipeline with stages for stats tests."""
    pipeline = (
        db.query(Pipeline)
        .filter(
            Pipeline.organization_id == test_org.id,
            Pipeline.is_default.is_(True),
        )
        .first()
    )

    if not pipeline:
        pipeline = Pipeline(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            name="Default Pipeline",
            is_default=True,
            current_version=1,
        )
        db.add(pipeline)
        db.flush()

    # Create stages
    stage = (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == pipeline.id, PipelineStage.slug == "new_unread")
        .first()
    )

    if not stage:
        stage = PipelineStage(
            id=uuid.uuid4(),
            pipeline_id=pipeline.id,
            slug="new_unread",
            label="New Unread",
            color="#3B82F6",
            stage_type="default",
            order=1,
            is_active=True,
        )
        db.add(stage)
        db.flush()

    return pipeline, stage


@pytest.fixture
def cases_for_stats(db, test_org, test_user, stats_pipeline):
    """Create cases at different time periods for stats testing."""
    pipeline, stage = stats_pipeline
    cases = []
    now = datetime.now(timezone.utc)

    # New leads in last 24h (2 unreached, 1 reached)
    for i in range(2):
        email = f"newlead{i}@test.com"
        normalized_email = normalize_email(email)
        case = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=stage.id,
            full_name=f"New Lead {i}",
            status_label=stage.label,
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            source="website",
            surrogate_number=f"S{10001 + i:05d}",
            created_by_user_id=test_user.id,
            owner_type="user",
            owner_id=test_user.id,
            created_at=now - timedelta(hours=2 + i),
        )
        db.add(case)
        cases.append(case)

    reached_email = "reached-lead@test.com"
    reached_normalized = normalize_email(reached_email)
    reached_case = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        stage_id=stage.id,
        full_name="Reached Lead",
        status_label=stage.label,
        email=reached_normalized,
        email_hash=hash_email(reached_normalized),
        source="website",
        surrogate_number="S10003",
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        created_at=now - timedelta(hours=3),
        contact_status=ContactStatus.REACHED.value,
        last_contacted_at=now - timedelta(hours=1),
    )
    db.add(reached_case)
    cases.append(reached_case)

    # New leads in previous 24h window (3 unreached, 24-48h ago)
    for i in range(3):
        email = f"prevlead{i}@test.com"
        normalized_email = normalize_email(email)
        case = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=stage.id,
            full_name=f"Prev Lead {i}",
            status_label=stage.label,
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            source="website",
            surrogate_number=f"S{10010 + i:05d}",
            created_by_user_id=test_user.id,
            owner_type="user",
            owner_id=test_user.id,
            created_at=now - timedelta(hours=30 + (i * 3)),
        )
        db.add(case)
        cases.append(case)

    # Other cases created this week (3 cases) - 4-6 days ago
    for i in range(3):
        email = f"thisweek{i}@test.com"
        normalized_email = normalize_email(email)
        case = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=stage.id,
            full_name=f"This Week Case {i}",
            status_label=stage.label,
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            source="website",
            surrogate_number=f"S{10020 + i:05d}",
            created_by_user_id=test_user.id,
            owner_type="user",
            owner_id=test_user.id,
            created_at=now - timedelta(days=4 + i),  # 4-6 days ago
        )
        db.add(case)
        cases.append(case)

    # Cases created last week (5 cases) - 8-12 days ago (clearly in 7-14 window)
    for i in range(5):
        email = f"lastweek{i}@test.com"
        normalized_email = normalize_email(email)
        case = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=stage.id,
            full_name=f"Last Week Case {i}",
            status_label=stage.label,
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            source="website",
            surrogate_number=f"S{10100 + i:05d}",
            created_by_user_id=test_user.id,
            owner_type="user",
            owner_id=test_user.id,
            created_at=now - timedelta(days=8 + i),  # 8-12 days ago
        )
        db.add(case)
        cases.append(case)

    # Older cases outside the last week (2 cases) - 35-40 days ago
    for i in range(2):
        email = f"older{i}@test.com"
        normalized_email = normalize_email(email)
        case = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=stage.id,
            full_name=f"Older Case {i}",
            status_label=stage.label,
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            source="website",
            surrogate_number=f"S{10110 + i:05d}",
            created_by_user_id=test_user.id,
            owner_type="user",
            owner_id=test_user.id,
            created_at=now - timedelta(days=35 + i),
        )
        db.add(case)
        cases.append(case)

    db.flush()
    return cases


# =============================================================================
# Tests
# =============================================================================


class TestCaseStats:
    """Tests for surrogate_service.get_surrogate_stats"""

    def test_get_stats_returns_all_fields(self, db, test_org, cases_for_stats):
        """Stats includes all expected fields including period comparisons."""
        stats = surrogate_service.get_surrogate_stats(db, test_org.id)

        # Basic fields
        assert "total" in stats
        assert "by_status" in stats
        assert "this_week" in stats
        assert "new_leads_24h" in stats

        # Period comparison fields
        assert "last_week" in stats
        assert "new_leads_prev_24h" in stats
        assert "week_change_pct" in stats
        assert "new_leads_change_pct" in stats
        assert "pending_tasks" in stats

    def test_this_week_count(self, db, test_org, cases_for_stats):
        """This week count is accurate."""
        stats = surrogate_service.get_surrogate_stats(db, test_org.id)

        # We created 9 cases this week
        assert stats["this_week"] == 9

    def test_last_week_count(self, db, test_org, cases_for_stats):
        """Last week count is accurate."""
        stats = surrogate_service.get_surrogate_stats(db, test_org.id)

        # We created 5 cases last week (7-14 days ago)
        assert stats["last_week"] == 5

    def test_week_change_percentage(self, db, test_org, cases_for_stats):
        """Week-over-week percentage is calculated correctly."""
        stats = surrogate_service.get_surrogate_stats(db, test_org.id)

        # this_week=9, last_week=5
        # Change = ((9 - 5) / 5) * 100 = 80%
        assert stats["week_change_pct"] == 80.0

    def test_new_leads_24h_count(self, db, test_org, cases_for_stats):
        """New leads count includes all leads created in the last 24h window."""
        stats = surrogate_service.get_surrogate_stats(db, test_org.id)

        # 3 leads created in last 24h (2 unreached + 1 reached)
        assert stats["new_leads_24h"] == 3

    def test_new_leads_prev_24h_count(self, db, test_org, cases_for_stats):
        """Previous 24h window count is accurate."""
        stats = surrogate_service.get_surrogate_stats(db, test_org.id)

        # We created 3 unreached leads in the previous 24h window
        assert stats["new_leads_prev_24h"] == 3

    def test_new_leads_change_percentage(self, db, test_org, cases_for_stats):
        """24h-over-24h percentage is calculated correctly."""
        stats = surrogate_service.get_surrogate_stats(db, test_org.id)

        # new_leads_24h=3, new_leads_prev_24h=3
        # Change = ((3 - 3) / 3) * 100 = 0%
        assert stats["new_leads_change_pct"] == 0.0

    def test_empty_org_returns_zeros(self, db):
        """Empty org returns zero values with 0.0 for percentages."""
        empty_org_id = uuid.uuid4()
        stats = surrogate_service.get_surrogate_stats(db, empty_org_id)

        assert stats["total"] == 0
        assert stats["this_week"] == 0
        assert stats["last_week"] == 0
        assert stats["week_change_pct"] == 0.0  # 0 current, 0 previous = 0%
        assert stats["new_leads_24h"] == 0
        assert stats["new_leads_prev_24h"] == 0
        assert stats["new_leads_change_pct"] == 0.0


class TestCaseStatsEndpoint:
    """Tests for GET /surrogates/stats endpoint"""

    @pytest.mark.asyncio
    async def test_stats_endpoint_returns_200(self, authed_client, cases_for_stats):
        """Stats endpoint returns 200 with all fields."""
        response = await authed_client.get("/surrogates/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total" in data
        assert "by_status" in data
        assert "this_week" in data
        assert "last_week" in data
        assert "week_change_pct" in data
        assert "new_leads_24h" in data
        assert "new_leads_prev_24h" in data
        assert "new_leads_change_pct" in data
        assert "pending_tasks" in data

    @pytest.mark.asyncio
    async def test_stats_endpoint_requires_auth(self, client):
        """Stats endpoint requires authentication."""
        response = await client.get("/surrogates/stats")
        assert response.status_code == 401
