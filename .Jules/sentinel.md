## 2024-05-23 - Raw JSON in Cookies
**Vulnerability:** OAuth state cookies stored raw JSON payloads, including double quotes which are restricted characters in cookie values (RFC 6265).
**Learning:** Raw JSON in cookies can lead to dropped cookies by strict proxies/browsers or parsing ambiguities, potentially causing authentication failures (DoS).
**Prevention:** Always Base64 encode complex data structures (like JSON) before storing them in cookies to ensure transport safety and compliance. When fixing, implement a fallback to handle legacy unencoded cookies during deployment.
