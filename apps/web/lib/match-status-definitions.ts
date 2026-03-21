import type { MatchStatus } from "@/lib/api/matches"

export interface MatchStatusDefinition {
    value: MatchStatus
    label: string
    order: number
    badgeClassName: string
    allowedTransitions: MatchStatus[]
}

export const MATCH_STATUS_DEFINITIONS: MatchStatusDefinition[] = [
    {
        value: "proposed",
        label: "Proposed",
        order: 1,
        badgeClassName: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
        allowedTransitions: ["reviewing", "accepted", "rejected", "cancelled"],
    },
    {
        value: "reviewing",
        label: "Reviewing",
        order: 2,
        badgeClassName: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
        allowedTransitions: ["accepted", "rejected", "cancelled"],
    },
    {
        value: "accepted",
        label: "Accepted",
        order: 3,
        badgeClassName: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
        allowedTransitions: ["cancel_pending"],
    },
    {
        value: "cancel_pending",
        label: "Cancel Pending",
        order: 4,
        badgeClassName: "bg-amber-50 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200",
        allowedTransitions: ["accepted", "cancelled"],
    },
    {
        value: "rejected",
        label: "Rejected",
        order: 5,
        badgeClassName: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
        allowedTransitions: [],
    },
    {
        value: "cancelled",
        label: "Cancelled",
        order: 6,
        badgeClassName: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
        allowedTransitions: [],
    },
]

export const MATCH_STATUS_BY_VALUE = Object.fromEntries(
    MATCH_STATUS_DEFINITIONS.map((definition) => [definition.value, definition]),
) as Record<MatchStatus, MatchStatusDefinition>

export function isMatchStatus(value: string | null | undefined): value is MatchStatus {
    return typeof value === "string" && value in MATCH_STATUS_BY_VALUE
}

export function getMatchStatusDefinition(value: string | null | undefined): MatchStatusDefinition {
    if (isMatchStatus(value)) {
        return MATCH_STATUS_BY_VALUE[value]
    }
    return MATCH_STATUS_BY_VALUE.proposed
}

export function getMatchStatusLabel(value: string | null | undefined): string {
    return getMatchStatusDefinition(value).label
}

export function getMatchStatusBadgeClassName(value: string | null | undefined): string {
    return getMatchStatusDefinition(value).badgeClassName
}

export const MATCH_STATUS_OPTIONS = MATCH_STATUS_DEFINITIONS.map((definition) => definition.value)
