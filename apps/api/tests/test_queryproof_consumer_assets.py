from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import re
from typing import Any

from scripts.performance.gates import parse_plan_expectations


API_ROOT = Path(__file__).resolve().parents[1]
PERFORMANCE_ROOT = API_ROOT / "performance"
QUERYPROOF_ROOT = PERFORMANCE_ROOT / "queryproof"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _normalize_sql(sql: str) -> str:
    without_explicit_public_schema = re.sub(r"\bpublic\.", "", sql, flags=re.IGNORECASE)
    return " ".join(without_explicit_public_schema.split()).rstrip(";")


def _assert_relations_are_schema_qualified(sql: str) -> None:
    unqualified_relation = re.compile(
        r"\b(?:FROM|JOIN|UPDATE|INTO)\s+(?!public\.)[a-z_][a-z0-9_]*",
        flags=re.IGNORECASE,
    )
    assert not unqualified_relation.search(sql)


def _normalized_invariant(invariant: object) -> dict[str, object]:
    payload = asdict(invariant)
    normalized = {
        key: sorted(value) if isinstance(value, set) else value
        for key, value in payload.items()
        if key != "max_wal_bytes" or value is not None
    }
    for key in ("required_relations", "required_indexes", "forbidden_indexes"):
        normalized[key] = [f"public.{value}" for value in normalized[key]]
    return normalized


def test_queryproof_capture_assets_preserve_the_ten_query_matrix() -> None:
    legacy = _load(PERFORMANCE_ROOT / "capture-manifest.json")
    port = _load(QUERYPROOF_ROOT / "capture-corpus.json")

    assert port["schema_version"] == 1
    assert port["source"] == "apps/api/performance/capture-manifest.json"
    assert port["expected_capture_count"] == 120
    assert len(port["queries"]) == 10

    legacy_by_id = {query["id"]: query for query in legacy["queries"]}
    port_by_id = {query["id"]: query for query in port["queries"]}
    assert port_by_id.keys() == legacy_by_id.keys()

    captures: set[str] = set()
    for query_id, query in port_by_id.items():
        historical = legacy_by_id[query_id]
        assert "sql" not in query
        sql_path = API_ROOT.parents[1] / query["path"]
        assert sql_path.is_file()
        sql = sql_path.read_text()
        _assert_relations_are_schema_qualified(sql)
        assert _normalize_sql(sql) == _normalize_sql(historical["sql"])
        assert query["parameter_types"] == historical["parameter_types"]
        assert query["prepared_plan_modes"] == historical["prepared_plan_modes"]
        assert query["capture_modes"] == historical["capture_modes"]
        assert query["cases"] == historical["scenarios"]

        for case in query["cases"]:
            for plan_mode in query["prepared_plan_modes"]:
                for capture_mode in query["capture_modes"]:
                    captures.add(f"{query_id}:{case['name']}:{plan_mode}:{capture_mode}")

    assert len(captures) == port["expected_capture_count"]


def test_queryproof_expectations_preserve_every_legacy_capture_key() -> None:
    legacy_manifest = _load(PERFORMANCE_ROOT / "capture-manifest.json")
    legacy_expectations = parse_plan_expectations(
        _load(PERFORMANCE_ROOT / "plan-expectations.json")
    )
    port = _load(QUERYPROOF_ROOT / "plan-expectations.json")

    assert port["schema_version"] == 2
    assert port["source"] == "apps/api/performance/plan-expectations.json"
    assert port["engine_contract"] == "prepared-plan-and-capture-mode-invariants"
    assert port["identifier_schema"] == "public"
    assert len(port["captures"]) == 120

    expected: dict[str, dict[str, object]] = {}
    for query in legacy_manifest["queries"]:
        for case in query["scenarios"]:
            for plan_mode in query["prepared_plan_modes"]:
                for capture_mode in query["capture_modes"]:
                    scenario = f"{case['name']}:{plan_mode}:{capture_mode}"
                    capture_id = f"{query['id']}:{scenario}"
                    expected[capture_id] = _normalized_invariant(
                        legacy_expectations[query["id"]].for_scenario(scenario)
                    )

    actual = {capture["id"]: capture["invariant"] for capture in port["captures"]}
    assert actual == expected
    for invariant in actual.values():
        for key in ("required_relations", "required_indexes", "forbidden_indexes"):
            assert all(value.startswith("public.") for value in invariant[key])


def test_queryproof_critical_routes_and_statistics_allowlist_preserve_provenance() -> None:
    legacy_routes = _load(PERFORMANCE_ROOT / "critical-query-corpus.json")
    port_routes = _load(QUERYPROOF_ROOT / "critical-routes.json")

    assert port_routes["schema_version"] == 1
    assert port_routes["source"] == "apps/api/performance/critical-query-corpus.json"
    assert len(port_routes["queries"]) == len(legacy_routes["queries"]) == 12

    historical_by_name = {query["name"]: query for query in legacy_routes["queries"]}
    assert {query["name"] for query in port_routes["queries"]} == set(historical_by_name)
    assert len({query["path"] for query in port_routes["queries"]}) == 12
    for query in port_routes["queries"]:
        historical = historical_by_name[query["name"]]
        assert "query" not in query
        assert query["route"] == historical["route"]
        assert query["critical_reason"] == historical["critical_reason"]
        sql_path = API_ROOT.parents[1] / query["path"]
        assert sql_path.is_file()
        sql = sql_path.read_text()
        _assert_relations_are_schema_qualified(sql)
        assert _normalize_sql(sql) == _normalize_sql(historical["query"])

    assert _load(QUERYPROOF_ROOT / "statistics-allowlist.json") == _load(
        PERFORMANCE_ROOT / "statistics-allowlist.json"
    )


def test_queryproof_json_assets_never_embed_raw_sql() -> None:
    statement = re.compile(
        r"\b(?:select|with|insert|update|delete|merge|call|create|alter|drop)\b",
        flags=re.IGNORECASE,
    )
    for path in QUERYPROOF_ROOT.glob("*.json"):
        payload = _load(path)
        for key in ("sql", "query", "statement"):
            assert all(key not in item for item in payload.get("queries", []))
        assert not statement.search(json.dumps(payload))
