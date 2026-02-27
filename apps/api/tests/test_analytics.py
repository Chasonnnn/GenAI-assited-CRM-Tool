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
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal

import pytest

from app.core.encryption import hash_email, hash_phone
from app.db.models import Surrogate, PipelineStage, MetaLead, MetaAdAccount, MetaDailySpend
from app.utils.normalization import normalize_email


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
        ("pre_qualified", "Pre-Qualified", 3, "#8B5CF6"),
        ("application_submitted", "Application Submitted", 4, "#8B5CF6"),
        ("approved", "Approved", 8, "#22C55E"),
    ]

    stages = {}
    for slug, label, order, color in stages_data:
        stage = (
            db.query(PipelineStage)
            .filter(PipelineStage.pipeline_id == pipeline.id, PipelineStage.slug == slug)
            .first()
        )

        if not stage:
            stage = PipelineStage(
                id=uuid.uuid4(),
                pipeline_id=pipeline.id,
                stage_key=slug,
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
            ("pre_qualified", 2),
            ("application_submitted", 1),
            ("approved", 1),
        ]
    ):
        stage = stages[stage_slug]
        for j in range(count):
            email = f"test{i}{j}@example.com"
            normalized_email = normalize_email(email)
            phone = "555-0100"
            case = Surrogate(
                id=uuid.uuid4(),
                organization_id=test_org.id,
                stage_id=stage.id,
                full_name=f"Test User {i}{j}",
                status_label=stage.label,
                email=normalized_email,
                email_hash=hash_email(normalized_email),
                phone=phone,
                phone_hash=hash_phone(phone),
                source="website",
                surrogate_number=f"S{10001 + (i * 10) + j:05d}",
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

    # Find cases in pre-qualified and approved stages
    pre_qualified_case = None
    converted_case = None
    approved_case = None

    for case in sample_cases:
        stage = db.query(PipelineStage).filter(PipelineStage.id == case.stage_id).first()
        if stage.slug == "pre_qualified" and not pre_qualified_case:
            pre_qualified_case = case
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

    # Create converted lead (pre-qualified)
    if pre_qualified_case:
        lead2 = MetaLead(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            meta_page_id="test-page",
            meta_lead_id=f"lead-{uuid.uuid4().hex[:8]}",
            meta_created_time=datetime.now(timezone.utc) - timedelta(days=3),
            received_at=datetime.now(timezone.utc) - timedelta(days=3),
            is_converted=True,
            converted_surrogate_id=pre_qualified_case.id,
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
            converted_surrogate_id=converted_case.id,
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
            converted_surrogate_id=approved_case.id,
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
        assert "total_surrogates" in data
        assert "new_this_period" in data
        assert "pre_qualified_rate" in data
        assert data["total_surrogates"] >= 0

    @pytest.mark.asyncio
    async def test_summary_with_date_range(self, authed_client, sample_cases):
        """Summary respects date range filters."""
        from_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        response = await authed_client.get(
            f"/analytics/summary?from_date={from_date}&to_date={to_date}"
        )
        assert response.status_code == 200

        data = response.json()
        assert "total_surrogates" in data

    @pytest.mark.asyncio
    async def test_summary_requires_auth(self, client):
        """Summary endpoint requires authentication."""
        response = await client.get("/analytics/summary")
        assert response.status_code == 401


class TestCasesByStatus:
    """Tests for GET /analytics/surrogates/by-status"""

    @pytest.mark.asyncio
    async def test_get_surrogates_by_status(self, authed_client, sample_cases):
        """Returns case counts grouped by status."""
        response = await authed_client.get("/analytics/surrogates/by-status")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # Each item should have status and count
        for item in data:
            assert "status" in item
            assert "count" in item
            assert isinstance(item["count"], int)


class TestCasesByAssignee:
    """Tests for GET /analytics/surrogates/by-assignee"""

    @pytest.mark.asyncio
    async def test_get_surrogates_by_assignee(self, authed_client, sample_cases):
        """Returns case counts grouped by assignee."""
        response = await authed_client.get("/analytics/surrogates/by-assignee")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # Each item should have user info and count
        for item in data:
            assert "count" in item
            assert isinstance(item["count"], int)


class TestCasesTrend:
    """Tests for GET /analytics/surrogates/trend"""

    @pytest.mark.asyncio
    async def test_get_surrogates_trend(self, authed_client, sample_cases):
        """Returns case creation trend data."""
        response = await authed_client.get("/analytics/surrogates/trend")
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
        response = await authed_client.get("/analytics/surrogates/trend?period=week")
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
        assert "leads_pre_qualified" in data
        assert "leads_converted" in data
        assert "pre_qualification_rate" in data
        assert "conversion_rate" in data
        assert "avg_time_to_convert_hours" in data

    @pytest.mark.asyncio
    async def test_meta_performance_counts(self, authed_client, sample_meta_leads):
        """Meta performance returns correct counts."""
        response = await authed_client.get("/analytics/meta/performance")
        assert response.status_code == 200

        data = response.json()
        assert data["leads_received"] == 4
        assert data["leads_pre_qualified"] == 3
        assert data["leads_converted"] == 2
        assert data["pre_qualification_rate"] >= 0
        assert data["conversion_rate"] >= 0

    @pytest.mark.asyncio
    async def test_meta_performance_with_date_range(self, authed_client, sample_meta_leads):
        """Meta performance respects date range."""
        from_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
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
        from_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
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
    """Tests for stored Meta spend endpoints."""

    @pytest.mark.asyncio
    async def test_meta_spend_totals(self, authed_client, db, test_org):
        """Meta spend totals reflect stored spend data."""
        ad_account = MetaAdAccount(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            ad_account_external_id="act_test_123",
            ad_account_name="Test Ad Account",
            is_active=True,
            spend_synced_at=datetime.now(timezone.utc),
        )
        db.add(ad_account)
        db.flush()

        spend_row = MetaDailySpend(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            ad_account_id=ad_account.id,
            spend_date=date.today(),
            campaign_external_id="cmp_123",
            campaign_name="Test Campaign",
            breakdown_type="_total",
            breakdown_value="_all",
            spend=Decimal("100.50"),
            impressions=1000,
            reach=900,
            clicks=50,
            leads=10,
        )
        db.add(spend_row)
        db.commit()

        response = await authed_client.get("/analytics/meta/spend/totals")
        assert response.status_code == 200

        data = response.json()
        assert data["total_spend"] == 100.5
        assert data["total_leads"] == 10
        assert data["sync_status"] == "synced"


class TestAnalyticsKPIs:
    """Tests for GET /analytics/kpis"""

    @pytest.mark.asyncio
    async def test_get_kpis(self, authed_client, sample_cases):
        """Returns KPI metrics."""
        response = await authed_client.get("/analytics/kpis")
        assert response.status_code == 200

        data = response.json()
        assert "new_surrogates" in data
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
        assert by_stage["pre_qualified"]["count"] == 4


# =============================================================================
# Performance By User Tests
# =============================================================================


@pytest.fixture
def performance_pipeline_stages(db, test_org):
    """Create pipeline stages matching PERFORMANCE_STAGE_SLUGS."""
    from app.db.models import Pipeline, PipelineStage

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

    # Stages matching PERFORMANCE_STAGE_SLUGS
    stages_data = [
        ("new_unread", "New Unread", 1, "#3B82F6"),
        ("contacted", "Contacted", 2, "#10B981"),
        ("pre_qualified", "Pre-Qualified", 3, "#8B5CF6"),
        ("ready_to_match", "Ready to Match", 4, "#F59E0B"),
        ("matched", "Matched", 5, "#22C55E"),
        ("application_submitted", "Application Submitted", 6, "#8B5CF6"),
        ("lost", "Lost", 7, "#EF4444"),
    ]

    stages = {}
    for slug, label, order, color in stages_data:
        stage = (
            db.query(PipelineStage)
            .filter(PipelineStage.pipeline_id == pipeline.id, PipelineStage.slug == slug)
            .first()
        )

        if not stage:
            stage = PipelineStage(
                id=uuid.uuid4(),
                pipeline_id=pipeline.id,
                stage_key=slug,
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
    return {"pipeline": pipeline, "stages": stages}


@pytest.fixture
def second_test_user(db, test_org):
    """Create a second test user for performance comparison."""
    from app.db.models import User, Membership
    from app.db.enums import Role

    user = User(
        id=uuid.uuid4(),
        email=f"test2-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Second User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=test_org.id,
        role=Role.CASE_MANAGER,
    )
    db.add(membership)
    db.flush()

    return user


@pytest.fixture
def performance_cases(db, test_org, test_user, second_test_user, performance_pipeline_stages):
    """Create sample cases with status history for performance testing."""
    from app.db.models import Surrogate, SurrogateStatusHistory, Queue
    from app.core.encryption import hash_email, hash_phone
    from app.utils.normalization import normalize_email

    stages = performance_pipeline_stages["stages"]
    cases = []

    # Create a queue for unassigned cases
    test_queue = Queue(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Test Queue",
        is_active=True,
    )
    db.add(test_queue)
    db.flush()

    # User 1: 3 cases - 2 reached application_submitted, 1 lost
    for i in range(3):
        email = f"perf_user1_{i}@example.com"
        normalized_email = normalize_email(email)
        case = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=stages["contacted"].id if i < 2 else stages["lost"].id,
            full_name=f"User1 Case {i}",
            status_label="Contacted" if i < 2 else "Lost",
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            phone="555-0100",
            phone_hash=hash_phone("555-0100"),
            source="website",
            surrogate_number=f"S{20001 + i:05d}",
            created_by_user_id=test_user.id,
            owner_type="user",
            owner_id=test_user.id,
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        db.add(case)
        db.flush()
        cases.append(case)

        # Add status history for progression
        if i < 2:  # Cases 0 and 1 reached application_submitted
            for stage_slug in [
                "contacted",
                "pre_qualified",
                "ready_to_match",
                "matched",
                "application_submitted",
            ]:
                history = SurrogateStatusHistory(
                    id=uuid.uuid4(),
                    surrogate_id=case.id,
                    organization_id=test_org.id,
                    to_stage_id=stages[stage_slug].id,
                    changed_by_user_id=test_user.id,
                    changed_at=datetime.now(timezone.utc)
                    - timedelta(days=25 - list(stages.keys()).index(stage_slug)),
                )
                db.add(history)
        else:  # Case 2 reached lost
            for stage_slug in ["contacted", "pre_qualified", "lost"]:
                history = SurrogateStatusHistory(
                    id=uuid.uuid4(),
                    surrogate_id=case.id,
                    organization_id=test_org.id,
                    to_stage_id=stages[stage_slug].id,
                    changed_by_user_id=test_user.id,
                    changed_at=datetime.now(timezone.utc)
                    - timedelta(days=25 - list(stages.keys()).index(stage_slug)),
                )
                db.add(history)

    # User 2: 2 cases - 1 reached matched only, 1 lost (but also reached application_submitted, should NOT count as lost)
    for i in range(2):
        email = f"perf_user2_{i}@example.com"
        normalized_email = normalize_email(email)
        case = Surrogate(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            stage_id=stages["matched"].id if i == 0 else stages["lost"].id,
            full_name=f"User2 Case {i}",
            status_label="Matched" if i == 0 else "Lost",
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            phone="555-0200",
            phone_hash=hash_phone("555-0200"),
            source="referral",
            surrogate_number=f"S{20010 + i:05d}",
            created_by_user_id=second_test_user.id,
            owner_type="user",
            owner_id=second_test_user.id,
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        db.add(case)
        db.flush()
        cases.append(case)

        if i == 0:  # Case reached matched only
            for stage_slug in ["contacted", "pre_qualified", "ready_to_match", "matched"]:
                history = SurrogateStatusHistory(
                    id=uuid.uuid4(),
                    surrogate_id=case.id,
                    organization_id=test_org.id,
                    to_stage_id=stages[stage_slug].id,
                    changed_by_user_id=second_test_user.id,
                    changed_at=datetime.now(timezone.utc)
                    - timedelta(days=25 - list(stages.keys()).index(stage_slug)),
                )
                db.add(history)
        else:  # Case reached application_submitted THEN lost (should NOT count as lost)
            for stage_slug in [
                "contacted",
                "pre_qualified",
                "ready_to_match",
                "matched",
                "application_submitted",
                "lost",
            ]:
                history = SurrogateStatusHistory(
                    id=uuid.uuid4(),
                    surrogate_id=case.id,
                    organization_id=test_org.id,
                    to_stage_id=stages[stage_slug].id,
                    changed_by_user_id=second_test_user.id,
                    changed_at=datetime.now(timezone.utc)
                    - timedelta(days=25 - list(stages.keys()).index(stage_slug)),
                )
                db.add(history)

    # Unassigned case (queue-owned - counted as unassigned)
    email = "perf_unassigned@example.com"
    normalized_email = normalize_email(email)
    unassigned_case = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        stage_id=stages["new_unread"].id,
        full_name="Unassigned Case",
        status_label="New Unread",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        phone="555-0300",
        phone_hash=hash_phone("555-0300"),
        source="website",
        surrogate_number="S20020",
        created_by_user_id=test_user.id,
        owner_type="queue",  # Queue-owned = unassigned
        owner_id=test_queue.id,  # Reference the queue
        created_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    db.add(unassigned_case)
    db.flush()
    cases.append(unassigned_case)

    db.commit()
    return cases


class TestPerformanceByUser:
    """Tests for GET /analytics/performance/by-user"""

    @pytest.mark.asyncio
    async def test_get_performance_by_user_returns_data(self, authed_client, performance_cases):
        """Returns performance data for all users."""
        response = await authed_client.get("/analytics/performance/by-user")
        assert response.status_code == 200

        data = response.json()
        assert "from_date" in data
        assert "to_date" in data
        assert "mode" in data
        assert "as_of" in data
        assert "data" in data
        assert "unassigned" in data
        assert data["mode"] == "cohort"
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_performance_user_metrics(self, authed_client, performance_cases, test_user):
        """Verifies correct metrics for test user."""
        response = await authed_client.get("/analytics/performance/by-user")
        assert response.status_code == 200

        data = response.json()
        user_data = None
        for user in data["data"]:
            if user["user_id"] == str(test_user.id):
                user_data = user
                break

        assert user_data is not None
        assert user_data["total_surrogates"] == 3
        assert user_data["contacted"] == 3  # All 3 reached contacted
        assert user_data["pre_qualified"] == 3  # All 3 reached pre-qualified
        assert user_data["application_submitted"] == 2  # 2 reached application_submitted
        assert user_data["lost"] == 1  # 1 lost (without application_submitted)

    @pytest.mark.asyncio
    async def test_lost_excludes_application_submitted(
        self, authed_client, performance_cases, second_test_user
    ):
        """Lost count excludes cases that reached application_submitted."""
        response = await authed_client.get("/analytics/performance/by-user")
        assert response.status_code == 200

        data = response.json()
        user2_data = None
        for user in data["data"]:
            if user["user_id"] == str(second_test_user.id):
                user2_data = user
                break

        assert user2_data is not None
        assert user2_data["total_surrogates"] == 2
        # Case that went application_submitted -> lost should NOT count as lost
        assert user2_data["lost"] == 0  # The lost case had also reached application_submitted
        assert user2_data["application_submitted"] == 1

    @pytest.mark.asyncio
    async def test_unassigned_bucket(self, authed_client, performance_cases):
        """Unassigned cases are grouped separately."""
        response = await authed_client.get("/analytics/performance/by-user")
        assert response.status_code == 200

        data = response.json()
        unassigned = data["unassigned"]
        assert unassigned["total_surrogates"] == 1

    @pytest.mark.asyncio
    async def test_conversion_rate_calculation(self, authed_client, performance_cases, test_user):
        """Conversion rate is calculated correctly."""
        response = await authed_client.get("/analytics/performance/by-user")
        assert response.status_code == 200

        data = response.json()
        user_data = None
        for user in data["data"]:
            if user["user_id"] == str(test_user.id):
                user_data = user
                break

        assert user_data is not None
        # User 1: 2 application_submitted out of 3 total = 66.67%
        expected_rate = (2 / 3) * 100
        assert abs(user_data["conversion_rate"] - expected_rate) < 0.1

    @pytest.mark.asyncio
    async def test_activity_mode(self, authed_client, performance_cases):
        """Activity mode returns data based on transitions in range."""
        response = await authed_client.get("/analytics/performance/by-user?mode=activity")
        assert response.status_code == 200

        data = response.json()
        assert data["mode"] == "activity"
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_date_range_filter(self, authed_client, performance_cases):
        """Date range filters cases correctly."""
        # Cases were created 30 days ago, filter to last 7 days should return fewer
        from_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        response = await authed_client.get(
            f"/analytics/performance/by-user?from_date={from_date}&to_date={to_date}"
        )
        assert response.status_code == 200

        data = response.json()
        # All cases were created 30 days ago, so none should match
        total_surrogates = sum(user["total_surrogates"] for user in data["data"])
        assert total_surrogates == 0

    @pytest.mark.asyncio
    async def test_requires_auth(self, client):
        """Endpoint requires authentication."""
        response = await client.get("/analytics/performance/by-user")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_zero_activity_users_included(
        self, authed_client, db, test_org, performance_pipeline_stages
    ):
        """Users with zero cases still appear in results."""
        from app.db.models import User, Membership
        from app.db.enums import Role

        # Create a user with no cases
        inactive_user = User(
            id=uuid.uuid4(),
            email=f"inactive-{uuid.uuid4().hex[:8]}@test.com",
            display_name="Inactive User",
            token_version=1,
            is_active=True,
        )
        db.add(inactive_user)
        db.flush()

        membership = Membership(
            id=uuid.uuid4(),
            user_id=inactive_user.id,
            organization_id=test_org.id,
            role=Role.INTAKE_SPECIALIST,
        )
        db.add(membership)
        db.commit()

        response = await authed_client.get("/analytics/performance/by-user")
        assert response.status_code == 200

        data = response.json()
        user_ids = [user["user_id"] for user in data["data"]]
        assert str(inactive_user.id) in user_ids

        inactive_data = next(u for u in data["data"] if u["user_id"] == str(inactive_user.id))
        assert inactive_data["total_surrogates"] == 0
