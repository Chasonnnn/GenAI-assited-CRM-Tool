"use client"

import { useState } from "react"
import Link from "@/components/app-link"
import { formatDistanceToNow, isBefore, parseISO, startOfToday } from "date-fns"
import {
    ActivityIcon,
    ArrowRightIcon,
    ChevronRightIcon,
    MailIcon,
    PhoneIcon,
    FileTextIcon,
    PlusCircleIcon,
    TrashIcon,
    PaperclipIcon,
    EditIcon,
    FlagIcon,
    Loader2Icon,
    UserPlusIcon,
    CalendarIcon,
} from "lucide-react"
import { OutcomeBadge } from "@/components/surrogates/OutcomeBadge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Button } from "@/components/ui/button"
import type { SurrogateActivity, SurrogateStatusHistory } from "@/lib/api/surrogates"
import type { PipelineStage } from "@/lib/api/pipelines"
import { getSurrogateOutcomePresentation, type SurrogateOutcomeKind } from "@/lib/surrogate-outcome-presentation"
import type { TaskListItem } from "@/lib/types/task"
import type { LucideIcon } from "lucide-react"
import { isTerminalStage } from "@/lib/surrogate-stage-context"
import { cn } from "@/lib/utils"

// ============================================================================
// Constants
// ============================================================================

const VISIBLE_STAGE_RANGE = 2 // Stages before/after current
const MAX_PER_STAGE = 3

// ============================================================================
// Types
// ============================================================================

interface StageGroup {
    id: string
    label: string
    color: string // From stage.color (hex)
    order: number // Pipeline order
    date: string | null // Formatted relative date for display
    rawDate: string | null // ISO string for sorting
    isCurrent: boolean
    isCompleted: boolean // order < current stage order
    isUpcoming: boolean // order > current stage order
    isTerminal: boolean
    transitionLabel: string | null
    reason: string | null
    isBackdated: boolean // effective_at !== recorded_at (> 60s diff)
    activityCount: number // Total count (BEFORE per-stage cap)
    activities: ActivityItem[] // Capped to max per stage
}

interface ActivityItem {
    id: string
    type: string
    title: string
    preview: string
    relativeDate: string
    actorName?: string
    timestamp: string
    exactTimestamp?: string
    outcomeKind?: SurrogateOutcomeKind
    outcomeValue?: string
}

// ============================================================================
// Activity Type Configuration
// ============================================================================

// Ignore status_changed in activity log (avoid duplicate with stage history)
const IGNORED_ACTIVITY_TYPES = ["status_changed"]

interface ActivityTypeConfig {
    icon: LucideIcon
    color: string
    bgColor: string
    label: string
}

const ACTIVITY_TYPE_CONFIG: Record<string, ActivityTypeConfig> = {
    // Actual backend types
    email_sent: { icon: MailIcon, color: "bg-cyan-500", bgColor: "bg-cyan-100 dark:bg-cyan-900/30", label: "Email sent" },
    email_bounced: { icon: MailIcon, color: "bg-red-500", bgColor: "bg-red-100 dark:bg-red-900/30", label: "Email bounced" },
    contact_attempt: { icon: PhoneIcon, color: "bg-cyan-500", bgColor: "bg-cyan-100 dark:bg-cyan-900/30", label: "Contact attempt" },
    interview_outcome_logged: {
        icon: CalendarIcon,
        color: "bg-sky-500",
        bgColor: "bg-sky-100 dark:bg-sky-900/30",
        label: "Interview outcome",
    },
    interview_scheduled: {
        icon: CalendarIcon,
        color: "bg-sky-500",
        bgColor: "bg-sky-100 dark:bg-sky-900/30",
        label: "Interview scheduled",
    },
    note_added: { icon: FileTextIcon, color: "bg-blue-500", bgColor: "bg-blue-100 dark:bg-blue-900/30", label: "Note" },
    note_deleted: { icon: FileTextIcon, color: "bg-blue-400", bgColor: "bg-blue-100 dark:bg-blue-900/30", label: "Note deleted" },
    task_created: { icon: PlusCircleIcon, color: "bg-green-500", bgColor: "bg-green-100 dark:bg-green-900/30", label: "Task created" },
    task_updated: { icon: EditIcon, color: "bg-green-500", bgColor: "bg-green-100 dark:bg-green-900/30", label: "Task updated" },
    task_completed: { icon: ActivityIcon, color: "bg-green-500", bgColor: "bg-green-100 dark:bg-green-900/30", label: "Task completed" },
    task_uncompleted: { icon: ActivityIcon, color: "bg-amber-500", bgColor: "bg-amber-100 dark:bg-amber-900/30", label: "Task reopened" },
    task_deleted: { icon: TrashIcon, color: "bg-red-400", bgColor: "bg-red-100 dark:bg-red-900/30", label: "Task deleted" },
    attachment_added: { icon: PaperclipIcon, color: "bg-amber-500", bgColor: "bg-amber-100 dark:bg-amber-900/30", label: "File uploaded" },
    attachment_deleted: { icon: PaperclipIcon, color: "bg-amber-400", bgColor: "bg-amber-100 dark:bg-amber-900/30", label: "File removed" },
    // Other known types
    info_edited: { icon: EditIcon, color: "bg-gray-400", bgColor: "bg-gray-100 dark:bg-gray-900/30", label: "Info updated" },
    record_created: { icon: PlusCircleIcon, color: "bg-green-500", bgColor: "bg-green-100 dark:bg-green-900/30", label: "Record created" },
    status_changed: { icon: ArrowRightIcon, color: "bg-blue-500", bgColor: "bg-blue-100 dark:bg-blue-900/30", label: "Stage changed" },
    archived: { icon: TrashIcon, color: "bg-gray-400", bgColor: "bg-gray-100 dark:bg-gray-900/30", label: "Archived" },
    restored: { icon: ActivityIcon, color: "bg-green-500", bgColor: "bg-green-100 dark:bg-green-900/30", label: "Restored" },
    unassigned: { icon: UserPlusIcon, color: "bg-gray-400", bgColor: "bg-gray-100 dark:bg-gray-900/30", label: "Unassigned" },
    priority_changed: { icon: FlagIcon, color: "bg-gray-400", bgColor: "bg-gray-100 dark:bg-gray-900/30", label: "Priority changed" },
    assigned: { icon: UserPlusIcon, color: "bg-gray-400", bgColor: "bg-gray-100 dark:bg-gray-900/30", label: "Assigned" },
    match_proposed: { icon: UserPlusIcon, color: "bg-violet-500", bgColor: "bg-violet-100 dark:bg-violet-900/30", label: "Match proposed" },
    match_reviewing: { icon: ActivityIcon, color: "bg-violet-500", bgColor: "bg-violet-100 dark:bg-violet-900/30", label: "Match under review" },
    match_accepted: { icon: ActivityIcon, color: "bg-green-500", bgColor: "bg-green-100 dark:bg-green-900/30", label: "Match accepted" },
    match_rejected: { icon: ActivityIcon, color: "bg-red-500", bgColor: "bg-red-100 dark:bg-red-900/30", label: "Match rejected" },
    match_cancel_requested: { icon: ActivityIcon, color: "bg-amber-500", bgColor: "bg-amber-100 dark:bg-amber-900/30", label: "Match cancellation requested" },
    match_cancelled: { icon: ActivityIcon, color: "bg-gray-500", bgColor: "bg-gray-100 dark:bg-gray-900/30", label: "Match cancelled" },
    status_change_requested: { icon: ArrowRightIcon, color: "bg-amber-500", bgColor: "bg-amber-100 dark:bg-amber-900/30", label: "Stage change requested" },
    status_change_approved: { icon: ArrowRightIcon, color: "bg-green-500", bgColor: "bg-green-100 dark:bg-green-900/30", label: "Stage change approved" },
    status_change_rejected: { icon: ArrowRightIcon, color: "bg-red-500", bgColor: "bg-red-100 dark:bg-red-900/30", label: "Stage change rejected" },
    status_change_request_cancelled: { icon: ArrowRightIcon, color: "bg-gray-500", bgColor: "bg-gray-100 dark:bg-gray-900/30", label: "Stage change request cancelled" },
    // Default fallback
    default: { icon: ActivityIcon, color: "bg-gray-400", bgColor: "bg-gray-100 dark:bg-gray-900/30", label: "Activity" },
}

function getActivityConfig(type: string): ActivityTypeConfig {
    const config = ACTIVITY_TYPE_CONFIG[type]
    if (config) return config
    // Fallback is guaranteed to exist (defined above)
    return ACTIVITY_TYPE_CONFIG.default!
}

// ============================================================================
// Preview Content Strategy (Safe fields only - avoid PII)
// ============================================================================

const activityTimestampFormatter = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
})

function formatActivityTimestamp(value: unknown): string | null {
    if (typeof value !== "string") return null
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return null
    return activityTimestampFormatter.format(date)
}

function getActivityPreview(activity: SurrogateActivity): string {
    const details = activity.details as Record<string, unknown> | null
    const type = activity.activity_type

    if (!details) return ""

    const formatContactMethods = (value: unknown): string | undefined => {
        if (!Array.isArray(value)) return undefined
        return value
            .map((method) => {
                const label = String(method)
                return label.charAt(0).toUpperCase() + label.slice(1)
            })
            .join(", ")
    }

    switch (type) {
        case "email_sent":
            {
                const basePreview =
                    (details.subject as string) ||
                    (details.preview as string) ||
                    (details.provider as string ? `via ${details.provider as string}` : "")
                const attachments = Array.isArray(details.attachments)
                    ? details.attachments as Array<{ filename?: string }>
                    : []
                const deliveryStatus =
                    typeof details.delivery_status === "string"
                        ? details.delivery_status.replaceAll("_", " ")
                        : ""
                const deliveredAt = formatActivityTimestamp(details.delivered_at)
                const openCount =
                    typeof details.open_count === "number" ? details.open_count : 0
                const openedAt = formatActivityTimestamp(details.opened_at)
                const clickCount =
                    typeof details.click_count === "number" ? details.click_count : 0
                const clickedAt = formatActivityTimestamp(details.clicked_at)
                const engagementSummary = [
                    deliveryStatus
                        ? `${deliveryStatus.charAt(0).toUpperCase()}${deliveryStatus.slice(1)}${deliveredAt ? ` ${deliveredAt}` : ""}`
                        : "",
                    openCount > 0
                        ? `${openCount} open${openCount === 1 ? "" : "s"}${openedAt ? ` (first ${openedAt})` : ""}`
                        : "",
                    clickCount > 0
                        ? `${clickCount} click${clickCount === 1 ? "" : "s"}${clickedAt ? ` (first ${clickedAt})` : ""}`
                        : "",
                    openCount > 0 ? "Open tracking is approximate" : "",
                ].filter(Boolean)

                const attachmentSummary =
                    attachments.length === 0
                        ? ""
                        : attachments.length === 1 && attachments[0]?.filename
                        ? `Attachment: ${attachments[0].filename}`
                        : `${attachments.length} attachments`
                return [basePreview, ...engagementSummary, attachmentSummary]
                    .filter(Boolean)
                    .join(" • ")
            }
        case "email_bounced":
            {
                const subject = details.subject as string | undefined
                const reason = details.reason as string | undefined
                const bounceType = details.bounce_type as string | undefined
                const provider = details.provider as string | undefined
                return [
                    subject ? `Subject: ${subject}` : undefined,
                    reason ? `Reason: ${reason}` : "Email bounced",
                    bounceType ? `${bounceType} bounce` : undefined,
                    provider ? `via ${provider}` : undefined,
                ]
                    .filter(Boolean)
                    .join(" • ")
            }
        case "contact_attempt":
            return [
                formatContactMethods(details.contact_methods),
                (details.note_preview as string | undefined) || undefined,
            ]
                .filter(Boolean)
                .join(" • ")
        case "interview_outcome_logged":
            {
                const occurredAt = formatActivityTimestamp(details.occurred_at)
                const scheduledStart = formatActivityTimestamp(details.scheduled_start)
                const scheduledEnd = formatActivityTimestamp(details.scheduled_end)
                const appointmentContext =
                    scheduledStart && scheduledEnd
                        ? `Appointment: ${scheduledStart} - ${scheduledEnd}`
                        : scheduledStart
                            ? `Appointment: ${scheduledStart}`
                            : details.appointment_id
                                ? "Appointment linked"
                                : ""

                return [
                    occurredAt ? `Occurred: ${occurredAt}` : "",
                    appointmentContext,
                    (details.notes as string | undefined) || "",
                ]
                    .filter(Boolean)
                    .join(" • ")
            }
        case "interview_scheduled":
            {
                const scheduledStart = formatActivityTimestamp(details.scheduled_start)
                return scheduledStart ? `Appointment: ${scheduledStart}` : ""
            }
        case "attachment_added":
            return (details.filename as string) || "File uploaded"
        case "attachment_deleted":
            return (details.filename as string) || "File removed"
        case "note_added":
        case "note_deleted":
            return (details.preview as string) || ""
        case "task_created":
        case "task_updated":
        case "task_completed":
        case "task_uncompleted":
        case "task_deleted":
            return (details.title as string) || ""
        case "status_changed": {
            const transition = [details.from, details.to].filter(Boolean).join(" → ")
            return [transition, details.reason].filter(Boolean).join(" • ")
        }
        case "info_edited":
            return Array.isArray(details.changed_fields)
                ? details.changed_fields
                      .map((field) => String(field).replaceAll("_", " "))
                      .join(", ")
                : ""
        default:
            return ""
    }
}

function getActivityTitle(activity: SurrogateActivity): string {
    const config = getActivityConfig(activity.activity_type)
    return config.label
}

function getActivityOutcomeMeta(activity: SurrogateActivity): {
    outcomeKind?: SurrogateOutcomeKind
    outcomeValue?: string
} {
    const details = activity.details as Record<string, unknown> | null
    if (!details) {
        return {}
    }
    if (activity.activity_type === "interview_scheduled") {
        return { outcomeKind: "interview", outcomeValue: "upcoming" }
    }
    if (typeof details.outcome !== "string") {
        return {}
    }
    if (activity.activity_type === "contact_attempt") {
        return { outcomeKind: "contact", outcomeValue: details.outcome }
    }
    if (activity.activity_type === "interview_outcome_logged") {
        return { outcomeKind: "interview", outcomeValue: details.outcome }
    }
    return {}
}

// ============================================================================
// Stage Assignment Logic
// ============================================================================

function getEntryTimestamp(entry: SurrogateStatusHistory): string {
    return entry.effective_at || entry.changed_at
}

function isBackdatedEntry(entry: SurrogateStatusHistory): boolean {
    if (!entry.effective_at || !entry.recorded_at) return false
    const effectiveTime = new Date(entry.effective_at).getTime()
    const recordedTime = new Date(entry.recorded_at).getTime()
    // Check if diff > 60 seconds (as specified in plan)
    return Math.abs(effectiveTime - recordedTime) > 60000
}

function dedupeStageHistory(history: SurrogateStatusHistory[]): SurrogateStatusHistory[] {
    const seenStages = new Set<string>()
    const deduped: SurrogateStatusHistory[] = []

    const sortedHistory = history.toSorted(
        (a, b) => new Date(getEntryTimestamp(b)).getTime() - new Date(getEntryTimestamp(a)).getTime()
    )

    // History is sorted by entry timestamp DESC (most recent first)
    for (const entry of sortedHistory) {
        if (entry.to_stage_id && !seenStages.has(entry.to_stage_id)) {
            seenStages.add(entry.to_stage_id)
            deduped.push(entry)
        }
    }
    return deduped
}

function getStageTransitionLabel(
    entry: SurrogateStatusHistory,
    stageLabelById: Map<string, string>
): string | null {
    const toLabel =
        entry.to_label_snapshot ||
        (entry.to_stage_id ? stageLabelById.get(entry.to_stage_id) : null)
    if (!toLabel) return null

    const fromLabel =
        entry.from_label_snapshot ||
        (entry.from_stage_id ? stageLabelById.get(entry.from_stage_id) : null)

    return fromLabel ? `${fromLabel} -> ${toLabel}` : toLabel
}

function assignActivityToStage(
    activity: SurrogateActivity,
    stageHistory: SurrogateStatusHistory[]
): string | null {
    // Sort history by entry timestamp DESC (most recent first)
    const sortedHistory = stageHistory.toSorted(
        (a, b) => new Date(getEntryTimestamp(b)).getTime() - new Date(getEntryTimestamp(a)).getTime()
    )

    const activityTime = new Date(activity.created_at).getTime()

    // Find the first stage where activity.created_at >= stage entry timestamp
    for (const entry of sortedHistory) {
        const stageEntryTime = new Date(getEntryTimestamp(entry)).getTime()
        if (activityTime >= stageEntryTime && entry.to_stage_id) {
            return entry.to_stage_id
        }
    }

    return null
}

function getStageKey(stage: PipelineStage): string | null {
    return stage.stage_key || stage.slug || null
}

function findStageIdByKey(stages: PipelineStage[], key: string): string | null {
    return stages.find((stage) => getStageKey(stage) === key)?.id ?? null
}

function resolveActivityStageId(
    activity: SurrogateActivity,
    stageHistory: SurrogateStatusHistory[],
    allPipelineStages: PipelineStage[]
): string | null {
    if (activity.activity_type === "interview_scheduled") {
        return (
            findStageIdByKey(allPipelineStages, "interview_scheduled") ||
            assignActivityToStage(activity, stageHistory)
        )
    }

    return assignActivityToStage(activity, stageHistory)
}

function getActivitySortRank(item: ActivityItem): number {
    if (item.type === "interview_scheduled") return 0
    return 1
}

// ============================================================================
// Windowing Logic
// ============================================================================

function getStageIndexById(stageGroups: StageGroup[], stageId?: string | null): number {
    if (!stageId) return 0
    const idx = stageGroups.findIndex((stage) => stage.id === stageId)
    return idx >= 0 ? idx : 0
}

function getVisibleStages(
    stageGroups: StageGroup[],
    showFullJourney: boolean,
    anchorStageId?: string | null,
    currentStageId?: string | null
): StageGroup[] {
    if (showFullJourney) return stageGroups

    const collectVisibleIds = (centerIndex: number, target: Set<string>) => {
        const startIdx = Math.max(0, centerIndex - VISIBLE_STAGE_RANGE)
        const endIdx = Math.min(stageGroups.length, centerIndex + VISIBLE_STAGE_RANGE + 1)
        for (const stage of stageGroups.slice(startIdx, endIdx)) {
            target.add(stage.id)
        }
    }

    const visibleIds = new Set<string>()
    const anchorIdx = getStageIndexById(stageGroups, anchorStageId ?? currentStageId)
    collectVisibleIds(anchorIdx, visibleIds)

    if (currentStageId && currentStageId !== anchorStageId) {
        collectVisibleIds(getStageIndexById(stageGroups, currentStageId), visibleIds)
    }

    return stageGroups.filter((stage) => visibleIds.has(stage.id))
}

// ============================================================================
// Data Transformation
// ============================================================================

function buildTimelineData(
    allPipelineStages: PipelineStage[],
    stageHistory: SurrogateStatusHistory[],
    activities: SurrogateActivity[],
    currentStageId: string,
    effectiveStageId?: string
): { stageGroups: StageGroup[] } {
    const stageLabelById = new Map(allPipelineStages.map((stage) => [stage.id, stage.label]))

    // 1. Filter: ignore status_changed activity types (duplicates stage history)
    const filteredActivities = activities.filter(
        (a) => !IGNORED_ACTIVITY_TYPES.includes(a.activity_type)
    )

    // 2. Dedupe stage history (handle regressions - show most recent entry per stage)
    const dedupedHistory = dedupeStageHistory(stageHistory)

    // 3. Build a map of stage ID -> entry metadata
    const stageEntryMeta = new Map<
        string,
        { entryAt: string; isBackdated: boolean; transitionLabel: string | null; reason: string | null }
    >()
    for (const entry of dedupedHistory) {
        if (entry.to_stage_id) {
            stageEntryMeta.set(entry.to_stage_id, {
                entryAt: getEntryTimestamp(entry),
                isBackdated: isBackdatedEntry(entry),
                transitionLabel: getStageTransitionLabel(entry, stageLabelById),
                reason: entry.reason,
            })
        }
    }

    // 4. Assign activities to stages
    const activitiesByStage = new Map<string, ActivityItem[]>()
    for (const activity of filteredActivities) {
        const stageId = resolveActivityStageId(activity, stageHistory, allPipelineStages)
        const item = {
            id: activity.id,
            type: activity.activity_type,
            title: getActivityTitle(activity),
            preview: getActivityPreview(activity),
            relativeDate: formatDistanceToNow(new Date(activity.created_at), { addSuffix: true }),
            actorName: activity.actor_name || "System",
            timestamp: activity.created_at,
            ...getActivityOutcomeMeta(activity),
        }
        if (!stageId) continue
        const items = activitiesByStage.get(stageId) || []
        items.push(item)
        activitiesByStage.set(stageId, items)
    }

    // 5. Sort activities within each stage by timestamp DESC
    for (const [, items] of activitiesByStage.entries()) {
        items.sort((a, b) => {
            const rankDiff = getActivitySortRank(a) - getActivitySortRank(b)
            if (rankDiff !== 0) return rankDiff
            const diff = new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
            return diff !== 0 ? diff : a.id.localeCompare(b.id)
        })
    }

    // 6. Find current stage order for completed/upcoming detection
    const activeStages = allPipelineStages
        .filter((s) => s.is_active)
        .sort((a, b) => a.order - b.order)
    const currentStage = activeStages.find((s) => s.id === currentStageId)
    const effectiveStage =
        activeStages.find((stage) => stage.id === effectiveStageId) ?? currentStage
    const currentStageOrder = effectiveStage?.order ?? currentStage?.order ?? 0

    // 7. Create StageGroup for ALL pipeline stages (preserve full story)
    const displayStages = activeStages.filter((stage) => {
        const terminalStage = stage.stage_type === "terminal" || isTerminalStage(stage)
        return !terminalStage || stage.id === currentStageId
    })
    const stageGroups: StageGroup[] = displayStages.map((stage) => {
        const allActivities = activitiesByStage.get(stage.id) || []
        const entryMeta = stageEntryMeta.get(stage.id)
        const entryAt = entryMeta?.entryAt || null
        const terminalStage = stage.stage_type === "terminal" || isTerminalStage(stage)

        return {
            id: stage.id,
            label: stage.label,
            color: stage.color || "#6b7280", // Fallback to gray if no color
            order: stage.order,
            date: entryAt ? formatDistanceToNow(new Date(entryAt), { addSuffix: true }) : null,
            rawDate: entryAt,
            isCurrent: stage.id === currentStageId,
            isCompleted: stage.id !== currentStageId && stage.order < currentStageOrder,
            isUpcoming: stage.id !== currentStageId && stage.order > currentStageOrder,
            isTerminal: terminalStage,
            transitionLabel: entryMeta?.transitionLabel ?? null,
            reason: entryMeta?.reason ?? null,
            isBackdated: entryMeta?.isBackdated ?? false,
            activityCount: allActivities.length, // Total count BEFORE cap
            activities: allActivities.slice(0, MAX_PER_STAGE), // Cap per stage
        }
    })

    return { stageGroups }
}

// ============================================================================
// Activity Row Component
// ============================================================================

function ActivityRow({ item }: { item: ActivityItem }) {
    const baseConfig = getActivityConfig(item.type)
    const outcomePresentation =
        item.outcomeKind && item.outcomeValue
            ? getSurrogateOutcomePresentation(item.outcomeKind, item.outcomeValue)
            : null
    const config = outcomePresentation
        ? {
              ...baseConfig,
              color: outcomePresentation.accentClassName,
              bgColor: outcomePresentation.iconContainerClassName,
          }
        : baseConfig
    const Icon = config.icon

    return (
        <div className="flex items-start gap-3 py-2">
            <div className={cn("w-1 self-stretch rounded-full", config.color)} />
            <div
                className={cn(
                    "size-6 rounded flex items-center justify-center shrink-0",
                    config.bgColor
                )}
            >
                <Icon className="size-3.5" />
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-medium truncate">{item.title}</div>
                    {item.outcomeKind && item.outcomeValue && (
                        <OutcomeBadge kind={item.outcomeKind} outcome={item.outcomeValue} />
                    )}
                </div>
                {item.preview && (
                    <div className="text-xs text-muted-foreground line-clamp-2">{item.preview}</div>
                )}
            </div>
            <div className="shrink-0 text-right text-xs text-muted-foreground">
                {item.actorName ? <div>{item.actorName}</div> : null}
                {item.exactTimestamp ? (
                    <time dateTime={item.timestamp}>{item.exactTimestamp}</time>
                ) : (
                    <div>{item.relativeDate}</div>
                )}
            </div>
        </div>
    )
}

export function ActivityEventRow({
    activity,
    showExactTimestamp = false,
}: {
    activity: SurrogateActivity
    showExactTimestamp?: boolean
}) {
    return (
        <ActivityRow
            item={{
                id: activity.id,
                type: activity.activity_type,
                title: getActivityTitle(activity),
                preview: getActivityPreview(activity),
                relativeDate: formatDistanceToNow(new Date(activity.created_at), {
                    addSuffix: true,
                }),
                actorName: activity.actor_name || "System",
                timestamp: activity.created_at,
                ...(showExactTimestamp
                    ? {
                          exactTimestamp:
                              formatActivityTimestamp(activity.created_at) ?? activity.created_at,
                      }
                    : {}),
                ...getActivityOutcomeMeta(activity),
            }}
        />
    )
}

const STAGE_ROW_CLASS =
    "grid w-full grid-cols-[1rem_0.625rem_minmax(0,1fr)_minmax(6.5rem,max-content)] items-center gap-x-2 rounded py-2 text-left"
const STAGE_ROW_LABEL_CLASS = "flex min-w-0 items-center gap-2"
const STAGE_ROW_META_CLASS = "justify-self-end text-right text-xs text-muted-foreground"

function StageEntryRow({
    entryTitle,
    entryLabel,
    isBackdated,
    reason,
}: {
    entryTitle: string
    entryLabel?: string | null
    isBackdated: boolean
    reason?: string | null
}) {
    return (
        <div className="flex items-start gap-3 py-2">
            <div className="w-1 self-stretch rounded-full bg-muted-foreground/20" />
            <div className="size-6 rounded flex items-center justify-center shrink-0 bg-muted/60">
                <ArrowRightIcon className="size-3.5 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-muted-foreground">{entryTitle}</div>
                {isBackdated && (
                    <div className="text-[11px] text-muted-foreground/70">
                        Backdated entry
                    </div>
                )}
                {reason ? <div className="text-xs text-muted-foreground">{reason}</div> : null}
            </div>
            {entryLabel && (
                <div className="text-xs text-muted-foreground shrink-0">{entryLabel}</div>
            )}
        </div>
    )
}

// ============================================================================
// Task Row Component
// ============================================================================

function TaskRow({ task, isOverdue = false }: { task: TaskListItem; isOverdue?: boolean }) {
    const dueDate = task.due_date ? parseISO(task.due_date) : null

    let dueLabel = ""
    if (dueDate) {
        const distance = formatDistanceToNow(dueDate, { addSuffix: false })
        dueLabel = isOverdue ? `${distance} overdue` : `due in ${distance}`
    }

    return (
        <div className="flex items-center gap-3 py-1 text-sm">
            <div
                className={cn(
                    "w-1 h-4 rounded-full",
                    isOverdue ? "bg-red-400/60" : "bg-muted-foreground/30"
                )}
            />
            <span className="flex-1 truncate">{task.title}</span>
            <span
                className={cn(
                    "text-xs",
                    isOverdue ? "text-red-600/80" : "text-muted-foreground"
                )}
            >
                {dueLabel}
            </span>
        </div>
    )
}

function ActivityTimelineStageList({
    stages,
    openStageIds,
    onStageToggle,
}: {
    stages: StageGroup[]
    openStageIds: Set<string>
    onStageToggle: (stageId: string, isOpen: boolean) => void
}) {
    return (
        <div className="space-y-0">
            {stages.map((stage) => {
                const hasContent = stage.activityCount > 0 || stage.isBackdated
                const showStageEntryRow =
                    !!stage.rawDate &&
                    (stage.isBackdated ||
                        stage.activityCount > 0 ||
                        (stage.isCurrent && !!stage.transitionLabel) ||
                        (stage.isTerminal && !!stage.transitionLabel))
                const stageEntryTitle =
                    (stage.isTerminal && stage.transitionLabel) || "Entered stage"
                const stageEntryLabel = stage.date

                if (!hasContent && !stage.isCurrent) {
                    return (
                        <div
                            key={stage.id}
                            data-testid={`timeline-stage-row-${stage.id}`}
                            className={STAGE_ROW_CLASS}
                        >
                            <span className="size-4" aria-hidden="true" />
                            <div
                                className={cn(
                                    "size-2 rounded-full",
                                    stage.isUpcoming && "bg-muted-foreground/30"
                                )}
                                style={
                                    !stage.isUpcoming
                                        ? { backgroundColor: stage.color }
                                        : undefined
                                }
                            />
                            <div className={STAGE_ROW_LABEL_CLASS}>
                                <span className="truncate text-sm text-muted-foreground">
                                    {stage.label}
                                </span>
                            </div>
                            <span
                                data-testid={`timeline-stage-meta-${stage.id}`}
                                className={cn(STAGE_ROW_META_CLASS, "opacity-0")}
                                aria-hidden="true"
                            >
                                --
                            </span>
                        </div>
                    )
                }

                return (
                    <Collapsible
                        key={stage.id}
                        open={openStageIds.has(stage.id)}
                        onOpenChange={(open) => onStageToggle(stage.id, open)}
                    >
                        <CollapsibleTrigger
                            data-testid={`timeline-stage-row-${stage.id}`}
                            className={cn("group hover:bg-muted/50", STAGE_ROW_CLASS)}
                        >
                            <ChevronRightIcon className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
                            <div
                                className={cn(
                                    "rounded-full",
                                    stage.isCurrent ? "size-2.5" : "size-2",
                                    stage.isUpcoming && "bg-muted-foreground/30"
                                )}
                                style={
                                    !stage.isUpcoming
                                        ? {
                                              backgroundColor: stage.color,
                                              boxShadow: stage.isCurrent
                                                  ? `0 0 0 2px hsl(var(--background)), 0 0 0 4px ${stage.color}40`
                                                  : undefined,
                                          }
                                        : undefined
                                }
                            />
                            <div className={STAGE_ROW_LABEL_CLASS}>
                                <span
                                    className={cn(
                                        "truncate text-sm font-medium",
                                        !stage.isCurrent && "text-muted-foreground"
                                    )}
                                >
                                    {stage.label}
                                </span>
                                {stage.activityCount > 0 ? (
                                    <Badge variant="secondary" className="shrink-0 text-xs">
                                        {stage.activityCount}
                                    </Badge>
                                ) : null}
                            </div>
                            <span
                                data-testid={`timeline-stage-meta-${stage.id}`}
                                className={cn(
                                    STAGE_ROW_META_CLASS,
                                    stage.isUpcoming && "opacity-0"
                                )}
                                aria-hidden={stage.isUpcoming ? "true" : undefined}
                            >
                                {stage.isUpcoming ? "—" : stage.date || "—"}
                            </span>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                            <div className="ml-6 border-l border-border/50 pl-4">
                                {showStageEntryRow && stageEntryLabel ? (
                                    <StageEntryRow
                                        entryTitle={stageEntryTitle}
                                        entryLabel={stageEntryLabel}
                                        isBackdated={stage.isBackdated}
                                        reason={stage.reason}
                                    />
                                ) : null}
                                {stage.activities.length > 0 ? (
                                    stage.activities.map((item) => (
                                        <ActivityRow key={item.id} item={item} />
                                    ))
                                ) : !showStageEntryRow ? (
                                    <div className="py-2 text-xs italic text-muted-foreground/60">
                                        No activity in this stage.
                                    </div>
                                ) : null}
                            </div>
                        </CollapsibleContent>
                    </Collapsible>
                )
            })}
        </div>
    )
}

function ActivityTimelineNextSteps({
    status,
    overdueTasks,
    upcomingTasks,
    onRetry,
}: {
    status: "loading" | "error" | "ready"
    overdueTasks: TaskListItem[]
    upcomingTasks: TaskListItem[]
    onRetry?: (() => void) | undefined
}) {
    if (status === "loading") {
        return (
            <div className="flex items-center gap-2 text-xs text-muted-foreground" role="status">
                <Loader2Icon className="size-3.5 animate-spin" aria-hidden="true" />
                Loading next steps…
            </div>
        )
    }
    if (status === "error") {
        return (
            <div className="space-y-2" role="alert">
                <p className="text-xs text-destructive">Failed to load next steps.</p>
                {onRetry ? (
                    <Button variant="outline" size="sm" onClick={onRetry}>
                        Retry next steps
                    </Button>
                ) : null}
            </div>
        )
    }
    if (overdueTasks.length === 0 && upcomingTasks.length === 0) return null

    return (
        <>
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                Next Steps
                <div className="flex-1 border-t border-dashed border-border/50" />
            </div>
            <div className="space-y-3">
                {overdueTasks.length > 0 ? (
                    <div className="space-y-1">
                        <span className="text-xs font-medium text-red-600">Overdue</span>
                        {overdueTasks.map((task) => (
                            <TaskRow key={task.id} task={task} isOverdue />
                        ))}
                    </div>
                ) : null}
                {upcomingTasks.length > 0 ? (
                    <div className="space-y-1">
                        <span className="text-xs font-medium text-muted-foreground">Upcoming</span>
                        {upcomingTasks.map((task) => (
                            <TaskRow key={task.id} task={task} />
                        ))}
                    </div>
                ) : null}
            </div>
        </>
    )
}

function ActivityTimelineLinks({
    historyHref,
    notesHref,
}: {
    historyHref?: string | undefined
    notesHref?: string | undefined
}) {
    if (!historyHref && !notesHref) return null
    return (
        <div className="flex gap-3 pt-2">
            {historyHref ? (
                <Link
                    href={historyHref}
                    className="text-xs text-primary underline-offset-4 hover:underline"
                >
                    View full history &rarr;
                </Link>
            ) : null}
            {notesHref ? (
                <Link
                    href={notesHref}
                    className="text-xs text-primary underline-offset-4 hover:underline"
                >
                    Notes &amp; Attachments &rarr;
                </Link>
            ) : null}
        </div>
    )
}

// ============================================================================
// Main Component
// ============================================================================

export interface EntityActivityTimelineProps {
    currentStageId: string
    effectiveStageId?: string
    stages: PipelineStage[]
    stageHistory: SurrogateStatusHistory[]
    activities?: SurrogateActivity[]
    tasks?: TaskListItem[]
    tasksStatus?: "loading" | "error" | "ready"
    onRetryTasks?: () => void
    status?: "loading" | "error" | "ready"
    onRetry?: () => void
    historyHref?: string
    notesHref?: string
}

const EMPTY_ACTIVITIES: SurrogateActivity[] = []
const EMPTY_TASKS: TaskListItem[] = []

export function EntityActivityTimeline({
    currentStageId,
    effectiveStageId,
    stages,
    stageHistory,
    activities = EMPTY_ACTIVITIES,
    tasks = EMPTY_TASKS,
    tasksStatus = "ready",
    onRetryTasks,
    status = "ready",
    onRetry,
    historyHref,
    notesHref,
}: EntityActivityTimelineProps) {
    const [showFullJourney, setShowFullJourney] = useState(false)

    const { stageGroups } = buildTimelineData(stages, stageHistory, activities, currentStageId, effectiveStageId)
    const visibleStages = getVisibleStages(stageGroups, showFullJourney, effectiveStageId, currentStageId)
    const defaultOpenStageId = stageGroups.find((stage) => stage.id === currentStageId)?.id ?? null
    const defaultStageKey = defaultOpenStageId ?? `missing:${currentStageId}`
    const createDefaultOpenStageIds = () => defaultOpenStageId
        ? new Set([defaultOpenStageId])
        : new Set<string>()
    const [openStageState, setOpenStageState] = useState(() => ({
        defaultStageKey,
        openStageIds: createDefaultOpenStageIds(),
    }))
    if (openStageState.defaultStageKey !== defaultStageKey) {
        setOpenStageState({
            defaultStageKey,
            openStageIds: createDefaultOpenStageIds(),
        })
    }
    const openStageIds = openStageState.defaultStageKey === defaultStageKey
        ? openStageState.openStageIds
        : createDefaultOpenStageIds()

    const { overdueTasks, upcomingTasks } = (() => {
        const today = startOfToday()
        const overdueEntries: Array<{ task: TaskListItem; dueDate: Date }> = []
        const upcomingEntries: Array<{ task: TaskListItem; dueDate: Date }> = []

        for (const task of tasks) {
            if (task.is_completed || !task.due_date) continue
            const dueDate = parseISO(task.due_date)
            if (Number.isNaN(dueDate.getTime())) continue

            const entry = { task, dueDate }
            if (isBefore(dueDate, today)) {
                overdueEntries.push(entry)
            } else {
                upcomingEntries.push(entry)
            }
        }

        const sortByDueDate = (
            a: { task: TaskListItem; dueDate: Date },
            b: { task: TaskListItem; dueDate: Date }
        ) =>
            a.dueDate.getTime() - b.dueDate.getTime()

        const overdueTasks: TaskListItem[] = []
        for (const entry of overdueEntries.toSorted(sortByDueDate)) {
            overdueTasks.push(entry.task)
            if (overdueTasks.length === 3) break
        }

        const upcomingTasks: TaskListItem[] = []
        for (const entry of upcomingEntries.toSorted(sortByDueDate)) {
            upcomingTasks.push(entry.task)
            if (upcomingTasks.length === 3) break
        }

        return {
            overdueTasks,
            upcomingTasks,
        }
    })()

    function handleStageToggle(stageId: string, isOpen: boolean) {
        const next = new Set(openStageIds)
        if (isOpen) {
            next.add(stageId)
        } else {
            next.delete(stageId)
        }
        setOpenStageState({
            defaultStageKey,
            openStageIds: next,
        })
    }

    if (status !== "ready") {
        return (
            <Card className="gap-2 py-4">
                <CardHeader className="px-4 pb-2">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <ActivityIcon className="size-4" aria-hidden="true" />
                        <h2>Activity</h2>
                    </CardTitle>
                </CardHeader>
                <CardContent className="px-4">
                    {status === "loading" ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                            <Loader2Icon className="size-4 animate-spin" />
                            Loading activity…
                        </div>
                    ) : (
                        <div className="space-y-3">
                            <p className="text-sm text-destructive">Failed to load activity.</p>
                            {onRetry ? (
                                <Button variant="outline" size="sm" onClick={onRetry}>Retry</Button>
                            ) : null}
                        </div>
                    )}
                </CardContent>
            </Card>
        )
    }

    return (
        <Card className="gap-2 py-4">
            <CardHeader className="px-4 pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-base flex items-center gap-2">
                        <ActivityIcon className="size-4" aria-hidden="true" />
                        <h2>Activity</h2>
                    </CardTitle>
                    {/* Hide toggle when ≤5 stages (all already visible) */}
                    {stageGroups.length > 5 && (
                        <Button
                            variant="ghost"
                            size="sm"
                            className="text-xs h-7"
                            onClick={() => setShowFullJourney(!showFullJourney)}
                        >
                            {showFullJourney ? "Collapse journey" : "Show full journey"}
                        </Button>
                    )}
                </div>
            </CardHeader>
            <CardContent className="px-4 space-y-4">
                <ActivityTimelineStageList
                    stages={visibleStages}
                    openStageIds={openStageIds}
                    onStageToggle={handleStageToggle}
                />
                <ActivityTimelineNextSteps
                    status={tasksStatus}
                    overdueTasks={overdueTasks}
                    upcomingTasks={upcomingTasks}
                    onRetry={onRetryTasks}
                />
                <ActivityTimelineLinks historyHref={historyHref} notesHref={notesHref} />
            </CardContent>
        </Card>
    )
}
