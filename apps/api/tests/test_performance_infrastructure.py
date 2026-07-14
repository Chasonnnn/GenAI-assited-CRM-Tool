from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


def test_ci_uses_postgres_18_1_and_separates_deterministic_performance_gates() -> None:
    workflow = _read(".github/workflows/ci.yml")

    assert "postgres:16" not in workflow
    assert workflow.count("postgres:18.1") >= 4
    assert "performance-gates:" in workflow

    performance_job = workflow.split("  performance-gates:", maxsplit=1)[1].split(
        "\n  frontend-tests:", maxsplit=1
    )[0]
    assert "pytest" in performance_job
    assert " k6 run " not in performance_job.lower()
    assert "load-tests" not in performance_job


def test_cloudsql_query_insights_never_records_client_addresses() -> None:
    cloudsql = _read("infra/terraform/cloudsql.tf")
    apis = _read("infra/terraform/apis.tf")

    assert re.search(r"query_insights_enabled\s*=\s*var\.query_insights_enabled", cloudsql)
    assert re.search(
        r"query_string_length\s*=\s*var\.query_insights_query_string_length",
        cloudsql,
    )
    assert re.search(
        r"query_plans_per_minute\s*=\s*var\.query_insights_query_plans_per_minute",
        cloudsql,
    )
    assert re.search(r"record_application_tags\s*=\s*true", cloudsql)
    assert re.search(r"record_client_address\s*=\s*false", cloudsql)
    assert '"cloudtrace.googleapis.com"' in apis


def test_cloud_run_latency_slo_and_error_budget_alert_are_configurable() -> None:
    monitoring = _read("infra/terraform/monitoring.tf")
    variables = _read("infra/terraform/variables.tf")

    assert 'service_type = "CLOUD_RUN"' in monitoring
    assert "service_name = var.api_service_name" in monitoring
    assert "location     = var.run_region" in monitoring
    assert 'resource "google_monitoring_slo" "api_latency"' in monitoring
    assert "threshold = var.api_latency_slo_threshold" in monitoring
    assert "goal                = var.api_latency_slo_goal" in monitoring
    assert "select_slo_burn_rate" in monitoring
    assert "var.api_latency_slo_burn_rate_threshold" in monitoring
    assert 'variable "api_latency_slo_threshold"' in variables
    assert 'variable "api_latency_slo_goal"' in variables
    assert 'variable "api_latency_slo_burn_rate_threshold"' in variables
