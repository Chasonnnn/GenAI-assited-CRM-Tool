import { buildServerApiHeaders } from "@/lib/server-api-headers"

export async function postUnsubscribeToApi(token: string, requestHeaders: Headers) {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
    const safeToken = encodeURIComponent(token || "")
    if (!safeToken) return

    const response = await fetch(`${apiBase}/email/unsubscribe/${safeToken}`, {
        method: "POST",
        // No cookies required; token is the auth.
        cache: "no-store",
        headers: buildServerApiHeaders(requestHeaders),
    })

    if (!response.ok) {
        throw new Error(`Unsubscribe API request failed with status ${response.status}`)
    }
}
