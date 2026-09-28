"""Exercise the release builder without pushing images or deploying services."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def build_web(tmp_path):
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['DOCKER_CALLS'], 'a') as f: f.write(json.dumps(args) + '\\n')\n"
        "if args[0] == 'pull': sys.exit(int(os.environ.get('PULL_STATUS', '0')))\n"
        "if args[:2] == ['image', 'inspect']: print('registry.example/crm/web@sha256:' + 'a'*64)\n"
        "if args[0] == 'build': sys.exit(int(os.environ.get('BUILD_STATUS', '0')))\n"
        "if args[0] == 'push': sys.exit(int(os.environ.get('PUSH_STATUS', '0')))\n"
    )
    docker.chmod(0o755)
    calls_file = tmp_path / "calls.jsonl"

    def run(**overrides):
        result = subprocess.run(
            ["bash", str(ROOT / "scripts/build_web_image.sh")],
            cwd=ROOT,
            env={
                **os.environ,
                "PATH": f"{tmp_path}:{os.environ['PATH']}",
                "DOCKER_CALLS": str(calls_file),
                "IMAGE_WEB": "registry.example/crm/web:latest",
                "NEXT_PUBLIC_API_BASE_URL": "https://api.example.com",
                "NEXT_DEPLOYMENT_ID": "release-build-id",
                "CACHE_BUST": "0",
                **overrides,
            },
            text=True,
            capture_output=True,
        )
        calls = [json.loads(line) for line in calls_file.read_text().splitlines()]
        return result, calls

    return run


@pytest.mark.parametrize("pull_status", ["0", "1"])
def test_web_builder_uses_one_immutable_cache_seed_for_both_stages(build_web, pull_status):
    result, calls = build_web(PULL_STATUS=pull_status)
    assert result.returncode == 0, result.stderr
    builds = [call for call in calls if call[0] == "build"]
    assert [call[call.index("--target") + 1] for call in builds] == ["builder", "runner"]
    seed = (
        "registry.example/crm/web@sha256:" + "a" * 64
        if pull_status == "0"
        else "node:24.18.0-bookworm-slim"
    )
    for call in builds:
        assert f"NEXT_CACHE_IMAGE={seed}" in call
        assert "NEXT_DEPLOYMENT_ID=release-build-id" in call
        assert "BUILDKIT_INLINE_CACHE=1" in call
    assert calls[-1] == ["push", "registry.example/crm/web:build-cache-0"]


def test_failed_web_build_does_not_publish_cache(build_web):
    result, calls = build_web(BUILD_STATUS="1")
    assert result.returncode != 0
    assert not any(call[0] == "push" for call in calls)
    assert len([call for call in calls if call[0] == "build"]) == 1


def test_cache_upload_failure_does_not_fail_web_release(build_web):
    result, _ = build_web(PUSH_STATUS="1")
    assert result.returncode == 0
    assert "next build may run cold" in result.stderr


def test_cache_bust_uses_a_separate_seed(build_web):
    result, calls = build_web(CACHE_BUST="reset-2")
    assert result.returncode == 0
    assert calls[0] == ["pull", "registry.example/crm/web:build-cache-reset-2"]


def test_web_release_supplies_a_unique_deployment_id_and_publishes_runner():
    config = yaml.safe_load((ROOT / "cloudbuild/web.yaml").read_text())
    build = next(step for step in config["steps"] if step.get("id") == "build-web")
    assert "NEXT_DEPLOYMENT_ID=$BUILD_ID" in build["env"]
    assert build["args"] == ["scripts/build_web_image.sh"]
    assert config["steps"][1]["args"] == ["push", "$_IMAGE_WEB"]
    assert config["images"] == ["$_IMAGE_WEB"]
