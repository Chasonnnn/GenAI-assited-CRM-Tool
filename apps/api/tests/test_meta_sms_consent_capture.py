from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.db.models import (
    MessagingConsentEvidence,
    MessagingConsentState,
    MessagingContact,
    MetaFormVersion,
    MetaLead,
    MetaPageMapping,
)
from app.db.models.meta import MetaFormLegalSnapshot
from app.jobs.handlers.meta import process_meta_lead_fetch
from app.services import meta_api, meta_lead_service, meta_sync_service, meta_token_service


class _Response:
    status_code = 200
    headers: dict[str, str] = {}
    text = ""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _CapturingClient:
    def __init__(self, calls: list[SimpleNamespace], payload: dict) -> None:
        self._calls = calls
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None):
        self._calls.append(SimpleNamespace(url=url, params=params))
        return _Response(self._payload)


@pytest.mark.asyncio
async def test_meta_lead_fetch_requests_disclaimer_responses(monkeypatch):
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(meta_api.settings, "META_TEST_MODE", False)
    monkeypatch.setattr(
        meta_api.httpx,
        "AsyncClient",
        lambda **_kwargs: _CapturingClient(
            calls,
            {
                "id": "lead_1",
                "field_data": [],
                "custom_disclaimer_responses": [
                    {"checkbox_key": "sms_operational", "is_checked": True}
                ],
            },
        ),
    )

    data, error = await meta_api.fetch_lead_details("lead_1", "token")

    assert error is None
    assert data is not None
    assert data["custom_disclaimer_responses"][0]["is_checked"] is True
    assert "custom_disclaimer_responses" in calls[0].params["fields"].split(",")


@pytest.mark.asyncio
async def test_meta_form_fetch_requests_legal_content_separately_from_questions(monkeypatch):
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(meta_api.settings, "META_TEST_MODE", False)
    monkeypatch.setattr(
        meta_api.httpx,
        "AsyncClient",
        lambda **_kwargs: _CapturingClient(calls, {"data": []}),
    )

    forms, error = await meta_api.fetch_page_leadgen_forms("page_1", "token")

    assert error is None
    assert forms == []
    requested_fields = set(calls[0].params["fields"].split(","))
    assert {"questions", "legal_content", "privacy_policy_url"} <= requested_fields


def test_meta_legal_copy_has_an_independent_immutable_snapshot(db, test_org):
    questions = [{"key": "phone_number", "label": "Phone", "type": "PHONE"}]
    first_form, first_schema_created = meta_sync_service._upsert_form(
        db,
        test_org.id,
        "page_1",
        {
            "id": "form_1",
            "name": "Surrogate inquiry",
            "questions": questions,
            "legal_content": {"custom_disclaimer": {"title": "SMS enrollment v1"}},
            "privacy_policy_url": "https://agency.example/privacy-v1",
        },
    )
    db.flush()
    first_schema_hash = db.get(MetaFormVersion, first_form.current_version_id).schema_hash

    second_form, second_schema_created = meta_sync_service._upsert_form(
        db,
        test_org.id,
        "page_1",
        {
            "id": "form_1",
            "name": "Surrogate inquiry",
            "questions": questions,
            "legal_content": {"custom_disclaimer": {"title": "SMS enrollment v2"}},
            "privacy_policy_url": "https://agency.example/privacy-v2",
        },
    )
    db.flush()

    snapshots = (
        db.query(MetaFormLegalSnapshot)
        .filter(MetaFormLegalSnapshot.form_id == first_form.id)
        .order_by(MetaFormLegalSnapshot.detected_at.asc(), MetaFormLegalSnapshot.id.asc())
        .all()
    )
    assert first_schema_created is True
    assert second_schema_created is False
    assert db.get(MetaFormVersion, second_form.current_version_id).schema_hash == first_schema_hash
    assert len(snapshots) == 2
    assert snapshots[0].legal_content_hash != snapshots[1].legal_content_hash
    assert snapshots[1].privacy_policy_url == "https://agency.example/privacy-v2"


@pytest.mark.asyncio
async def test_meta_lead_job_retains_disclaimer_response_and_legal_snapshot(
    db, test_org, monkeypatch
):
    mapping = MetaPageMapping(
        organization_id=test_org.id,
        page_id="page_1",
        page_name="Agency",
        is_active=True,
    )
    db.add(mapping)
    form, _ = meta_sync_service._upsert_form(
        db,
        test_org.id,
        "page_1",
        {
            "id": "form_1",
            "name": "Surrogate inquiry",
            "questions": [],
            "legal_content": {
                "custom_disclaimer": {
                    "checkboxes": [
                        {
                            "key": "sms_operational",
                            "text": "I agree to receive application texts.",
                        },
                        {
                            "key": "sms_promotional",
                            "text": "I agree to receive promotional texts.",
                        },
                    ]
                }
            },
            "privacy_policy_url": "https://agency.example/privacy",
        },
    )
    db.commit()

    monkeypatch.setattr(
        meta_token_service,
        "get_token_for_page",
        lambda *_args, **_kwargs: SimpleNamespace(token="page-token", connection_id=None),
    )

    async def fake_fetch(*_args, **_kwargs):
        return (
            {
                "id": "lead_1",
                "created_time": "2026-07-31T12:00:00+0000",
                "field_data": [{"name": "phone_number", "values": ["+15554810901"]}],
                "form_id": "form_1",
                "page_id": "page_1",
                "custom_disclaimer_responses": [
                    {"checkbox_key": "sms_operational", "is_checked": True},
                    {"checkbox_key": "sms_promotional", "is_checked": False},
                ],
            },
            None,
        )

    monkeypatch.setattr(meta_api, "fetch_lead_details", fake_fetch)
    monkeypatch.setattr(
        meta_lead_service,
        "process_stored_meta_lead",
        lambda *_args, **_kwargs: ("stored", None),
    )

    await process_meta_lead_fetch(
        db,
        SimpleNamespace(payload={"leadgen_id": "lead_1", "page_id": "page_1"}),
    )

    lead = (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == test_org.id,
            MetaLead.meta_lead_id == "lead_1",
        )
        .one()
    )
    snapshot = db.get(MetaFormLegalSnapshot, lead.meta_form_legal_snapshot_id)
    assert lead.custom_disclaimer_responses == [
        {"checkbox_key": "sms_operational", "is_checked": True},
        {"checkbox_key": "sms_promotional", "is_checked": False},
    ]
    assert snapshot is not None
    assert snapshot.form_id == form.id

    contact = (
        db.query(MessagingContact)
        .filter(
            MessagingContact.organization_id == test_org.id,
            MessagingContact.meta_lead_id == lead.id,
        )
        .one()
    )
    operational = (
        db.query(MessagingConsentState)
        .filter(
            MessagingConsentState.contact_id == contact.id,
            MessagingConsentState.purpose == "operational",
        )
        .one()
    )
    promotional = (
        db.query(MessagingConsentState)
        .filter(
            MessagingConsentState.contact_id == contact.id,
            MessagingConsentState.purpose == "promotional",
        )
        .one()
    )
    evidence = db.query(MessagingConsentEvidence).filter_by(contact_id=contact.id).one()
    assert operational.status == "opted_in"
    assert promotional.status == "unknown"
    assert evidence.source == "meta_lead_ads"
    assert evidence.source_reference == "lead_1:sms_operational"
    assert evidence.disclosure_text_snapshot == "I agree to receive application texts."
    assert evidence.evidence_metadata == {
        "affirmative_action": "meta_custom_disclaimer_checkbox",
        "checkbox_key": "sms_operational",
        "legal_snapshot_id": str(snapshot.id),
        "privacy_policy_url": "https://agency.example/privacy",
    }
