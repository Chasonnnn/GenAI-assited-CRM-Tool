from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text()


def test_root_dockerignore_has_common_exclusions() -> None:
    content = _read(".dockerignore")
    for pattern in [
        ".git",
        "**/node_modules",
        "**/.env",
        "**/.env.*",
        "**/.next",
        "**/dist",
        "**/coverage",
    ]:
        assert pattern in content, f"Missing {pattern} in root .dockerignore"


def test_api_dockerignore_exists_and_excludes_local_artifacts() -> None:
    path = ROOT / "apps/api/.dockerignore"
    assert path.exists(), "apps/api/.dockerignore is missing"
    content = path.read_text()
    for pattern in [
        ".env",
        ".env.*",
        ".venv",
        "__pycache__",
        "tests",
    ]:
        assert pattern in content, f"Missing {pattern} in apps/api/.dockerignore"


def test_api_dockerfile_pins_python_patch_version() -> None:
    content = _read("apps/api/Dockerfile")
    expected = "FROM python:3.11.14-slim-bookworm"
    assert content.count(expected) == 2, "Python base image must be pinned in both stages"


def test_web_dockerfile_pins_node_and_optimizes_cache() -> None:
    content = _read("apps/web/Dockerfile")
    expected = "FROM node:20.20.0-bullseye-slim"
    assert f"{expected} AS builder" in content
    assert f"{expected} AS runner" in content

    idx_pkg = content.find("COPY apps/web/package.json")
    idx_lock = content.find("COPY apps/web/package.json apps/web/pnpm-lock.yaml")
    idx_install = content.find("pnpm install")
    idx_copy_web = content.find("COPY apps/web ./apps/web")
    idx_copy_api = content.find("COPY apps/api ./apps/api")

    assert idx_pkg != -1 and idx_lock != -1 and idx_install != -1
    assert idx_pkg < idx_install and idx_lock < idx_install
    assert idx_copy_web > idx_install
    assert idx_copy_api > idx_install


def test_web_dockerfile_runs_non_root_and_has_healthcheck() -> None:
    content = _read("apps/web/Dockerfile")
    runner_idx = content.find("AS runner")
    assert runner_idx != -1, "Runner stage missing"

    user_idx = content.find("USER node", runner_idx)
    assert user_idx != -1, "Runner stage must switch to non-root user"

    health_idx = content.find("HEALTHCHECK", runner_idx)
    assert health_idx != -1, "Runner stage missing HEALTHCHECK"
    assert "/health" in content[health_idx:], "HEALTHCHECK should target /health"


def test_compose_uses_postgres_18_1_with_new_pgdata() -> None:
    content = _read("docker-compose.yml")
    assert "image: postgres:18.1" in content
    assert "- pgdata:/var/lib/postgresql" in content
