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


def _normalize_entries(report: Any) -> list[dict[str, Any]]:
    if isinstance(report, list):
        return report
    if isinstance(report, dict):
        dependencies = report.get("dependencies")
        if isinstance(dependencies, list):
            return dependencies
        vulnerabilities = report.get("vulnerabilities") or report.get("vulns")
        if isinstance(vulnerabilities, list):
            by_package: dict[tuple[str, str], dict[str, Any]] = {}
            for item in vulnerabilities:
                if not isinstance(item, dict):
                    continue
                package = item.get("package") or item.get("dependency") or {}
                name = item.get("name") or (
                    package.get("name") if isinstance(package, dict) else None
                )
                version = item.get("version") or (
                    package.get("version") if isinstance(package, dict) else None
                )
                vuln = item.get("vuln") or item.get("vulnerability") or {}
                vuln_id = item.get("id") or (vuln.get("id") if isinstance(vuln, dict) else None)
                fix_versions = item.get("fix_versions") or (
                    vuln.get("fix_versions") if isinstance(vuln, dict) else []
                )
                if not name or not vuln_id:
                    continue
                key = (str(name), str(version or "unknown"))
                entry = by_package.setdefault(
                    key, {"name": str(name), "version": str(version or "unknown"), "vulns": []}
                )
                entry["vulns"].append(
                    {"id": str(vuln_id), "fix_versions": list(fix_versions or [])}
                )
            return list(by_package.values())
    return []


def _parse_report(output: str) -> list[dict[str, Any]]:
    if not output.strip():
        return []
    parsed = json.loads(output)
    return _normalize_entries(parsed)


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

    if not report and result.stdout.strip():
        print(
            "pip-audit output was not in a supported JSON shape; failing with original output.",
            file=sys.stderr,
        )
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
