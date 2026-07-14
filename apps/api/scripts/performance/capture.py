"""Privacy-safe structured EXPLAIN capture for deterministic performance gates.

Manifests are deliberately JSON-only and strict. Query parameters exist only in
memory and in PostgreSQL protocol bindings; reports never include SQL text,
parameter values, or plan expression fields that may inline custom-plan values.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from scripts.performance.plans import PreparedPlanMode


class ManifestError(ValueError):
    """Raised when a capture manifest is unsafe or internally inconsistent."""


class CaptureMode(str, Enum):
    ESTIMATED = "estimated"
    ANALYZE = "analyze"


@dataclass(frozen=True)
class ParameterScenario:
    name: str
    parameters: tuple[Any, ...]
    automatic_warmup_parameters: tuple[tuple[Any, ...], ...]


@dataclass(frozen=True)
class CaptureQuery:
    query_id: str
    sql: str
    parameter_types: tuple[str, ...]
    prepared_plan_modes: tuple[PreparedPlanMode, ...]
    capture_modes: tuple[CaptureMode, ...]
    scenarios: tuple[ParameterScenario, ...]
    allow_write: bool = False


@dataclass(frozen=True)
class CaptureManifest:
    schema_version: int
    queries: tuple[CaptureQuery, ...]


@dataclass(frozen=True)
class CapturedPlan:
    query_id: str
    scenario: str
    prepared_plan_mode: PreparedPlanMode
    capture_mode: CaptureMode
    parameter_count: int
    automatic_warmup_count: int
    plan: list[dict[str, Any]]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "scenario": self.scenario,
            "prepared_plan_mode": self.prepared_plan_mode.value,
            "capture_mode": self.capture_mode.value,
            "parameter_count": self.parameter_count,
            "automatic_warmup_count": self.automatic_warmup_count,
            "plan": self.plan,
        }


@dataclass(frozen=True)
class CaptureReport:
    captures: tuple[CapturedPlan, ...]
    schema_version: int = 1

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "captures": [capture.to_mapping() for capture in self.captures],
        }


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_PARAMETER = re.compile(r"\$(\d+)")
_SQL_COMMENT = re.compile(r"--|/\*|\*/")
_WRITE_PREFIX = re.compile(r"^\s*(INSERT|UPDATE|DELETE|MERGE)\b", re.IGNORECASE)
_READ_PREFIX = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
_DML_IN_CTE = re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE)\b", re.IGNORECASE)

_SUPPORTED_PARAMETER_TYPES = frozenset(
    {
        "smallint",
        "integer",
        "bigint",
        "numeric",
        "real",
        "double precision",
        "boolean",
        "text",
        "uuid",
        "date",
        "timestamp",
        "timestamp with time zone",
        "timestamp without time zone",
        "timestamptz",
        "json",
        "jsonb",
        "smallint[]",
        "integer[]",
        "bigint[]",
        "numeric[]",
        "boolean[]",
        "text[]",
        "uuid[]",
        "date[]",
        "timestamp[]",
        "timestamptz[]",
    }
)

_TOP_LEVEL_FIELDS = frozenset({"schema_version", "queries"})
_QUERY_FIELDS = frozenset(
    {
        "id",
        "sql",
        "parameter_types",
        "prepared_plan_modes",
        "capture_modes",
        "scenarios",
        "allow_write",
        "automatic_warmup_count",
    }
)
_SCENARIO_FIELDS = frozenset({"name", "parameters", "automatic_warmup_parameters"})

_PLAN_STRING_FIELDS = frozenset(
    {
        "Node Type",
        "Parent Relationship",
        "Join Type",
        "Relation Name",
        "Schema",
        "Alias",
        "Index Name",
        "Scan Direction",
        "Strategy",
        "Partial Mode",
        "Operation",
    }
)
_PLAN_BOOLEAN_FIELDS = frozenset({"Parallel Aware", "Async Capable", "Inner Unique"})
_PLAN_NUMERIC_FIELDS = frozenset(
    {
        "Startup Cost",
        "Total Cost",
        "Plan Rows",
        "Plan Width",
        "Actual Rows",
        "Actual Loops",
        "Rows Removed by Filter",
        "Rows Removed by Index Recheck",
        "Rows Removed by Join Filter",
        "Heap Fetches",
        "Exact Heap Blocks",
        "Lossy Heap Blocks",
        "Workers Planned",
        "Workers Launched",
        "Shared Hit Blocks",
        "Shared Read Blocks",
        "Shared Dirtied Blocks",
        "Shared Written Blocks",
        "Local Hit Blocks",
        "Local Read Blocks",
        "Local Dirtied Blocks",
        "Local Written Blocks",
        "Temp Read Blocks",
        "Temp Written Blocks",
        "WAL Records",
        "WAL FPI",
        "WAL Bytes",
    }
)

_PLAN_CACHE_VALUES = {
    PreparedPlanMode.GENERIC: "force_generic_plan",
    PreparedPlanMode.CUSTOM: "force_custom_plan",
    PreparedPlanMode.AUTOMATIC: "auto",
}


def _require_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ManifestError(f"{context} must be a JSON object")
    if not all(isinstance(key, str) for key in value):
        raise ManifestError(f"{context} fields must be strings")
    return value


def _reject_unknown_fields(value: Mapping[str, Any], allowed: frozenset[str], context: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ManifestError(f"{context} has unknown fields: {', '.join(sorted(unknown))}")


def _require_sequence(value: Any, context: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ManifestError(f"{context} must be a JSON array")
    return value


def _safe_name(value: Any, context: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ManifestError(f"{context} must match {_IDENTIFIER.pattern}")
    return value


def _safe_sql(value: Any, *, allow_write: bool) -> tuple[str, int]:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError("query sql must be a non-empty string")
    sql = value.strip()
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()
    if ";" in sql:
        raise ManifestError("query sql must contain a single SQL statement")
    if _SQL_COMMENT.search(sql):
        raise ManifestError("query sql must not contain SQL comments")

    is_write = bool(_WRITE_PREFIX.match(sql))
    is_read = bool(_READ_PREFIX.match(sql))
    if not is_read and not is_write:
        raise ManifestError("query sql must be SELECT, WITH, INSERT, UPDATE, DELETE, or MERGE")
    if sql.lstrip().upper().startswith("WITH") and _DML_IN_CTE.search(sql):
        is_write = True
    if is_write and not allow_write:
        raise ManifestError("write queries require allow_write=true")

    indexes = sorted({int(match) for match in _PARAMETER.findall(sql)})
    if indexes and indexes != list(range(1, indexes[-1] + 1)):
        raise ManifestError("query parameters must be contiguous from $1")
    return sql, indexes[-1] if indexes else 0


def _parse_enum_sequence(
    value: Any,
    enum_type: type[Enum],
    context: str,
) -> tuple[Any, ...]:
    items = _require_sequence(value, context)
    try:
        parsed = tuple(enum_type(item) for item in items)
    except (TypeError, ValueError) as error:
        allowed = ", ".join(member.value for member in enum_type)
        raise ManifestError(f"{context} values must be one of: {allowed}") from error
    if not parsed:
        raise ManifestError(f"{context} must not be empty")
    if len(parsed) != len(set(parsed)):
        raise ManifestError(f"{context} must not contain duplicates")
    return parsed


def _parse_parameter_types(value: Any, parameter_count: int) -> tuple[str, ...]:
    raw_types = _require_sequence(value, "query parameter_types")
    parameter_types: list[str] = []
    for raw_type in raw_types:
        normalized = " ".join(str(raw_type).lower().split())
        if normalized not in _SUPPORTED_PARAMETER_TYPES:
            raise ManifestError(f"unsupported parameter type: {raw_type!r}")
        parameter_types.append(normalized)
    if len(parameter_types) != parameter_count:
        raise ManifestError(
            "query parameter_types length must match the number of positional parameters"
        )
    return tuple(parameter_types)


def _parameter_tuple(value: Any, parameter_count: int, context: str) -> tuple[Any, ...]:
    parameters = tuple(_require_sequence(value, context))
    if len(parameters) != parameter_count:
        raise ManifestError(f"{context} length must match query parameter count")
    return parameters


def _parse_scenarios(
    value: Any,
    *,
    parameter_count: int,
    automatic_warmup_count: int,
) -> tuple[ParameterScenario, ...]:
    raw_scenarios = _require_sequence(value, "query scenarios")
    scenarios: list[ParameterScenario] = []
    names: set[str] = set()
    for index, raw_scenario in enumerate(raw_scenarios):
        context = f"query scenario {index}"
        scenario = _require_mapping(raw_scenario, context)
        _reject_unknown_fields(scenario, _SCENARIO_FIELDS, context)
        name = _safe_name(scenario.get("name"), f"{context} name")
        if name in names:
            raise ManifestError(f"duplicate query scenario name: {name}")
        names.add(name)
        parameters = _parameter_tuple(
            scenario.get("parameters", []), parameter_count, f"{context} parameters"
        )
        raw_warmups = scenario.get("automatic_warmup_parameters")
        if raw_warmups is None:
            warmups = tuple(parameters for _ in range(automatic_warmup_count))
        else:
            warmups = tuple(
                _parameter_tuple(item, parameter_count, f"{context} automatic warmup")
                for item in _require_sequence(raw_warmups, f"{context} automatic warmups")
            )
        scenarios.append(
            ParameterScenario(
                name=name,
                parameters=parameters,
                automatic_warmup_parameters=warmups,
            )
        )
    if not scenarios:
        raise ManifestError("query scenarios must not be empty")
    return tuple(scenarios)


def _parse_query(value: Any, index: int) -> CaptureQuery:
    context = f"query {index}"
    query = _require_mapping(value, context)
    _reject_unknown_fields(query, _QUERY_FIELDS, context)
    query_id = _safe_name(query.get("id"), f"{context} id")
    allow_write = query.get("allow_write", False)
    if not isinstance(allow_write, bool):
        raise ManifestError(f"{context} allow_write must be boolean")
    sql, parameter_count = _safe_sql(query.get("sql"), allow_write=allow_write)
    parameter_types = _parse_parameter_types(query.get("parameter_types", []), parameter_count)

    warmup_count = query.get("automatic_warmup_count", 5)
    if not isinstance(warmup_count, int) or isinstance(warmup_count, bool):
        raise ManifestError(f"{context} automatic_warmup_count must be an integer")
    if not 0 <= warmup_count <= 20:
        raise ManifestError(f"{context} automatic_warmup_count must be between 0 and 20")

    return CaptureQuery(
        query_id=query_id,
        sql=sql,
        parameter_types=parameter_types,
        prepared_plan_modes=_parse_enum_sequence(
            query.get("prepared_plan_modes", [mode.value for mode in PreparedPlanMode]),
            PreparedPlanMode,
            f"{context} prepared_plan_modes",
        ),
        capture_modes=_parse_enum_sequence(
            query.get("capture_modes", [mode.value for mode in CaptureMode]),
            CaptureMode,
            f"{context} capture_modes",
        ),
        scenarios=_parse_scenarios(
            query.get("scenarios", []),
            parameter_count=parameter_count,
            automatic_warmup_count=warmup_count,
        ),
        allow_write=allow_write,
    )


def parse_capture_manifest(value: Any) -> CaptureManifest:
    """Validate a deserialized JSON capture manifest."""

    manifest = _require_mapping(value, "capture manifest")
    _reject_unknown_fields(manifest, _TOP_LEVEL_FIELDS, "capture manifest")
    if manifest.get("schema_version") != 1:
        raise ManifestError("capture manifest schema_version must be 1")
    raw_queries = _require_sequence(manifest.get("queries"), "capture manifest queries")
    queries = tuple(_parse_query(query, index) for index, query in enumerate(raw_queries))
    if not queries:
        raise ManifestError("capture manifest queries must not be empty")
    query_ids = [query.query_id for query in queries]
    if len(query_ids) != len(set(query_ids)):
        raise ManifestError("capture manifest query ids must be unique")
    return CaptureManifest(schema_version=1, queries=queries)


def load_capture_manifest(path: Path) -> CaptureManifest:
    """Load a strict JSON manifest from disk."""

    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManifestError(f"capture manifest must be valid JSON: {path}") from error
    return parse_capture_manifest(value)


def _safe_plan_node(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("Node Type"), str):
        raise ValueError("EXPLAIN JSON does not contain a valid Plan node")
    safe: dict[str, Any] = {}
    for key in _PLAN_STRING_FIELDS:
        field = value.get(key)
        if isinstance(field, str):
            safe[key] = field
    for key in _PLAN_BOOLEAN_FIELDS:
        field = value.get(key)
        if isinstance(field, bool):
            safe[key] = field
    for key in _PLAN_NUMERIC_FIELDS:
        field = value.get(key)
        if isinstance(field, (int, float)) and not isinstance(field, bool):
            safe[key] = field
    children = value.get("Plans")
    if isinstance(children, Sequence) and not isinstance(children, (str, bytes, bytearray)):
        safe["Plans"] = [_safe_plan_node(child) for child in children]
    return safe


def sanitize_explain_document(value: Any) -> list[dict[str, Any]]:
    """Keep only structural and deterministic-work fields from EXPLAIN JSON."""

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError("EXPLAIN JSON result is not valid JSON") from error
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) != 1:
            raise ValueError("EXPLAIN JSON must contain exactly one document")
        value = value[0]
    if not isinstance(value, Mapping):
        raise ValueError("EXPLAIN JSON document must be an object")
    return [{"Plan": _safe_plan_node(value.get("Plan"))}]


def _parameter_expression(index: int, parameter_type: str, null_sentinel: str) -> str:
    setting = f"performance_capture.parameter_{index}"
    return f"NULLIF(pg_catalog.current_setting('{setting}'), '{null_sentinel}')::{parameter_type}"


def _execute_statement_sql(
    statement_name: str,
    parameter_types: tuple[str, ...],
    null_sentinel: str,
) -> str:
    if not parameter_types:
        return f"EXECUTE {statement_name}"
    expressions = ", ".join(
        _parameter_expression(index, parameter_type, null_sentinel)
        for index, parameter_type in enumerate(parameter_types, start=1)
    )
    return f"EXECUTE {statement_name} ({expressions})"


def _explain_sql(
    statement_name: str,
    parameter_types: tuple[str, ...],
    capture_mode: CaptureMode,
    null_sentinel: str,
) -> str:
    if capture_mode is CaptureMode.ANALYZE:
        options = "ANALYZE TRUE, BUFFERS TRUE, WAL TRUE, TIMING FALSE, SUMMARY TRUE, FORMAT JSON"
    else:
        options = "COSTS TRUE, VERBOSE FALSE, SETTINGS FALSE, FORMAT JSON"
    return (
        f"EXPLAIN ({options}) "
        f"{_execute_statement_sql(statement_name, parameter_types, null_sentinel)}"
    )


def _adapt_parameter(value: Any, parameter_type: str) -> Any:
    if parameter_type in {"json", "jsonb"} and value is not None:
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    return value


def _bind_parameters(
    cursor: Any,
    parameter_types: tuple[str, ...],
    parameters: tuple[Any, ...],
    null_sentinel: str,
) -> None:
    for index, (parameter_type, parameter) in enumerate(
        zip(parameter_types, parameters, strict=True), start=1
    ):
        setting = f"performance_capture.parameter_{index}"
        cursor.execute(
            f"SELECT pg_catalog.set_config('{setting}', "
            f"COALESCE((%s::{parameter_type})::text, '{null_sentinel}'), true)",
            (_adapt_parameter(parameter, parameter_type),),
        )


def _capture_one(
    connection: Any,
    query: CaptureQuery,
    scenario: ParameterScenario,
    prepared_plan_mode: PreparedPlanMode,
    capture_mode: CaptureMode,
) -> CapturedPlan:
    statement_name = f"perf_capture_{uuid4().hex}"
    null_sentinel = f"__PERF_CAPTURE_NULL_{uuid4().hex.upper()}__"
    parameter_declaration = (
        f" ({', '.join(query.parameter_types)})" if query.parameter_types else ""
    )
    prepare_sql = f"PREPARE {statement_name}{parameter_declaration} AS {query.sql}"
    execute_sql = _execute_statement_sql(
        statement_name,
        query.parameter_types,
        null_sentinel,
    )
    automatic_warmup_count = 0

    with connection.transaction(force_rollback=True):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_catalog.set_config('plan_cache_mode', %s, true)",
                (_PLAN_CACHE_VALUES[prepared_plan_mode],),
            )
            cursor.execute(
                "SELECT pg_catalog.set_config('auto_explain.log_parameter_max_length', '0', true)"
            )
            cursor.execute("SELECT pg_catalog.set_config('auto_explain.log_timing', 'off', true)")
            cursor.execute("SELECT pg_catalog.set_config('log_parameter_max_length', '0', true)")
            cursor.execute(prepare_sql)
            if prepared_plan_mode is PreparedPlanMode.AUTOMATIC:
                for warmup_parameters in scenario.automatic_warmup_parameters:
                    _bind_parameters(
                        cursor,
                        query.parameter_types,
                        warmup_parameters,
                        null_sentinel,
                    )
                    cursor.execute(execute_sql)
                    automatic_warmup_count += 1
            _bind_parameters(
                cursor,
                query.parameter_types,
                scenario.parameters,
                null_sentinel,
            )
            cursor.execute(
                _explain_sql(
                    statement_name,
                    query.parameter_types,
                    capture_mode,
                    null_sentinel,
                )
            )
            row = cursor.fetchone()
            if row is None or not row:
                raise ValueError("EXPLAIN returned no JSON document")
            plan = sanitize_explain_document(row[0])
            cursor.execute(f"DEALLOCATE {statement_name}")

    return CapturedPlan(
        query_id=query.query_id,
        scenario=scenario.name,
        prepared_plan_mode=prepared_plan_mode,
        capture_mode=capture_mode,
        parameter_count=len(scenario.parameters),
        automatic_warmup_count=automatic_warmup_count,
        plan=plan,
    )


def capture_manifest(connection: Any, manifest: CaptureManifest) -> CaptureReport:
    """Capture every query/scenario/plan-mode combination in a rollback-only transaction."""

    captures = tuple(
        _capture_one(connection, query, scenario, prepared_plan_mode, capture_mode)
        for query in manifest.queries
        for scenario in query.scenarios
        for prepared_plan_mode in query.prepared_plan_modes
        for capture_mode in query.capture_modes
    )
    return CaptureReport(captures=captures)


__all__ = [
    "CaptureManifest",
    "CaptureMode",
    "CaptureQuery",
    "CaptureReport",
    "CapturedPlan",
    "ManifestError",
    "ParameterScenario",
    "PreparedPlanMode",
    "capture_manifest",
    "load_capture_manifest",
    "parse_capture_manifest",
    "sanitize_explain_document",
]
