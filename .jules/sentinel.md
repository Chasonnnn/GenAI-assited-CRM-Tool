## 2025-03-09 - Fixed nanoid high vulnerability in frontend
**Vulnerability:** nanoid custom generators can loop indefinitely when size is zero.
**Learning:** Found deep nested dependencies needing an override in `pnpm-workspace.yaml`.
**Prevention:** Pin dependencies correctly and run `pnpm install --frozen-lockfile=false` to regenerate `pnpm-lock.yaml`.
