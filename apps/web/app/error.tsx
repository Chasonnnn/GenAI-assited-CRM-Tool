"use client"

import { ErrorState } from "@/components/error-state"

/**
 * Global error boundary.
 *
 * Catches errors in the root layout and provides a retry mechanism.
 */
export default function GlobalError({
    error,
    reset,
}: {
    error: Error & { digest?: string }
    reset: () => void
}) {
    return (
        <div className="min-h-screen bg-background">
            <ErrorState error={error} reset={reset} secondaryHref="/dashboard" />
        </div>
    )
}
