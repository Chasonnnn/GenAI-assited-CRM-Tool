export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
    if (error instanceof Error && 'status' in error) {
        const status = (error as { status: number }).status
        if (status === 401 || status === 403 || status === 429) {
            return false
        }
    }
    return failureCount < 2
}
