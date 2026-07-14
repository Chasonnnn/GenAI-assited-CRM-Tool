from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping


class StatisticsSafetyError(ValueError):
    pass


_PII_COLUMNS = re.compile(
    r"(^|_)(email|phone|mobile|first_name|last_name|full_name|name|address|street|city|"
    r"postal|zip|ssn|dob|birth|notes?|message|body|token|secret|password|ip_address)($|_)",
    re.IGNORECASE,
)
_PII_VALUES = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(
        r"(?<![0-9A-Fa-f.-])(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?"
        r"\d{3}[-.\s]?\d{4}(?![0-9A-Fa-f.-])"
    ),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:bearer\s+)?eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
)
_ALLOWED_STATISTICS_CALL = re.compile(
    r"^\s*SELECT\s+\*\s+FROM\s+pg_catalog\."
    r"pg_restore_(?:relation|attribute)_stats\s*\(.*\)\s*;\s*$",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class StatisticsAllowlist:
    relations: frozenset[str]
    columns: frozenset[tuple[str, str]]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Mapping[str, Any]]) -> "StatisticsAllowlist":
        relations = frozenset(payload)
        columns = frozenset(
            (relation, str(column))
            for relation, options in payload.items()
            for column in options.get("columns", [])
        )
        for relation, column in columns:
            if _PII_COLUMNS.search(column):
                raise StatisticsSafetyError(
                    f"PII column cannot be allowlisted: {relation}.{column}"
                )
        return cls(relations=relations, columns=columns)

    @classmethod
    def from_json_file(cls, path: Path) -> "StatisticsAllowlist":
        return cls.from_mapping(json.loads(path.read_text()))


def _split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_quote = False
    in_line_comment = False
    index = 0
    while index < len(sql):
        char = sql[index]
        current.append(char)
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
        elif not in_quote and char == "-" and index + 1 < len(sql) and sql[index + 1] == "-":
            current.append(sql[index + 1])
            index += 1
            in_line_comment = True
        elif char == "'":
            if in_quote and index + 1 < len(sql) and sql[index + 1] == "'":
                current.append(sql[index + 1])
                index += 1
            else:
                in_quote = not in_quote
        elif char == ";" and not in_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        index += 1
    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)
    return statements


def _sql_unquote(value: str) -> str:
    return value.replace("''", "'")


def _extract_labeled_value(statement: str, label: str) -> str | None:
    key_value = re.search(
        rf"'{re.escape(label)}'\s*,\s*'((?:''|[^'])*)'",
        statement,
        re.IGNORECASE,
    )
    if key_value:
        return _sql_unquote(key_value.group(1))
    named = re.search(
        rf"\b{re.escape(label)}\b\s*(?:=>|:=)\s*'((?:''|[^'])*)'",
        statement,
        re.IGNORECASE,
    )
    if named:
        return _sql_unquote(named.group(1))
    return None


def _contains_pii_value(statement: str) -> bool:
    return any(pattern.search(statement) for pattern in _PII_VALUES)


def _strip_leading_comments(statement: str) -> str:
    lines = statement.splitlines()
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith("--")):
        lines.pop(0)
    return "\n".join(lines)


def sanitize_statistics_dump(sql: str, allowlist: StatisticsAllowlist) -> str:
    """Return allowlisted PG18 stats calls, rejecting any PII evidence."""
    retained: list[str] = []
    for statement in _split_sql_statements(sql):
        if (
            "pg_restore_relation_stats" not in statement
            and "pg_restore_attribute_stats" not in statement
        ):
            continue
        statement = _strip_leading_comments(statement)
        if not _ALLOWED_STATISTICS_CALL.fullmatch(statement):
            raise StatisticsSafetyError("Unexpected SQL in statistics-only dump")
        schema = _extract_labeled_value(statement, "schemaname")
        relation_name = _extract_labeled_value(statement, "relname")
        column = _extract_labeled_value(statement, "attname")
        if not schema or not relation_name:
            raise StatisticsSafetyError("Unable to identify relation in statistics statement")
        relation = f"{schema}.{relation_name}"

        if relation not in allowlist.relations:
            continue
        # A full relation statistics dump necessarily includes every analyzed column.
        # Direct-PII columns are discarded before inspecting their values; attempting
        # to put one on the allowlist is rejected by StatisticsAllowlist itself.
        if column and _PII_COLUMNS.search(column):
            continue
        if column and (relation, column) not in allowlist.columns:
            continue
        if _contains_pii_value(statement):
            raise StatisticsSafetyError(f"PII-like value found in statistics dump: {relation}")
        retained.append(statement if statement.endswith(";") else f"{statement};")

    if not retained:
        raise StatisticsSafetyError("No allowlisted statistics remained after sanitization")
    return (
        "-- Sanitized PostgreSQL planner statistics. Contains no table rows.\n"
        + "\n".join(retained)
        + "\n"
    )
