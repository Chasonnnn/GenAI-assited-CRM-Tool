from __future__ import annotations

from pathlib import Path


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
    assert "url = local.monitoring_webhook_url" in content
    assert "notification_channels = local.alert_notification_channels" in content


def test_alert_channel_locals_include_webhook() -> None:
    content = _read("infra/terraform/locals.tf")
    assert "alert_notification_channels" in content
    assert "monitoring_webhook_enabled" in content
    assert "/internal/alerts/gcp?auth_token=" in content
