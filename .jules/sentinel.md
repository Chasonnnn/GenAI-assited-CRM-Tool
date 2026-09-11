## 2024-05-25 - Fix Next.js Remote Code Execution Vulnerability
**Vulnerability:** Unauthenticated Remote Code Execution in next < 16.3.3.
**Learning:** The frontend dependencies must be actively audited and patched, as direct dependencies like Next.js can introduce critical RCEs.
**Prevention:** Continue enforcing dependency security checks and pinning vulnerable packages via overrides.
