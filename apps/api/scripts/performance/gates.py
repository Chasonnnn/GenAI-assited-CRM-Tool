from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any

from scripts.performance.plans import (
    PlanInvariant,
    compare_plan_metrics,
    extract_plan_metrics,
)
from scripts.performance.reporting import serialize_safe_report


class PlanExpectationConfigError(ValueError):
    """Raised when plan expectation JSON is unsafe or ambiguous."""


@dataclass(frozen=True)
class QueryPlanExpectation:
    default: PlanInvariant
    scenarios: dict[str, PlanInvariant]

    def for_scenario(self, scenario: str) -> PlanInvariant:
        return self.scenarios.get(scenario, self.default)


_INVARIANT_SEQUENCE_FIELDS = frozenset(
    {
        "required_nodes",
        "forbidden_nodes",
        "required_joins",
        "forbidden_joins",
        "required_relations",
        "required_indexes",
        "forbidden_indexes",
    }
)
_INVARIANT_LIMIT_FIELDS = frozenset(
    {
        "estimated_rows_min",
        "estimated_rows_max",
        "max_loop_count",
        "max_temp_blocks",
        "max_wal_bytes",
    }
)
_INVARIANT_FIELDS = _INVARIANT_SEQUENCE_FIELDS | _INVARIANT_LIMIT_FIELDS | {"allow_sequential_scan"}
_SCENARIO_KEY = re.compile(
    r"^[a-z][a-z0-9_-]{0,63}:(generic|custom|automatic):(estimated|analyze)$"
)


def _mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise PlanExpectationConfigError(f"{context} must be a JSON object")
    return value


def _validate_invariant_payload(value: Any, context: str) -> dict[str, Any]:
    payload = dict(_mapping(value, context))
    unknown = set(payload) - _INVARIANT_FIELDS
    if unknown:
        raise PlanExpectationConfigError(
            f"{context} has unknown invariant fields: {', '.join(sorted(unknown))}"
        )
    for field in _INVARIANT_SEQUENCE_FIELDS:
        if field not in payload:
            continue
        items = payload[field]
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
            raise PlanExpectationConfigError(f"{context} {field} must be an array of strings")
        if not all(isinstance(item, str) and item for item in items):
            raise PlanExpectationConfigError(f"{context} {field} must be an array of strings")
        if len(items) != len(set(items)):
            raise PlanExpectationConfigError(f"{context} {field} must not contain duplicates")
    if "allow_sequential_scan" in payload and not isinstance(
        payload["allow_sequential_scan"], bool
    ):
        raise PlanExpectationConfigError(f"{context} allow_sequential_scan must be a boolean")
    for field in _INVARIANT_LIMIT_FIELDS:
        if field not in payload or payload[field] is None:
            continue
        limit = payload[field]
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            raise PlanExpectationConfigError(
                f"{context} {field} must be a non-negative integer or null"
            )
    return payload


def _invariant_from_payload(payload: Mapping[str, Any]) -> PlanInvariant:
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


def _parse_query_expectation(value: Any, query_name: str) -> QueryPlanExpectation:
    payload = dict(_mapping(value, f"query {query_name}"))
    uses_scenarios = bool({"defaults", "scenarios"} & set(payload))
    if not uses_scenarios:
        defaults = _validate_invariant_payload(payload, f"query {query_name}")
        return QueryPlanExpectation(
            default=_invariant_from_payload(defaults),
            scenarios={},
        )

    unknown = set(payload) - {"defaults", "scenarios"}
    if unknown:
        raise PlanExpectationConfigError(
            f"query {query_name} mixes scenario config with unknown fields: "
            f"{', '.join(sorted(unknown))}"
        )
    defaults = _validate_invariant_payload(
        payload.get("defaults", {}), f"query {query_name} defaults"
    )
    raw_scenarios = _mapping(payload.get("scenarios", {}), f"query {query_name} scenarios")
    scenarios: dict[str, PlanInvariant] = {}
    for scenario, raw_override in raw_scenarios.items():
        if not _SCENARIO_KEY.fullmatch(scenario):
            raise PlanExpectationConfigError(
                f"query {query_name} scenario key must match {_SCENARIO_KEY.pattern}: {scenario}"
            )
        override = _validate_invariant_payload(
            raw_override, f"query {query_name} scenario {scenario}"
        )
        scenarios[scenario] = _invariant_from_payload({**defaults, **override})
    return QueryPlanExpectation(
        default=_invariant_from_payload(defaults),
        scenarios=scenarios,
    )


def parse_plan_expectations(value: Any) -> dict[str, QueryPlanExpectation]:
    """Parse legacy or scenario-aware plan expectations with strict types."""

    payload = _mapping(value, "plan expectations")
    unknown = set(payload) - {"schema_version", "queries"}
    if unknown:
        raise PlanExpectationConfigError(
            f"plan expectations has unknown fields: {', '.join(sorted(unknown))}"
        )
    if payload.get("schema_version") != 1:
        raise PlanExpectationConfigError("plan expectations schema_version must be 1")
    queries = _mapping(payload.get("queries"), "plan expectations queries")
    if not queries:
        raise PlanExpectationConfigError("plan expectations queries must not be empty")
    return {
        query_name: _parse_query_expectation(query_payload, query_name)
        for query_name, query_payload in queries.items()
    }


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
    expectations = parse_plan_expectations(json.loads(expectations_path.read_text()))

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
    for query_name, expectation in sorted(expectations.items()):
        for scenario_name, base_scenario in sorted(base_queries[query_name].items()):
            invariant = expectation.for_scenario(scenario_name)
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
