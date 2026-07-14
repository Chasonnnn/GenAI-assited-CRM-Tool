from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping


_SENSITIVE_KEYS = re.compile(
    r"(^|_)(bind|binds|parameter|parameters|cookie|cookies|token|tokens|secret|password|"
    r"authorization|email|phone|first_name|last_name)($|_)",
    re.IGNORECASE,
)
_SENSITIVE_VALUES = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b(?:bearer\s+)?eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
)
_SAFE_SENSITIVE_COUNTS = {"parameter_count"}


@dataclass(frozen=True)
class LoadComparison:
    advisory: bool
    metrics: dict[str, dict[str, float | None]]
    gate_failures: tuple[str, ...] = ()


def _percent_delta(base: float, candidate: float) -> float | None:
    if base == 0:
        return 0.0 if candidate == 0 else None
    return round((candidate - base) / base * 100, 3)


def compare_load_summaries(
    *,
    base: Mapping[str, float | int],
    candidate: Mapping[str, float | int],
) -> LoadComparison:
    metrics: dict[str, dict[str, float | None]] = {}
    for name in sorted(set(base) | set(candidate)):
        base_value = float(base.get(name, 0))
        candidate_value = float(candidate.get(name, 0))
        metrics[name] = {
            "base": base_value,
            "candidate": candidate_value,
            "delta_percent": _percent_delta(base_value, candidate_value),
        }
    return LoadComparison(advisory=True, metrics=metrics)


def _validate_safe(value: Any, path: str = "report") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if _SENSITIVE_KEYS.search(str(key)) and str(key) not in _SAFE_SENSITIVE_COUNTS:
                raise ValueError(f"sensitive report key at {path}.{key}")
            _validate_safe(child, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_safe(child, f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in _SENSITIVE_VALUES:
            if pattern.search(value):
                raise ValueError(f"sensitive report value at {path}")


def serialize_safe_report(report: Mapping[str, Any]) -> str:
    _validate_safe(report)
    return json.dumps(report, indent=2, sort_keys=True)
