from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.performance.capture import (
    CaptureMode,
    ManifestError,
    PreparedPlanMode,
    capture_manifest,
    load_capture_manifest,
    parse_capture_manifest,
)


def _manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "queries": [
            {
                "id": "surrogates-by-stage",
                "sql": ("SELECT id FROM surrogates WHERE organization_id = $1 AND stage_id = $2"),
                "parameter_types": ["uuid", "text"],
                "prepared_plan_modes": ["generic", "custom", "automatic"],
                "capture_modes": ["estimated", "analyze"],
                "scenarios": [
                    {
                        "name": "hot",
                        "parameters": [
                            "00000000-0000-0000-0000-000000000001",
                            "qualified-hot-secret",
                        ],
                    },
                    {
                        "name": "cold",
                        "parameters": [
                            "00000000-0000-0000-0000-000000000099",
                            "cold-secret",
                        ],
                        "automatic_warmup_parameters": [
                            ["00000000-0000-0000-0000-000000000099", "cold-secret"]
                        ],
                    },
                ],
            }
        ],
    }


class _FakeTransaction:
    def __init__(self, connection: _FakeConnection, force_rollback: bool) -> None:
        self.connection = connection
        self.force_rollback = force_rollback

    def __enter__(self) -> None:
        self.connection.transaction_force_rollback.append(self.force_rollback)

    def __exit__(self, *_args: object) -> None:
        return None


class _FakeCursor:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, sql: str, parameters: object = None) -> None:
        self.connection.executions.append((sql, parameters))

    def fetchone(self) -> tuple[list[dict[str, object]]]:
        return (
            [
                {
                    "Plan": {
                        "Node Type": "Index Scan",
                        "Relation Name": "surrogates",
                        "Index Name": "ix_surrogates_org_stage",
                        "Total Cost": 42.5,
                        "Plan Rows": 10,
                        "Actual Rows": 4,
                        "Actual Loops": 1,
                        "Shared Hit Blocks": 8,
                        "Shared Read Blocks": 1,
                        "Temp Read Blocks": 0,
                        "Temp Written Blocks": 0,
                        "WAL Records": 0,
                        "WAL FPI": 0,
                        "WAL Bytes": 0,
                        "Filter": "(stage_id = 'qualified-hot-secret'::text)",
                        "Index Cond": (
                            "(organization_id = '00000000-0000-0000-0000-000000000001'::uuid)"
                        ),
                        "Output": ["id", "email"],
                    },
                    "Planning Time": 0.123,
                    "Execution Time": 0.456,
                    "Settings": {"plan_cache_mode": "force_custom_plan"},
                }
            ],
        )


class _FakeConnection:
    def __init__(self) -> None:
        self.executions: list[tuple[str, object]] = []
        self.transaction_force_rollback: list[bool] = []

    def transaction(self, *, force_rollback: bool) -> _FakeTransaction:
        return _FakeTransaction(self, force_rollback)

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)


def test_manifest_parsing_supports_hot_and_cold_prepared_plan_scenarios() -> None:
    manifest = parse_capture_manifest(_manifest())

    query = manifest.queries[0]
    assert query.query_id == "surrogates-by-stage"
    assert query.parameter_types == ("uuid", "text")
    assert query.prepared_plan_modes == (
        PreparedPlanMode.GENERIC,
        PreparedPlanMode.CUSTOM,
        PreparedPlanMode.AUTOMATIC,
    )
    assert query.capture_modes == (CaptureMode.ESTIMATED, CaptureMode.ANALYZE)
    assert [scenario.name for scenario in query.scenarios] == ["hot", "cold"]


def test_load_manifest_requires_json_and_does_not_accept_yaml(tmp_path: Path) -> None:
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(_manifest()))
    assert load_capture_manifest(path).queries[0].query_id == "surrogates-by-stage"

    yaml_path = tmp_path / "capture.yaml"
    yaml_path.write_text("schema_version: 1\nqueries: []\n")
    with pytest.raises(ManifestError, match="valid JSON"):
        load_capture_manifest(yaml_path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"unexpected": True}, "unknown fields"),
        ({"sql": "SELECT 1; SELECT 2"}, "single SQL statement"),
        ({"sql": "SELECT 1 -- hidden statement"}, "SQL comments"),
        ({"parameter_types": ["uuid); DROP TABLE users; --", "text"]}, "parameter type"),
        ({"sql": "SELECT $1, $3"}, "contiguous"),
    ],
)
def test_manifest_rejects_unsafe_or_ambiguous_queries(
    mutation: dict[str, object], message: str
) -> None:
    payload = _manifest()
    query = payload["queries"][0]  # type: ignore[index]
    assert isinstance(query, dict)
    query.update(mutation)

    with pytest.raises(ManifestError, match=message):
        parse_capture_manifest(payload)


def test_capture_uses_rollback_only_transactions_and_safe_explain_options() -> None:
    connection = _FakeConnection()
    manifest = parse_capture_manifest(_manifest())

    report = capture_manifest(connection, manifest)

    assert len(report.captures) == 12
    assert connection.transaction_force_rollback == [True] * 12
    explain_sql = [sql for sql, _ in connection.executions if sql.startswith("EXPLAIN")]
    assert len(explain_sql) == 12
    assert any(
        "ANALYZE TRUE" in sql
        and "BUFFERS TRUE" in sql
        and "WAL TRUE" in sql
        and "TIMING FALSE" in sql
        for sql in explain_sql
    )
    assert any("ANALYZE" not in sql and "FORMAT JSON" in sql for sql in explain_sql)


def test_capture_reports_omit_bind_values_and_expression_fields() -> None:
    connection = _FakeConnection()
    report = capture_manifest(connection, parse_capture_manifest(_manifest()))

    rendered = json.dumps(report.to_mapping(), sort_keys=True)

    assert "qualified-hot-secret" not in rendered
    assert "cold-secret" not in rendered
    assert "00000000-0000-0000-0000-000000000001" not in rendered
    assert '"Filter"' not in rendered
    assert '"Index Cond"' not in rendered
    assert '"Output"' not in rendered
    assert "plan_hash" not in rendered
    assert "ix_surrogates_org_stage" in rendered
    assert report.to_mapping()["captures"][0]["parameter_count"] == 2


def test_capture_disables_parameter_logging_and_warms_automatic_mode() -> None:
    connection = _FakeConnection()
    manifest = parse_capture_manifest(_manifest())

    capture_manifest(connection, manifest)

    setting_calls = [
        (sql, parameters) for sql, parameters in connection.executions if "set_config" in sql
    ]
    assert any(parameters == ("auto",) for _, parameters in setting_calls)
    assert any("auto_explain.log_parameter_max_length" in sql for sql, _ in setting_calls)
    assert any("log_parameter_max_length" in sql for sql, _ in setting_calls)

    automatic_transactions = 4
    automatic_warmups = [
        (sql, parameters) for sql, parameters in connection.executions if sql.startswith("EXECUTE")
    ]
    # Hot defaults to five warmups; cold explicitly supplies one. Each runs for
    # estimated and analyzed captures in automatic mode.
    assert len(automatic_warmups) == (5 + 1) * (automatic_transactions // 2)
    assert all("hot-secret" not in sql and "cold-secret" not in sql for sql, _ in automatic_warmups)
    assert all(
        "qualified-hot-secret" not in sql
        and "cold-secret" not in sql
        and "00000000-0000-0000-0000-000000000001" not in sql
        for sql, _ in connection.executions
    )
    assert all("%s" not in sql for sql, _ in automatic_warmups)


def test_write_capture_requires_explicit_opt_in_and_still_rolls_back() -> None:
    payload = _manifest()
    query = payload["queries"][0]  # type: ignore[index]
    assert isinstance(query, dict)
    query["sql"] = "UPDATE surrogates SET stage_id = $2 WHERE organization_id = $1"

    with pytest.raises(ManifestError, match="allow_write"):
        parse_capture_manifest(payload)

    query["allow_write"] = True
    connection = _FakeConnection()
    capture_manifest(connection, parse_capture_manifest(payload))
    assert connection.transaction_force_rollback == [True] * 12
