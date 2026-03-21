from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.services import journey_service, pdf_export_service


def test_chart_svg_and_insight_helpers():
    trend = [{"date": "2026-01-01", "count": 3}, {"date": "2026-01-02", "count": 9}]
    status = [{"status": "approved", "count": 7}, {"status": "matched", "count": 2}]
    insights = pdf_export_service._compute_insights(trend, status)
    assert "Trend:" in insights["trend"]
    assert "Bottleneck:" in insights["bottleneck"]

    bars = pdf_export_service._generate_horizontal_bar_chart_svg(
        [{"label": "A", "value": 3}, {"label": "B", "value": 5}],
        "label",
        "value",
        "Horizontal",
    )
    assert "<svg" in bars and "Horizontal" in bars

    vertical = pdf_export_service._generate_vertical_bar_chart_svg(
        [{"status": "approved", "count": 4}, {"status": "matched", "count": 2}],
        "status",
        "count",
        "Vertical",
    )
    assert "<svg" in vertical and "Vertical" in vertical

    line = pdf_export_service._generate_line_chart_svg(
        [{"date": "2026-01-01", "count": 1}, {"date": "2026-01-02", "count": 2}],
        "Trend",
    )
    assert "<svg" in line and "Trend" in line

    pie = pdf_export_service._generate_pie_chart_svg(
        [{"name": "X", "value": 3}, {"name": "Y", "value": 1}],
        "name",
        "value",
        "Pie",
    )
    assert "<svg" in pie and "Pie" in pie

    funnel = pdf_export_service._generate_funnel_svg(
        [{"stage": "New", "count": 8}, {"stage": "Matched", "count": 2}],
        "Funnel",
    )
    assert "<svg" in funnel and "Funnel" in funnel

    us_map = pdf_export_service._generate_us_map_svg(
        [{"state": "CA", "count": 5}, {"state": "TX", "count": 3}],
        "Map",
    )
    assert "<svg" in us_map and "Map" in us_map


def test_generate_analytics_html_includes_sections():
    html = pdf_export_service._generate_analytics_html(
        summary={
            "total_surrogates": 12,
            "new_this_period": 5,
            "qualification_rate": 41.7,
            "pending_tasks": 2,
            "overdue_tasks": 1,
        },
        surrogates_by_status=[{"status": "approved", "count": 6}],
        surrogates_by_assignee=[{"user_email": "agent@example.com", "count": 4}],
        trend_data=[{"date": "2026-01-01", "count": 2}, {"date": "2026-01-02", "count": 5}],
        meta_performance={
            "leads_received": 12,
            "leads_qualified": 8,
            "leads_converted": 3,
            "conversion_rate": 25.0,
            "avg_time_to_convert_hours": 48,
        },
        org_name="Test Org",
        date_range="Jan 2026",
        funnel_data=[{"stage": "New", "count": 12}, {"stage": "Qualified", "count": 8}],
        state_data=[{"state": "CA", "count": 4}],
        performance_data={
            "columns": [
                {"stage_key": "contacted", "label": "Contacted"},
                {"stage_key": "application_submitted", "label": "Application Submitted"},
                {"stage_key": "lost", "label": "Lost"},
            ],
            "conversion_stage_key": "application_submitted",
            "data": [
                {
                    "user_name": "Owner",
                    "total_surrogates": 10,
                    "stage_counts": {
                        "contacted": 9,
                        "application_submitted": 5,
                        "lost": 1,
                    },
                    "conversion_rate": 30,
                    "avg_days_to_match": 10.5,
                    "avg_days_to_conversion": 4.5,
                }
            ],
            "unassigned": {"total_surrogates": 0, "stage_counts": {}},
        },
        meta_spend={"total_spend": 2500.0, "cost_per_lead": 33.33},
    )
    assert "Test Org Analytics Report" in html
    assert "Key Metrics" in html
    assert "AI Insights" in html
    assert "Conversion Funnel" in html
    assert "Individual Performance" in html


@pytest.mark.asyncio
async def test_export_analytics_pdf_async_uses_renderer(db, test_org, monkeypatch):
    from app.services import analytics_service

    monkeypatch.setattr(
        analytics_service,
        "get_pdf_export_data",
        lambda **_kwargs: {
            "summary": {
                "total_surrogates": 8,
                "new_this_period": 3,
                "qualification_rate": 37.5,
                "pending_tasks": 2,
                "overdue_tasks": 1,
            },
            "surrogates_by_status": [{"status": "approved", "count": 3}],
            "surrogates_by_assignee": [{"user_email": "agent@example.com", "count": 3}],
            "trend_data": [{"date": "2026-01-01", "count": 1}, {"date": "2026-01-02", "count": 2}],
            "meta_performance": {
                "leads_received": 0,
                "leads_qualified": 0,
                "leads_converted": 0,
                "conversion_rate": 0,
            },
            "org_name": "Test Org",
            "funnel_data": [],
            "state_data": [],
            "performance_data": {"data": [], "columns": [], "unassigned": {"total_surrogates": 0, "stage_counts": {}}},
        },
    )

    async def _fake_meta_spend_summary(**_kwargs):
        return {"total_spend": 0, "cost_per_lead": None}

    monkeypatch.setattr(analytics_service, "get_meta_spend_summary", _fake_meta_spend_summary)

    rendered_html: dict[str, str] = {}

    async def _fake_render_html_to_pdf(html_content: str) -> bytes:
        rendered_html["html"] = html_content
        return b"%PDF-1.7 analytics"

    monkeypatch.setattr(pdf_export_service, "_render_html_to_pdf", _fake_render_html_to_pdf)

    pdf_bytes = await pdf_export_service.export_analytics_pdf_async(
        db=db,
        organization_id=test_org.id,
        start_dt=None,
        end_dt=None,
        date_range_str="All Time",
    )
    assert pdf_bytes.startswith(b"%PDF")
    assert "Test Org Analytics Report" in rendered_html["html"]


def test_export_journey_pdf_and_generate_journey_html(db, test_org, monkeypatch):
    milestone = journey_service.JourneyMilestone(
        slug="application_intake",
        label="Application & Intake",
        description="Intake started",
        status="current",
        completed_at=None,
        is_soft=False,
        default_image_url="https://example.com/default.jpg",
    )
    phase = journey_service.JourneyPhase(
        slug="getting_started",
        label="Getting Started",
        milestones=[milestone],
    )
    response = journey_service.JourneyResponse(
        surrogate_id=str(uuid4()),
        surrogate_name="Candidate A",
        journey_version=1,
        is_terminal=True,
        terminal_message="Case is in terminal status",
        terminal_date=datetime.now(timezone.utc).isoformat(),
        phases=[phase],
        organization_name="Test Org",
        organization_logo_url=None,
    )
    monkeypatch.setattr(pdf_export_service.settings, "FRONTEND_URL", "")
    monkeypatch.setattr(journey_service, "get_journey", lambda *_args, **_kwargs: response)

    rendered: dict[str, str] = {}

    async def _fake_render_html_to_pdf(html_content: str):
        rendered["html"] = html_content
        return b"%PDF-1.7 journey"

    monkeypatch.setattr(pdf_export_service, "_render_html_to_pdf", _fake_render_html_to_pdf)

    surrogate_id = uuid4()
    pdf = pdf_export_service.export_journey_pdf(
        db=db,
        org_id=test_org.id,
        surrogate_id=surrogate_id,
        variant="internal",
    )
    assert pdf.startswith(b"%PDF")
    assert "Surrogacy Journey" in rendered["html"]
    assert "Candidate A" in rendered["html"]
    assert "Application &amp; Intake" in rendered["html"]

    journey_html = pdf_export_service._generate_journey_html(response, milestone_images={})
    assert "Surrogacy Journey" in journey_html
    assert "terminal-banner" in journey_html
    assert "Application &amp; Intake" in journey_html
