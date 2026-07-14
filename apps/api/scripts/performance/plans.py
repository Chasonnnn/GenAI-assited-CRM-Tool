from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


@dataclass(frozen=True)
class PlanMetrics:
    node_types: frozenset[str]
    join_types: frozenset[str]
    relations: frozenset[str]
    indexes: frozenset[str]
    estimated_cost: float
    estimated_rows: int
    logical_blocks: int
    scanned_rows: int
    loop_count: int
    temp_blocks: int
    wal_records: int
    wal_fpi: int
    wal_bytes: int


@dataclass(frozen=True)
class PlanInvariant:
    required_nodes: set[str] = field(default_factory=set)
    forbidden_nodes: set[str] = field(default_factory=set)
    required_joins: set[str] = field(default_factory=set)
    forbidden_joins: set[str] = field(default_factory=set)
    required_relations: set[str] = field(default_factory=set)
    required_indexes: set[str] = field(default_factory=set)
    forbidden_indexes: set[str] = field(default_factory=set)
    allow_sequential_scan: bool = True
    estimated_rows_min: int | None = None
    estimated_rows_max: int | None = None
    max_loop_count: int | None = None
    max_temp_blocks: int | None = None
    max_wal_bytes: int | None = None


@dataclass(frozen=True)
class BudgetFailure:
    metric: str
    message: str
    base: float | int | str | None = None
    candidate: float | int | str | None = None


@dataclass(frozen=True)
class QueryWorkload:
    query_count: int
    fingerprint_counts: dict[str, int]


class PreparedPlanMode(str, Enum):
    GENERIC = "generic"
    CUSTOM = "custom"
    AUTOMATIC = "automatic"


_PLAN_CACHE_VALUES = {
    PreparedPlanMode.GENERIC: "force_generic_plan",
    PreparedPlanMode.CUSTOM: "force_custom_plan",
    PreparedPlanMode.AUTOMATIC: "auto",
}


def plan_cache_settings(mode: PreparedPlanMode) -> tuple[str, tuple[str]]:
    return "SET LOCAL plan_cache_mode = %s", (_PLAN_CACHE_VALUES[mode],)


def _plan_root(document: Any) -> dict[str, Any]:
    if isinstance(document, list) and document:
        document = document[0]
    if not isinstance(document, dict):
        raise ValueError("EXPLAIN JSON must be a mapping or one-item list")
    root = document.get("Plan", document)
    if not isinstance(root, dict) or "Node Type" not in root:
        raise ValueError("EXPLAIN JSON does not contain a Plan node")
    return root


def _walk_nodes(root: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield root
    for child in root.get("Plans", []):
        if isinstance(child, dict):
            yield from _walk_nodes(child)


def extract_plan_metrics(document: Any) -> PlanMetrics:
    root = _plan_root(document)
    nodes = list(_walk_nodes(root))

    relation_scan_nodes = [
        node
        for node in nodes
        if node.get("Relation Name")
        and (
            str(node.get("Node Type", "")).endswith("Scan")
            or node.get("Node Type") in {"Bitmap Heap Scan", "Tid Scan", "Tid Range Scan"}
        )
    ]
    scanned_rows = sum(
        round(
            (
                float(node.get("Actual Rows", 0) or 0)
                + float(node.get("Rows Removed by Filter", 0) or 0)
                + float(node.get("Rows Removed by Index Recheck", 0) or 0)
            )
            * float(node.get("Actual Loops", 1) or 0)
        )
        for node in relation_scan_nodes
    )

    return PlanMetrics(
        node_types=frozenset(str(node["Node Type"]) for node in nodes if node.get("Node Type")),
        join_types=frozenset(str(node["Join Type"]) for node in nodes if node.get("Join Type")),
        relations=frozenset(
            str(node["Relation Name"]) for node in nodes if node.get("Relation Name")
        ),
        indexes=frozenset(str(node["Index Name"]) for node in nodes if node.get("Index Name")),
        estimated_cost=float(root.get("Total Cost", 0) or 0),
        estimated_rows=int(root.get("Plan Rows", 0) or 0),
        logical_blocks=int(root.get("Shared Hit Blocks", 0) or 0)
        + int(root.get("Shared Read Blocks", 0) or 0),
        scanned_rows=scanned_rows,
        loop_count=sum(int(node.get("Actual Loops", 0) or 0) for node in relation_scan_nodes),
        temp_blocks=int(root.get("Temp Read Blocks", 0) or 0)
        + int(root.get("Temp Written Blocks", 0) or 0),
        wal_records=int(root.get("WAL Records", 0) or 0),
        wal_fpi=int(root.get("WAL FPI", 0) or 0),
        wal_bytes=int(root.get("WAL Bytes", 0) or 0),
    )


def _crosses_dual_budget(base: int, candidate: int, percent: float, absolute: int) -> bool:
    growth = candidate - base
    relative_growth = growth / base if base else (float("inf") if growth > 0 else 0.0)
    return growth > absolute and relative_growth > percent


def _adverse_structure(base: PlanMetrics, candidate: PlanMetrics) -> bool:
    adverse_nodes = {"Seq Scan", "Nested Loop", "Sort", "Materialize"}
    return bool((candidate.node_types - base.node_types) & adverse_nodes) or bool(
        base.indexes - candidate.indexes
    )


def _invariant_failures(metrics: PlanMetrics, invariant: PlanInvariant) -> list[BudgetFailure]:
    failures: list[BudgetFailure] = []
    checks = (
        ("required_node", invariant.required_nodes - metrics.node_types),
        ("forbidden_node", invariant.forbidden_nodes & metrics.node_types),
        ("required_join", invariant.required_joins - metrics.join_types),
        ("forbidden_join", invariant.forbidden_joins & metrics.join_types),
        ("required_relation", invariant.required_relations - metrics.relations),
        ("required_index", invariant.required_indexes - metrics.indexes),
        ("forbidden_index", invariant.forbidden_indexes & metrics.indexes),
    )
    for metric, values in checks:
        for value in sorted(values):
            failures.append(
                BudgetFailure(metric=metric, message=f"Plan invariant {metric}: {value}")
            )
    if not invariant.allow_sequential_scan and "Seq Scan" in metrics.node_types:
        failures.append(
            BudgetFailure(
                metric="forbidden_node",
                message="Plan invariant forbids sequential scans for this query",
            )
        )
    limit_checks = (
        ("estimated_rows_max", metrics.estimated_rows, invariant.estimated_rows_max),
        ("loop_count", metrics.loop_count, invariant.max_loop_count),
        ("temp_blocks", metrics.temp_blocks, invariant.max_temp_blocks),
        ("wal_bytes", metrics.wal_bytes, invariant.max_wal_bytes),
    )
    for metric, actual, maximum in limit_checks:
        if maximum is not None and actual > maximum:
            failures.append(
                BudgetFailure(
                    metric=metric,
                    message=f"Plan invariant {metric} exceeded configured maximum",
                    base=maximum,
                    candidate=actual,
                )
            )
    if (
        invariant.estimated_rows_min is not None
        and metrics.estimated_rows < invariant.estimated_rows_min
    ):
        failures.append(
            BudgetFailure(
                metric="estimated_rows_min",
                message="Plan invariant estimated rows fell below configured minimum",
                base=invariant.estimated_rows_min,
                candidate=metrics.estimated_rows,
            )
        )
    return failures


def compare_plan_metrics(
    base: PlanMetrics,
    candidate: PlanMetrics,
    invariant: PlanInvariant,
) -> list[BudgetFailure]:
    failures = _invariant_failures(candidate, invariant)
    if _crosses_dual_budget(base.logical_blocks, candidate.logical_blocks, 0.15, 32):
        failures.append(
            BudgetFailure(
                metric="logical_blocks",
                message="Logical-buffer growth exceeded 15% and 32 blocks",
                base=base.logical_blocks,
                candidate=candidate.logical_blocks,
            )
        )
    if _crosses_dual_budget(base.scanned_rows, candidate.scanned_rows, 0.15, 100):
        failures.append(
            BudgetFailure(
                metric="scanned_rows",
                message="Scanned-row growth exceeded 15% and 100 rows",
                base=base.scanned_rows,
                candidate=candidate.scanned_rows,
            )
        )
    if base.temp_blocks == 0 and candidate.temp_blocks > 0:
        failures.append(
            BudgetFailure(
                metric="temp_blocks",
                message="Candidate introduced temporary-block usage",
                base=base.temp_blocks,
                candidate=candidate.temp_blocks,
            )
        )
    if candidate.estimated_cost > base.estimated_cost * 1.20 and _adverse_structure(
        base, candidate
    ):
        failures.append(
            BudgetFailure(
                metric="estimated_cost",
                message="Estimated cost grew above 20% with an adverse structural change",
                base=base.estimated_cost,
                candidate=candidate.estimated_cost,
            )
        )
    return failures


def compare_query_workloads(
    base: QueryWorkload,
    candidate: QueryWorkload,
    *,
    allowed_query_count_increase: int = 0,
) -> list[BudgetFailure]:
    failures: list[BudgetFailure] = []
    if candidate.query_count > base.query_count + allowed_query_count_increase:
        failures.append(
            BudgetFailure(
                metric="query_count",
                message="Unexplained query-count increase",
                base=base.query_count,
                candidate=candidate.query_count,
            )
        )
    for fingerprint, candidate_count in sorted(candidate.fingerprint_counts.items()):
        base_count = base.fingerprint_counts.get(fingerprint, 0)
        if candidate_count > max(1, base_count):
            failures.append(
                BudgetFailure(
                    metric="duplicate_fingerprint",
                    message=f"Duplicate fingerprint increased: {fingerprint}",
                    base=base_count,
                    candidate=candidate_count,
                )
            )
    return failures
