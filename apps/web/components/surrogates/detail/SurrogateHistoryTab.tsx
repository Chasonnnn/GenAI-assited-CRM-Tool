"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

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

function formatActivityDetails(type: string, details: Record<string, unknown>): string {
    const aiPrefix = details?.source === "ai" ? "AI-generated" : ""
    const withAiPrefix = (detail: string) => (aiPrefix ? `${aiPrefix} · ${detail}` : detail)
    const aiOnly = () => (aiPrefix ? aiPrefix : "")

    switch (type) {
        case "status_changed":
            return withAiPrefix(
                `${details.from} → ${details.to}${details.reason ? `: ${details.reason}` : ""}`
            )
        case "info_edited":
            if (isRecord(details.changes)) {
                const changes = Object.entries(details.changes)
                    .map(([field, value]) => `${field.replace(/_/g, " ")}: ${String(value)}`)
                    .join(", ")
                return aiPrefix ? withAiPrefix(changes) : changes
            }
            return aiOnly()
        case "assigned":
            return aiPrefix
                ? withAiPrefix(details.from_user_id ? "Reassigned" : "Assigned to user")
                : details.from_user_id
                  ? "Reassigned"
                  : "Assigned to user"
        case "unassigned":
            return aiPrefix ? withAiPrefix("Removed assignment") : "Removed assignment"
        case "surrogate_assigned_to_queue": {
            const toQueue = details.to_queue_id ? `Queue ${String(details.to_queue_id)}` : "queue"
            return withAiPrefix(`Assigned to ${toQueue}`)
        }
        case "surrogate_claimed": {
            const fromQueue = details.from_queue_id
                ? `Queue ${String(details.from_queue_id)}`
                : "queue"
            return withAiPrefix(`Claimed from ${fromQueue}`)
        }
        case "surrogate_released": {
            const toQueue = details.to_queue_id ? `Queue ${String(details.to_queue_id)}` : "queue"
            return withAiPrefix(`Released to ${toQueue}`)
        }
        case "priority_changed":
            return aiPrefix
                ? withAiPrefix(details.is_priority ? "Marked as priority" : "Removed priority")
                : details.is_priority
                  ? "Marked as priority"
                  : "Removed priority"
        case "note_added": {
            const preview = details.preview ? String(details.preview) : ""
            return preview ? withAiPrefix(preview) : withAiPrefix("Note added")
        }
        case "note_deleted": {
            const preview = details.preview ? String(details.preview) : ""
            return preview ? withAiPrefix(`${preview} (deleted)`) : withAiPrefix("Note deleted")
        }
        case "attachment_added": {
            const filename = details.filename ? String(details.filename) : "file"
            return withAiPrefix(`Uploaded: ${filename}`)
        }
        case "attachment_deleted": {
            const filename = details.filename ? String(details.filename) : "file"
            return withAiPrefix(`Deleted: ${filename}`)
        }
        case "task_created":
            return details.title ? withAiPrefix(`Task: ${String(details.title)}`) : aiOnly()
        case "task_deleted":
            return details.title
                ? withAiPrefix(`Deleted: ${String(details.title)}`)
                : withAiPrefix("Task deleted")
        case "email_sent": {
            const subject = details.subject ? `Subject: ${String(details.subject)}` : ""
            const provider = details.provider ? `via ${String(details.provider)}` : ""
            const templateId = details.template_id ? `template ${String(details.template_id)}` : ""
            const parts = [subject, provider, templateId].filter(Boolean)
            return parts.length > 0 ? withAiPrefix(parts.join(" • ")) : withAiPrefix("Email sent")
        }
        case "email_bounced": {
            const subject = details.subject ? `Subject: ${String(details.subject)}` : ""
            const provider = details.provider ? `via ${String(details.provider)}` : ""
            const reason = details.reason ? `Reason: ${String(details.reason)}` : "Email bounced"
            const bounceType = details.bounce_type ? `${String(details.bounce_type)} bounce` : ""
            const parts = [subject, reason, bounceType, provider].filter(Boolean)
            return withAiPrefix(parts.join(" • "))
        }
        case "contact_attempt": {
            const methods = Array.isArray(details.contact_methods)
                ? details.contact_methods.map((method) => String(method)).join(", ")
                : ""
            const outcome = String(details.outcome || "").replace(/_/g, " ")
            const backdated = details.is_backdated ? " (backdated)" : ""
            const summary = `${methods}: ${outcome}${backdated}`
            const notePreview = details.note_preview ? String(details.note_preview) : ""
            return withAiPrefix([summary, notePreview].filter(Boolean).join(" • "))
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
                                            {formatActivityDetails(entry.activity_type, entry.details)}
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
