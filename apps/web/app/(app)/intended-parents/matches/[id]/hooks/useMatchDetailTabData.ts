"use client"

import { useMemo } from "react"
import type { DataSource, SourceFilter } from "./useMatchDetailTabState"

type SurrogateNoteInput = {
    id: string
    body: string
    created_at: string
    author_name?: string | null
}

type IntendedParentNoteInput = {
    id: string
    content: string
    created_at: string
}

type AttachmentInput = {
    id: string
    filename: string
    file_size: number
    created_at: string
}

type TaskItemInput = {
    id: string
    title: string
    due_date: string | null
    is_completed: boolean
}

type TaskCollectionInput = {
    items: TaskItemInput[]
} | null | undefined

type SurrogateActivityItemInput = {
    id: string
    activity_type: string
    details?: Record<string, unknown> | null
    actor_name: string | null
    created_at: string
}

type SurrogateActivityInput = {
    items: SurrogateActivityItemInput[]
} | null | undefined

type IntendedParentHistoryItemInput = {
    id: string
    old_status?: string | null
    new_status?: string | null
    reason?: string | null
    changed_by_name: string | null
    changed_at: string
}

type MatchTabDataInput = {
    id?: string | null
    intended_parent_id?: string | null
    notes?: string | null
    updated_at?: string | null
    created_at?: string | null
    proposed_at?: string | null
} | null | undefined

export type CombinedNote = {
    id: string
    content: string
    created_at: string
    source: DataSource
    author_name?: string
}

export type CombinedFile = {
    id: string
    filename: string
    file_size: number
    created_at: string
    source: DataSource
}

export type CombinedTask = {
    id: string
    title: string
    due_date: string | null
    is_completed: boolean
    source: DataSource
}

export type CombinedActivity = {
    id: string
    event_type: string
    description: string
    actor_name: string | null
    created_at: string
    source: DataSource
}

type UseMatchDetailTabDataParams = {
    sourceFilter: SourceFilter
    surrogateNotes: SurrogateNoteInput[]
    intendedParentNotes: IntendedParentNoteInput[]
    surrogateFiles: AttachmentInput[]
    intendedParentFiles: AttachmentInput[]
    surrogateTasks: TaskCollectionInput
    intendedParentTasks: TaskCollectionInput
    surrogateActivity: SurrogateActivityInput
    intendedParentHistory: IntendedParentHistoryItemInput[] | null | undefined
    match: MatchTabDataInput
}

export const isDeletableSource = (value: DataSource): value is "surrogate" | "ip" =>
    value === "surrogate" || value === "ip"

const SURROGATE_ACTIVITY_LABELS: Record<string, string> = {
    email_sent: "Email sent",
    email_bounced: "Email bounced",
    contact_attempt: "Contact attempt",
    interview_outcome_logged: "Interview outcome",
    note_added: "Note",
    note_deleted: "Note deleted",
    task_created: "Task created",
    task_deleted: "Task deleted",
    attachment_added: "File uploaded",
    attachment_deleted: "File removed",
    info_edited: "Info updated",
    priority_changed: "Priority changed",
    assigned: "Assigned",
    unassigned: "Unassigned",
    surrogate_assigned_to_queue: "Assigned to queue",
    surrogate_claimed: "Claimed from queue",
    surrogate_released: "Released to queue",
    match_proposed: "Match Proposed",
    match_reviewing: "Match Reviewing",
    match_accepted: "Match Accepted",
    match_rejected: "Match Rejected",
    match_cancelled: "Match Cancelled",
    status_changed: "Status Change",
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value)
}

function stripHtml(value: string): string {
    return value.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()
}

function humanizeValue(value: string): string {
    return value
        .replace(/_/g, " ")
        .replace(/\b\w/g, (char) => char.toUpperCase())
}

function getStringValue(details: Record<string, unknown>, key: string): string | null {
    const value = details[key]
    if (typeof value !== "string") return null
    const trimmed = value.trim()
    return trimmed ? trimmed : null
}

function formatStatusChangeDescription(
    oldStatus: string | null | undefined,
    newStatus: string | null | undefined,
    reason: string | null | undefined,
): string {
    const oldLabel = oldStatus ? humanizeValue(oldStatus) : "New"
    const newLabel = newStatus ? humanizeValue(newStatus) : "Unknown"
    const trimmedReason = reason?.trim()
    return trimmedReason
        ? `${oldLabel} -> ${newLabel} (${trimmedReason})`
        : `${oldLabel} -> ${newLabel}`
}

function formatInfoEditedDescription(details: Record<string, unknown>): string {
    const changes = details.changes
    if (!isRecord(changes)) return "Information updated"

    const changedFields = Object.keys(changes).map((field) => humanizeValue(field))
    return changedFields.length > 0
        ? `Updated ${changedFields.join(", ")}`
        : "Information updated"
}

function getSurrogateActivityEventType(activityType: string): string {
    return SURROGATE_ACTIVITY_LABELS[activityType] ?? humanizeValue(activityType)
}

function getSurrogateActivityDescription(activity: SurrogateActivityItemInput): string {
    const details = isRecord(activity.details) ? activity.details : null
    if (!details) return getSurrogateActivityEventType(activity.activity_type)

    switch (activity.activity_type) {
        case "attachment_added":
        case "attachment_deleted":
            return getStringValue(details, "filename") ?? getSurrogateActivityEventType(activity.activity_type)
        case "note_added":
        case "note_deleted":
            return getStringValue(details, "preview") ?? getSurrogateActivityEventType(activity.activity_type)
        case "task_created":
        case "task_deleted":
            return getStringValue(details, "title") ?? getSurrogateActivityEventType(activity.activity_type)
        case "email_sent":
            return (
                getStringValue(details, "subject") ??
                getStringValue(details, "preview") ??
                getSurrogateActivityEventType(activity.activity_type)
            )
        case "email_bounced": {
            const subject = getStringValue(details, "subject")
            const reason = getStringValue(details, "reason")
            const bounceType = getStringValue(details, "bounce_type")
            return [subject, reason, bounceType].filter(Boolean).join(" • ") || "Email bounced"
        }
        case "contact_attempt":
            return (
                [
                    getStringValue(details, "outcome"),
                    getStringValue(details, "note_preview"),
                ]
                    .filter(Boolean)
                    .join(" • ") || "Contact attempt logged"
            )
        case "assigned": {
            const toUser = getStringValue(details, "to_user_name") ?? getStringValue(details, "to_user_id")
            const fromUser = getStringValue(details, "from_user_name") ?? getStringValue(details, "from_user_id")
            if (toUser && fromUser) return `Reassigned from ${fromUser} to ${toUser}`
            if (toUser) return `Assigned to ${toUser}`
            return "Assignment updated"
        }
        case "unassigned": {
            const fromUser = getStringValue(details, "from_user_name") ?? getStringValue(details, "from_user_id")
            return fromUser ? `Removed assignment from ${fromUser}` : "Assignment removed"
        }
        case "surrogate_assigned_to_queue": {
            const queueName = getStringValue(details, "to_queue_name") ?? getStringValue(details, "to_queue_id")
            return queueName ? `Assigned to ${queueName}` : "Assigned to queue"
        }
        case "surrogate_claimed": {
            const queueName = getStringValue(details, "from_queue_name") ?? getStringValue(details, "from_queue_id")
            return queueName ? `Claimed from ${queueName}` : "Claimed from queue"
        }
        case "surrogate_released": {
            const queueName = getStringValue(details, "to_queue_name") ?? getStringValue(details, "to_queue_id")
            return queueName ? `Released to ${queueName}` : "Released to queue"
        }
        case "priority_changed":
            return details.is_priority ? "Marked as priority" : "Removed priority"
        case "info_edited":
            return formatInfoEditedDescription(details)
        case "status_changed":
            return formatStatusChangeDescription(
                getStringValue(details, "from"),
                getStringValue(details, "to"),
                getStringValue(details, "reason"),
            )
        case "match_proposed":
            return "Match was proposed"
        case "match_reviewing":
            return "Match moved to reviewing"
        case "match_accepted": {
            const cancelledMatches = details.cancelled_matches
            if (typeof cancelledMatches === "number" && cancelledMatches > 0) {
                return `Match was accepted and ${cancelledMatches} competing matches were cancelled`
            }
            return "Match was accepted"
        }
        case "match_rejected":
            return getStringValue(details, "rejection_reason")
                ? `Rejected: ${getStringValue(details, "rejection_reason")}`
                : "Match was rejected"
        case "match_cancelled":
            return "Match was cancelled"
        default:
            return (
                getStringValue(details, "description") ??
                getStringValue(details, "preview") ??
                getStringValue(details, "title") ??
                getStringValue(details, "filename") ??
                getSurrogateActivityEventType(activity.activity_type)
            )
    }
}

function matchesCurrentMatch(
    activity: SurrogateActivityItemInput,
    match: MatchTabDataInput,
): boolean {
    if (activity.activity_type !== "match_proposed") return false

    const details = isRecord(activity.details) ? activity.details : null
    if (details && match?.id) {
        const detailMatchId = getStringValue(details, "match_id")
        if (detailMatchId) return detailMatchId === match.id
    }

    if (details && match?.intended_parent_id) {
        const detailIntendedParentId = getStringValue(details, "intended_parent_id")
        if (detailIntendedParentId) return detailIntendedParentId === match.intended_parent_id
    }

    return activity.created_at === match?.proposed_at
}

function filterBySource<T extends { source: DataSource }>(
    items: T[],
    sourceFilter: SourceFilter
): T[] {
    if (sourceFilter === "all") return items
    return items.filter((item) => item.source === sourceFilter)
}

export function buildMatchCombinedActivity({
    surrogateActivity,
    intendedParentNotes,
    intendedParentFiles,
    intendedParentHistory,
    match,
}: Pick<
    UseMatchDetailTabDataParams,
    | "surrogateActivity"
    | "intendedParentNotes"
    | "intendedParentFiles"
    | "intendedParentHistory"
    | "match"
>): CombinedActivity[] {
    const activity: CombinedActivity[] = []

    for (const surrogateEvent of surrogateActivity?.items || []) {
        const eventType = getSurrogateActivityEventType(surrogateEvent.activity_type)
        activity.push({
            id: surrogateEvent.id,
            event_type: eventType,
            description: getSurrogateActivityDescription(surrogateEvent),
            actor_name: surrogateEvent.actor_name,
            created_at: surrogateEvent.created_at,
            source: "surrogate",
        })
    }

    for (const intendedParentNote of intendedParentNotes) {
        activity.push({
            id: `ip-note-${intendedParentNote.id}`,
            event_type: "Note",
            description: stripHtml(intendedParentNote.content),
            actor_name: null,
            created_at: intendedParentNote.created_at,
            source: "ip",
        })
    }

    for (const intendedParentFile of intendedParentFiles) {
        activity.push({
            id: `ip-file-${intendedParentFile.id}`,
            event_type: "File uploaded",
            description: intendedParentFile.filename,
            actor_name: null,
            created_at: intendedParentFile.created_at,
            source: "ip",
        })
    }

    for (const history of intendedParentHistory || []) {
        activity.push({
            id: `ip-history-${history.id}`,
            event_type: "Status Change",
            description: formatStatusChangeDescription(
                history.old_status,
                history.new_status,
                history.reason,
            ),
            actor_name: history.changed_by_name,
            created_at: history.changed_at,
            source: "ip",
        })
    }

    const hasCanonicalMatchProposed = (surrogateActivity?.items || []).some((surrogateEvent) =>
        matchesCurrentMatch(surrogateEvent, match),
    )

    if (match?.proposed_at && !hasCanonicalMatchProposed) {
        activity.push({
            id: "match-proposed",
            event_type: "Match Proposed",
            description: "Match was proposed",
            actor_name: null,
            created_at: match.proposed_at,
            source: "match",
        })
    }

    activity.sort((a, b) => {
        const timeDiff = new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        return timeDiff !== 0 ? timeDiff : a.id.localeCompare(b.id)
    })

    return activity
}

export function useMatchDetailTabData({
    sourceFilter,
    surrogateNotes,
    intendedParentNotes,
    surrogateFiles,
    intendedParentFiles,
    surrogateTasks,
    intendedParentTasks,
    surrogateActivity,
    intendedParentHistory,
    match,
}: UseMatchDetailTabDataParams) {
    const combinedNotes = useMemo<CombinedNote[]>(() => {
        const notes: CombinedNote[] = []

        for (const surrogateNote of surrogateNotes) {
            const note: CombinedNote = {
                id: surrogateNote.id,
                content: surrogateNote.body,
                created_at: surrogateNote.created_at,
                source: "surrogate",
            }
            if (surrogateNote.author_name) {
                note.author_name = surrogateNote.author_name
            }
            notes.push(note)
        }

        for (const intendedParentNote of intendedParentNotes) {
            notes.push({
                id: intendedParentNote.id,
                content: intendedParentNote.content,
                created_at: intendedParentNote.created_at,
                source: "ip",
            })
        }

        if (match?.notes) {
            notes.push({
                id: "match-notes",
                content: match.notes,
                created_at: match.updated_at || match.created_at || "",
                source: "match",
            })
        }

        notes.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        return notes
    }, [intendedParentNotes, match, surrogateNotes])

    const combinedFiles = useMemo<CombinedFile[]>(() => {
        const files: CombinedFile[] = []

        for (const surrogateFile of surrogateFiles) {
            files.push({
                id: surrogateFile.id,
                filename: surrogateFile.filename,
                file_size: surrogateFile.file_size,
                created_at: surrogateFile.created_at,
                source: "surrogate",
            })
        }

        for (const intendedParentFile of intendedParentFiles) {
            files.push({
                id: intendedParentFile.id,
                filename: intendedParentFile.filename,
                file_size: intendedParentFile.file_size,
                created_at: intendedParentFile.created_at,
                source: "ip",
            })
        }

        files.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        return files
    }, [intendedParentFiles, surrogateFiles])

    const combinedTasks = useMemo<CombinedTask[]>(() => {
        const taskMap = new Map<string, CombinedTask>()

        for (const surrogateTask of surrogateTasks?.items || []) {
            taskMap.set(surrogateTask.id, {
                id: surrogateTask.id,
                title: surrogateTask.title,
                due_date: surrogateTask.due_date,
                is_completed: surrogateTask.is_completed,
                source: "surrogate",
            })
        }

        for (const intendedParentTask of intendedParentTasks?.items || []) {
            const existingTask = taskMap.get(intendedParentTask.id)
            if (existingTask) {
                taskMap.set(intendedParentTask.id, {
                    ...existingTask,
                    source: "match",
                })
                continue
            }

            taskMap.set(intendedParentTask.id, {
                id: intendedParentTask.id,
                title: intendedParentTask.title,
                due_date: intendedParentTask.due_date,
                is_completed: intendedParentTask.is_completed,
                source: "ip",
            })
        }

        return Array.from(taskMap.values())
    }, [intendedParentTasks, surrogateTasks])

    const combinedActivity = useMemo<CombinedActivity[]>(
        () =>
            buildMatchCombinedActivity({
                surrogateActivity,
                intendedParentNotes,
                intendedParentFiles,
                intendedParentHistory,
                match,
            }),
        [intendedParentFiles, intendedParentHistory, intendedParentNotes, match, surrogateActivity],
    )

    const filteredNotes = useMemo(
        () => filterBySource(combinedNotes, sourceFilter),
        [combinedNotes, sourceFilter]
    )
    const filteredFiles = useMemo(
        () => filterBySource(combinedFiles, sourceFilter),
        [combinedFiles, sourceFilter]
    )
    const filteredTasks = useMemo(
        () => filterBySource(combinedTasks, sourceFilter),
        [combinedTasks, sourceFilter]
    )
    const filteredActivity = useMemo(
        () => filterBySource(combinedActivity, sourceFilter),
        [combinedActivity, sourceFilter]
    )

    return {
        filteredNotes,
        filteredFiles,
        filteredTasks,
        filteredActivity,
    }
}
