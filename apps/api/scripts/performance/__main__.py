from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import psycopg

from scripts.performance.capture import (
    CaptureManifest,
    CaptureMode,
    capture_manifest,
    load_capture_manifest,
)
from scripts.performance.corpus import (
    QueryFingerprint,
    fingerprint_query,
    select_corpus,
    write_corpus,
)
from scripts.performance.gates import compare_plan_reports
from scripts.performance.orchestrator import run_deterministic_comparison
from scripts.performance.plans import PreparedPlanMode
from scripts.performance.reporting import compare_load_summaries, serialize_safe_report
from scripts.performance.statistics_artifacts import (
    export_encrypted_statistics,
    restore_encrypted_statistics,
)


API_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = API_ROOT.parents[1]
DEFAULT_ALLOWLIST = API_ROOT / "performance" / "statistics-allowlist.json"


def _database_url(argument: str | None) -> str:
    value = argument or os.environ.get("DATABASE_URL", "")
    if not value:
        raise SystemExit("DATABASE_URL or --database-url is required")
    return value


def _psycopg_database_url(argument: str | None) -> str:
    return _database_url(argument).replace("postgresql+psycopg://", "postgresql://", 1)


def _capture_plans(args: argparse.Namespace) -> int:
    manifest = load_capture_manifest(args.manifest)
    queries = manifest.queries
    if args.capture_mode != "all":
        capture_mode = CaptureMode(args.capture_mode)
        queries = tuple(replace(query, capture_modes=(capture_mode,)) for query in queries)
    if args.prepared_plan_mode != "all":
        prepared_mode = PreparedPlanMode(args.prepared_plan_mode)
        queries = tuple(replace(query, prepared_plan_modes=(prepared_mode,)) for query in queries)
    filtered_manifest = CaptureManifest(schema_version=manifest.schema_version, queries=queries)
    with psycopg.connect(_psycopg_database_url(args.database_url)) as connection:
        report = capture_manifest(connection, filtered_manifest).to_mapping()
    rendered = serialize_safe_report(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n")
    print(f"Captured {len(report['captures'])} privacy-safe structured plans to {args.output}")
    return 0


def _read_critical_queries(path: Path | None) -> tuple[list[QueryFingerprint], set[str]]:
    if path is None:
        return [], set()
    payload = json.loads(path.read_text())
    samples: list[QueryFingerprint] = []
    routes: set[str] = set()
    for item in payload.get("queries", []):
        route = str(item["route"])
        fingerprint, normalized = fingerprint_query(str(item["query"]))
        routes.add(route)
        samples.append(
            QueryFingerprint(
                fingerprint=fingerprint,
                normalized_query=normalized,
                total_exec_time_ms=0,
                calls=0,
                route=route,
            )
        )
    return samples, routes


def _export_corpus(args: argparse.Namespace) -> int:
    rows: list[tuple[str, str, float, int]] = []
    with psycopg.connect(_database_url(args.database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT queryid::text, query, total_exec_time, calls
                FROM pg_stat_statements
                WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
                  AND query NOT ILIKE '%%pg_stat_statements%%'
                ORDER BY total_exec_time DESC
                LIMIT 1000
                """
            )
            rows = [(str(row[0]), str(row[1]), float(row[2]), int(row[3])) for row in cursor]

    samples: list[QueryFingerprint] = []
    total_time = sum(max(0.0, row[2]) for row in rows)
    for _query_id, query, total_exec_time, calls in rows:
        fingerprint, normalized = fingerprint_query(query)
        samples.append(
            QueryFingerprint(
                fingerprint=fingerprint,
                normalized_query=normalized,
                total_exec_time_ms=total_exec_time,
                calls=calls,
                database_load_fraction=(total_exec_time / total_time if total_time else 0.0),
            )
        )

    critical, critical_routes = _read_critical_queries(args.critical_queries)
    corpus = select_corpus(
        [*samples, *critical],
        critical_routes=critical_routes,
        limit=args.limit,
    )
    write_corpus(args.output, corpus)
    print(f"Wrote {len(corpus)} normalized fingerprints to {args.output}")
    return 0


def _k6_summary(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text())
    metrics = payload.get("metrics", {})
    duration = metrics.get("http_req_duration", {}).get("values", {})
    requests = metrics.get("http_reqs", {}).get("values", {})
    errors = metrics.get("http_req_failed", {}).get("values", {})
    return {
        "p50_ms": float(duration.get("med", 0)),
        "p95_ms": float(duration.get("p(95)", 0)),
        "p99_ms": float(duration.get("p(99)", 0)),
        "throughput_rps": float(requests.get("rate", 0)),
        "error_rate": float(errors.get("rate", 0)),
    }


def _load_comparison(args: argparse.Namespace) -> int:
    results_dir = API_ROOT / "performance" / "artifacts" / "load-latest"
    results_dir.mkdir(parents=True, exist_ok=True)
    runner = REPOSITORY_ROOT / "load-tests" / "compare-local.sh"
    environment = os.environ.copy()
    environment["PERF_RESULTS_DIR"] = str(results_dir)
    subprocess.run(
        [str(runner), args.base, args.candidate],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=True,
    )

    base = _k6_summary(results_dir / "base-summary.json")
    candidate = _k6_summary(results_dir / "candidate-summary.json")
    comparison = compare_load_summaries(base=base, candidate=candidate)
    database_work: dict[str, Any] = {}
    for side in ("base", "candidate"):
        path = results_dir / f"{side}-db.json"
        database_work[side] = json.loads(path.read_text()) if path.exists() else {}
    report = {
        "schema_version": 1,
        "advisory": True,
        "base_ref": args.base,
        "candidate_ref": args.candidate,
        "wall_clock": comparison.metrics,
        "database_work": database_work,
        "gate_failures": [],
    }
    rendered = serialize_safe_report(report)
    (results_dir / "comparison.json").write_text(rendered + "\n")
    print(rendered)
    print("Advisory only: wall-clock latency can never fail a merge.")
    return 0


def _compare(args: argparse.Namespace) -> int:
    if args.mode == "load":
        return _load_comparison(args)
    expectations = args.expectations or API_ROOT / "performance" / "plan-expectations.json"
    if bool(args.base_report) != bool(args.candidate_report):
        raise SystemExit("provide both --base-report and --candidate-report, or neither")
    if args.base_report and args.candidate_report:
        base_report = args.base_report
        candidate_report = args.candidate_report
    else:
        admin_database_url = os.environ.get("PERFORMANCE_ADMIN_DATABASE_URL") or _database_url(None)
        results_dir = API_ROOT / "performance" / "artifacts" / "deterministic-latest"
        result = run_deterministic_comparison(
            repository_root=REPOSITORY_ROOT,
            base_ref=args.base,
            candidate_ref=args.candidate,
            admin_database_url=admin_database_url,
            results_dir=results_dir,
            seed_profile=args.seed_profile,
        )
        base_report = result.base_report
        candidate_report = result.candidate_report
    report, failed = compare_plan_reports(
        base_report_path=base_report,
        candidate_report_path=candidate_report,
        expectations_path=expectations,
    )
    print(serialize_safe_report(report))
    return 1 if failed else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.performance",
        description="Local deterministic PostgreSQL performance validation",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser(
        "capture", help="capture privacy-safe structured EXPLAIN JSON from a manifest"
    )
    capture.add_argument("--database-url")
    capture.add_argument(
        "--manifest",
        type=Path,
        default=API_ROOT / "performance" / "capture-manifest.json",
    )
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument(
        "--capture-mode",
        choices=("all", "estimated", "analyze"),
        default="all",
    )
    capture.add_argument(
        "--prepared-plan-mode",
        choices=("all", "generic", "custom", "automatic"),
        default="all",
    )
    capture.set_defaults(handler=_capture_plans)

    compare = subparsers.add_parser("compare", help="compare base and candidate")
    compare.add_argument("--base", default="origin/main")
    compare.add_argument("--candidate", default="HEAD")
    compare.add_argument("--mode", choices=("deterministic", "load"), default="deterministic")
    compare.add_argument("--base-report", type=Path)
    compare.add_argument("--candidate-report", type=Path)
    compare.add_argument("--expectations", type=Path)
    compare.add_argument(
        "--seed-profile",
        choices=("smoke", "production", "growth10x"),
        default="production",
    )
    compare.set_defaults(handler=_compare)

    corpus = subparsers.add_parser("export-corpus", help="export normalized pg_stat_statements")
    corpus.add_argument("--database-url")
    corpus.add_argument("--critical-queries", type=Path)
    corpus.add_argument("--output", type=Path, required=True)
    corpus.add_argument("--limit", type=int, default=100)
    corpus.set_defaults(handler=_export_corpus)

    export_stats = subparsers.add_parser(
        "export-stats", help="sanitize and encrypt a PostgreSQL 18 statistics-only dump"
    )
    export_stats.add_argument("--database-url")
    export_stats.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    export_stats.add_argument("--output", type=Path, required=True)
    export_stats.add_argument("--key-env", default="PERFORMANCE_STATS_FERNET_KEY")
    export_stats.set_defaults(
        handler=lambda args: (
            export_encrypted_statistics(
                database_url=_database_url(args.database_url),
                allowlist_path=args.allowlist,
                output_path=args.output,
                key_environment_variable=args.key_env,
            )
            or 0
        )
    )

    restore_stats = subparsers.add_parser(
        "restore-stats", help="decrypt and stream planner statistics into an ephemeral database"
    )
    restore_stats.add_argument("--database-url")
    restore_stats.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    restore_stats.add_argument("--artifact", type=Path, required=True)
    restore_stats.add_argument("--key-env", default="PERFORMANCE_STATS_FERNET_KEY")
    restore_stats.set_defaults(
        handler=lambda args: (
            restore_encrypted_statistics(
                database_url=_database_url(args.database_url),
                allowlist_path=args.allowlist,
                artifact_path=args.artifact,
                key_environment_variable=args.key_env,
            )
            or 0
        )
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
