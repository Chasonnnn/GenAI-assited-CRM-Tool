## 2024-08-15 - nanoid vulnerability

**Vulnerability:** `nanoid` prior to 3.3.18 contains a vulnerability where custom generators can loop indefinitely when size is zero, leading to potential denial of service.
**Learning:** Fixing a vulnerability in a deeply nested dependency across multiple workspaces often requires pinning the version in `pnpm-workspace.yaml` under `overrides` instead of updating individual `package.json` files.
**Prevention:** Regularly run `pnpm audit --audit-level=high` (or `bash scripts/pnpm_audit_guard.sh`) and review `pnpm-workspace.yaml` for necessary global overrides to ensure secure versions propagate down the dependency tree.
