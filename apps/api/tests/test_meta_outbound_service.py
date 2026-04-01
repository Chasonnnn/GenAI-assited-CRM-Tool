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
    assert meta_outbound_service.map_stage_key_to_meta_status_for_org(
        db, test_org.id, "contacted"
    ) == "Intake"
    assert (
        meta_outbound_service.map_stage_key_to_meta_status_for_org(db, test_org.id, "disqualified")
        == "Not qualified/Lost"
    )
