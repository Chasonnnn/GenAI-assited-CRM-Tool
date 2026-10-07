#!/usr/bin/env bash
# Fail when two ADR files in docs/adr share a numeric prefix.
set -euo pipefail

cd "$(dirname "$0")/.."

# Duplicates that predate this check; remove an entry after renumbering that ADR.
# Each grandfathered group counts as one owner of its number.
grandfathered='
0006-dated-medical-records.md
0006-email-templates-use-the-react-email-editor.md
0006-notification-action-items-are-computed-on-read.md
0006-workflow-editor-is-a-linear-canvas-page.md
0008-case-manager-created-surrogate-access.md
0008-notification-email-is-opt-in-per-type.md
'

duplicates="$(
    for path in docs/adr/[0-9]*.md; do
        name="${path##*/}"
        if grep -qxF "$name" <<<"$grandfathered"; then
            printf '%s grandfathered\n' "${name%%-*}"
        else
            printf '%s %s\n' "${name%%-*}" "$name"
        fi
    done | sort -u | awk '{ count[$1]++; names[$1] = names[$1] " " $2 } END { for (p in count) if (count[p] > 1) print p ":" names[p] }'
)"

if [[ -n "$duplicates" ]]; then
    printf 'ADR numbers used more than once:\n%s\n' "$duplicates" >&2
    exit 1
fi
