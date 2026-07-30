from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
RELEASE_WORKFLOW = ROOT / ".github/workflows/release-please.yml"


def test_release_only_pull_requests_run_ci() -> None:
    workflow = CI_WORKFLOW.read_text()
    pull_request_trigger = workflow.split("jobs:", 1)[0]

    assert "pull_request:" in pull_request_trigger
    assert "paths-ignore:" not in pull_request_trigger


def test_ci_builds_every_production_image_with_deployment_inputs() -> None:
    workflow = CI_WORKFLOW.read_text()

    expected_builds = [
        "docker build -t crm-api:ci apps/api",
        "docker build -f apps/api/Dockerfile.worker -t crm-worker:ci apps/api",
        (
            "docker build -f apps/web/Dockerfile "
            "--build-arg NEXT_PUBLIC_API_BASE_URL=https://api.surrogacyforce.com "
            "-t crm-web:ci ."
        ),
    ]
    for build in expected_builds:
        assert build in workflow


def test_ci_uses_the_repository_pnpm_release() -> None:
    workflow = CI_WORKFLOW.read_text()
    package = json.loads((ROOT / "apps/web/package.json").read_text())
    expected_version = package["packageManager"].split("@", 1)[1].split("+", 1)[0]

    prepared_versions = set(re.findall(r"corepack prepare pnpm@([^ ]+) --activate", workflow))

    assert prepared_versions == {expected_version}


def test_package_manager_is_corepack_compatible_and_mise_checksum_pinned() -> None:
    package = json.loads((ROOT / "apps/web/package.json").read_text())
    mise_config = tomllib.loads((ROOT / "mise.toml").read_text())
    mise_lock = tomllib.loads((ROOT / "mise.lock").read_text())
    pnpm_version = mise_config["tools"]["pnpm"]

    assert package["packageManager"] == f"pnpm@{pnpm_version}"

    locked_pnpm = mise_lock["tools"]["pnpm"]
    assert len(locked_pnpm) == 1
    assert locked_pnpm[0]["version"] == pnpm_version

    locked_platforms = {
        key.removeprefix("platforms."): value
        for key, value in locked_pnpm[0].items()
        if key.startswith("platforms.")
    }
    assert set(locked_platforms) == set(mise_config["settings"]["lockfile_platforms"])
    for platform in locked_platforms.values():
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", platform["checksum"])


def test_ci_uses_the_repository_mise_runtime_versions() -> None:
    workflow = CI_WORKFLOW.read_text()
    tools = tomllib.loads((ROOT / "mise.toml").read_text())["tools"]

    python_versions = re.findall(r"python-version: '([^']+)'", workflow)
    node_versions = re.findall(r"node-version: '([^']+)'", workflow)
    uv_versions = re.findall(
        r"uses: astral-sh/setup-uv@v7\s+with:\s+version: '([^']+)'",
        workflow,
    )

    assert python_versions and set(python_versions) == {tools["python"]}
    assert node_versions and set(node_versions) == {tools["node"]}
    assert len(uv_versions) == workflow.count("uses: astral-sh/setup-uv@v7")
    assert set(uv_versions) == {tools["uv"]}


def test_release_automation_uses_the_node_24_action() -> None:
    workflow = RELEASE_WORKFLOW.read_text()

    assert "uses: googleapis/release-please-action@v5" in workflow
    assert "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24" not in workflow
