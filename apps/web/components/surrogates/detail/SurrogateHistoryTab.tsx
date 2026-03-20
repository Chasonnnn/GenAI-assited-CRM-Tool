"use client"

import type { ReactNode } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatHeight } from "@/components/surrogates/detail/surrogate-detail-utils"

type SurrogateActivityEntry = {
    id: string
    activity_type: string
    actor_name: string | null
    created_at: string
    details?: Record<string, unknown> | null
}

type SurrogateHistoryTabProps = {
    activities: SurrogateActivityEntry[]
    formatDateTime: (dateString: string) => string
}

function formatActivityType(type: string): string {
    const labels: Record<string, string> = {
        surrogate_created: "Surrogate Created",
        info_edited: "Information Edited",
        stage_changed: "Stage Changed",
        assigned: "Assigned",
        unassigned: "Unassigned",
        surrogate_assigned_to_queue: "Assigned to Queue",
        surrogate_claimed: "Surrogate Claimed",
        surrogate_released: "Released to Queue",
        priority_changed: "Priority Changed",
        archived: "Archived",
        restored: "Restored",
        note_added: "Note Added",
        note_deleted: "Note Deleted",
        attachment_added: "Attachment Uploaded",
        attachment_deleted: "Attachment Deleted",
        email_bounced: "Email Bounced",
        task_created: "Task Created",
        task_deleted: "Task Deleted",
        contact_attempt: "Contact Attempt",
    }

    return labels[type] || type.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase())
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value)
}

function formatInfoEditedFieldLabel(field: string): string {
    if (field === "height_ft") return "height"
    if (field === "weight_lb") return "weight"
    return field.replace(/_/g, " ")
}

function formatInfoEditedValue(field: string, value: unknown): string {
    if (field === "height_ft") {
        return formatHeight(value as number | string | null | undefined)
    }

    if (field === "weight_lb") {
        if (typeof value === "number" && Number.isFinite(value)) return `${value} lb`
        if (typeof value === "string") {
            const trimmed = value.trim()
            const numeric = Number(trimmed)
            if (trimmed !== "" && Number.isFinite(numeric)) return `${numeric} lb`
        }
    }

    return String(value)
}

function getQueueName(
    details: Record<string, unknown>,
    nameKey: "to_queue_name" | "from_queue_name",
    idKey: "to_queue_id" | "from_queue_id"
): string {
    if (typeof details[nameKey] === "string") {
        const queueName = details[nameKey].trim()
        if (queueName) return queueName
    }

    if (details[idKey]) return `Queue ${String(details[idKey])}`
    return "queue"
}

function getUserDisplayName(
    details: Record<string, unknown>,
    nameKey: "to_user_name" | "from_user_name",
    idKey: "to_user_id" | "from_user_id"
): string {
    if (typeof details[nameKey] === "string") {
        const userName = details[nameKey].trim()
        if (userName) return userName
    }

    if (details[idKey]) return `user ${String(details[idKey])}`
    return "user"
}

function formatDateDetail(
    value: unknown,
    formatDateTime: (dateString: string) => string
): string | null {
    if (typeof value !== "string" || value.trim() === "") return null
    return formatDateTime(value)
}

function addAiPrefix(lines: string[], details: Record<string, unknown>): string[] {
    if (details?.source !== "ai" || lines.length === 0) return lines
    return [`AI-generated · ${lines[0]}`, ...lines.slice(1)]
}

function formatActivityDetails(
    type: string,
    details: Record<string, unknown>,
    formatDateTime: (dateString: string) => string,
    createdAt: string
): ReactNode {
    const aiPrefix = details?.source === "ai" ? "AI-generated" : ""
    const aiOnly = () => (aiPrefix ? aiPrefix : "")
    const createdAtFormatted = formatDateDetail(createdAt, formatDateTime)

    switch (type) {
        case "status_changed": {
            const lines = addAiPrefix(
                [
                    `${details.from} → ${details.to}${details.reason ? `: ${details.reason}` : ""}`,
                ],
                details
            )
            const effectiveAt = formatDateDetail(details.effective_at, formatDateTime)
            const recordedAt = formatDateDetail(details.recorded_at, formatDateTime)
            if (effectiveAt) lines.push(`Effective: ${effectiveAt}`)
            if (recordedAt && recordedAt !== effectiveAt) lines.push(`Recorded: ${recordedAt}`)
            return lines
        }
        case "info_edited":
            if (isRecord(details.changes)) {
                const changes = Object.entries(details.changes)
                    .map(
                        ([field, value]) =>
                            `${formatInfoEditedFieldLabel(field)}: ${formatInfoEditedValue(
                                field,
                                value
                            )}`
                    )
                    .join(", ")
                return aiPrefix ? `AI-generated · ${changes}` : changes
            }
            return aiOnly()
        case "assigned":
            {
                const toUser = getUserDisplayName(details, "to_user_name", "to_user_id")
                const hasPreviousAssignee = Boolean(details.from_user_id || details.from_user_name)
                if (hasPreviousAssignee) {
                    const fromUser = getUserDisplayName(details, "from_user_name", "from_user_id")
                    return aiPrefix
                        ? `AI-generated · Reassigned from ${fromUser} to ${toUser}`
                        : `Reassigned from ${fromUser} to ${toUser}`
                }
                return aiPrefix ? `AI-generated · Assigned to ${toUser}` : `Assigned to ${toUser}`
            }
        case "unassigned":
            {
                const fromUser = getUserDisplayName(details, "from_user_name", "from_user_id")
                return aiPrefix
                    ? `AI-generated · Removed assignment from ${fromUser}`
                    : `Removed assignment from ${fromUser}`
            }
        case "surrogate_assigned_to_queue": {
            const toQueue = getQueueName(details, "to_queue_name", "to_queue_id")
            return aiPrefix ? `AI-generated · Assigned to ${toQueue}` : `Assigned to ${toQueue}`
        }
        case "surrogate_claimed": {
            const fromQueue = getQueueName(details, "from_queue_name", "from_queue_id")
            return aiPrefix ? `AI-generated · Claimed from ${fromQueue}` : `Claimed from ${fromQueue}`
        }
        case "surrogate_released": {
            const toQueue = getQueueName(details, "to_queue_name", "to_queue_id")
            return aiPrefix ? `AI-generated · Released to ${toQueue}` : `Released to ${toQueue}`
        }
        case "priority_changed":
            return aiPrefix
                ? `AI-generated · ${details.is_priority ? "Marked as priority" : "Removed priority"}`
                : details.is_priority
                  ? "Marked as priority"
                  : "Removed priority"
        case "note_added": {
            const preview = details.preview ? String(details.preview) : ""
            if (preview) return aiPrefix ? `AI-generated · ${preview}` : preview
            return aiPrefix ? "AI-generated · Note added" : "Note added"
        }
        case "note_deleted": {
            const preview = details.preview ? String(details.preview) : ""
            if (preview) return aiPrefix ? `AI-generated · ${preview} (deleted)` : `${preview} (deleted)`
            return aiPrefix ? "AI-generated · Note deleted" : "Note deleted"
        }
        case "attachment_added": {
            const filename = details.filename ? String(details.filename) : "file"
            return aiPrefix ? `AI-generated · Uploaded: ${filename}` : `Uploaded: ${filename}`
        }
        case "attachment_deleted": {
            const filename = details.filename ? String(details.filename) : "file"
            return aiPrefix ? `AI-generated · Deleted: ${filename}` : `Deleted: ${filename}`
        }
        case "task_created":
            return details.title
                ? aiPrefix
                    ? `AI-generated · Task: ${String(details.title)}`
                    : `Task: ${String(details.title)}`
                : aiOnly()
        case "task_deleted":
            return details.title
                ? aiPrefix
                    ? `AI-generated · Deleted: ${String(details.title)}`
                    : `Deleted: ${String(details.title)}`
                : aiPrefix
                    ? "AI-generated · Task deleted"
                    : "Task deleted"
        case "email_sent": {
            const subject = details.subject ? `Subject: ${String(details.subject)}` : ""
            const provider = details.provider ? `via ${String(details.provider)}` : ""
            const templateName =
                typeof details.template_name === "string" ? details.template_name.trim() : ""
            const templateDetail = templateName
                ? `template ${templateName}`
                : details.template_id
                  ? "template"
                  : ""
            const parts = [subject, provider, templateDetail].filter(Boolean)
            if (parts.length > 0) {
                return aiPrefix ? `AI-generated · ${parts.join(" • ")}` : parts.join(" • ")
            }
            return aiPrefix ? "AI-generated · Email sent" : "Email sent"
        }
        case "email_bounced": {
            const subject = details.subject ? `Subject: ${String(details.subject)}` : ""
            const provider = details.provider ? `via ${String(details.provider)}` : ""
            const reason = details.reason ? `Reason: ${String(details.reason)}` : "Email bounced"
            const bounceType = details.bounce_type ? `${String(details.bounce_type)} bounce` : ""
            const parts = [subject, reason, bounceType, provider].filter(Boolean)
            return aiPrefix ? `AI-generated · ${parts.join(" • ")}` : parts.join(" • ")
        }
        case "contact_attempt": {
            const methods = Array.isArray(details.contact_methods)
                ? details.contact_methods.map((method) => String(method)).join(", ")
                : ""
            const outcome = String(details.outcome || "").replace(/_/g, " ")
            const backdated = details.is_backdated ? " (backdated)" : ""
            const lines = addAiPrefix([`${methods}: ${outcome}${backdated}`], details)
            const attemptedAt = formatDateDetail(details.attempted_at, formatDateTime)
            if (attemptedAt && attemptedAt !== createdAtFormatted) {
                lines.push(`Attempted: ${attemptedAt}`)
            }
            const notePreview = details.note_preview ? String(details.note_preview) : ""
            const notes = details.notes ? String(details.notes) : ""
            if (notePreview) lines.push(notePreview)
            else if (notes) lines.push(notes)
            return lines
        }
        case "interview_outcome_logged": {
            const outcome = String(details.outcome || "").replace(/_/g, " ")
            const lines = addAiPrefix([`Outcome: ${outcome}`], details)
            const occurredAt = formatDateDetail(details.occurred_at, formatDateTime)
            if (occurredAt) lines.push(`Occurred: ${occurredAt}`)
            const scheduledStart = formatDateDetail(details.scheduled_start, formatDateTime)
            const scheduledEnd = formatDateDetail(details.scheduled_end, formatDateTime)
            if (scheduledStart || scheduledEnd) {
                lines.push(
                    `Appointment: ${[scheduledStart, scheduledEnd].filter(Boolean).join(" to ")}`
                )
            }
            if (details.notes) lines.push(String(details.notes))
            return lines
        }
        default:
            return aiOnly()
    }
}

export function SurrogateHistoryTab({ activities, formatDateTime }: SurrogateHistoryTabProps) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Activity Log</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
                {activities.length > 0 ? (
                    activities.map((entry, idx) => {
                        const isLast = idx === activities.length - 1
                        return (
                            <div key={entry.id} className="flex gap-3">
                                <div className="relative">
                                    <div className="mt-1.5 h-2 w-2 rounded-full bg-primary"></div>
                                    {!isLast && (
                                        <div className="absolute left-1 top-4 h-full w-px bg-border"></div>
                                    )}
                                </div>
                                <div className="flex-1 space-y-1 pb-4">
                                    <div className="text-sm font-medium">
                                        {formatActivityType(entry.activity_type)}
                                    </div>
                                    <div className="text-xs text-muted-foreground">
                                        {entry.actor_name || "System"} •{" "}
                                        {formatDateTime(entry.created_at)}
                                    </div>
                                    {entry.details && (
                                        <div className="pt-1 text-sm text-muted-foreground">
                                            {(() => {
                                                const detailsContent = formatActivityDetails(
                                                    entry.activity_type,
                                                    entry.details,
                                                    formatDateTime,
                                                    entry.created_at
                                                )
                                                if (Array.isArray(detailsContent)) {
                                                    return (
                                                        <div className="space-y-1">
                                                            {detailsContent.map((line) => (
                                                                <div key={line}>{line}</div>
                                                            ))}
                                                        </div>
                                                    )
                                                }
                                                return detailsContent
                                            })()}
                                        </div>
                                    )}
                                </div>
                            </div>
                        )
                    })
                ) : (
                    <p className="py-4 text-center text-sm text-muted-foreground">
                        No activity recorded.
                    </p>
                )}
            </CardContent>
        </Card>
    )
}
