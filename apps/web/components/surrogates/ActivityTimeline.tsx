"use client"

import { memo, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
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
    UserPlusIcon,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Button } from "@/components/ui/button"
import { useSurrogateHistory } from "@/lib/hooks/use-surrogates"
import type { SurrogateActivity, SurrogateStatusHistory } from "@/lib/api/surrogates"
import type { PipelineStage } from "@/lib/api/pipelines"
import type { TaskListItem } from "@/lib/types/task"
import type { LucideIcon } from "lucide-react"
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
    timestamp: string
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
    contact_attempt: { icon: PhoneIcon, color: "bg-cyan-500", bgColor: "bg-cyan-100 dark:bg-cyan-900/30", label: "Contact attempt" },
    note_added: { icon: FileTextIcon, color: "bg-blue-500", bgColor: "bg-blue-100 dark:bg-blue-900/30", label: "Note" },
    note_deleted: { icon: FileTextIcon, color: "bg-blue-400", bgColor: "bg-blue-100 dark:bg-blue-900/30", label: "Note deleted" },
    task_created: { icon: PlusCircleIcon, color: "bg-green-500", bgColor: "bg-green-100 dark:bg-green-900/30", label: "Task created" },
    task_deleted: { icon: TrashIcon, color: "bg-red-400", bgColor: "bg-red-100 dark:bg-red-900/30", label: "Task deleted" },
    attachment_added: { icon: PaperclipIcon, color: "bg-amber-500", bgColor: "bg-amber-100 dark:bg-amber-900/30", label: "File uploaded" },
    attachment_deleted: { icon: PaperclipIcon, color: "bg-amber-400", bgColor: "bg-amber-100 dark:bg-amber-900/30", label: "File removed" },
    // Other known types
    info_edited: { icon: EditIcon, color: "bg-gray-400", bgColor: "bg-gray-100 dark:bg-gray-900/30", label: "Info updated" },
    priority_changed: { icon: FlagIcon, color: "bg-gray-400", bgColor: "bg-gray-100 dark:bg-gray-900/30", label: "Priority changed" },
    assigned: { icon: UserPlusIcon, color: "bg-gray-400", bgColor: "bg-gray-100 dark:bg-gray-900/30", label: "Assigned" },
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

function getActivityPreview(activity: SurrogateActivity): string {
    const details = activity.details as Record<string, unknown> | null
    const type = activity.activity_type

    if (!details) return ""

    switch (type) {
        case "email_sent":
            return (
                (details.subject as string) ||
                (details.preview as string) ||
                (details.provider as string ? `via ${details.provider as string}` : "")
            )
        case "contact_attempt":
            return [
                details.outcome as string | undefined,
                Array.isArray(details.contact_methods)
                    ? (details.contact_methods as string[]).join(", ")
                    : undefined,
            ]
                .filter(Boolean)
                .join(" • ")
        case "attachment_added":
            return (details.filename as string) || "File uploaded"
        case "attachment_deleted":
            return (details.filename as string) || "File removed"
        case "note_added":
        case "note_deleted":
            return (details.preview as string) || ""
        case "task_created":
        case "task_deleted":
            return (details.title as string) || ""
        default:
            return ""
    }
}

function getActivityTitle(activity: SurrogateActivity): string {
    const config = getActivityConfig(activity.activity_type)
    return config.label
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

    const sortedHistory = [...history].sort(
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

function assignActivityToStage(
    activity: SurrogateActivity,
    stageHistory: SurrogateStatusHistory[]
): string | null {
    // Sort history by entry timestamp DESC (most recent first)
    const sortedHistory = [...stageHistory].sort(
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

// ============================================================================
// Windowing Logic
// ============================================================================

function getCurrentStageIndex(stageGroups: StageGroup[]): number {
    const idx = stageGroups.findIndex((s) => s.isCurrent)
    return idx >= 0 ? idx : 0 // Safe fallback to first stage
}

function getVisibleStages(stageGroups: StageGroup[], showFullJourney: boolean): StageGroup[] {
    if (showFullJourney) return stageGroups

    const currentIdx = getCurrentStageIndex(stageGroups)
    // Clamp at edges: show fewer than 5 when near start/end
    const startIdx = Math.max(0, currentIdx - VISIBLE_STAGE_RANGE)
    const endIdx = Math.min(stageGroups.length, currentIdx + VISIBLE_STAGE_RANGE + 1)
    return stageGroups.slice(startIdx, endIdx)
}

// ============================================================================
// Data Transformation
// ============================================================================

function buildTimelineData(
    allPipelineStages: PipelineStage[],
    stageHistory: SurrogateStatusHistory[],
    activities: SurrogateActivity[],
    currentStageId: string
): { stageGroups: StageGroup[] } {
    // 1. Filter: ignore status_changed activity types (duplicates stage history)
    const filteredActivities = activities.filter(
        (a) => !IGNORED_ACTIVITY_TYPES.includes(a.activity_type)
    )

    // 2. Dedupe stage history (handle regressions - show most recent entry per stage)
    const dedupedHistory = dedupeStageHistory(stageHistory)

    // 3. Build a map of stage ID -> entry metadata
    const stageEntryMeta = new Map<
        string,
        { entryAt: string; isBackdated: boolean }
    >()
    for (const entry of dedupedHistory) {
        if (entry.to_stage_id) {
            stageEntryMeta.set(entry.to_stage_id, {
                entryAt: getEntryTimestamp(entry),
                isBackdated: isBackdatedEntry(entry),
            })
        }
    }

    // 4. Assign activities to stages
    const activitiesByStage = new Map<string, ActivityItem[]>()
    for (const activity of filteredActivities) {
        const stageId = assignActivityToStage(activity, stageHistory)
        const item = {
            id: activity.id,
            type: activity.activity_type,
            title: getActivityTitle(activity),
            preview: getActivityPreview(activity),
            relativeDate: formatDistanceToNow(new Date(activity.created_at), { addSuffix: true }),
            timestamp: activity.created_at,
        }
        if (!stageId) continue
        const items = activitiesByStage.get(stageId) || []
        items.push(item)
        activitiesByStage.set(stageId, items)
    }

    // 5. Sort activities within each stage by timestamp DESC
    for (const [, items] of activitiesByStage.entries()) {
        items.sort((a, b) => {
            const diff = new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
            return diff !== 0 ? diff : a.id.localeCompare(b.id)
        })
    }

    // 6. Find current stage order for completed/upcoming detection
    const activeStages = allPipelineStages
        .filter((s) => s.is_active)
        .sort((a, b) => a.order - b.order)
    const currentStage = activeStages.find((s) => s.id === currentStageId)
    const currentStageOrder = currentStage?.order ?? 0

    // 7. Create StageGroup for ALL pipeline stages (preserve full story)
    const displayStages = activeStages.filter(
        (stage) => stage.stage_type !== "terminal" && !["lost", "disqualified"].includes(stage.slug)
    )
    const stageGroups: StageGroup[] = displayStages.map((stage) => {
        const allActivities = activitiesByStage.get(stage.id) || []
        const entryMeta = stageEntryMeta.get(stage.id)
        const entryAt = entryMeta?.entryAt || null

        return {
            id: stage.id,
            label: stage.label,
            color: stage.color || "#6b7280", // Fallback to gray if no color
            order: stage.order,
            date: entryAt ? formatDistanceToNow(new Date(entryAt), { addSuffix: true }) : null,
            rawDate: entryAt,
            isCurrent: stage.id === currentStageId,
            isCompleted: stage.order < currentStageOrder,
            isUpcoming: stage.order > currentStageOrder,
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

const ActivityRow = memo(function ActivityRow({ item }: { item: ActivityItem }) {
    const config = getActivityConfig(item.type)
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
                <div className="text-sm font-medium truncate">{item.title}</div>
                {item.preview && (
                    <div className="text-xs text-muted-foreground line-clamp-2">{item.preview}</div>
                )}
            </div>
            <div className="text-xs text-muted-foreground shrink-0">{item.relativeDate}</div>
        </div>
    )
})

const StageEntryRow = memo(function StageEntryRow({
    entryLabel,
    isBackdated,
}: {
    entryLabel: string
    isBackdated: boolean
}) {
    return (
        <div className="flex items-start gap-3 py-2">
            <div className="w-1 self-stretch rounded-full bg-muted-foreground/20" />
            <div className="size-6 rounded flex items-center justify-center shrink-0 bg-muted/60">
                <ArrowRightIcon className="size-3.5 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-muted-foreground">Entered stage</div>
                {isBackdated && (
                    <div className="text-[11px] text-muted-foreground/70">
                        Backdated entry
                    </div>
                )}
            </div>
            <div className="text-xs text-muted-foreground shrink-0">{entryLabel}</div>
        </div>
    )
})

// ============================================================================
// Task Row Component
// ============================================================================

const TaskRow = memo(function TaskRow({ task, isOverdue = false }: { task: TaskListItem; isOverdue?: boolean }) {
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
})

// ============================================================================
// Main Component
// ============================================================================

interface ActivityTimelineProps {
    surrogateId: string
    currentStageId: string
    stages: PipelineStage[]
    activities?: SurrogateActivity[]
    tasks?: TaskListItem[]
}

export function ActivityTimeline({
    surrogateId,
    currentStageId,
    stages,
    activities = [],
    tasks = [],
}: ActivityTimelineProps) {
    const [showFullJourney, setShowFullJourney] = useState(false)
    const [openStageIds, setOpenStageIds] = useState<Set<string>>(() => new Set())
    const prevShowFullJourney = useRef(showFullJourney)

    // Fetch stage history
    const { data: stageHistory = [] } = useSurrogateHistory(surrogateId)

    // Memoize timeline building
    const { stageGroups } = useMemo(
        () => buildTimelineData(stages, stageHistory, activities, currentStageId),
        [stages, stageHistory, activities, currentStageId]
    )

    // Apply windowing
    const visibleStages = useMemo(
        () => getVisibleStages(stageGroups, showFullJourney),
        [stageGroups, showFullJourney]
    )

    const autoOpenStageIds = useMemo(
        () =>
            stageGroups
                .filter(
                    (stage) =>
                        (stage.isCurrent && stage.activityCount > 0) || stage.isBackdated
                )
                .map((stage) => stage.id),
        [stageGroups]
    )

    useEffect(() => {
        if (openStageIds.size === 0 && autoOpenStageIds.length > 0) {
            setOpenStageIds(new Set(autoOpenStageIds))
        }
    }, [autoOpenStageIds, openStageIds.size])

    useEffect(() => {
        const toggled = prevShowFullJourney.current !== showFullJourney
        prevShowFullJourney.current = showFullJourney
        if (!toggled) return
        setOpenStageIds(new Set(autoOpenStageIds))
    }, [showFullJourney, autoOpenStageIds])

    // Task categorization
    const { overdueTasks, upcomingTasks } = useMemo(() => {
        const today = startOfToday()
        const pending = tasks
            .filter((task) => !task.is_completed && task.due_date)
            .map((task) => ({
                task,
                dueDate: parseISO(task.due_date as string),
            }))
            .filter((entry) => !Number.isNaN(entry.dueDate.getTime()))

        const overdue = pending.filter((entry) => isBefore(entry.dueDate, today))
        const upcoming = pending.filter((entry) => !isBefore(entry.dueDate, today))

        const sortByDueDate = (a: { dueDate: Date }, b: { dueDate: Date }) =>
            a.dueDate.getTime() - b.dueDate.getTime()

        return {
            overdueTasks: overdue.sort(sortByDueDate).map((entry) => entry.task).slice(0, 3),
            upcomingTasks: upcoming.sort(sortByDueDate).map((entry) => entry.task).slice(0, 3),
        }
    }, [tasks])

    function handleStageToggle(stageId: string, isOpen: boolean) {
        setOpenStageIds((prev) => {
            const next = new Set(prev)
            if (isOpen) {
                next.add(stageId)
            } else {
                next.delete(stageId)
            }
            return next
        })
    }

    return (
        <Card className="gap-4 py-4">
            <CardHeader className="px-4 pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-base flex items-center gap-2">
                        <ActivityIcon className="size-4" />
                        Activity
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
                {/* Stage Timeline */}
                <div className="space-y-0">
                    {visibleStages.map((stage) => {
                        // hasContent = has activity OR is backdated (backdated stages always get full row)
                        const hasContent = stage.activityCount > 0 || stage.isBackdated
                        // Show stage entry row when backdated or has activities
                        const showStageEntryRow =
                            !!stage.rawDate && (stage.isBackdated || stage.activityCount > 0)

                        // Empty non-current stages without content: minimal row (no chevron, no timestamp)
                        if (!hasContent && !stage.isCurrent) {
                            return (
                                <div
                                    key={stage.id}
                                    className="flex items-center gap-2 py-1.5 pl-5"
                                >
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
                                    <span className="text-sm text-muted-foreground">
                                        {stage.label}
                                    </span>
                                </div>
                            )
                        }

                        // Full collapsible row (current stage, has activity, or backdated)
                        return (
                            <Collapsible
                                key={stage.id}
                                open={openStageIds.has(stage.id)}
                                onOpenChange={(open) => handleStageToggle(stage.id, open)}
                            >
                                {/* Stage Header */}
                                <CollapsibleTrigger className="group flex items-center gap-2 w-full py-2 hover:bg-muted/50 rounded text-left">
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
                                    <span
                                        className={cn(
                                            "text-sm font-medium",
                                            !stage.isCurrent && "text-muted-foreground"
                                        )}
                                    >
                                        {stage.label}
                                    </span>
                                    {stage.activityCount > 0 && (
                                        <Badge variant="secondary" className="text-xs">
                                            {stage.activityCount}
                                        </Badge>
                                    )}
                                    {!stage.isUpcoming && (
                                        <span className="text-xs text-muted-foreground ml-auto">
                                            {stage.date || "—"}
                                        </span>
                                    )}
                                </CollapsibleTrigger>

                                {/* Stage Details */}
                                <CollapsibleContent>
                                    <div className="ml-6 pl-4 border-l border-border/50">
                                        {showStageEntryRow && (
                                            <StageEntryRow
                                                entryLabel={stage.date as string}
                                                isBackdated={stage.isBackdated}
                                            />
                                        )}
                                        {stage.activities.length > 0 ? (
                                            stage.activities.map((item) => (
                                                <ActivityRow key={item.id} item={item} />
                                            ))
                                        ) : (
                                            !showStageEntryRow && (
                                                <div className="py-2 text-xs text-muted-foreground/60 italic">
                                                    No activity in this stage.
                                                </div>
                                            )
                                        )}
                                    </div>
                                </CollapsibleContent>
                            </Collapsible>
                        )
                    })}
                </div>

                {/* Next Steps Section */}
                {(overdueTasks.length > 0 || upcomingTasks.length > 0) && (
                    <>
                        <div className="text-xs font-medium text-muted-foreground flex items-center gap-2">
                            Next Steps
                            <div className="flex-1 border-t border-dashed border-border/50" />
                        </div>
                        <div className="space-y-3">
                            {/* Overdue subsection */}
                            {overdueTasks.length > 0 && (
                                <div className="space-y-1">
                                    <span className="text-xs font-medium text-red-600">
                                        Overdue
                                    </span>
                                    {overdueTasks.map((task) => (
                                        <TaskRow key={task.id} task={task} isOverdue />
                                    ))}
                                </div>
                            )}

                            {/* Upcoming subsection */}
                            {upcomingTasks.length > 0 && (
                                <div className="space-y-1">
                                    <span className="text-xs font-medium text-muted-foreground">
                                        Upcoming
                                    </span>
                                    {upcomingTasks.map((task) => (
                                        <TaskRow key={task.id} task={task} />
                                    ))}
                                </div>
                            )}
                        </div>
                    </>
                )}

                {/* Deep links to relevant tabs */}
                <div className="flex gap-3 pt-2">
                    <Link
                        href={`/surrogates/${surrogateId}?tab=history`}
                        className="text-xs text-primary hover:underline underline-offset-4"
                    >
                        View full history &rarr;
                    </Link>
                    <Link
                        href={`/surrogates/${surrogateId}?tab=notes`}
                        className="text-xs text-primary hover:underline underline-offset-4"
                    >
                        Notes &amp; Attachments &rarr;
                    </Link>
                </div>
            </CardContent>
        </Card>
    )
}
