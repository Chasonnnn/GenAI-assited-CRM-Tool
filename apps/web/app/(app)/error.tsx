"use client"

import { ErrorState } from "@/components/error-state"

export default function AppError({
    error,
    retry,
}: {
    error: Error & { digest?: string }
    retry: () => void
}) {
    return (
        <ErrorState
            error={error}
            reset={retry}
            secondaryHref="/dashboard"
            secondaryLabel="Go to Dashboard"
        />
    )
}
