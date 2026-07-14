from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text()


def test_all_plan_sensitive_ci_services_use_postgres_18_1() -> None:
    workflow = _read(".github/workflows/ci.yml")

    assert "postgres:16" not in workflow
    assert workflow.count("postgres:18.1") >= 3
    performance_job = workflow.split("  performance-gates:", 1)[1].split("\n  frontend-tests:", 1)[
        0
    ]
    assert "--mode deterministic" in performance_job
    assert "--seed-profile production" in performance_job
    assert "--mode load" not in performance_job
    assert "tests/test_performance_scenario_expectations.py" in performance_job


def test_performance_compose_overlay_enables_benchmark_instrumentation_safely() -> None:
    overlay = _read("docker-compose.performance.yml")

    assert "shared_preload_libraries=pg_stat_statements,auto_explain" in overlay
    assert "track_io_timing=on" in overlay
    assert "auto_explain.log_min_duration=0" in overlay
    assert "auto_explain.log_analyze=on" in overlay
    assert "auto_explain.log_timing=off" in overlay
    assert "auto_explain.log_parameter_max_length=0" in overlay


def test_k6_wall_clock_metrics_have_no_latency_threshold() -> None:
    suite = _read("load-tests/k6-core-flows.js")

    assert "http_req_duration: [" not in suite
    assert "p(95)<" not in suite
    assert "intelligent-suggestions/summary" in suite


def test_k6_runner_uses_identical_candidate_seed_data_and_fixture_keys() -> None:
    runner = _read("load-tests/compare-local.sh")

    assert 'seed_checkout "${CANDIDATE_DIR}" perf_base' in runner
    assert 'seed_checkout "${CANDIDATE_DIR}" perf_candidate' in runner
    assert 'seed_checkout "${BASE_DIR}" perf_base' not in runner
    for key in (
        "VERSION_ENCRYPTION_KEY",
        "META_ENCRYPTION_KEY",
        "DATA_ENCRYPTION_KEY",
        "FERNET_KEY",
        "PII_HASH_KEY",
    ):
        assert (
            runner.count(f'{key}="${{BENCHMARK_FERNET_KEY}}"') >= 2
            or runner.count(f'{key}="${{BENCHMARK_HASH_KEY}}"') >= 2
        )


def test_k6_runner_extracts_login_cookies_portably_and_fails_fast() -> None:
    runner = _read("load-tests/compare-local.sh")

    assert "curl --silent --show-error --fail" in runner
    assert "tolower($0) ~ /^set-cookie:/" in runner
    assert "Login did not return a session cookie" in runner


def test_performance_artifacts_are_ignored() -> None:
    gitignore = _read(".gitignore")

    assert "apps/api/performance/artifacts/" in gitignore
    assert "*.stats.enc" in gitignore


def test_cloudsql_query_insights_and_cloud_run_slo_are_declared() -> None:
    cloudsql = _read("infra/terraform/cloudsql.tf")
    monitoring = _read("infra/terraform/monitoring.tf")

    assert "insights_config" in cloudsql
    assert "query_insights_enabled" in cloudsql
    assert "record_application_tags" in cloudsql
    assert 'resource "google_monitoring_service" "api"' in monitoring
    assert 'resource "google_monitoring_slo" "api_latency"' in monitoring
    assert "select_slo_burn_rate" in monitoring


def test_performance_documentation_excludes_cloudsql_clones() -> None:
    documentation = _read("docs/performance-validation.md")

    assert "Cloud SQL clone" in documentation
    assert "excluded" in documentation.lower()
    assert "10%" in documentation
    assert "statistics-only" in documentation
    assert "scenario-specific overrides" in documentation
    assert "controlled `VACUUM (ANALYZE)`" in documentation
    assert "table and TOAST autovacuum" in documentation


def test_cloud_run_canary_helper_requires_explicit_revisions_and_supports_rollback() -> None:
    script = _read("scripts/cloud-run-canary.sh")

    assert "PROJECT_ID" in script
    assert "REGION" in script
    assert "CANDIDATE_REVISION" in script
    assert "STABLE_REVISION" in script
    assert "CANDIDATE_PERCENT:-10" in script
    assert 'case "${ACTION}"' in script
    assert "start)" in script
    assert "promote)" in script
    assert "rollback)" in script
    assert "--to-revisions" in script


def test_deterministic_orchestrator_has_failure_and_interrupt_cleanup() -> None:
    orchestrator = _read("apps/api/scripts/performance/orchestrator.py")

    assert "with tempfile.TemporaryDirectory" in orchestrator
    assert "finally:" in orchestrator
    assert "_drop_database" in orchestrator
    assert "_remove_worktree" in orchestrator
    assert "pg_terminate_backend" in orchestrator


def test_every_capture_query_has_an_explicit_plan_expectation() -> None:
    manifest = json.loads(_read("apps/api/performance/capture-manifest.json"))
    expectations = json.loads(_read("apps/api/performance/plan-expectations.json"))

    assert {query["id"] for query in manifest["queries"]} == set(expectations["queries"])
