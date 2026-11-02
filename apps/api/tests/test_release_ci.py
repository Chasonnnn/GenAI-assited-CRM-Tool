from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from itertools import product
from pathlib import Path

import pytest
import yaml

from scripts import ci_test_shards

ROOT = Path(__file__).resolve().parents[3]
API_ROOT = ROOT / "apps/api"
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
RELEASE_WORKFLOW = ROOT / ".github/workflows/release-please.yml"


def test_zap_permissions_only_change_report_directory(tmp_path):
    workflow = CI_WORKFLOW.read_text()
    command = re.search(
        r"- name: Allow ZAP to write workspace\n(?:\s+if: .+\n)?\s+run: (.+)", workflow
    )
    assert command is not None
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    bytecode = cache / "module.pyc"
    bytecode.write_bytes(b"test")
    bytecode.chmod(0o644)
    cache.chmod(0o755)
    tmp_path.chmod(0o755)
    subprocess.run(
        ["bash", "-eu", "-c", command.group(1)],
        env={**os.environ, "GITHUB_WORKSPACE": str(tmp_path)},
        check=True,
    )
    assert tmp_path.stat().st_mode & 0o002
    # Do not traverse API bytecode: temporary files can disappear during startup.
    assert cache.stat().st_mode & 0o777 == 0o755
    assert bytecode.stat().st_mode & 0o777 == 0o644


def test_match_expansion_release_preflights_before_opening_compatibility_window():
    build = (ROOT / "cloudbuild/api.yaml").read_text()
    assert '_MATCH_EXPANSION_ROLLOUT: "false"' in build
    assert "_MATCH_EXPANSION_REHEARSED_SHA" in build
    assert "app.db.release_migration" in build
    assert build.index("id: match-expansion-preflight") < build.index(
        "id: match-compatibility-window"
    )
    assert build.index("id: match-compatibility-window") < build.index("id: migrate-release")
    assert "MATCH_CASE_EXPANSION_ENABLED=false" in build
    assert "MATCH_CASE_EXPANSION_ENABLED=true" not in build
    assert "DB_MIGRATION_CHECK=true,DB_AUTO_MIGRATE=false" in build
    # A normal retry after a partial expansion must restore readiness checks too.
    assert (
        'worker_env="GCP_SERVICE_NAME=$_WORKER_SERVICE,DB_MIGRATION_CHECK=true,DB_AUTO_MIGRATE=false"'
        in build
    )


@pytest.mark.parametrize("expansion", ["false", "true"])
def test_release_preserves_migration_gates_and_deploys_bounded_pools(tmp_path, expansion):
    build = yaml.safe_load((ROOT / "cloudbuild/api.yaml").read_text())
    calls = tmp_path / "calls.jsonl"
    gcloud = tmp_path / "gcloud"
    gcloud.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['GCLOUD_CALLS'], 'a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
    )
    gcloud.chmod(0o755)
    for service in ("api", "worker"):
        (tmp_path / f"release-{service}-image-ref").write_text(f"example/{service}@sha256:test\n")
    env = {
        **os.environ,
        **build["substitutions"],
        "_MATCH_EXPANSION_ROLLOUT": expansion,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GCLOUD_CALLS": str(calls),
    }
    release_steps = build["steps"][
        next(
            i for i, step in enumerate(build["steps"]) if step.get("id") == "resolve-release-images"
        )
        + 1 :
    ]
    for step in release_steps:
        script = step.get("args", [""])[-1]
        script = script.replace("$$", "$").replace("/workspace/", f"{tmp_path}/")
        subprocess.run(["bash", "-ceu", script], env=env, check=True)

    recorded = [json.loads(line) for line in calls.read_text().splitlines()]
    executions = [
        i for i, argv in enumerate(recorded) if argv[:4] == ["beta", "run", "jobs", "execute"]
    ]
    assert len(executions) == (2 if expansion == "true" else 1)
    assert all("--wait" in recorded[i] for i in executions)
    compatibility_updates = [
        i
        for i, argv in enumerate(recorded)
        if any("DB_MIGRATION_CHECK=false" in arg for arg in argv)
    ]
    if expansion == "true":
        assert len(compatibility_updates) == 2
        assert (
            executions[0] < min(compatibility_updates) <= max(compatibility_updates) < executions[1]
        )
    else:
        assert not compatibility_updates
    deployments = [
        (i, argv)
        for i, argv in enumerate(recorded)
        if argv[:3] == ["run", "services", "update"] and "--image" in argv
    ]
    assert len(deployments) == 2
    for index, argv in deployments:
        assert executions[-1] < index
        service = argv[3]
        ceiling = "2" if service == "crm-api" else "3"
        assert argv[argv.index("--max") + 1] == ceiling
        assert argv[argv.index("--max-instances") + 1] == ceiling
        variables = dict(
            item.split("=", 1) for item in argv[argv.index("--update-env-vars") + 1].split(",")
        )
        assert variables["DB_POOL_SIZE"] == "2"
        assert variables["DB_MAX_OVERFLOW"] == "0"
        assert variables["DB_MIGRATION_CHECK"] == "true"
        assert variables["DB_AUTO_MIGRATE"] == "false"
        assert variables.get("MATCH_CASE_EXPANSION_ENABLED") == (
            "false" if expansion == "true" else None
        )


def _trigger_paths(workflow: str, event: str) -> set[str]:
    trigger_block = workflow.split("jobs:", 1)[0]
    event_match = re.search(
        rf"^  {event}:\n(?P<body>.*?)(?=^  [a-z_]+:|^concurrency:)",
        trigger_block,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert event_match is not None
    return set(re.findall(r"^      - '([^']+)'$", event_match.group("body"), re.MULTILINE))


def test_ci_uses_safe_path_filters_and_cancels_stale_runs() -> None:
    workflow = CI_WORKFLOW.read_text()
    pull_request_trigger = workflow.split("jobs:", 1)[0]
    expected_paths = {
        ".agents/**",
        "apps/**",
        "cloudbuild/**",
        "docs/adr/**",
        "infra/terraform/**",
        "scripts/**",
        "pyproject.toml",
        "uv.lock",
        "Makefile",
        "mise.toml",
        "mise.lock",
        ".dockerignore",
        "zap-baseline.conf",
        ".release-please-manifest.json",
        "release-please-config.json",
        ".github/workflows/ci.yml",
        ".github/workflows/release-please.yml",
    }

    assert "pull_request:" in pull_request_trigger
    assert "paths-ignore:" not in pull_request_trigger
    assert _trigger_paths(workflow, "push") == expected_paths
    assert _trigger_paths(workflow, "pull_request") == expected_paths
    assert "concurrency:\n" in pull_request_trigger
    assert "  group: ci-${{ github.workflow }}-${{ github.ref }}" in pull_request_trigger
    assert "  cancel-in-progress: true" in pull_request_trigger


def test_ci_checks_stacked_permission_pr_without_broadening_push_triggers() -> None:
    branches = dict(
        re.findall(
            r"^  (push|pull_request):\n    branches: \[([^\]]+)\]",
            CI_WORKFLOW.read_text(),
            re.MULTILINE,
        )
    )
    assert branches["pull_request"].split(", ") == [
        "main",
        "develop",
        "codex/platform-upgrades",
    ]
    assert branches["push"].split(", ") == ["main", "develop"]


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

    assert "matrix:\n        include:" in workflow
    assert "needs: production-artifact-builds" in workflow
    assert "name: Production Artifacts" in workflow


def test_ci_parallelizes_safe_backend_tests_and_serializes_migrations(tmp_path) -> None:
    workflow = CI_WORKFLOW.read_text()
    pyproject = (ROOT / "apps/api/pyproject.toml").read_text()

    assert '"pytest-xdist==3.8.0"' in pyproject
    assert "--ignore-glob 'tests/test_migration_*.py'" in workflow
    assert "-n 4 --dist loadscope" in workflow
    assert "tests/test_migration_*.py" in workflow
    jobs = yaml.safe_load(workflow)["jobs"]
    groups = jobs["backend-test-groups"]["strategy"]["matrix"]["group"]
    assert groups == ["parallel-1", "parallel-2", "parallel-3", "parallel-4", "serial"]
    assert '"${test_files[@]}"' in workflow
    assert "COVERAGE_FILE: .coverage.${{ matrix.group }}" in workflow
    assert jobs["backend-tests"]["needs"] == ["changes", "backend-test-groups"]
    assert 'test "$GROUP_RESULT" = success' in workflow
    assert "uv run coverage combine" in workflow
    assert "uv run coverage xml" in workflow
    coverage = tomllib.loads(pyproject)["tool"]["coverage"]["report"]
    assert coverage["fail_under"] > 0

    # Execute the workflow's partitioner: each safe file must run exactly once.
    command = next(
        step["run"]
        for step in jobs["backend-test-groups"]["steps"]
        if step.get("name") == "Run parallel-safe tests"
    )
    select = 'python scripts/ci_test_shards.py select "${TEST_GROUP#parallel-}" 4'
    assert f"{select} > /tmp/backend-test-files" in command
    safe_files = {f"tests/test_{name}.py" for name in ("a", "b", "c", "d", "e")}
    safe_files.add("tests/nested/test_f.py")
    for path in safe_files | {
        "tests/test_migration_schema.py",
        "tests/test_email_delivery_outbox.py",
        "tests/test_ops_cli_integration.py",
        "tests/conftest.py",
    }:
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()
    selected = []
    for group in groups[:-1]:
        result = subprocess.run(
            [
                "bash",
                "-c",
                select.replace("python scripts/", f"{sys.executable} {API_ROOT}/scripts/"),
            ],
            cwd=tmp_path,
            env={**os.environ, "TEST_GROUP": group},
            check=True,
            capture_output=True,
            text=True,
        )
        shard = result.stdout.splitlines()
        assert shard
        selected.extend(shard)
    assert set(selected) == safe_files
    assert len(selected) == len(safe_files)


def test_backend_shards_balance_recorded_durations(tmp_path) -> None:
    durations = {"tests/test_a.py": 10.0, "tests/test_b.py": 6.0, "tests/test_c.py": 4.0}
    files = [*durations, "tests/test_new.py"]
    # The unrecorded file counts as the median duration (6s), so the shards total 14s and 12s.
    shards = ci_test_shards.assign_shards(files, durations, 2)
    assert shards == [
        ["tests/test_a.py", "tests/test_c.py"],
        ["tests/test_b.py", "tests/test_new.py"],
    ]

    report = tmp_path / "junit.xml"
    report.write_text(
        "<testsuites><testsuite>"
        '<testcase classname="tests.test_a" name="one" time="1"/>'
        '<testcase classname="tests.test_a.TestGroup" name="two" time="2"/>'
        '<testcase classname="tests.nested.test_b" name="three" time="0.5"/>'
        "</testsuite></testsuites>"
    )
    assert ci_test_shards.junit_file_durations([report]) == {
        "tests/nested/test_b.py": 0.5,
        "tests/test_a.py": 3.0,
    }


def test_backend_test_durations_cover_current_parallel_files() -> None:
    recorded = json.loads(ci_test_shards.DURATIONS.read_text())
    current = ci_test_shards.parallel_safe_files(API_ROOT / "tests")
    current = [str(Path(file).relative_to(API_ROOT)) for file in current]
    # New files fall back to the median; refresh the file when many are missing.
    missing = set(current) - set(recorded)
    assert len(missing) <= len(current) // 10, sorted(missing)


def test_ci_isolates_global_database_assertions_from_parallel_workers() -> None:
    workflow = CI_WORKFLOW.read_text()
    parallel = workflow.split("- name: Run parallel-safe tests", 1)[1].split("- name:", 1)[0]
    serial = workflow.split("- name: Run shared-database tests serially", 1)[1].split("- name:", 1)[
        0
    ]

    assert "--ignore tests/test_email_delivery_outbox.py" in parallel
    assert "tests/test_email_delivery_outbox.py" in serial
    assert "--ignore tests/test_ops_cli_integration.py" in parallel
    assert "tests/test_ops_cli_integration.py" in serial
    assert "-n 4" not in serial
    assert "if: startsWith(matrix.group, 'parallel-')" in parallel
    assert "if: matrix.group == 'serial'" in serial
    assert "--cov-fail-under=0" in parallel
    assert "--cov-fail-under=0" in serial


def test_ci_shards_frontend_tests_and_preserves_aggregate_gate() -> None:
    workflow = CI_WORKFLOW.read_text()

    jobs = yaml.safe_load(workflow)["jobs"]
    assert jobs["frontend-test-shards"]["strategy"]["matrix"]["shard"] == [1, 2, 3, 4]
    assert "pnpm test --shard=${{ matrix.shard }}/4" in workflow
    assert jobs["frontend-coverage"]["needs"] == "frontend-test-shards"
    gate = jobs["frontend-tests"]
    assert gate["needs"] == ["changes", "frontend-build", "frontend-coverage"]
    assert gate["name"] == "Frontend Tests"
    assert gate["if"] == _RUN_AREA.format(area="frontend")
    assert "--coverage --reporter=default --reporter=blob" in workflow
    assert "path: apps/web/.vitest/blob/*.json" in workflow
    assert "path: apps/web/.vitest/blob\n" in workflow
    assert "pnpm test --merge-reports --coverage" in workflow
    verify = gate["steps"][0]
    assert verify["env"] == {
        "BUILD_RESULT": "${{ needs.frontend-build.result }}",
        "COVERAGE_RESULT": "${{ needs.frontend-coverage.result }}",
    }
    for build, coverage in product(("success", "failure", "skipped", "cancelled"), repeat=2):
        result = subprocess.run(
            ["bash", "-e", "-c", verify["run"]],
            env={**os.environ, "BUILD_RESULT": build, "COVERAGE_RESULT": coverage},
            capture_output=True,
        )
        assert (result.returncode == 0) == (build == coverage == "success")


_RUN_AREA = (
    "${{{{ !cancelled() && (needs.changes.result != 'success' "
    "|| needs.changes.outputs.{area} == 'true') }}}}"
)
_AREA_ENV = "${{{{ needs.changes.result != 'success' || needs.changes.outputs.{area} == 'true' }}}}"


def _changed_areas(paths: list[str]) -> dict[str, str]:
    result = subprocess.run(
        [sys.executable, "-I", str(ROOT / "scripts/ci_changed_areas.py")],
        input="\n".join(paths),
        check=True,
        capture_output=True,
        text=True,
    )
    return dict(line.split("=", 1) for line in result.stdout.splitlines())


@pytest.mark.parametrize(
    ("paths", "backend", "frontend"),
    [
        (["apps/web/components/button.tsx"], "false", "true"),
        (["apps/web/tests/button.test.tsx", "apps/web/app/page.tsx"], "false", "true"),
        (["apps/api/app/main.py"], "true", "false"),
        (["uv.lock", "cloudbuild/api.yaml", "docs/adr/0001-x.md"], "true", "false"),
        (["apps/api/app/main.py", "apps/web/app/page.tsx"], "true", "true"),
        # Backend tests read these web files.
        (["apps/web/lib/constants/stages.generated.ts"], "true", "true"),
        (["apps/web/package.json"], "true", "true"),
        (["apps/web/public/journey/defaults/match.jpg"], "true", "true"),
        # Frontend tests read these backend files.
        (["apps/api/app/core/stage_definitions.py"], "true", "true"),
        (["apps/api/tests/fixtures/public_email_rule_cases.json"], "true", "true"),
        # Shared inputs and an empty diff run every area.
        (["apps/web/app/page.tsx", ".github/workflows/ci.yml"], "true", "true"),
        (["mise.lock"], "true", "true"),
        (["scripts/gen_stage_map.py"], "true", "true"),
        ([], "true", "true"),
    ],
)
def test_ci_changed_areas_skip_only_unaffected_areas(paths, backend, frontend) -> None:
    assert _changed_areas(paths) == {"backend": backend, "frontend": frontend}


def test_ci_backend_tests_read_only_listed_web_files() -> None:
    """A backend test that reads a new web file must add it to BACKEND_READS_FROM_WEB."""
    listed = (ROOT / "scripts/ci_changed_areas.py").read_text()
    pattern = re.compile(r"apps/web/[\w./-]+|\"apps\", \"web\", ((?:\"[\w.-]+\"(?:, )?)+)")
    for test in (API_ROOT / "tests").rglob("*.py"):
        if test.name == Path(__file__).name:
            continue  # This file holds CI fixtures and reads only listed web files.
        for match in pattern.finditer(test.read_text()):
            if match.group(1):
                path = "apps/web/" + "/".join(re.findall(r'"([\w.-]+)"', match.group(1)))
            else:
                path = match.group(0).rstrip(".")
            if path.startswith("apps/web/.vitest") or path.startswith("apps/web/.next"):
                continue
            # Directory reads are listed with /**; file reads are listed exactly.
            assert f'"{path}"' in listed or any(
                path.startswith(prefix)
                for prefix in re.findall(r'"(apps/web/[\w./-]+)/\*\*"', listed)
            ), f"{test.name} reads {path}"


def test_ci_select_areas_step_diffs_the_pull_request_merge(tmp_path) -> None:
    step = next(
        step
        for step in yaml.safe_load(CI_WORKFLOW.read_text())["jobs"]["changes"]["steps"]
        if step.get("id") == "areas"
    )
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts/ci_changed_areas.py").write_text(
        (ROOT / "scripts/ci_changed_areas.py").read_text()
    )
    git = ["git", "-c", "user.name=ci", "-c", "user.email=ci@example.com"]

    def run(*command: str) -> None:
        subprocess.run(command, cwd=repo, check=True, capture_output=True)

    run("git", "init", "-q", "-b", "main")
    (repo / "apps/api").mkdir(parents=True)
    (repo / "apps/api/main.py").write_text("base\n")
    run("git", "add", ".")
    run(*git, "commit", "-qm", "base")
    run("git", "checkout", "-qb", "feature")
    (repo / "apps/web").mkdir(parents=True)
    (repo / "apps/web/page.tsx").write_text("feature\n")
    run("git", "add", ".")
    run(*git, "commit", "-qm", "feature")
    run("git", "checkout", "-q", "main")
    # The base branch moves on; its change must not count as part of the pull request.
    (repo / "apps/api/main.py").write_text("moved\n")
    run(*git, "commit", "-qam", "moved")
    run(*git, "merge", "-q", "--no-ff", "feature", "-m", "merge")

    for event, expected in (
        ("pull_request", {"backend": "false", "frontend": "true"}),
        ("push", {"backend": "true", "frontend": "true"}),
    ):
        output = tmp_path / f"{event}.out"
        subprocess.run(
            ["bash", "-e", "-c", step["run"]],
            cwd=repo,
            env={**os.environ, "EVENT_NAME": event, "GITHUB_OUTPUT": str(output)},
            check=True,
            capture_output=True,
        )
        assert dict(line.split("=", 1) for line in output.read_text().splitlines()) == expected

    # A classifier crash must fail the job, which runs every area, not leave empty outputs.
    (repo / "scripts/ci_changed_areas.py").write_text("raise SystemExit(1)\n")
    failed = subprocess.run(
        ["bash", "-e", "-c", step["run"]],
        cwd=repo,
        env={**os.environ, "EVENT_NAME": "pull_request", "GITHUB_OUTPUT": str(tmp_path / "x")},
        capture_output=True,
    )
    assert failed.returncode != 0


def test_ci_area_skips_fail_open_when_change_detection_fails() -> None:
    jobs = yaml.safe_load(CI_WORKFLOW.read_text())["jobs"]
    gated = {
        "backend-test-groups": "backend",
        "backend-tests": "backend",
        "backend-fastapi-gates": "backend",
        "ticketing-launch-gate": "backend",
        "frontend-build": "frontend",
        "frontend-test-shards": "frontend",
        "frontend-tests": "frontend",
    }
    for name, area in gated.items():
        assert jobs[name]["if"] == _RUN_AREA.format(area=area), name
    # These jobs always run and skip only the steps of an unaffected area.
    for name in ("lint", "security-scans", "production-artifact-builds"):
        assert jobs[name]["needs"] == "changes"
        assert jobs[name]["if"] == "${{ !cancelled() }}"
    for name in ("lint", "security-scans"):
        env = jobs[name]["env"]
        assert env["RUN_BACKEND"] == _AREA_ENV.format(area="backend")
        assert env["RUN_FRONTEND"] == _AREA_ENV.format(area="frontend")
        conditions = {step.get("if") for step in jobs[name]["steps"]}
        assert {"env.RUN_BACKEND == 'true'", "env.RUN_FRONTEND == 'true'"} <= conditions
    builds = jobs["production-artifact-builds"]
    assert {entry["name"]: entry["area"] for entry in builds["strategy"]["matrix"]["include"]} == {
        "api": "backend",
        "worker": "backend",
        "web": "frontend",
    }
    build_step = next(step for step in builds["steps"] if "matrix.command" in step.get("run", ""))
    assert build_step["if"] == (
        "needs.changes.result != 'success' || needs.changes.outputs[matrix.area] == 'true'"
    )
    # Every job that waits for change detection is covered above.
    waits = {name for name, job in jobs.items() if "changes" in job.get("needs", [])}
    assert waits == set(gated) | {"lint", "security-scans", "production-artifact-builds"}


def test_ci_backend_coverage_floors_read_the_xml_totals(tmp_path) -> None:
    command = next(
        step["run"]
        for step in yaml.safe_load(CI_WORKFLOW.read_text())["jobs"]["backend-tests"]["steps"]
        if step.get("name") == "Combine coverage and enforce floors"
    )
    script = re.search(r"python - <<'PYTHON'\n(.*?)\nPYTHON", command, re.DOTALL)
    assert script is not None
    for lines, branches, passes in ((8000, 6400, True), (7900, 6400, False), (8000, 6200, False)):
        (tmp_path / "coverage.xml").write_text(
            f'<coverage lines-valid="10000" lines-covered="{lines}" '
            f'branches-valid="10000" branches-covered="{branches}"/>'
        )
        result = subprocess.run(
            [sys.executable, "-c", script.group(1)], cwd=tmp_path, capture_output=True
        )
        assert (result.returncode == 0) == passes


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
