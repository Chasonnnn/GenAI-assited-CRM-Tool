"use client"

import { formatDistance } from "date-fns"

import { formatUtcDateLabel } from "@/components/ui/time-display-utils"
import { useCurrentMinuteTimestamp } from "@/components/ui/use-current-minute-timestamp"

export function UtcDate({
    value,
    month = "short",
    fallback = "-",
}: {
    value: string | null | undefined
    month?: "short" | "long"
    fallback?: string
}) {
    return <span>{formatUtcDateLabel(value, { month, fallback })}</span>
}

export function RelativeTime({
    value,
    fallback = "-",
}: {
    value: string | null | undefined
    fallback?: string
}) {
    const now = useCurrentMinuteTimestamp()

    if (!value) return <span>{fallback}</span>
    if (now === null) {
        return <span suppressHydrationWarning>{formatUtcDateLabel(value)}</span>
    }

    return (
        <span suppressHydrationWarning>
            {formatDistance(new Date(value), now, { addSuffix: true })}
        </span>
    )
}
