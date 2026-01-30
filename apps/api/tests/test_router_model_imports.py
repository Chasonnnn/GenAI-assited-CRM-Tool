"""Boundary check: routers should not import ORM models directly."""

from __future__ import annotations

from pathlib import Path


def test_routers_do_not_import_models_directly() -> None:
    routers_dir = Path(__file__).resolve().parents[1] / "app" / "routers"
    offenders: list[str] = []

    for path in routers_dir.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if "app.db.models" in content:
            offenders.append(str(path.relative_to(routers_dir)))

    assert not offenders, f"Routers should not import models directly: {offenders}"
