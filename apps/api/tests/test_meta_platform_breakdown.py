from datetime import UTC, datetime


def test_meta_platform_breakdown_counts(db, test_org):
    from app.db.models import MetaLead
    from app.services import analytics_meta_service

    now = datetime.now(UTC)
    leads = [
        MetaLead(
            organization_id=test_org.id,
            meta_lead_id="lead_fb",
            meta_form_id="form_1",
            meta_page_id="page_1",
            field_data_raw={"meta_platform": "facebook"},
            meta_created_time=now,
        ),
        MetaLead(
            organization_id=test_org.id,
            meta_lead_id="lead_ig",
            meta_form_id="form_1",
            meta_page_id="page_1",
            field_data_raw={"platform": "instagram"},
            meta_created_time=now,
        ),
        MetaLead(
            organization_id=test_org.id,
            meta_lead_id="lead_unknown",
            meta_form_id="form_1",
            meta_page_id="page_1",
            field_data_raw={},
            meta_created_time=now,
        ),
    ]
    db.add_all(leads)
    db.commit()

    result = analytics_meta_service.get_meta_platform_breakdown(db, test_org.id)
    counts = {item["platform"]: item["lead_count"] for item in result}

    assert counts.get("facebook") == 1
    assert counts.get("instagram") == 1
    assert counts.get("Unknown") == 1


def test_meta_attribution_columns_follow_field_data_updates(db, test_org):
    from sqlalchemy import event

    from app.db.models import MetaLead
    from app.services import analytics_meta_service

    lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_enriched",
        field_data={"ad_id": "ad_1"},
        field_data_raw={},
        meta_created_time=datetime.now(UTC),
    )
    db.add(lead)
    db.flush()
    assert (lead.meta_platform, lead.meta_ad_id) == (None, "ad_1")

    # Insight enrichment replaces field_data_raw; the trigger recomputes both columns.
    lead.field_data_raw = {"meta_platform": "Instagram", "meta_ad_id": "ad_2"}
    db.flush()
    assert (lead.meta_platform, lead.meta_ad_id) == ("Instagram", "ad_2")

    statements: list[str] = []

    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        platforms = analytics_meta_service.get_meta_platform_breakdown(db, test_org.id)
        by_ad = analytics_meta_service.get_leads_by_ad(db, test_org.id)
    finally:
        event.remove(engine, "before_cursor_execute", capture_sql)

    assert platforms == [{"platform": "instagram", "lead_count": 1}]
    assert [row["ad_id"] for row in by_ad] == ["ad_2"]
    assert not [sql for sql in statements if "field_data" in sql]
