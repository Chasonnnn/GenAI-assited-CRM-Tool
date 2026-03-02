"""Disallow ellipsis-required markers in FastAPI/Pydantic declarations."""

from __future__ import annotations

import ast
from pathlib import Path

ELLIPSIS_CALLS = {"Field", "Query", "Path", "Header", "Body", "Form", "File", "Cookie"}


def _iter_target_files() -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    files: list[Path] = []
    files.extend(sorted((root / "app" / "routers").rglob("*.py")))
    files.extend(sorted((root / "app" / "schemas").rglob("*.py")))
    files.extend(sorted((root / "app" / "services").rglob("*.py")))
    return files


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def test_no_ellipsis_required_markers() -> None:
    offenders: list[str] = []

    for path in _iter_target_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = _call_name(node)
            if call_name not in ELLIPSIS_CALLS:
                continue
            if not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and first.value is Ellipsis:
                offenders.append(f"{path}:{node.lineno}:{call_name}(...) is not allowed")

    assert not offenders, "Found ellipsis-required markers:\n" + "\n".join(offenders)
