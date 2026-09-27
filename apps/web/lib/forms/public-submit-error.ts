import { ApiError } from "@/lib/api"

const FORM_CHANGED_MESSAGE = "This form changed. Reload the page and try again."

// Allowlist: other 409 details, such as the pending-duplicate one, reveal whether a person applied.
const FORM_CHANGED_CONFLICT_DETAILS = new Set([
    FORM_CHANGED_MESSAGE,
    "Published version is no longer current",
])

/**
 * Returns the reload message for a public submit 409 caused by a stale form version or a remapped
 * phone field. Returns null for every other error so pages keep their generic message.
 */
export function getPublicSubmitConflictMessage(error: unknown): string | null {
    if (!(error instanceof ApiError) || error.status !== 409) return null
    return FORM_CHANGED_CONFLICT_DETAILS.has(error.message) ? FORM_CHANGED_MESSAGE : null
}
