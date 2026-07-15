from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.performance.gates import (
    PlanExpectationConfigError,
    compare_plan_reports,
    parse_plan_expectations,
)
from scripts.performance.plans import PlanMetrics, compare_plan_metrics


def _plan(
    *,
    index_name: str,
    shared_blocks: int = 10,
    actual_rows: int = 10,
) -> list[dict[str, object]]:
    return [
        {
            "Plan": {
                "Node Type": "Index Scan",
                "Relation Name": "surrogates",
                "Index Name": index_name,
                "Total Cost": 10,
                "Plan Rows": 10,
                "Actual Rows": actual_rows,
                "Actual Loops": 1,
                "Shared Hit Blocks": shared_blocks,
                "Shared Read Blocks": 0,
                "Temp Read Blocks": 0,
                "Temp Written Blocks": 0,
                "WAL Records": 0,
                "WAL FPI": 0,
                "WAL Bytes": 0,
            }
        }
    ]


def _capture(
    scenario: str,
    prepared_plan_mode: str,
    capture_mode: str,
    *,
    index_name: str,
    shared_blocks: int = 10,
) -> dict[str, object]:
    return {
        "query_id": "surrogates_by_stage",
        "scenario": scenario,
        "prepared_plan_mode": prepared_plan_mode,
        "capture_mode": capture_mode,
        "plan": _plan(index_name=index_name, shared_blocks=shared_blocks),
    }


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload))
    return path


def test_legacy_per_query_expectation_remains_a_default_for_every_scenario() -> None:
    parsed = parse_plan_expectations(
        {
            "schema_version": 1,
            "queries": {
                "surrogates_by_stage": {
                    "required_nodes": ["Index Scan"],
                    "required_relations": ["surrogates"],
                    "allow_sequential_scan": False,
                }
            },
        }
    )

    hot = parsed["surrogates_by_stage"].for_scenario("hot:generic:estimated")
    cold = parsed["surrogates_by_stage"].for_scenario("cold:custom:analyze")

    assert hot == cold
    assert hot.required_nodes == {"Index Scan"}
    assert hot.required_relations == {"surrogates"}
    assert hot.allow_sequential_scan is False


def test_scenario_override_merges_with_defaults_without_affecting_other_scenarios() -> None:
    parsed = parse_plan_expectations(
        {
            "schema_version": 1,
            "queries": {
                "surrogates_by_stage": {
                    "defaults": {
                        "required_nodes": ["Index Scan"],
                        "required_relations": ["surrogates"],
                        "max_temp_blocks": 0,
                    },
                    "scenarios": {
                        "hot:generic:estimated": {"required_indexes": ["idx_surrogates_hot"]},
                        "cold:custom:analyze": {
                            "required_indexes": ["idx_surrogates_cold"],
                            "estimated_rows_max": 20,
                        },
                    },
                }
            },
        }
    )

    hot = parsed["surrogates_by_stage"].for_scenario("hot:generic:estimated")
    cold = parsed["surrogates_by_stage"].for_scenario("cold:custom:analyze")
    fallback = parsed["surrogates_by_stage"].for_scenario("hot:automatic:analyze")

    assert hot.required_nodes == {"Index Scan"}
    assert hot.required_relations == {"surrogates"}
    assert hot.required_indexes == {"idx_surrogates_hot"}
    assert cold.required_indexes == {"idx_surrogates_cold"}
    assert cold.estimated_rows_max == 20
    assert fallback.required_indexes == set()
    assert fallback.max_temp_blocks == 0


def test_report_comparison_applies_the_exact_scenario_override(tmp_path: Path) -> None:
    captures = [
        _capture("hot", "generic", "estimated", index_name="idx_surrogates_hot"),
        _capture("cold", "custom", "analyze", index_name="idx_surrogates_cold"),
    ]
    report_path = _write(
        tmp_path / "report.json",
        {"schema_version": 1, "captures": captures},
    )
    expectations_path = _write(
        tmp_path / "expectations.json",
        {
            "schema_version": 1,
            "queries": {
                "surrogates_by_stage": {
                    "defaults": {
                        "required_nodes": ["Index Scan"],
                        "required_relations": ["surrogates"],
                    },
                    "scenarios": {
                        "hot:generic:estimated": {"required_indexes": ["idx_surrogates_hot"]},
                        "cold:custom:analyze": {"required_indexes": ["idx_surrogates_cold"]},
                    },
                }
            },
        },
    )

    report, failed = compare_plan_reports(
        base_report_path=report_path,
        candidate_report_path=report_path,
        expectations_path=expectations_path,
    )

    assert failed is False
    assert report["gate"] == "passed"
    assert len(report["results"]) == 2
    assert all(result["failures"] == [] for result in report["results"])


def test_scenario_invariants_do_not_weaken_deterministic_growth_budgets(tmp_path: Path) -> None:
    base_path = _write(
        tmp_path / "base.json",
        {
            "schema_version": 1,
            "captures": [
                _capture(
                    "hot",
                    "generic",
                    "estimated",
                    index_name="idx_surrogates_hot",
                    shared_blocks=100,
                )
            ],
        },
    )
    candidate_path = _write(
        tmp_path / "candidate.json",
        {
            "schema_version": 1,
            "captures": [
                _capture(
                    "hot",
                    "generic",
                    "estimated",
                    index_name="idx_surrogates_hot",
                    shared_blocks=200,
                )
            ],
        },
    )
    expectations_path = _write(
        tmp_path / "expectations.json",
        {
            "schema_version": 1,
            "queries": {
                "surrogates_by_stage": {
                    "defaults": {"required_nodes": ["Index Scan"]},
                    "scenarios": {
                        "hot:generic:estimated": {"required_indexes": ["idx_surrogates_hot"]}
                    },
                }
            },
        },
    )

    report, failed = compare_plan_reports(
        base_report_path=base_path,
        candidate_report_path=candidate_path,
        expectations_path=expectations_path,
    )

    assert failed is True
    assert [failure["metric"] for failure in report["results"][0]["failures"]] == ["logical_blocks"]


@pytest.mark.parametrize(
    ("query_payload", "message"),
    [
        (
            {
                "defaults": {"required_nodes": ["Index Scan"]},
                "scenarios": {"hot:generic": {}},
            },
            "scenario key",
        ),
        (
            {
                "defaults": {"required_nodes": ["Index Scan"], "mystery_budget": 1},
                "scenarios": {},
            },
            "unknown invariant fields",
        ),
        (
            {
                "defaults": {"allow_sequential_scan": "false"},
                "scenarios": {},
            },
            "allow_sequential_scan",
        ),
    ],
)
def test_expectation_parser_rejects_ambiguous_or_mistyped_config(
    query_payload: dict[str, object], message: str
) -> None:
    with pytest.raises(PlanExpectationConfigError, match=message):
        parse_plan_expectations(
            {
                "schema_version": 1,
                "queries": {"surrogates_by_stage": query_payload},
            }
        )


def test_checked_in_expectations_parse() -> None:
    api_root = Path(__file__).resolve().parents[1]
    payload = json.loads((api_root / "performance" / "plan-expectations.json").read_text())

    parsed = parse_plan_expectations(payload)

    assert len(parsed) == 10


def test_checked_in_expectations_preserve_legacy_role_plan_variants() -> None:
    api_root = Path(__file__).resolve().parents[1]
    payload = json.loads((api_root / "performance" / "plan-expectations.json").read_text())

    parsed = parse_plan_expectations(payload)

    for tenant in ("hot", "cold"):
        for capture_mode in ("estimated", "analyze"):
            invariant = parsed["tasks_open_by_owner"].for_scenario(
                f"{tenant}:generic:{capture_mode}"
            )
            assert invariant.required_nodes == {
                "Bitmap Heap Scan",
                "Bitmap Index Scan",
                "Limit",
            }
            assert invariant.required_indexes == {"idx_tasks_org_owner"}
            assert invariant.allow_sequential_scan is False

    tasks = parsed["tasks_open_by_owner"].for_scenario("hot:generic:analyze")

    task_plan = PlanMetrics(
        node_types=frozenset({"Bitmap Heap Scan", "Bitmap Index Scan", "Limit"}),
        join_types=frozenset(),
        relations=frozenset({"tasks"}),
        indexes=frozenset({"idx_tasks_org_owner"}),
        estimated_cost=36.24,
        estimated_rows=20,
        logical_blocks=3,
        scanned_rows=8,
        loop_count=1,
        temp_blocks=0,
        wal_records=0,
        wal_fpi=0,
        wal_bytes=0,
    )
    assert compare_plan_metrics(task_plan, task_plan, tasks) == []
    missing_task_index = PlanMetrics(
        **{**task_plan.__dict__, "indexes": frozenset({"unrelated_index"})}
    )
    assert [
        failure.metric for failure in compare_plan_metrics(task_plan, missing_task_index, tasks)
    ] == ["required_index"]
    adverse_task_plan = PlanMetrics(
        **{
            **task_plan.__dict__,
            "node_types": frozenset({"Limit", "Seq Scan"}),
            "indexes": frozenset(),
        }
    )
    assert {
        failure.metric for failure in compare_plan_metrics(task_plan, adverse_task_plan, tasks)
    } == {"required_node", "required_index", "forbidden_node"}

    for plan_mode in ("generic", "automatic"):
        for capture_mode in ("estimated", "analyze"):
            invariant = parsed["analytics_surrogates_by_stage"].for_scenario(
                f"hot:{plan_mode}:{capture_mode}"
            )
            assert invariant.required_joins == {"Inner", "Right"}
            assert invariant.required_indexes == {"idx_surrogates_org_active"}

    analytics = parsed["analytics_surrogates_by_stage"].for_scenario("hot:automatic:analyze")

    analytics_plan = PlanMetrics(
        node_types=frozenset({"Aggregate", "Hash", "Hash Join", "Index Scan", "Seq Scan"}),
        join_types=frozenset({"Inner", "Right"}),
        relations=frozenset({"pipeline_stages", "pipelines", "surrogates"}),
        indexes=frozenset({"idx_surrogates_org_active"}),
        estimated_cost=498.92,
        estimated_rows=24,
        logical_blocks=1051,
        scanned_rows=4090,
        loop_count=3,
        temp_blocks=0,
        wal_records=0,
        wal_fpi=0,
        wal_bytes=0,
    )
    assert compare_plan_metrics(analytics_plan, analytics_plan, analytics) == []
    missing_analytics_index = PlanMetrics(
        **{**analytics_plan.__dict__, "indexes": frozenset({"unrelated_index"})}
    )
    assert [
        failure.metric
        for failure in compare_plan_metrics(analytics_plan, missing_analytics_index, analytics)
    ] == ["required_index"]
    adverse_analytics_plan = PlanMetrics(
        **{
            **analytics_plan.__dict__,
            "join_types": frozenset({"Inner"}),
            "indexes": frozenset({"unrelated_index"}),
        }
    )
    assert {
        failure.metric
        for failure in compare_plan_metrics(analytics_plan, adverse_analytics_plan, analytics)
    } == {"required_join", "required_index"}
