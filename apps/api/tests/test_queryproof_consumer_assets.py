from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import tomllib
from typing import Any

import pytest

from scripts import queryproof_consumer
from scripts.performance.gates import parse_plan_expectations


API_ROOT = Path(__file__).resolve().parents[1]
PERFORMANCE_ROOT = API_ROOT / "performance"
QUERYPROOF_ROOT = PERFORMANCE_ROOT / "queryproof"

ESTIMATED_INVARIANT_KEYS = {
    "required_nodes",
    "forbidden_nodes",
    "required_joins",
    "forbidden_joins",
    "required_relations",
    "required_indexes",
    "forbidden_indexes",
    "allow_sequential_scan",
    "estimated_rows_min",
    "estimated_rows_max",
}
EXECUTOR_ONLY_INVARIANT_KEYS = {
    "max_loop_count",
    "max_heap_fetches",
    "max_index_searches",
    "max_rows_removed_by_filter",
    "max_rows_removed_by_join_filter",
    "max_rows_removed_by_index_recheck",
    "max_temp_blocks",
}


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
                    invariant = _normalized_invariant(
                        legacy_expectations[query["id"]].for_scenario(scenario)
                    )
                    if capture_mode == "estimated":
                        for key in EXECUTOR_ONLY_INVARIANT_KEYS:
                            invariant.pop(key, None)
                    expected[capture_id] = invariant

    actual = {capture["id"]: capture["invariant"] for capture in port["captures"]}
    assert actual == expected
    for invariant in actual.values():
        for key in ("required_relations", "required_indexes", "forbidden_indexes"):
            assert all(value.startswith("public.") for value in invariant[key])


def test_queryproof_expectations_separate_estimated_and_executor_evidence() -> None:
    captures = _load(QUERYPROOF_ROOT / "plan-expectations.json")["captures"]
    estimated = [capture for capture in captures if capture["capture_mode"] == "estimated"]
    analyzed = [capture for capture in captures if capture["capture_mode"] == "analyze"]

    assert len(estimated) == len(analyzed) == 60
    for capture in estimated:
        invariant = capture["invariant"]
        assert set(invariant) == ESTIMATED_INVARIANT_KEYS
        assert set(invariant).isdisjoint(EXECUTOR_ONLY_INVARIANT_KEYS)

    for capture in analyzed:
        invariant = capture["invariant"]
        assert set(invariant) == ESTIMATED_INVARIANT_KEYS | {
            "max_loop_count",
            "max_temp_blocks",
        }
        assert invariant["max_loop_count"] is None
        assert invariant["max_temp_blocks"] == 0


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


def test_queryproof_manifest_is_query_only_and_preserves_all_capture_ids() -> None:
    manifest = tomllib.loads((API_ROOT.parents[1] / "queryproof.toml").read_text())
    corpus = _load(QUERYPROOF_ROOT / "capture-corpus.json")
    expectations = _load(QUERYPROOF_ROOT / "plan-expectations.json")

    assert manifest["version"] == 1
    assert manifest["expectations_path"] == (
        "apps/api/performance/queryproof/plan-expectations.json"
    )
    assert manifest["database"] == {
        "admin_url_env": "QUERYPROOF_ADMIN_DATABASE_URL",
        "application_url_env": "DATABASE_URL",
        "application_url_scheme": "postgresql+psycopg",
        "application_role": queryproof_consumer.BENCHMARK_ROLE,
    }
    assert "service" not in manifest
    assert "probes" not in manifest
    assert "load" not in manifest
    assert set(manifest["profiles"]) == {"smoke", "production"}

    expected_capture_ids = {capture["id"] for capture in expectations["captures"]}
    actual_capture_ids: set[str] = set()
    manifest_queries = {query["id"]: query for query in manifest["queries"]}
    assert set(manifest_queries) == {query["id"] for query in corpus["queries"]}

    for corpus_query in corpus["queries"]:
        query = manifest_queries[corpus_query["id"]]
        assert query["path"] == corpus_query["path"]
        cases = {case["id"]: case for case in query["cases"]}
        for corpus_case in corpus_query["cases"]:
            case = cases[corpus_case["name"]]
            assert [parameter["kind"] for parameter in case["parameters"]] == (
                corpus_query["parameter_types"]
            )
            assert [parameter["value"] for parameter in case["parameters"]] == (
                corpus_case["parameters"]
            )
            for capture in case["captures"]:
                actual_capture_ids.add(
                    f"{query['id']}:{case['id']}:{capture['plan']}:{capture['capture']}"
                )

    assert actual_capture_ids == expected_capture_ids
    assert len(actual_capture_ids) == corpus["expected_capture_count"] == 120


def test_queryproof_lifecycle_uses_candidate_owned_migrations_seed_and_role_setup() -> None:
    manifest = tomllib.loads((API_ROOT.parents[1] / "queryproof.toml").read_text())

    assert manifest["lifecycle"]["migrate"] == [
        {
            "argv": ["uv", "run", "python", "-m", "alembic", "upgrade", "head"],
            "cwd": "apps/api",
            "env": {"ENV": "test"},
        }
    ]
    assert manifest["seeds"] == [
        {
            "id": "queryproof-cluster-role",
            "phase": "before_migrate",
            "command": {
                "argv": [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "scripts.queryproof_consumer",
                    "provision-role",
                ],
                "cwd": "apps/api",
                "env": {"QUERYPROOF_EXPECTED_SEED_PROFILE": "production"},
            },
        },
        {
            "id": "production-shaped-deterministic",
            "phase": "after_migrate",
            "command": {
                "argv": ["uv", "run", "python", "-m", "scripts.seed_mock_data"],
                "cwd": "apps/api",
                "env": {
                    "ENV": "test",
                    "DATA_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
                    "FERNET_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
                    "JWT_SECRET": "local-performance-jwt-secret-not-a-secret",
                    "META_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
                    "PII_HASH_KEY": "local-performance-pii-hash-key-not-a-secret",
                    "SEED_PROFILE": "production",
                    "SEED_RANDOM_SEED": "20260713",
                    "SEED_REDACT_SUMMARY": "true",
                    "VERSION_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
                },
            },
        },
        {
            "id": "queryproof-read-only-acl",
            "phase": "after_migrate",
            "command": {
                "argv": [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "scripts.queryproof_consumer",
                    "apply-role-acl",
                ],
                "cwd": "apps/api",
                "env": {"QUERYPROOF_EXPECTED_SEED_PROFILE": "production"},
            },
        },
    ]
    dependency = manifest["dependencies"]
    assert dependency == [
        {
            "id": "crm-deterministic-query-mode",
            "check": {
                "argv": [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "scripts.queryproof_consumer",
                    "doctor",
                ],
                "cwd": "apps/api",
                "env": {"QUERYPROOF_EXPECTED_SEED_PROFILE": "production"},
            },
        }
    ]


def test_queryproof_benchmark_role_is_read_only_and_relation_allowlisted() -> None:
    assert queryproof_consumer.BENCHMARK_ROLE == "crm_queryproof_app"
    assert queryproof_consumer.READ_ONLY_RELATIONS == (
        "automation_workflows",
        "org_intelligent_suggestion_rules",
        "pipeline_stages",
        "pipelines",
        "surrogates",
        "tasks",
        "workflow_executions",
    )
    assert queryproof_consumer.extension_statements() == (
        "CREATE EXTENSION IF NOT EXISTS pg_stat_statements",
    )
    statements = queryproof_consumer.role_acl_statements()
    combined = "\n".join(statements)
    assert "GRANT USAGE ON SCHEMA public" in combined
    assert "GRANT SELECT ON TABLE" in combined
    assert "GRANT INSERT" not in combined
    assert "GRANT UPDATE" not in combined
    assert "GRANT DELETE" not in combined
    assert "GRANT USAGE ON SEQUENCE" not in combined
    assert "REVOKE ALL PRIVILEGES ON ALL SEQUENCES" in combined
    for relation in queryproof_consumer.READ_ONLY_RELATIONS:
        assert f'public."{relation}"' in combined

    corpus_relations = {
        qualified.split(".", maxsplit=1)[1]
        for path in (QUERYPROOF_ROOT / "queries").glob("*.sql")
        for qualified in re.findall(r"\bpublic\.[a-z_][a-z0-9_]*\b", path.read_text())
    }
    assert corpus_relations == set(queryproof_consumer.READ_ONLY_RELATIONS)


def test_queryproof_consumer_doctor_requires_explicit_deterministic_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://local.invalid/db")
    monkeypatch.setenv("QUERYPROOF_EXPECTED_SEED_PROFILE", "production")
    monkeypatch.delenv("QUERYPROOF_MODE", raising=False)
    with pytest.raises(RuntimeError, match="QUERYPROOF_MODE"):
        queryproof_consumer.doctor(os.environ)

    monkeypatch.setenv("QUERYPROOF_MODE", "deterministic")
    queryproof_consumer.doctor(os.environ)
