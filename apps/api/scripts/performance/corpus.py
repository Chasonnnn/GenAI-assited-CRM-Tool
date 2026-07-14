from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable


_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"--[^\n]*")
_STRING_LITERAL = re.compile(r"(?:E)?'(?:''|[^'])*'", re.IGNORECASE)
_DOLLAR_QUOTED = re.compile(r"\$[A-Za-z_]*\$.*?\$[A-Za-z_]*\$", re.DOTALL)
_NUMBER_LITERAL = re.compile(r"(?<![$\w.])-?\d+(?:\.\d+)?(?![\w.])")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class QueryFingerprint:
    fingerprint: str
    normalized_query: str
    total_exec_time_ms: float
    calls: int
    route: str | None = None
    database_load_fraction: float = 0.0


def normalize_query(query: str) -> str:
    """Normalize SQL without retaining comments or literal bind values."""
    normalized = _BLOCK_COMMENT.sub(" ", query)
    normalized = _LINE_COMMENT.sub(" ", normalized)
    normalized = _DOLLAR_QUOTED.sub("$str", normalized)
    normalized = _STRING_LITERAL.sub("$str", normalized)
    normalized = _NUMBER_LITERAL.sub("$num", normalized)
    normalized = _WHITESPACE.sub(" ", normalized).strip().rstrip(";")
    return normalized.lower()


def fingerprint_query(query: str) -> tuple[str, str]:
    normalized = normalize_query(query)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
    return digest, normalized


def select_corpus(
    samples: Iterable[QueryFingerprint],
    *,
    critical_routes: set[str] | frozenset[str] = frozenset(),
    limit: int = 100,
) -> list[QueryFingerprint]:
    """Select a bounded corpus using database time plus critical-route coverage."""
    if limit <= 0:
        raise ValueError("Corpus limit must be positive")

    deduplicated: dict[str, QueryFingerprint] = {}
    for sample in samples:
        existing = deduplicated.get(sample.fingerprint)
        if existing is None or sample.total_exec_time_ms > existing.total_exec_time_ms:
            deduplicated[sample.fingerprint] = sample

    ranked = sorted(
        deduplicated.values(),
        key=lambda sample: (-sample.total_exec_time_ms, sample.fingerprint),
    )
    total_database_time = sum(max(0.0, sample.total_exec_time_ms) for sample in ranked)

    top_time_fingerprints: set[str] = {
        sample.fingerprint for sample in ranked[:50] if sample.total_exec_time_ms >= 0
    }
    one_percent_fingerprints = {
        sample.fingerprint
        for sample in ranked
        if total_database_time > 0 and sample.total_exec_time_ms / total_database_time >= 0.01
    }
    critical_fingerprints = {
        sample.fingerprint for sample in ranked if sample.route in critical_routes
    }

    # Reserve room for critical low-volume routes before filling by database time.
    critical_ranked = [
        sample.fingerprint for sample in ranked if sample.fingerprint in critical_fingerprints
    ]
    selected_fingerprints = set(critical_ranked[:limit])

    for sample in ranked:
        if len(selected_fingerprints) >= limit:
            break
        if sample.fingerprint in one_percent_fingerprints | top_time_fingerprints:
            selected_fingerprints.add(sample.fingerprint)
    for sample in ranked:
        if len(selected_fingerprints) >= limit:
            break
        selected_fingerprints.add(sample.fingerprint)

    return [sample for sample in ranked if sample.fingerprint in selected_fingerprints]


def write_corpus(path: Path, corpus: Iterable[QueryFingerprint]) -> None:
    payload = {
        "schema_version": 1,
        "queries": [asdict(sample) for sample in corpus],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
