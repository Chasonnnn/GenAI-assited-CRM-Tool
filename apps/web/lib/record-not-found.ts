// The proxy rewrites unknown app-shell record ids to this route so the not-found
// state renders inside app/(app)/layout with a real 404 status.
export const RECORD_NOT_FOUND_PATH = "/record-not-found"

export const RECORD_NOT_FOUND_STATES = {
    campaign: {
        title: "Campaign not found",
        backHref: "/automation/campaigns",
        backLabel: "Back to Campaigns",
    },
    form: {
        title: "Form not found",
        backHref: "/automation/forms",
        backLabel: "Back to Forms",
    },
    match: {
        title: "Match not found",
        backHref: "/intended-parents/matches",
        backLabel: "Back to Matches",
    },
    member: {
        title: "Member not found",
        backHref: "/settings/team",
        backLabel: "Back to Team",
    },
    role: {
        title: "Role not found",
        backHref: "/settings/team/roles",
        backLabel: "Back to Role Permissions",
    },
} as const

export type RecordNotFoundKind = keyof typeof RECORD_NOT_FOUND_STATES

export type RecordNotFoundState = (typeof RECORD_NOT_FOUND_STATES)[RecordNotFoundKind]

export function getRecordNotFoundPath(kind: RecordNotFoundKind): string {
    return `${RECORD_NOT_FOUND_PATH}/${kind}`
}

export function getRecordNotFoundState(kind: string): RecordNotFoundState | null {
    return Object.hasOwn(RECORD_NOT_FOUND_STATES, kind)
        ? RECORD_NOT_FOUND_STATES[kind as RecordNotFoundKind]
        : null
}
