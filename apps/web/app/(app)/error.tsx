"use client"

import { ErrorState } from "@/components/error-state"

/**
 * App group error boundary.
 *
 * Catches errors within the (app) authenticated routes.
 */
export default function AppError({
    error,
    reset,
}: {
    error: Error & { digest?: string }
    reset: () => void
}) {
    return <ErrorState error={error} reset={reset} secondaryHref="/dashboard" />
}
