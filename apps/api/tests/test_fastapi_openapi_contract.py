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
