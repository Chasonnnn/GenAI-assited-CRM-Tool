#!/usr/bin/env python3
"""Run pip-audit and fail only when fixes exist."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any


def _run_pip_audit(args: list[str]) -> subprocess.CompletedProcess[str]:
    command = ["pip-audit", "--format", "json", *args]
    return subprocess.run(command, capture_output=True, text=True)


def _parse_report(output: str) -> list[dict[str, Any]]:
    if not output.strip():
        return []
    return json.loads(output)


def main() -> int:
    extra_args = [arg for arg in sys.argv[1:] if arg not in ("--format", "json")]
    result = _run_pip_audit(extra_args)

    if result.returncode not in (0, 1):
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.returncode

    try:
        report = _parse_report(result.stdout)
    except Exception:
        print("pip-audit output was not valid JSON; failing with original output.", file=sys.stderr)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.returncode

    blocking: list[tuple[str, str, str, list[str]]] = []
    unpatched: list[tuple[str, str, str]] = []

    for entry in report:
        name = str(entry.get("name", "unknown"))
        version = str(entry.get("version", "unknown"))
        for vuln in entry.get("vulns", []):
            vuln_id = str(vuln.get("id", "unknown"))
            fix_versions = vuln.get("fix_versions") or []
            if fix_versions:
                blocking.append((name, version, vuln_id, list(fix_versions)))
            else:
                unpatched.append((name, version, vuln_id))

    if blocking:
        print("Blocking vulnerabilities with fixes available:")
        for name, version, vuln_id, fix_versions in blocking:
            print(f"- {name} {version} {vuln_id} (fix: {', '.join(fix_versions)})")
        return 1

    if unpatched:
        print("Vulnerabilities detected, but no fixes available yet:")
        for name, version, vuln_id in unpatched:
            print(f"- {name} {version} {vuln_id} (no fix listed)")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
