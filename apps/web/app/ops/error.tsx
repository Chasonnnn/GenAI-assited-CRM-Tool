"use client"

import { ErrorState } from "@/components/error-state"

/**
 * Ops group error boundary.
 *
 * Catches errors within the /ops admin routes.
 */
export default function OpsError({
    error,
    retry,
}: {
    error: Error & { digest?: string }
    retry: () => void
}) {
    return <ErrorState error={error} reset={retry} secondaryHref="/ops" secondaryLabel="Go to Ops" />
}
