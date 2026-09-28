import type { MatchStatus } from "@/lib/api/matches"

export interface MatchStatusDefinition {
    value: MatchStatus
    label: string
    order: number
    badgeClassName: string
    allowedTransitions: MatchStatus[]
    systemTransitions: MatchStatus[]
}

export const MATCH_STATUS_DEFINITIONS: MatchStatusDefinition[] = [
    {
        value: "under_review",
        label: "Under Review",
        order: 2,
        badgeClassName: "bg-amber-700 text-white",
        allowedTransitions: ["accepted", "declined"],
        systemTransitions: [],
    },
    {
        value: "accepted",
        label: "Accepted",
        order: 3,
        badgeClassName: "bg-green-700 text-white",
        allowedTransitions: ["cancellation_pending"],
        systemTransitions: ["completed"],
    },
    {
        value: "cancellation_pending",
        label: "Cancellation Pending",
        order: 4,
        badgeClassName: "bg-orange-700 text-white",
        allowedTransitions: ["accepted", "cancelled"],
        systemTransitions: [],
    },
    {
        value: "declined",
        label: "Declined",
        order: 5,
        badgeClassName: "bg-red-700 text-white",
        allowedTransitions: [],
        systemTransitions: [],
    },
    {
        value: "cancelled",
        label: "Cancelled",
        order: 6,
        badgeClassName: "bg-gray-600 text-white",
        allowedTransitions: [],
        systemTransitions: [],
    },
    {
        value: "completed",
        label: "Completed",
        order: 7,
        badgeClassName: "bg-teal-700 text-white",
        allowedTransitions: [],
        systemTransitions: ["accepted"],
    },
]

const MATCH_STATUS_BY_VALUE = Object.fromEntries(
    MATCH_STATUS_DEFINITIONS.map((definition) => [definition.value, definition]),
) as Record<MatchStatus, MatchStatusDefinition>

export function isMatchStatus(value: string | null | undefined): value is MatchStatus {
    return typeof value === "string" && Object.hasOwn(MATCH_STATUS_BY_VALUE, value)
}

export function getMatchStatusLabel(value: string | null | undefined): string {
    return isMatchStatus(value) ? MATCH_STATUS_BY_VALUE[value].label : value || "Unknown"
}

export function getMatchStatusBadgeClassName(value: string | null | undefined): string {
    return isMatchStatus(value)
        ? MATCH_STATUS_BY_VALUE[value].badgeClassName
        : "bg-gray-600 text-white"
}

export function getMatchKindLabel(kind: string | null | undefined): string {
    return kind === "donor" ? "Donor" : "Surrogate"
}

const MATCH_ACTION_LABELS: Record<string, string> = {
    propose: "Propose",
    accept: "Accept",
    decline: "Decline",
    request_cancel: "Request cancellation",
    withdraw_cancel: "Withdraw cancellation request",
}

export function getMatchActionLabel(action: string): string {
    return MATCH_ACTION_LABELS[action] ?? "Unknown match action"
}
