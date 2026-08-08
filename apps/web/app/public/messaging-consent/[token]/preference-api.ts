import { buildServerApiHeaders } from "@/lib/server-api-headers"

export type MessagingConsentStatus = "unknown" | "opted_in" | "opted_out" | "reopt_pending"

export interface MessagingPreference {
    legal_brand: string
    masked_phone: string
    support_contact: string
    expected_frequency: string | null
    sms_terms_url: string
    privacy_policy_url: string
    purposes: Partial<Record<"operational" | "promotional", {
        disclosure: string
        status: MessagingConsentStatus
    }>>
    global_suppression_active: boolean
    expires_at: string
}

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

export async function getMessagingPreference(
    token: string,
    requestHeaders: Headers,
): Promise<MessagingPreference | null> {
    const response = await fetch(
        `${apiBase}/public/messaging-consent/${encodeURIComponent(token)}`,
        {
            cache: "no-store",
            headers: buildServerApiHeaders(requestHeaders),
        },
    )
    if (response.status === 404 || response.status === 409) return null
    if (!response.ok) throw new Error(`Preference API request failed with status ${response.status}`)
    return response.json() as Promise<MessagingPreference>
}

export async function updateMessagingPreference(
    token: string,
    requestHeaders: Headers,
    input: {
        action: "opt_in" | "opt_out"
        purposes: Array<"operational" | "promotional">
        submission_id: string
    },
): Promise<MessagingPreference> {
    const response = await fetch(
        `${apiBase}/public/messaging-consent/${encodeURIComponent(token)}`,
        {
            method: "POST",
            cache: "no-store",
            headers: {
                ...buildServerApiHeaders(requestHeaders),
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ ...input, affirmative: true }),
        },
    )
    if (!response.ok) {
        const payload = await response.json().catch(() => null) as { detail?: string } | null
        throw new Error(payload?.detail || `Preference update failed with status ${response.status}`)
    }
    return response.json() as Promise<MessagingPreference>
}
