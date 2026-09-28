// Retrying cannot change these answers: auth, permission, missing or malformed ids, and rate limits.
const NON_RETRYABLE_STATUSES = new Set([401, 403, 404, 422, 429])

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
    if (error instanceof Error && 'status' in error) {
        const status = (error as { status: number }).status
        if (NON_RETRYABLE_STATUSES.has(status)) {
            return false
        }
    }
    return failureCount < 2
}
