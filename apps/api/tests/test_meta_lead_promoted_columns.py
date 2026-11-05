"""Trigger-maintained Meta columns match the Python reads they replaced."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import event, text

from app.db.models import MetaLead, Surrogate
from app.services import (
    analytics_meta_service,
    meta_crm_dataset_service,
    zapier_outbound_service,
)

CLICK_ID_KEYS = ("fbc", "meta_fbc", "click_id", "meta_click_id")


def _key(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def _scalar(value):
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        for item in value:
            if found := _scalar(item):
                return found
    return None


def _search(doc):
    # Frozen copy of the outbound search that meta_lead_click_id_search replaced.
    if isinstance(doc, dict):
        for key, value in doc.items():
            if _key(str(key)) in CLICK_ID_KEYS and (found := _scalar(value)):
                return found
        for value in doc.values():
            if found := _search(value):
                return found
    elif isinstance(doc, list):
        for item in doc:
            if found := _search(item):
                return found
    return None


def _reference_click_id(raw, normalized, payload):
    found = (
        _search(raw or {}) or _search(normalized or {}) or _search(payload or {}) or ""
    ).strip()
    return found if found.startswith("fb.") else None


DOCS = [
    ({"fbc": "fb.1.a"}, None, None),
    ({"FBC": "  fb.1.upper\t"}, None, None),
    # str.strip() also removes Unicode whitespace.
    ({"fbc": "\u00a0fb.1.nbsp\u3000"}, None, None),
    ({"Meta Click-ID": ["", "fb.1.list"]}, None, None),
    ({"a": {"b": [{"meta_fbc": "fb.1.deep"}]}}, None, None),
    # Each object checks its own keys before nested values.
    ({"nested": {"fbc": "fb.1.nested"}, "click_id": "fb.1.own"}, None, None),
    # The first value found decides, even without the fb. prefix.
    ({"click_id": "gclid"}, {"fbc": "fb.1.later"}, None),
    ({"fbc": ""}, {"fbc": "   "}, {"fbc": "fb.1.payload"}),
    ({"fbc": 123}, {"fbc": None}, {"fbc": {"value": "fb.1.object"}}),
    ({"fbclid": "fb.1.not_a_key"}, None, None),
    ([{"fbc": "fb.1.top_list"}], None, None),
    ({"field_data": [{"name": "fbc", "values": ["fb.1.values"]}]}, None, None),
    ({"click id": "vfb.1"}, None, None),
    ({}, {}, {}),
    (None, None, None),
]


@pytest.mark.parametrize("raw,normalized,payload", DOCS)
def test_click_id_function_matches_the_python_search(db, raw, normalized, payload):
    stored = db.execute(
        text(
            "SELECT CAST(:raw AS jsonb), CAST(:normalized AS jsonb), CAST(:payload AS jsonb), "
            "meta_lead_click_id(CAST(:raw AS jsonb), CAST(:normalized AS jsonb), "
            "CAST(:payload AS jsonb))"
        ),
        {
            "raw": None if raw is None else json.dumps(raw),
            "normalized": None if normalized is None else json.dumps(normalized),
            "payload": None if payload is None else json.dumps(payload),
        },
    ).one()
    # Compare on the stored documents: jsonb keeps its own key order.
    assert stored[3] == _reference_click_id(*stored[:3])


def test_stage_event_lead_load_reads_the_click_id_column(db, test_org):
    lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_click",
        field_data={"question": "yes"},
        raw_payload={"tracking": {"fbc": "fb.1.click"}},
        meta_created_time=datetime.now(UTC),
    )
    db.add(lead)
    db.flush()
    lead_id = lead.id
    db.expire_all()

    statements: list[str] = []

    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        dataset_lead = (
            db.query(MetaLead)
            .options(*meta_crm_dataset_service.STAGE_EVENT_LEAD_LOAD)
            .filter(MetaLead.id == lead_id)
            .one()
        )
        assert dataset_lead.meta_click_id == "fb.1.click"
        assert len(statements) == 1
        assert "raw_payload" not in statements[0] and "field_data" not in statements[0]

        db.expunge_all()
        statements.clear()
        zapier_lead = (
            db.query(MetaLead)
            .options(*zapier_outbound_service.STAGE_EVENT_LEAD_LOAD)
            .filter(MetaLead.id == lead_id)
            .one()
        )
        zapier_outbound_service._extract_meta_fields(zapier_lead)
        assert zapier_lead.meta_click_id == "fb.1.click"
        assert len(statements) == 1
        assert "raw_payload" not in statements[0]
    finally:
        event.remove(engine, "before_cursor_execute", capture_sql)


def test_campaign_names_fall_back_to_the_promoted_ad_name(db, test_org, default_stage, test_user):
    db.add(
        Surrogate(
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            owner_type="user",
            owner_id=test_user.id,
            surrogate_number=f"S{uuid4().hex[:8]}",
            full_name="Ad Lead",
            email=f"ad-{uuid4().hex[:8]}@example.com",
            email_hash=uuid4().hex * 2,
            meta_ad_external_id="ad_unsynced",
            import_metadata={"meta_ad_name": "Imported spring ad", "question": "yes"},
        )
    )
    db.flush()

    statements: list[str] = []

    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        campaigns = analytics_meta_service.get_campaigns(db, test_org.id)
    finally:
        event.remove(engine, "before_cursor_execute", capture_sql)

    assert campaigns == [{"ad_id": "ad_unsynced", "ad_name": "Imported spring ad", "lead_count": 1}]
    assert not [sql for sql in statements if "import_metadata" in sql]
