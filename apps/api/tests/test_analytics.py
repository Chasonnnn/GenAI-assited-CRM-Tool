"""
Tests for analytics endpoints.

Tests the analytics router endpoints including:
- Analytics summary
- Cases by status
- Cases by assignee
- Cases trend
- Meta leads performance
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import Case, PipelineStage, MetaLead


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def analytics_pipeline_stages(db, test_org):
    """Create multiple pipeline stages for analytics tests."""
    from app.db.models import Pipeline

    # Get or create default pipeline
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

    # Create stages with different orders
    stages_data = [
        ("new_unread", "New Unread", 1, "#3B82F6"),
        ("contacted", "Contacted", 2, "#10B981"),
        ("qualified", "Qualified", 3, "#8B5CF6"),
        ("applied", "Applied", 4, "#F59E0B"),
        ("application_submitted", "Application Submitted", 5, "#8B5CF6"),
        ("approved", "Approved", 8, "#22C55E"),
    ]

    stages = {}
    for slug, label, order, color in stages_data:
        stage = (
            db.query(PipelineStage)
            .filter(
                PipelineStage.pipeline_id == pipeline.id, PipelineStage.slug == slug
            )
            .first()
        )

        if not stage:
            stage = PipelineStage(
                id=uuid.uuid4(),
                pipeline_id=pipeline.id,
                slug=slug,
                label=label,
                color=color,
                stage_type="default",
                order=order,
                is_active=True,
            )
            db.add(stage)
        stages[slug] = stage

    db.flush()
    return stages


@pytest.fixture
def sample_cases(db, test_org, test_user, analytics_pipeline_stages):
    """Create sample cases for analytics tests."""
    stages = analytics_pipeline_stages
    cases = []

    # Create cases in different stages
    for i, (stage_slug, count) in enumerate(
        [
            ("new_unread", 3),
            ("contacted", 2),
            ("qualified", 2),
            ("application_submitted", 1),
            ("approved", 1),
        ]
    ):
        stage = stages[stage_slug]
        for j in range(count):
            case = Case(
                id=uuid.uuid4(),
                organization_id=test_org.id,
                stage_id=stage.id,
                full_name=f"Test User {i}{j}",
                status_label=stage.label,
                email=f"test{i}{j}@example.com",
                phone="555-0100",
                source="website",
                case_number=f"C-{i:03d}-{j:03d}",
                created_by_user_id=test_user.id,
                owner_type="user",
                owner_id=test_user.id,
                created_at=datetime.now(timezone.utc) - timedelta(days=j),
            )
            db.add(case)
            cases.append(case)

    db.flush()
    return cases


@pytest.fixture
def sample_meta_leads(db, test_org, sample_cases, analytics_pipeline_stages):
    """Create sample Meta leads for analytics tests."""
    leads = []

    # Find cases in qualified and approved stages
    qualified_case = None
    converted_case = None
    approved_case = None

    for case in sample_cases:
        stage = (
            db.query(PipelineStage).filter(PipelineStage.id == case.stage_id).first()
        )
        if stage.slug == "qualified" and not qualified_case:
            qualified_case = case
        if stage.slug == "application_submitted" and not converted_case:
            converted_case = case
        if stage.slug == "approved" and not approved_case:
            approved_case = case

    # Create unconverted lead
    lead1 = MetaLead(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        meta_page_id="test-page",
        meta_lead_id=f"lead-{uuid.uuid4().hex[:8]}",
        meta_created_time=datetime.now(timezone.utc) - timedelta(days=5),
        received_at=datetime.now(timezone.utc) - timedelta(days=5),
        is_converted=False,
        status="processed",
    )
    db.add(lead1)
    leads.append(lead1)

    # Create converted lead (qualified)
    if qualified_case:
        lead2 = MetaLead(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            meta_page_id="test-page",
            meta_lead_id=f"lead-{uuid.uuid4().hex[:8]}",
            meta_created_time=datetime.now(timezone.utc) - timedelta(days=3),
            received_at=datetime.now(timezone.utc) - timedelta(days=3),
            is_converted=True,
            converted_case_id=qualified_case.id,
            converted_at=datetime.now(timezone.utc) - timedelta(days=2),
            status="converted",
        )
        db.add(lead2)
        leads.append(lead2)

    # Create converted lead (application_submitted)
    if converted_case:
        lead3 = MetaLead(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            meta_page_id="test-page",
            meta_lead_id=f"lead-{uuid.uuid4().hex[:8]}",
            meta_created_time=datetime.now(timezone.utc) - timedelta(days=4),
            received_at=datetime.now(timezone.utc) - timedelta(days=4),
            is_converted=True,
            converted_case_id=converted_case.id,
            converted_at=datetime.now(timezone.utc) - timedelta(days=1),
            status="converted",
        )
        db.add(lead3)
        leads.append(lead3)

    # Create converted lead (approved)
    if approved_case:
        lead4 = MetaLead(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            meta_page_id="test-page",
            meta_lead_id=f"lead-{uuid.uuid4().hex[:8]}",
            meta_created_time=datetime.now(timezone.utc) - timedelta(days=7),
            received_at=datetime.now(timezone.utc) - timedelta(days=7),
            is_converted=True,
            converted_case_id=approved_case.id,
            converted_at=datetime.now(timezone.utc) - timedelta(days=1),
            status="converted",
        )
        db.add(lead4)
        leads.append(lead4)

    db.flush()
    return leads


# =============================================================================
# Tests
# =============================================================================


class TestAnalyticsSummary:
    """Tests for GET /analytics/summary"""

    @pytest.mark.asyncio
    async def test_get_summary_returns_counts(self, authed_client, sample_cases):
        """Summary returns total cases and new this period."""
        response = await authed_client.get("/analytics/summary")
        assert response.status_code == 200

        data = response.json()
        assert "total_cases" in data
        assert "new_this_period" in data
        assert "qualified_rate" in data
        assert data["total_cases"] >= 0

    @pytest.mark.asyncio
    async def test_summary_with_date_range(self, authed_client, sample_cases):
        """Summary respects date range filters."""
        from_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime(
            "%Y-%m-%d"
        )
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        response = await authed_client.get(
            f"/analytics/summary?from_date={from_date}&to_date={to_date}"
        )
        assert response.status_code == 200

        data = response.json()
        assert "total_cases" in data

    @pytest.mark.asyncio
    async def test_summary_requires_auth(self, client):
        """Summary endpoint requires authentication."""
        response = await client.get("/analytics/summary")
        assert response.status_code == 401


class TestCasesByStatus:
    """Tests for GET /analytics/cases/by-status"""

    @pytest.mark.asyncio
    async def test_get_cases_by_status(self, authed_client, sample_cases):
        """Returns case counts grouped by status."""
        response = await authed_client.get("/analytics/cases/by-status")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # Each item should have status and count
        for item in data:
            assert "status" in item
            assert "count" in item
            assert isinstance(item["count"], int)


class TestCasesByAssignee:
    """Tests for GET /analytics/cases/by-assignee"""

    @pytest.mark.asyncio
    async def test_get_cases_by_assignee(self, authed_client, sample_cases):
        """Returns case counts grouped by assignee."""
        response = await authed_client.get("/analytics/cases/by-assignee")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # Each item should have user info and count
        for item in data:
            assert "count" in item
            assert isinstance(item["count"], int)


class TestCasesTrend:
    """Tests for GET /analytics/cases/trend"""

    @pytest.mark.asyncio
    async def test_get_cases_trend(self, authed_client, sample_cases):
        """Returns case creation trend data."""
        response = await authed_client.get("/analytics/cases/trend")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # Each point should have date and count
        for point in data:
            assert "date" in point
            assert "count" in point

    @pytest.mark.asyncio
    async def test_trend_with_period(self, authed_client, sample_cases):
        """Trend respects period parameter."""
        response = await authed_client.get("/analytics/cases/trend?period=week")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)


class TestMetaPerformance:
    """Tests for GET /analytics/meta/performance"""

    @pytest.mark.asyncio
    async def test_get_meta_performance(self, authed_client, sample_meta_leads):
        """Returns Meta leads performance metrics."""
        response = await authed_client.get("/analytics/meta/performance")
        assert response.status_code == 200

        data = response.json()
        assert "leads_received" in data
        assert "leads_qualified" in data
        assert "leads_converted" in data
        assert "qualification_rate" in data
        assert "conversion_rate" in data
        assert "avg_time_to_convert_hours" in data

    @pytest.mark.asyncio
    async def test_meta_performance_counts(self, authed_client, sample_meta_leads):
        """Meta performance returns correct counts."""
        response = await authed_client.get("/analytics/meta/performance")
        assert response.status_code == 200

        data = response.json()
        assert data["leads_received"] == 4
        assert data["leads_qualified"] == 3
        assert data["leads_converted"] == 2
        assert data["qualification_rate"] >= 0
        assert data["conversion_rate"] >= 0

    @pytest.mark.asyncio
    async def test_meta_performance_with_date_range(
        self, authed_client, sample_meta_leads
    ):
        """Meta performance respects date range."""
        from_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime(
            "%Y-%m-%d"
        )
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        response = await authed_client.get(
            f"/analytics/meta/performance?from_date={from_date}&to_date={to_date}"
        )
        assert response.status_code == 200

        data = response.json()
        assert "leads_received" in data

    @pytest.mark.asyncio
    async def test_meta_performance_prefers_meta_created_time(
        self,
        authed_client,
        db,
        test_org,
        sample_meta_leads,
    ):
        """Meta performance filters by meta_created_time when available."""
        from_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime(
            "%Y-%m-%d"
        )
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        response = await authed_client.get(
            f"/analytics/meta/performance?from_date={from_date}&to_date={to_date}"
        )
        assert response.status_code == 200
        baseline = response.json()["leads_received"]

        old_lead = MetaLead(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            meta_page_id="test-page",
            meta_lead_id=f"lead-{uuid.uuid4().hex[:8]}",
            meta_created_time=datetime.now(timezone.utc) - timedelta(days=90),
            received_at=datetime.now(timezone.utc) - timedelta(days=1),
            is_converted=False,
            status="processed",
        )
        db.add(old_lead)
        db.commit()

        response = await authed_client.get(
            f"/analytics/meta/performance?from_date={from_date}&to_date={to_date}"
        )
        assert response.status_code == 200
        assert response.json()["leads_received"] == baseline


class TestMetaSpend:
    """Tests for GET /analytics/meta/spend"""

    @pytest.mark.asyncio
    async def test_meta_spend_with_time_series_and_breakdowns(
        self, authed_client, monkeypatch
    ):
        """Meta spend returns time series and breakdowns when requested."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "META_TEST_MODE", True)

        response = await authed_client.get(
            "/analytics/meta/spend?time_increment=1&breakdowns=region"
        )
        assert response.status_code == 200

        data = response.json()
        assert "time_series" in data
        assert "breakdowns" in data
        assert len(data["time_series"]) >= 1
        assert len(data["breakdowns"]) >= 1


class TestAnalyticsKPIs:
    """Tests for GET /analytics/kpis"""

    @pytest.mark.asyncio
    async def test_get_kpis(self, authed_client, sample_cases):
        """Returns KPI metrics."""
        response = await authed_client.get("/analytics/kpis")
        assert response.status_code == 200

        data = response.json()
        assert "new_cases" in data
        assert "total_active" in data
        assert "needs_attention" in data
        assert "period_days" in data


class TestAnalyticsFunnel:
    """Tests for GET /analytics/funnel"""

    @pytest.mark.asyncio
    async def test_get_funnel(self, authed_client, sample_cases):
        """Returns funnel stage data."""
        response = await authed_client.get("/analytics/funnel")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

        # Each stage should have stage info and counts
        for stage in data["data"]:
            assert "stage" in stage
            assert "count" in stage
            assert "percentage" in stage

        by_stage = {stage["stage"]: stage for stage in data["data"]}
        assert by_stage["new_unread"]["count"] == 9
        assert by_stage["contacted"]["count"] == 6
        assert by_stage["qualified"]["count"] == 4
