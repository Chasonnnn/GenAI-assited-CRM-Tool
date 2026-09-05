## 2026-09-05 - Bumped browserslist to fix CVEs
**Vulnerability:** browserslist <=4.28.6 had known vulnerabilities (CVE-2026-GHSA-c83g-rgw3-j3cx, GHSA-73wf-gq98-2v4g).
**Learning:** The frontend build tools depend on packages that require manual overrides when vulnerable sub-dependencies are identified.
**Prevention:** Maintain strict dependency constraints via overrides in pnpm-workspace.yaml.
