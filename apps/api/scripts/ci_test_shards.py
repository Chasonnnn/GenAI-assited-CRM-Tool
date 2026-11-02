"""Split parallel-safe backend test files into CI shards of similar duration.

``select`` prints the files for one shard. ``record`` rewrites the duration file
from the JUnit reports that the CI shards upload.
"""

from __future__ import annotations

import argparse
import json
import statistics
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

DURATIONS = Path(__file__).resolve().parents[1] / "tests" / "ci_test_durations.json"

# These files assert on database-wide state, so they run in the serial group.
SERIAL_FILES = {"test_email_delivery_outbox.py", "test_ops_cli_integration.py"}

# CI shard wall time fits (JUnit seconds + 1.5s per file) / 4 workers. JUnit times
# omit the per-file cost, so a shard of many small files otherwise runs longest.
FILE_OVERHEAD_SECONDS = 1.5


def parallel_safe_files(tests_dir: Path) -> list[str]:
    return sorted(
        path.as_posix()
        for path in tests_dir.rglob("test_*.py")
        if not path.name.startswith("test_migration_") and path.name not in SERIAL_FILES
    )


def assign_shards(files: list[str], durations: dict[str, float], count: int) -> list[list[str]]:
    """Give each file, longest first, to the shard with the least total cost."""
    # A file without a recorded duration counts as a typical file.
    default = statistics.median(durations.values()) if durations else 1.0

    def cost(name: str) -> float:
        return durations.get(name, default) + FILE_OVERHEAD_SECONDS

    shards: list[list[str]] = [[] for _ in range(count)]
    loads = [0.0] * count
    for file in sorted(files, key=lambda name: (-cost(name), name)):
        index = loads.index(min(loads))
        shards[index].append(file)
        loads[index] += cost(file)
    return [sorted(shard) for shard in shards]


def junit_file_durations(reports: list[Path]) -> dict[str, float]:
    totals: Counter[str] = Counter()
    for report in reports:
        for case in ET.parse(report).iter("testcase"):
            parts = case.get("classname", "").split(".")
            module = next((i for i, part in enumerate(parts) if part.startswith("test_")), None)
            if module is not None:
                totals["/".join(parts[: module + 1]) + ".py"] += float(case.get("time") or 0)
    return {file: round(seconds, 1) for file, seconds in sorted(totals.items())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    select = commands.add_parser("select")
    select.add_argument("shard", type=int, help="1-based shard number")
    select.add_argument("count", type=int)
    record = commands.add_parser("record")
    record.add_argument("reports", type=Path, nargs="+")
    args = parser.parse_args()

    if args.command == "record":
        DURATIONS.write_text(json.dumps(junit_file_durations(args.reports), indent=1) + "\n")
        return
    if not 1 <= args.shard <= args.count:
        parser.error("shard must be between 1 and count")
    durations = json.loads(DURATIONS.read_text()) if DURATIONS.exists() else {}
    shards = assign_shards(parallel_safe_files(Path("tests")), durations, args.count)
    print("\n".join(shards[args.shard - 1]))


if __name__ == "__main__":
    main()
