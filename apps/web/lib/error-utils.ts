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

export function isPermissionError(error: unknown): boolean {
    return error instanceof ApiError && error.status === 403
}
