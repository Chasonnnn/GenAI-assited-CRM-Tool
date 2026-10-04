"""OpenAPI contract guard for path/method/status shape."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app


def _build_contract() -> dict[str, dict[str, list[str]]]:
    schema = app.openapi()
    contract: dict[str, dict[str, list[str]]] = {}
    for path, methods in schema.get("paths", {}).items():
        method_contract: dict[str, list[str]] = {}
        for method, operation in methods.items():
            responses = sorted(
                operation.get("responses", {}).keys(),
                key=lambda x: int(x) if x.isdigit() else x,
            )
            method_contract[method.upper()] = responses
        contract[path] = method_contract
    return contract


def test_openapi_contract_snapshot_matches() -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "openapi_contract_snapshot.json"
    expected = json.loads(fixture.read_text(encoding="utf-8"))
    actual = _build_contract()
    assert actual == expected


def test_match_read_action_contract() -> None:
    fields = app.openapi()["components"]["schemas"]["MatchRead"]["properties"]
    assert fields["allowed_actions"]["type"] == "array"
    assert fields["allowed_actions"]["items"] == {"type": "string"}
    assert fields["blocked_reasons"]["type"] == "object"
    assert fields["blocked_reasons"]["additionalProperties"] == {"type": "string"}
    assert fields["pending_cancellation_request_id"]["anyOf"] == [
        {"type": "string"},
        {"type": "null"},
    ]


def test_task_reads_declare_nullable_form_context() -> None:
    schemas = app.openapi()["components"]["schemas"]
    for name in ("TaskRead", "TaskListItem"):
        fields = schemas[name]["properties"]
        for key in ("form_submission_id", "form_id"):
            assert fields[key]["anyOf"] == [{"type": "string", "format": "uuid"}, {"type": "null"}]
        assert fields["form_name"]["anyOf"] == [{"type": "string"}, {"type": "null"}]


def test_twilio_readiness_declares_toll_free_verification_status() -> None:
    properties = app.openapi()["components"]["schemas"]["TwilioRouteReadiness"]["properties"]
    assert properties["sender_type"]["anyOf"][0]["enum"] == ["10dlc", "toll_free", "unknown"]
    assert properties["toll_free_verification_status"]["anyOf"][0]["enum"] == [
        "PENDING_REVIEW",
        "IN_REVIEW",
        "TWILIO_APPROVED",
        "TWILIO_REJECTED",
    ]


def test_public_forms_declare_sms_phone_field_key() -> None:
    schemas = app.openapi()["components"]["schemas"]
    phone_key = schemas["MessagingConsentOptionsRead"]["properties"]["phone_field_key"]
    assert {item["type"] for item in phone_key["anyOf"]} == {"string", "null"}
    assert "phone_field_key" in schemas["MessagingConsentOptionsRead"]["required"]
    for name in ("FormIntakePublicRead", "FormEmbedPublicRead"):
        assert schemas[name]["properties"]["messaging_consent"]["$ref"] == (
            "#/components/schemas/MessagingConsentOptionsRead"
        )
    for surface in ("intake", "embed"):
        operation = app.openapi()["paths"][f"/forms/public/{surface}/{{slug}}/submit"]["post"]
        content = next(iter(operation["requestBody"]["content"].values()))
        body = schemas[content["schema"]["$ref"].rsplit("/", 1)[-1]]
        phone_key = body["properties"]["sms_phone_field_key"]
        assert {item["type"] for item in phone_key["anyOf"]} == {"string", "null"}
        assert "sms_phone_field_key" not in body["required"]
