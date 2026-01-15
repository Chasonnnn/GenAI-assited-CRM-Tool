"""
Tests for case statistics endpoint with period comparisons.

Tests the /surrogates/stats endpoint including:
- Basic stats (total, by_status, this_week, this_month)
- Period comparisons (last_week, last_month, percentage changes)
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.encryption import hash_email
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

    # Cases created this week (3 cases) - within last 7 days
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
            surrogate_number=f"TW-{i:03d}",
            created_by_user_id=test_user.id,
            owner_type="user",
            owner_id=test_user.id,
            created_at=now - timedelta(days=1 + i),  # 1-3 days ago
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
            surrogate_number=f"LW-{i:03d}",
            created_by_user_id=test_user.id,
            owner_type="user",
            owner_id=test_user.id,
            created_at=now - timedelta(days=8 + i),  # 8-12 days ago
        )
        db.add(case)
        cases.append(case)

    # Cases created this month but not this/last week (4 cases) - 15-20 days ago
    for i in range(4):
        email = f"thismonth{i}@test.com"
        normalized_email = normalize_email(email)
        case = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=stage.id,
            full_name=f"This Month Case {i}",
            status_label=stage.label,
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            source="website",
            surrogate_number=f"TM-{i:03d}",
            created_by_user_id=test_user.id,
            owner_type="user",
            owner_id=test_user.id,
            created_at=now - timedelta(days=15 + i),  # 15-18 days ago (within 30 days)
        )
        db.add(case)
        cases.append(case)

    # Cases created last month (2 cases) - 35-40 days ago (in 30-60 day window)
    for i in range(2):
        email = f"lastmonth{i}@test.com"
        normalized_email = normalize_email(email)
        case = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=stage.id,
            full_name=f"Last Month Case {i}",
            status_label=stage.label,
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            source="website",
            surrogate_number=f"LM-{i:03d}",
            created_by_user_id=test_user.id,
            owner_type="user",
            owner_id=test_user.id,
            created_at=now - timedelta(days=35 + i),  # 35-36 days ago
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
        assert "this_month" in stats

        # Period comparison fields
        assert "last_week" in stats
        assert "last_month" in stats
        assert "week_change_pct" in stats
        assert "month_change_pct" in stats
        assert "pending_tasks" in stats

    def test_this_week_count(self, db, test_org, cases_for_stats):
        """This week count is accurate."""
        stats = surrogate_service.get_surrogate_stats(db, test_org.id)

        # We created 3 cases this week
        assert stats["this_week"] == 3

    def test_last_week_count(self, db, test_org, cases_for_stats):
        """Last week count is accurate."""
        stats = surrogate_service.get_surrogate_stats(db, test_org.id)

        # We created 5 cases last week (7-14 days ago)
        assert stats["last_week"] == 5

    def test_week_change_percentage(self, db, test_org, cases_for_stats):
        """Week-over-week percentage is calculated correctly."""
        stats = surrogate_service.get_surrogate_stats(db, test_org.id)

        # this_week=3, last_week=5
        # Change = ((3 - 5) / 5) * 100 = -40%
        assert stats["week_change_pct"] == -40.0

    def test_this_month_count(self, db, test_org, cases_for_stats):
        """This month count includes all cases in last 30 days."""
        stats = surrogate_service.get_surrogate_stats(db, test_org.id)

        # 3 (this week) + 5 (last week) + 4 (this month earlier) = 12
        # (Cases at 20-23 days ago are within 30 days)
        assert stats["this_month"] == 12

    def test_last_month_count(self, db, test_org, cases_for_stats):
        """Last month count is accurate."""
        stats = surrogate_service.get_surrogate_stats(db, test_org.id)

        # We created 2 cases 35-36 days ago (in the 30-60 day window)
        assert stats["last_month"] == 2

    def test_month_change_percentage(self, db, test_org, cases_for_stats):
        """Month-over-month percentage is calculated correctly."""
        stats = surrogate_service.get_surrogate_stats(db, test_org.id)

        # this_month=12, last_month=2
        # Change = ((12 - 2) / 2) * 100 = 500%
        assert stats["month_change_pct"] == 500.0

    def test_empty_org_returns_zeros(self, db):
        """Empty org returns zero values with 0.0 for percentages."""
        empty_org_id = uuid.uuid4()
        stats = surrogate_service.get_surrogate_stats(db, empty_org_id)

        assert stats["total"] == 0
        assert stats["this_week"] == 0
        assert stats["last_week"] == 0
        assert stats["week_change_pct"] == 0.0  # 0 current, 0 previous = 0%
        assert stats["this_month"] == 0
        assert stats["last_month"] == 0
        assert stats["month_change_pct"] == 0.0


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
        assert "this_month" in data
        assert "last_month" in data
        assert "month_change_pct" in data
        assert "pending_tasks" in data

    @pytest.mark.asyncio
    async def test_stats_endpoint_requires_auth(self, client):
        """Stats endpoint requires authentication."""
        response = await client.get("/surrogates/stats")
        assert response.status_code == 401
