from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"


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
