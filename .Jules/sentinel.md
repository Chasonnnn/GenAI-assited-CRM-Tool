## $(date +%Y-%m-%d) - Fix Quadratic ReDoS in Tiptap Markdown parsing
**Vulnerability:** Quadratic ReDoS in block and inline Markdown attribute parsing in Tiptap Core.
**Learning:** Found by running `pnpm audit --audit-level=high`. Pinned `@tiptap/core` to version `3.30.5` in `pnpm-workspace.yaml` overrides. Added tests to verify the override and lockfile resolution.
**Prevention:** Regularly run `pnpm audit` and keep dependencies updated. Use package manager overrides to enforce secure versions of transitive dependencies.
