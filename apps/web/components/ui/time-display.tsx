"use client"

import { useSyncExternalStore } from "react"
import { formatDistance } from "date-fns"

const SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
const LONG_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

const nowListeners = new Set<() => void>()
const MINUTE = 60_000
let nowSnapshot = getCurrentMinuteTimestamp()
let nowTimer: ReturnType<typeof setInterval> | null = null

function getCurrentMinuteTimestamp() {
    return Math.floor(Date.now() / MINUTE) * MINUTE
}

function subscribeNow(listener: () => void) {
    nowListeners.add(listener)
    if (nowTimer === null) {
        nowTimer = setInterval(() => {
            nowSnapshot = getCurrentMinuteTimestamp()
            for (const notify of nowListeners) notify()
        }, MINUTE)
    }

    return () => {
        nowListeners.delete(listener)
        if (nowListeners.size === 0 && nowTimer !== null) {
            clearInterval(nowTimer)
            nowTimer = null
        }
    }
}

function getNowSnapshot() {
    const currentMinute = getCurrentMinuteTimestamp()
    if (currentMinute !== nowSnapshot) {
        nowSnapshot = currentMinute
    }
    return nowSnapshot
}

function getServerNowSnapshot() {
    return null
}

export function formatUtcDateLabel(
    value: string | null | undefined,
    options: { month?: "short" | "long"; fallback?: string } = {},
) {
    if (!value) return options.fallback ?? "-"

    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
    if (!match) return value

    const year = match[1]
    const monthIndex = Number(match[2]) - 1
    const day = Number(match[3])
    const monthLabel = (options.month === "long" ? LONG_MONTHS : SHORT_MONTHS)[monthIndex]

    if (!monthLabel || !Number.isInteger(day) || day < 1 || day > 31) return value

    return `${monthLabel} ${day}, ${year}`
}

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
    const now = useSyncExternalStore(subscribeNow, getNowSnapshot, getServerNowSnapshot)

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
