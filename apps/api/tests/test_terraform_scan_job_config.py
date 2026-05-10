from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text()


def test_attachment_scan_cloud_run_job_is_declared() -> None:
    content = _read("infra/terraform/clamav.tf")
    assert 'resource "google_cloud_run_v2_job" "attachment_scan"' in content
    assert 'command = ["python", "-m", "app.scan_job_runner"]' in content
    assert "var.attachment_scan_job_memory" in content
    assert "var.attachment_scan_job_cpu" in content


def test_attachment_scan_job_env_is_exposed_to_services() -> None:
    content = _read("infra/terraform/locals.tf")
    assert "ATTACHMENT_SCAN_CLOUD_RUN_JOB_NAME" in content
    assert "ATTACHMENT_SCAN_CLOUD_RUN_REGION" in content


def test_api_service_account_can_execute_attachment_scan_job() -> None:
    content = _read("infra/terraform/clamav-iam.tf")
    assert 'resource "google_project_iam_member" "api_run_developer"' in content
    assert 'role    = "roles/run.developer"' in content
    assert 'member  = "serviceAccount:${google_service_account.api.email}"' in content


def test_worker_scale_scheduler_uses_dedicated_scaler_identity() -> None:
    service_accounts = _read("infra/terraform/service-accounts.tf")
    schedule = _read("infra/terraform/worker-schedule.tf")
    clamav_iam = _read("infra/terraform/clamav-iam.tf")

    assert 'resource "google_service_account" "worker_scaler"' in service_accounts
    assert 'account_id   = "crm-worker-scaler-sa"' in service_accounts
    assert 'resource "google_project_iam_custom_role" "worker_scaler"' in schedule
    assert '"run.services.get"' in schedule
    assert '"run.services.update"' in schedule
    assert 'resource "google_project_iam_member" "worker_scaler_run_update"' in schedule
    assert 'resource "google_service_account_iam_member" "worker_scaler_sa_user_worker"' in schedule
    assert 'service_account_email = google_service_account.worker_scaler[0].email' in schedule
    assert "(var.clamav_update_enabled || var.worker_schedule_enabled)" not in clamav_iam


def test_cloudbuild_updates_attachment_scan_job_image() -> None:
    content = _read("cloudbuild/api.yaml")
    assert "$_ATTACHMENT_SCAN_JOB" in content
    assert (
        'args: ["run", "jobs", "update", "$_ATTACHMENT_SCAN_JOB", "--image", "$_IMAGE_WORKER", "--region", "$_REGION", "--quiet"]'
        in content
    )
