"use client"

import { ErrorState } from "@/components/error-state"

/**
 * Ops group error boundary.
 *
 * Catches errors within the /ops admin routes.
 */
export default function OpsError({
    error,
    reset,
}: {
    error: Error & { digest?: string }
    reset: () => void
}) {
    return <ErrorState error={error} reset={reset} secondaryHref="/ops" secondaryLabel="Go to Ops" />
}
