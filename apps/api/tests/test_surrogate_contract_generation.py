"""Generated surrogate contract guardrail."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_generator_module(script_path: Path):
    spec = importlib.util.spec_from_file_location("gen_surrogate_contracts", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load contract generator: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_surrogate_generated_types_are_up_to_date() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "gen_surrogate_contracts.py"
    output_path = repo_root / "apps" / "web" / "lib" / "types" / "surrogate.generated.ts"

    generator = _load_generator_module(script_path)
    rendered = generator.render_typescript()  # type: ignore[attr-defined]

    assert output_path.exists(), (
        f"Missing generated contract file: {output_path}. "
        "Run: python3 scripts/gen_surrogate_contracts.py"
    )
    assert output_path.read_text(encoding="utf-8") == rendered, (
        "surrogate.generated.ts is out of date. "
        "Run: python3 scripts/gen_surrogate_contracts.py"
    )
