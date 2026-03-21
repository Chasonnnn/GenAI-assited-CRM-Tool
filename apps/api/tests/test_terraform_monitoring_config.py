from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text()


def _slice_block(content: str, start_token: str, end_token: str) -> str:
    start_idx = content.find(start_token)
    assert start_idx != -1, f"Missing block start: {start_token}"
    end_idx = content.find(end_token, start_idx + len(start_token))
    assert end_idx != -1, f"Missing block end: {end_token}"
    return content[start_idx:end_idx]


def test_cloudrun_web_has_startup_and_liveness_probes() -> None:
    content = _read("infra/terraform/cloudrun.tf")
    web_block = _slice_block(
        content,
        'resource "google_cloud_run_v2_service" "web" {',
        'resource "google_cloud_run_v2_service_iam_member" "api_invoker" {',
    )

    assert "startup_probe" in web_block
    assert "liveness_probe" in web_block
    assert 'path = "/health"' in web_block
    assert "port = 3000" in web_block


def test_monitoring_webhook_channel_is_configured() -> None:
    content = _read("infra/terraform/monitoring.tf")
    assert 'resource "google_monitoring_notification_channel" "ops_webhook"' in content
    assert "webhook_tokenauth" in content
    assert re.search(r"url\s*=\s*local\.monitoring_webhook_url", content)
    assert re.search(r"token\s*=\s*var\.monitoring_webhook_token", content)
    assert "notification_channels = local.alert_notification_channels" in content


def test_alert_channel_locals_include_webhook() -> None:
    content = _read("infra/terraform/locals.tf")
    assert "alert_notification_channels" in content
    assert "monitoring_webhook_enabled" in content
    assert "/internal/alerts/gcp" in content
    assert "?auth_token=" not in content


def test_google_provider_uses_project_for_quota_billing() -> None:
    content = _read("infra/terraform/providers.tf")
    assert 'provider "google"' in content
    assert 'provider "google-beta"' in content
    assert "user_project_override = true" in content
    assert "billing_project       = var.project_id" in content


def test_api_and_worker_mount_cloudsql_socket() -> None:
    content = _read("infra/terraform/cloudrun.tf")
    assert 'resource "google_cloud_run_v2_service" "api"' in content
    assert 'resource "google_cloud_run_v2_service" "worker"' in content
    assert 'mount_path = "/cloudsql"' in content
    assert "cloud_sql_instance {" in content


def test_billing_budget_uses_email_specific_channels_or_default_recipients() -> None:
    content = _read("infra/terraform/budget.tf")
    vars_content = _read("infra/terraform/variables.tf")
    assert "billing_budget_notification_channel_ids" in vars_content
    assert (
        "monitoring_notification_channels = var.billing_budget_notification_channel_ids" in content
    )
    assert (
        "disable_default_iam_recipients   = length(var.billing_budget_notification_channel_ids) > 0"
        in content
    )
    assert 'projects = ["projects/${data.google_project.current.number}"]' in content


def test_ticketing_logging_metrics_and_alerts_are_configured() -> None:
    content = _read("infra/terraform/monitoring.tf")
    assert 'resource "google_logging_metric" "ticketing_outbound_failures"' in content
    assert 'resource "google_logging_metric" "mailbox_ingestion_failures"' in content
    assert "type=ticket_outbound_send" in content
    assert "final=true" in content
    assert (
        'resource.type=\\"cloud_run_revision\\" metric.type=\\"logging.googleapis.com/user/'
        in content
    )
    assert (
        "type=(mailbox_backfill|mailbox_history_sync|mailbox_watch_refresh|email_occurrence_fetch_raw|email_occurrence_parse|email_occurrence_stitch|ticket_apply_linking)"
        in content
    )
    assert 'resource "google_monitoring_alert_policy" "ticketing_outbound_failures"' in content
    assert 'resource "google_monitoring_alert_policy" "mailbox_ingestion_failures"' in content
