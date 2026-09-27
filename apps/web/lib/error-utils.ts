import { ApiError } from "@/lib/api"

export function getErrorMessage(error: unknown, fallback: string): string {
    if (error instanceof ApiError && error.message) {
        return error.message
    }
    if (error instanceof Error && error.message) {
        return error.message
    }
    return fallback
}

export function getErrorStatus(error: unknown): number | null {
    return error instanceof ApiError ? error.status : null
}

export function isPermissionError(error: unknown): boolean {
    return getErrorStatus(error) === 403
}

/**
 * 404, or with `includeInvalidId` also 422: FastAPI answers a malformed path id
 * (for example a non-UUID record id) with 422, which a record route should treat as not found.
 */
export function isNotFoundError(
    error: unknown,
    { includeInvalidId = false }: { includeInvalidId?: boolean } = {},
): boolean {
    const status = getErrorStatus(error)
    return status === 404 || (includeInvalidId && status === 422)
}

/** A 403 that is not about the viewer's role or permissions. */
export type NonRoleForbiddenReason =
    | "ai_disabled"
    | "ai_consent"
    | "org_deleting"
    | "session_domain"
    | "mfa_required"
    | "membership"

// Exact 403 `detail` strings raised in apps/api (core/deps.py, routers/ai_*, interviews,
// surrogates_import). Keep in sync when those messages change; any other 403 is a role
// or permission denial. The detail text itself is never rendered.
const NON_ROLE_FORBIDDEN_DETAILS: ReadonlyMap<string, NonRoleForbiddenReason> = new Map([
    ["AI is not enabled", "ai_disabled"],
    ["AI is not enabled for this organization", "ai_disabled"],
    ["AI features are not enabled for this organization", "ai_disabled"],
    ["AI consent not accepted", "ai_consent"],
    [
        "AI consent not accepted. An admin must accept the data processing consent before using AI.",
        "ai_consent",
    ],
    ["AI consent has not been accepted for this organization", "ai_consent"],
    ["Organization is scheduled for deletion", "org_deleting"],
    ["Session invalid for this domain", "session_domain"],
    ["MFA verification required", "mfa_required"],
    ["No organization membership", "membership"],
    ["Membership inactive", "membership"],
])

/** Returns the reason for a known non-role 403, or null for role denials and other errors. */
export function getNonRoleForbiddenReason(error: unknown): NonRoleForbiddenReason | null {
    if (!(error instanceof ApiError) || error.status !== 403) return null
    return NON_ROLE_FORBIDDEN_DETAILS.get(error.message.trim()) ?? null
}

export type QueryErrorKind = "forbidden" | "not_found" | "error"

/** Classifies a failed query so pages branch 403 → denied, 404 → not found, else → load error. */
export function getQueryErrorKind(
    error: unknown,
    options: { includeInvalidId?: boolean } = {},
): QueryErrorKind {
    if (isPermissionError(error)) return "forbidden"
    if (isNotFoundError(error, options)) return "not_found"
    return "error"
}
