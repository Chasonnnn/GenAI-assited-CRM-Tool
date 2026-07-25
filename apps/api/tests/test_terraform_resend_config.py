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


def test_platform_resend_admission_group_token_is_injected_as_a_service_secret() -> None:
    content = _read("infra/terraform/locals.tf")
    service_secret_block = _slice_block(
        content,
        "common_secret_keys = [",
        "billing_secret_keys = [",
    )

    assert '"PLATFORM_RESEND_ADMISSION_GROUP_TOKEN"' in service_secret_block


def test_cloudbuild_replaces_snapshot_aware_worker_before_api_producers() -> None:
    content = _read("cloudbuild/api.yaml")
    migration_step = (
        'args: ["beta", "run", "jobs", "execute", "$_MIGRATE_JOB", '
        '"--region", "$_REGION", "--wait", "--quiet"]'
    )
    worker_step = (
        'args: ["run", "services", "update", "$_WORKER_SERVICE", '
        '"--image", "$_IMAGE_WORKER", "--region", "$_REGION", "--quiet"]'
    )
    api_step = (
        'args: ["run", "services", "update", "$_API_SERVICE", '
        '"--image", "$_IMAGE_API", "--region", "$_REGION", "--quiet"]'
    )

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
