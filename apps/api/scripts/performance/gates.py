from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from scripts.performance.plans import (
    PlanInvariant,
    compare_plan_metrics,
    extract_plan_metrics,
)
from scripts.performance.reporting import serialize_safe_report


def _invariant_from_payload(payload: dict[str, Any]) -> PlanInvariant:
    return PlanInvariant(
        required_nodes=set(payload.get("required_nodes", [])),
        forbidden_nodes=set(payload.get("forbidden_nodes", [])),
        required_joins=set(payload.get("required_joins", [])),
        forbidden_joins=set(payload.get("forbidden_joins", [])),
        required_relations=set(payload.get("required_relations", [])),
        required_indexes=set(payload.get("required_indexes", [])),
        forbidden_indexes=set(payload.get("forbidden_indexes", [])),
        allow_sequential_scan=bool(payload.get("allow_sequential_scan", True)),
        estimated_rows_min=payload.get("estimated_rows_min"),
        estimated_rows_max=payload.get("estimated_rows_max"),
        max_loop_count=payload.get("max_loop_count"),
        max_temp_blocks=payload.get("max_temp_blocks"),
        max_wal_bytes=payload.get("max_wal_bytes"),
    )


def _json_metrics(metrics: Any) -> dict[str, Any]:
    payload = asdict(metrics)
    for key in ("node_types", "join_types", "relations", "indexes"):
        payload[key] = sorted(payload[key])
    return payload


def compare_plan_reports(
    *,
    base_report_path: Path,
    candidate_report_path: Path,
    expectations_path: Path,
) -> tuple[dict[str, Any], bool]:
    base = json.loads(base_report_path.read_text())
    candidate = json.loads(candidate_report_path.read_text())
    expectations = json.loads(expectations_path.read_text())

    def normalize_report(payload: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
        if "queries" in payload:
            return payload["queries"]
        normalized: dict[str, dict[str, dict[str, Any]]] = {}
        for capture in payload.get("captures", []):
            scenario = ":".join(
                (
                    capture["scenario"],
                    capture["prepared_plan_mode"],
                    capture["capture_mode"],
                )
            )
            normalized.setdefault(capture["query_id"], {})[scenario] = {"plan": capture["plan"]}
        return normalized

    base_queries = normalize_report(base)
    candidate_queries = normalize_report(candidate)
    results: list[dict[str, Any]] = []
    failed = False
    for query_name, expectation_payload in sorted(expectations["queries"].items()):
        invariant = _invariant_from_payload(expectation_payload)
        for scenario_name, base_scenario in sorted(base_queries[query_name].items()):
            candidate_scenario = candidate_queries[query_name][scenario_name]
            base_metrics = extract_plan_metrics(base_scenario["plan"])
            candidate_metrics = extract_plan_metrics(candidate_scenario["plan"])
            failures = compare_plan_metrics(base_metrics, candidate_metrics, invariant)
            failed = failed or bool(failures)
            results.append(
                {
                    "query": query_name,
                    "scenario": scenario_name,
                    "base": _json_metrics(base_metrics),
                    "candidate": _json_metrics(candidate_metrics),
                    "failures": [asdict(failure) for failure in failures],
                }
            )

    report = {
        "schema_version": 1,
        "gate": "failed" if failed else "passed",
        "results": results,
    }
    # Validate before returning so callers cannot accidentally emit bind values or PII.
    serialize_safe_report(report)
    return report, failed
