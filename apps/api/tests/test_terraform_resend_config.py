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


def test_platform_resend_admission_group_token_is_scoped_to_api_and_worker() -> None:
    locals_content = _read("infra/terraform/locals.tf")
    common_secret_block = _slice_block(
        locals_content,
        "common_secret_keys = [",
        "service_secret_keys =",
    )
    service_secret_block = _slice_block(
        locals_content,
        "service_secret_keys =",
        "billing_secret_keys = [",
    )
    cloudrun_content = _read("infra/terraform/cloudrun.tf")
    clamav_content = _read("infra/terraform/clamav.tf")

    assert '"PLATFORM_RESEND_ADMISSION_GROUP_TOKEN"' not in common_secret_block
    assert '"PLATFORM_RESEND_ADMISSION_GROUP_TOKEN"' in service_secret_block
    assert cloudrun_content.count("sort(local.service_secret_keys)") == 2
    assert cloudrun_content.count("sort(local.common_secret_keys)") == 1
    assert cloudrun_content.count("for_each = local.job_env") == 1
    assert clamav_content.count("sort(local.common_secret_keys)") == 2
    assert "local.service_secret_keys" not in clamav_content
    assert clamav_content.count("for_each = local.job_env") == 2


def test_cloudbuild_replaces_snapshot_aware_worker_before_api_producers() -> None:
    content = _read("cloudbuild/api.yaml")
    migration_step = 'gcloud beta run jobs execute "$_MIGRATE_JOB"'
    worker_step = 'gcloud run services update "$_WORKER_SERVICE"'
    api_step = 'gcloud run services update "$_API_SERVICE"'

    assert content.index(migration_step) < content.index(worker_step) < content.index(api_step)


def test_resend_admission_secret_documents_two_phase_existing_environment_rollout() -> None:
    content = _read("infra/terraform/README.md")
    target_address = 'google_secret_manager_secret.secrets["PLATFORM_RESEND_ADMISSION_GROUP_TOKEN"]'
    add_version = "gcloud secrets versions add PLATFORM_RESEND_ADMISSION_GROUP_TOKEN --data-file=-"
    full_plan = "terraform -chdir=infra/terraform plan"
    full_apply = "terraform -chdir=infra/terraform apply"

    target_position = content.index(target_address)
    version_position = content.index(add_version, target_position)
    plan_position = content.index(full_plan, version_position)
    apply_position = content.index(full_apply, plan_position)

    assert target_position < version_position < plan_position < apply_position
