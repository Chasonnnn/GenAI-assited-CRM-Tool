import { buildServerApiHeaders } from "@/lib/server-api-headers"

export async function postUnsubscribeToApi(token: string, requestHeaders: Headers) {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
    const safeToken = encodeURIComponent(token || "")
    if (!safeToken) return

    // Best-effort: the API endpoint is the source of truth for recording suppressions.
    // We intentionally show the same success message regardless of token validity.
    try {
        await fetch(`${apiBase}/email/unsubscribe/${safeToken}`, {
            method: "POST",
            // No cookies required; token is the auth.
            cache: "no-store",
            headers: buildServerApiHeaders(requestHeaders),
        })
    } catch {
        // Ignore failures to avoid leaking availability details to recipients.
    }
}
