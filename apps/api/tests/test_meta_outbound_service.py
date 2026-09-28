from app.services import meta_outbound_service


def test_resolve_stage_dedupe_key_uses_bucket_mapping():
    mapping = [
        {
            "stage_key": "pre_qualified",
            "event_name": "Qualified",
            "bucket": "qualified",
            "enabled": True,
        },
        {
            "stage_key": "interview_scheduled",
            "event_name": "Qualified",
            "bucket": "qualified",
            "enabled": True,
        },
    ]

    assert meta_outbound_service.resolve_stage_dedupe_key("pre_qualified", mapping) == "qualified"
    assert (
        meta_outbound_service.resolve_stage_dedupe_key("interview_scheduled", mapping)
        == "qualified"
    )


def test_build_stage_event_key_dedupes_same_meta_bucket():
    mapping = [
        {
            "stage_key": "pre_qualified",
            "event_name": "Qualified",
            "bucket": "qualified",
            "enabled": True,
        },
        {
            "stage_key": "interview_scheduled",
            "event_name": "Qualified",
            "bucket": "qualified",
            "enabled": True,
        },
    ]

    assert (
        meta_outbound_service.build_stage_event_key(
            "meta_crm_dataset", "lead-123", "pre_qualified", mapping
        )
        == "meta_crm_dataset:lead-123:qualified"
    )
    assert (
        meta_outbound_service.build_stage_event_key(
            "meta_crm_dataset", "lead-123", "interview_scheduled", mapping
        )
        == "meta_crm_dataset:lead-123:qualified"
    )


def test_map_bucket_to_meta_status():
    assert meta_outbound_service.map_bucket_to_meta_status("intake") == "Intake"
    assert meta_outbound_service.map_bucket_to_meta_status("qualified") == "Qualified/Converted"
    assert meta_outbound_service.map_bucket_to_meta_status("converted") == "Qualified/Converted"
    assert meta_outbound_service.map_bucket_to_meta_status("not_qualified") == "Not qualified/Lost"
    assert meta_outbound_service.map_bucket_to_meta_status("lost") == "Lost"
    assert meta_outbound_service.map_bucket_to_meta_status("none") is None


def test_map_stage_key_to_meta_status_for_org(db, test_org):
    assert (
        meta_outbound_service.map_stage_key_to_meta_status_for_org(
            db, test_org.id, "interview_scheduled"
        )
        == "Qualified/Converted"
    )
    assert (
        meta_outbound_service.map_stage_key_to_meta_status_for_org(
            db, test_org.id, "ready_to_match"
        )
        == "Qualified/Converted"
    )
    assert (
        meta_outbound_service.map_stage_key_to_meta_status_for_org(db, test_org.id, "contacted")
        == "Intake"
    )
    assert (
        meta_outbound_service.map_stage_key_to_meta_status_for_org(db, test_org.id, "disqualified")
        == "Not qualified/Lost"
    )


def test_clamp_meta_event_time_moves_only_events_older_than_six_days():
    from datetime import UTC, datetime, timedelta

    now = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
    recent = now - timedelta(days=5)
    old = now - timedelta(days=10)

    assert meta_outbound_service.clamp_meta_event_time(recent, now=now) == recent
    assert meta_outbound_service.clamp_meta_event_time(old, now=now) == now - timedelta(days=6)
    assert meta_outbound_service.clamp_meta_event_time(
        old.replace(tzinfo=None), now=now
    ) == now - timedelta(days=6)


def test_meta_lead_reporting_window_uses_the_sent_event_time():
    from datetime import UTC, datetime, timedelta

    event_time = datetime(2026, 9, 22, tzinfo=UTC)

    assert meta_outbound_service.is_meta_lead_within_reporting_window(
        event_time - timedelta(days=90), event_time=event_time
    )
    assert not meta_outbound_service.is_meta_lead_within_reporting_window(
        event_time - timedelta(days=91), event_time=event_time
    )
    assert meta_outbound_service.is_meta_lead_within_reporting_window(None, event_time=event_time)
