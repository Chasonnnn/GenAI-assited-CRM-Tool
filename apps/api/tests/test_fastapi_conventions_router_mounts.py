"""Ensure router-level prefix/tags live on APIRouter declarations."""

from __future__ import annotations

import ast
from pathlib import Path


def test_main_include_router_does_not_pass_prefix_or_tags() -> None:
    main_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    tree = ast.parse(main_path.read_text(encoding="utf-8"))

    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "include_router"):
            continue
        kw_names = {kw.arg for kw in node.keywords}
        bad = sorted(name for name in ("prefix", "tags") if name in kw_names)
        if bad:
            offenders.append(f"{main_path}:{node.lineno}:{','.join(bad)}")

    assert not offenders, "Found include_router prefix/tags in main.py:\n" + "\n".join(offenders)
