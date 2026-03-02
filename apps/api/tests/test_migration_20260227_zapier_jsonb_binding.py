from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa


def _load_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260227_1200_stage_key_pre_qualified_cutover.py"
    )
    spec = importlib.util.spec_from_file_location(
        "migration_20260227_1200_stage_key_pre_qualified_cutover", migration_path
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("Could not load migration module")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows
        self.update_calls: list[tuple[object, dict[str, object] | None]] = []

    def execute(self, statement, params=None):
        sql = str(statement)
        if "SELECT id, outbound_event_mapping FROM zapier_webhook_settings" in sql:
            return _FakeResult(self._rows)
        self.update_calls.append((statement, params))
        return None


def test_rewrite_zapier_mappings_binds_json_payload_with_json_type():
    migration = _load_migration_module()

    conn = _FakeConn(
        [
            {
                "id": uuid4(),
                "outbound_event_mapping": [
                    {
                        "stage_slug": "qualified",
                        "event_name": "QualifiedLead",
                        "enabled": True,
                    }
                ],
            }
        ]
    )

    migration._rewrite_zapier_mappings(conn)

    assert conn.update_calls, "Expected migration to emit an UPDATE for normalized mapping"
    statement, params = conn.update_calls[0]
    assert params is not None
    outbound_event_mapping = params["outbound_event_mapping"]
    bind_type = statement._bindparams["outbound_event_mapping"].type
    assert isinstance(bind_type, sa.JSON), "JSON payload must be bound with JSON type"

    payload = json.loads(json.dumps(outbound_event_mapping))
    assert payload[0]["stage_key"] == "pre_qualified"
    assert payload[0]["event_name"] == "PreQualifiedLead"
