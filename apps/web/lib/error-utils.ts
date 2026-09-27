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
