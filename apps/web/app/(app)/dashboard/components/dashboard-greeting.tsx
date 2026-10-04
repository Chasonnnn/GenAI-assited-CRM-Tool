"use client"

import { useState } from "react"

import { useMountEffect } from "@/lib/hooks/use-mount-effect"

const WELCOME_BACK_WINDOW_MS = 2 * 60 * 60 * 1000

function getLastVisitKey(userId: string): string {
    return `dashboard-last-visit-${userId}`
}

// Storage can be unavailable (private mode, blocked site data); the greeting then
// falls back to the time of day.
function readLastVisit(userId: string): number | null {
    try {
        const raw = window.localStorage.getItem(getLastVisitKey(userId))
        const value = raw === null ? Number.NaN : Number(raw)
        return Number.isFinite(value) ? value : null
    } catch {
        return null
    }
}

function writeLastVisit(userId: string) {
    try {
        window.localStorage.setItem(getLastVisitKey(userId), String(Date.now()))
    } catch {
        // See readLastVisit.
    }
}

export function getFirstName(displayName: string | undefined): string | null {
    const [firstName] = (displayName ?? "").trim().split(/\s+/)
    return firstName || null
}

export function getGreeting(now: Date, lastVisitAt: number | null): string {
    const sinceLastVisit = lastVisitAt === null ? null : now.getTime() - lastVisitAt
    if (sinceLastVisit !== null && sinceLastVisit >= 0 && sinceLastVisit < WELCOME_BACK_WINDOW_MS) {
        return "Welcome back"
    }
    const hour = now.getHours()
    if (hour >= 5 && hour < 12) return "Good morning"
    if (hour >= 12 && hour < 17) return "Good afternoon"
    return "Good evening"
}

type DashboardGreetingProps = {
    /** Parents key this component by user id so a user switch remounts it. */
    userId: string
    displayName: string | undefined
}

export function DashboardGreeting({ userId, displayName }: DashboardGreetingProps) {
    // Read once per mount so the greeting stays stable while the page re-renders.
    const [greeting] = useState(() => getGreeting(new Date(), readLastVisit(userId)))

    useMountEffect(() => {
        writeLastVisit(userId)
        return () => writeLastVisit(userId)
    })

    const firstName = getFirstName(displayName)
    return <>{firstName ? `${greeting}, ${firstName}` : greeting}</>
}
