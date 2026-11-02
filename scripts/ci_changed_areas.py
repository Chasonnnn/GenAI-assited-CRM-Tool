#!/usr/bin/env python3
"""Decide which CI areas a pull request must run.

Reads changed paths, one per line, on stdin. Prints ``backend=<bool>`` and
``frontend=<bool>`` lines in the GITHUB_OUTPUT format.

An area is skipped only when no changed path can affect it. Any doubt runs the area.
"""

from __future__ import annotations

import sys
from fnmatch import fnmatchcase

# Changes here can affect every job.
SHARED = (
    ".github/**",
    ".dockerignore",
    "Makefile",
    "mise.toml",
    "mise.lock",
    "scripts/**",
)

# Web files that backend tests or services read.
BACKEND_READS_FROM_WEB = (
    "apps/web/Dockerfile",
    "apps/web/package.json",
    "apps/web/pnpm-lock.yaml",
    "apps/web/pnpm-workspace.yaml",
    "apps/web/next.config.js",
    "apps/web/lib/constants/stages.generated.ts",
    "apps/web/lib/types/surrogate.generated.ts",
    "apps/web/public/**",
    "apps/web/tests/public-field-validation.test.ts",
)

# Files outside apps/web that frontend tests read.
FRONTEND_READS_OUTSIDE_WEB = (
    "apps/api/app/core/stage_definitions.py",
    "apps/api/tests/fixtures/**",
)


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(
        fnmatchcase(path, pattern) or (pattern.endswith("/**") and path.startswith(pattern[:-2]))
        for pattern in patterns
    )


def changed_areas(paths: list[str]) -> dict[str, bool]:
    paths = [path.strip() for path in paths if path.strip()]
    if not paths:
        return {"backend": True, "frontend": True}
    backend = frontend = False
    for path in paths:
        if _matches(path, SHARED):
            return {"backend": True, "frontend": True}
        in_web = path.startswith("apps/web/")
        if not in_web or _matches(path, BACKEND_READS_FROM_WEB):
            backend = True
        if in_web or _matches(path, FRONTEND_READS_OUTSIDE_WEB):
            frontend = True
    return {"backend": backend, "frontend": frontend}


def main() -> None:
    for area, selected in changed_areas(sys.stdin.read().splitlines()).items():
        print(f"{area}={str(selected).lower()}")


if __name__ == "__main__":
    main()
