# Sentinel's Journal

## 2025-02-19 - Zoom Webhook Replay Vulnerability
**Vulnerability:** Zoom webhooks were vulnerable to replay attacks because the timestamp in the request header was not verified against the current server time. Additionally, the concatenation of timestamp and body (`v0:timestamp:body`) allowed a potential collision attack if the timestamp contained a colon (`:`).
**Learning:** Checking HMAC signature alone proves *authenticity* (who sent it) but not *freshness* (when it was sent). Protocol-specific canonicalization (like Zoom's colon separation) can introduce ambiguity if inputs aren't strictly validated (e.g. enforcing numeric timestamps).
**Prevention:** Always validate timestamps are within a small window (e.g., 5 minutes) to prevent replays. Validate input formats (e.g., ensure timestamp is numeric) before using them in signature construction to prevent canonicalization collisions.
