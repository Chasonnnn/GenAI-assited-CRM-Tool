#!/usr/bin/env bash
# Fail when two ADR files in docs/adr share a numeric prefix.
set -euo pipefail

cd "$(dirname "$0")/.."

duplicates="$(
    for path in docs/adr/[0-9]*.md; do
        name="${path##*/}"
        printf '%s %s\n' "${name%%-*}" "$name"
    done | awk '{ count[$1]++; names[$1] = names[$1] " " $2 } END { for (p in count) if (count[p] > 1) print p ":" names[p] }'
)"

if [[ -n "$duplicates" ]]; then
    printf 'ADR numbers used more than once:\n%s\n' "$duplicates" >&2
    exit 1
fi
