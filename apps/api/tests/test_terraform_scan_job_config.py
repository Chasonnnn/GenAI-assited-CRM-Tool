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
    assert "service_account_email = google_service_account.worker_scaler[0].email" in schedule
    assert "(var.clamav_update_enabled || var.worker_schedule_enabled)" not in clamav_iam


def test_worker_capacity_remains_available_for_background_automation() -> None:
    variables = _read("infra/terraform/variables.tf")
    cloudrun = _read("infra/terraform/cloudrun.tf")
    tfvars_example = _read("infra/terraform/terraform.tfvars.example")

    worker_min = variables.split('variable "worker_min_instances"', 1)[1].split("}", 1)[0]
    schedule_enabled = variables.split('variable "worker_schedule_enabled"', 1)[1].split("}", 1)[0]
    night_min = variables.split('variable "worker_min_instances_night"', 1)[1].split("}", 1)[0]

    assert "default     = 1" in worker_min
    assert "default     = false" in schedule_enabled
    assert "default     = 1" in night_min
    assert "template[0].scaling[0].min_instance_count" not in cloudrun
    assert "# worker_min_instances = 1" in tfvars_example
    assert "# worker_schedule_enabled = false" in tfvars_example
    assert "# worker_min_instances_night = 1" in tfvars_example


def test_worker_workflow_fallbacks_have_explicit_safe_terraform_controls() -> None:
    variables = _read("infra/terraform/variables.tf")
    locals = _read("infra/terraform/locals.tf")
    cloudrun = _read("infra/terraform/cloudrun.tf")

    scheduled = variables.split('variable "workflow_sweep_fallback_enabled"', 1)[1].split("}", 1)[0]
    maintenance = variables.split('variable "workflow_maintenance_fallback_enabled"', 1)[1].split(
        "}", 1
    )[0]
    approvals = variables.split('variable "workflow_approval_expiry_fallback_enabled"', 1)[1].split(
        "}", 1
    )[0]

    assert "default     = true" in scheduled
    assert "default     = false" in maintenance
    assert "default     = false" in approvals
    assert "WORKFLOW_SWEEP_FALLBACK_ENABLED" in locals
    assert "WORKFLOW_MAINTENANCE_FALLBACK_ENABLED" in locals
    assert "WORKFLOW_APPROVAL_EXPIRY_FALLBACK_ENABLED" in locals
    assert "for_each = local.worker_env" in cloudrun


def test_cloudbuild_updates_attachment_scan_job_image() -> None:
    content = _read("cloudbuild/api.yaml")
    assert "$_ATTACHMENT_SCAN_JOB" in content
    assert 'gcloud run jobs update "$_ATTACHMENT_SCAN_JOB"' in content
    assert '--image "$${worker_image_ref}"' in content


def test_cloudbuild_updates_compatible_scan_runner_before_claim_producers() -> None:
    content = _read("cloudbuild/api.yaml")
    migration_execute = content.index('gcloud beta run jobs execute "$_MIGRATE_JOB"')
    scan_job_update = content.index('gcloud run jobs update "$_ATTACHMENT_SCAN_JOB"')
    api_update = content.index('gcloud run services update "$_API_SERVICE"')
    worker_update = content.index('gcloud run services update "$_WORKER_SERVICE"')

    assert migration_execute < scan_job_update < worker_update < api_update


def test_cloudbuild_resolves_and_deploys_one_digest_image_set() -> None:
    content = _read("cloudbuild/api.yaml")

    assert "RELEASE_SHA=$COMMIT_SHA" in content
    assert "RELEASE_TAG=$COMMIT_SHA-$BUILD_ID" in content
    assert 'test -n "$${RELEASE_SHA}"' in content
    assert 'test -n "$${RELEASE_TAG}"' in content
    assert 'api_image="$${IMAGE_API_LATEST%:*}:$${RELEASE_TAG}"' in content
    assert 'worker_image="$${IMAGE_WORKER_LATEST%:*}:$${RELEASE_TAG}"' in content
    assert content.count("gcloud artifacts docker images describe") == 2
    assert "value(image_summary.digest)" in content
    assert 'test "$${api_digest#sha256:}" != "$${api_digest}"' in content
    assert 'test "$${worker_digest#sha256:}" != "$${worker_digest}"' in content
    assert '[[ "$${api_digest}" =~ ^sha256:[0-9a-f]{64}$$ ]]' in content
    assert '[[ "$${worker_digest}" =~ ^sha256:[0-9a-f]{64}$$ ]]' in content
    assert "/workspace/release-api-image-ref" in content
    assert "/workspace/release-worker-image-ref" in content
    assert content.count('--image "$${api_image_ref}"') >= 2
    assert content.count('--image "$${worker_image_ref}"') >= 3
    assert '--image "$${api_image}"' not in content
    assert '--image "$${worker_image}"' not in content
    assert '"--image", "$_IMAGE_API"' not in content
    assert '"--image", "$_IMAGE_WORKER"' not in content


def test_cloudbuild_preserves_the_resumed_worker_configuration() -> None:
    content = _read("cloudbuild/api.yaml")
    worker_update = content.index('gcloud run services update "$_WORKER_SERVICE"')
    api_update = content.index('gcloud run services update "$_API_SERVICE"')
    worker_step = content[worker_update:api_update]

    assert '--image "$${worker_image_ref}"' in worker_step
    assert "--update-env-vars" not in worker_step
    assert "--remove-env-vars" not in worker_step
    assert "WORKER_CUTOVER_HOLD" not in worker_step
    assert "EMAIL_DELIVERY_DISPATCH_ENABLED" not in worker_step
    assert "WORKER_JOB_TYPES" not in worker_step


def test_release_a_runbook_requires_operator_gates_before_resume() -> None:
    content = _read("docs/runbooks/release-a-job-claim-cutover.md")
    normalized = " ".join(content.split())

    assert "WORKER_CUTOVER_HOLD=true" in content
    assert "EMAIL_DELIVERY_DISPATCH_ENABLED=false" in content
    assert "does not change `WORKER_JOB_TYPES`" in normalized
    assert "zero active `crm-attachment-scan` executions" in content
    assert "reconcile-legacy-job-claims" in content
    assert "--manifest" in content
    assert "--expected-count" in content
    assert "--expected-fingerprint" in content
    assert "IAM-controlled" in content
    assert "encrypted at rest" in content
    assert "`applied_at`" in content
    assert "No automatic resume" in content
    assert "deploy the exact `@sha256:` API and worker digest" in normalized
    assert "--remove-env-vars WORKER_CUTOVER_HOLD" in content
    assert "restore the captured pre-cutover values" in normalized.lower()
