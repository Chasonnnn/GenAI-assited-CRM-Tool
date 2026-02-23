## 2025-02-17 - Fail Securely in Webhook Verification
**Vulnerability:** Resend webhook signature verification silently fell back to using the raw secret bytes if base64 decoding failed (even for `whsec_` prefixed secrets).
**Learning:** Lenient decoding (or silent failure) of security configuration can mask errors and weaken security guarantees. Always validate assumptions about key formats explicitly.
**Prevention:** When parsing cryptographic keys or secrets, ensure strict validation. If the format is invalid, fail immediately and log an error rather than attempting to "make it work" with a fallback.
