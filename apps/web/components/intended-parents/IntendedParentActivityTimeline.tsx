"use client"

import { memo, useEffect, useMemo, useRef, useState } from "react"
import { formatDistanceToNow, isBefore, parseISO, startOfToday } from "date-fns"
import {
    ActivityIcon,
    ArrowRightIcon,
    ChevronRightIcon,
    FileTextIcon,
    PaperclipIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"
import type { PipelineStage } from "@/lib/api/pipelines"
import type { TaskListItem } from "@/lib/api/tasks"
import type { Attachment } from "@/lib/api/attachments"
import type { EntityNoteListItem, IntendedParentStatusHistoryItem } from "@/lib/types/intended-parent"
import type { LucideIcon } from "lucide-react"

const VISIBLE_STAGE_RANGE = 2
const MAX_PER_STAGE = 3

interface StageGroup {
    id: string
    label: string
    color: string
    order: number
    date: string | null
    rawDate: string | null
    isCurrent: boolean
    isUpcoming: boolean
    transitionLabel: string | null
    isBackdated: boolean
    activityCount: number
    activities: ActivityItem[]
}

interface ActivityItem {
    id: string
    type: "note_added" | "attachment_added"
    title: string
    preview: string
    relativeDate: string
    timestamp: string
}

interface ActivityTypeConfig {
    icon: LucideIcon
    color: string
    bgColor: string
}

const ACTIVITY_TYPE_CONFIG: Record<ActivityItem["type"], ActivityTypeConfig> = {
    note_added: {
        icon: FileTextIcon,
        color: "bg-blue-500",
        bgColor: "bg-blue-100 dark:bg-blue-900/30",
    },
    attachment_added: {
        icon: PaperclipIcon,
        color: "bg-amber-500",
        bgColor: "bg-amber-100 dark:bg-amber-900/30",
    },
}

function stripHtml(value: string): string {
    return value.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()
}

function getHistoryTimestamp(entry: IntendedParentStatusHistoryItem): string {
    return entry.effective_at ?? entry.changed_at
}

function isBackdatedEntry(entry: IntendedParentStatusHistoryItem): boolean {
    if (!entry.effective_at || !entry.recorded_at) return false
    const effectiveTime = new Date(entry.effective_at).getTime()
    const recordedTime = new Date(entry.recorded_at).getTime()
    return Math.abs(effectiveTime - recordedTime) > 60000
}

function dedupeStageHistory(
    history: IntendedParentStatusHistoryItem[],
): IntendedParentStatusHistoryItem[] {
    const seenStages = new Set<string>()
    const deduped: IntendedParentStatusHistoryItem[] = []

    const sortedHistory = [...history].sort(
        (a, b) =>
            new Date(getHistoryTimestamp(b)).getTime() - new Date(getHistoryTimestamp(a)).getTime(),
    )

    for (const entry of sortedHistory) {
        if (entry.new_stage_id && !seenStages.has(entry.new_stage_id)) {
            seenStages.add(entry.new_stage_id)
            deduped.push(entry)
        }
    }

    return deduped
}

function assignActivityToStage(
    activityTimestamp: string,
    stageHistory: IntendedParentStatusHistoryItem[],
): string | null {
    const sortedHistory = [...stageHistory].sort(
        (a, b) =>
            new Date(getHistoryTimestamp(b)).getTime() - new Date(getHistoryTimestamp(a)).getTime(),
    )

    const activityTime = new Date(activityTimestamp).getTime()

    for (const entry of sortedHistory) {
        const stageEntryTime = new Date(getHistoryTimestamp(entry)).getTime()
        if (activityTime >= stageEntryTime && entry.new_stage_id) {
            return entry.new_stage_id
        }
    }

    return null
}

function getVisibleStages(
    stageGroups: StageGroup[],
    showFullJourney: boolean,
    currentStageId?: string | null,
): StageGroup[] {
    if (showFullJourney) return stageGroups

    const currentIndex = Math.max(
        0,
        stageGroups.findIndex((stage) => stage.id === currentStageId),
    )
    const startIdx = Math.max(0, currentIndex - VISIBLE_STAGE_RANGE)
    const endIdx = Math.min(stageGroups.length, currentIndex + VISIBLE_STAGE_RANGE + 1)
    return stageGroups.slice(startIdx, endIdx)
}

function buildTimelineData(
    stages: PipelineStage[],
    history: IntendedParentStatusHistoryItem[],
    notes: EntityNoteListItem[],
    attachments: Attachment[],
    currentStageId: string,
): StageGroup[] {
    const dedupedHistory = dedupeStageHistory(history)
    const stageEntryMeta = new Map<
        string,
        { entryAt: string; isBackdated: boolean; transitionLabel: string | null }
    >()

    for (const entry of dedupedHistory) {
        if (!entry.new_stage_id) continue
        stageEntryMeta.set(entry.new_stage_id, {
            entryAt: getHistoryTimestamp(entry),
            isBackdated: isBackdatedEntry(entry),
            transitionLabel: entry.old_status
                ? `${entry.old_status.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())} -> ${entry.new_status.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}`
                : null,
        })
    }

    const activitiesByStage = new Map<string, ActivityItem[]>()
    const pushActivity = (stageId: string | null, item: ActivityItem) => {
        if (!stageId) return
        const items = activitiesByStage.get(stageId) || []
        items.push(item)
        activitiesByStage.set(stageId, items)
    }

    for (const note of notes) {
        pushActivity(assignActivityToStage(note.created_at, history), {
            id: note.id,
            type: "note_added",
            title: "Note",
            preview: stripHtml(note.content),
            relativeDate: formatDistanceToNow(new Date(note.created_at), { addSuffix: true }),
            timestamp: note.created_at,
        })
    }

    for (const attachment of attachments) {
        pushActivity(assignActivityToStage(attachment.created_at, history), {
            id: attachment.id,
            type: "attachment_added",
            title: "File uploaded",
            preview: attachment.filename,
            relativeDate: formatDistanceToNow(new Date(attachment.created_at), { addSuffix: true }),
            timestamp: attachment.created_at,
        })
    }

    for (const [, items] of activitiesByStage.entries()) {
        items.sort(
            (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
        )
    }

    const activeStages = stages.filter((stage) => stage.is_active).sort((a, b) => a.order - b.order)

    return activeStages.map((stage) => {
        const allActivities = activitiesByStage.get(stage.id) || []
        const entryMeta = stageEntryMeta.get(stage.id)

        return {
            id: stage.id,
            label: stage.label,
            color: stage.color || "#6b7280",
            order: stage.order,
            date: entryMeta?.entryAt
                ? formatDistanceToNow(new Date(entryMeta.entryAt), { addSuffix: true })
                : null,
            rawDate: entryMeta?.entryAt ?? null,
            isCurrent: stage.id === currentStageId,
            isUpcoming: stage.id !== currentStageId && stage.order > (activeStages.find((item) => item.id === currentStageId)?.order ?? 0),
            transitionLabel: entryMeta?.transitionLabel ?? null,
            isBackdated: entryMeta?.isBackdated ?? false,
            activityCount: allActivities.length,
            activities: allActivities.slice(0, MAX_PER_STAGE),
        }
    })
}

const ActivityRow = memo(function ActivityRow({ item }: { item: ActivityItem }) {
    const config = ACTIVITY_TYPE_CONFIG[item.type]
    const Icon = config.icon

    return (
        <div className="flex items-start gap-3 py-2">
            <div className={cn("w-1 self-stretch rounded-full", config.color)} />
            <div
                className={cn(
                    "size-6 rounded flex items-center justify-center shrink-0",
                    config.bgColor,
                )}
            >
                <Icon className="size-3.5" />
            </div>
            <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{item.title}</div>
                {item.preview ? (
                    <div className="line-clamp-2 text-xs text-muted-foreground">{item.preview}</div>
                ) : null}
            </div>
            <div className="shrink-0 text-xs text-muted-foreground">{item.relativeDate}</div>
        </div>
    )
})

const StageEntryRow = memo(function StageEntryRow({
    entryTitle,
    entryLabel,
    isBackdated,
}: {
    entryTitle: string
    entryLabel?: string | null
    isBackdated: boolean
}) {
    return (
        <div className="flex items-start gap-3 py-2">
            <div className="w-1 self-stretch rounded-full bg-muted-foreground/20" />
            <div className="flex size-6 shrink-0 items-center justify-center rounded bg-muted/60">
                <ArrowRightIcon className="size-3.5 text-muted-foreground" />
            </div>
            <div className="min-w-0 flex-1">
                <div className="text-xs font-medium text-muted-foreground">{entryTitle}</div>
                {isBackdated ? (
                    <div className="text-[11px] text-muted-foreground/70">Backdated entry</div>
                ) : null}
            </div>
            {entryLabel ? <div className="shrink-0 text-xs text-muted-foreground">{entryLabel}</div> : null}
        </div>
    )
})

const TaskRow = memo(function TaskRow({
    task,
    isOverdue = false,
}: {
    task: TaskListItem
    isOverdue?: boolean
}) {
    const dueDate = task.due_date ? parseISO(task.due_date) : null
    let dueLabel = ""
    if (dueDate) {
        const distance = formatDistanceToNow(dueDate, { addSuffix: false })
        dueLabel = isOverdue ? `${distance} overdue` : `due in ${distance}`
    }

    return (
        <div className="flex items-center gap-3 py-1 text-sm">
            <div className={cn("h-4 w-1 rounded-full", isOverdue ? "bg-red-400/60" : "bg-muted-foreground/30")} />
            <span className="flex-1 truncate">{task.title}</span>
            <span className={cn("text-xs", isOverdue ? "text-red-600/80" : "text-muted-foreground")}>
                {dueLabel}
            </span>
        </div>
    )
})

interface IntendedParentActivityTimelineProps {
    currentStageId: string
    stages: PipelineStage[]
    history: IntendedParentStatusHistoryItem[]
    notes?: EntityNoteListItem[]
    attachments?: Attachment[]
    tasks?: TaskListItem[]
}

const EMPTY_NOTES: EntityNoteListItem[] = []
const EMPTY_ATTACHMENTS: Attachment[] = []
const EMPTY_TASKS: TaskListItem[] = []

export function IntendedParentActivityTimeline({
    currentStageId,
    stages,
    history,
    notes = EMPTY_NOTES,
    attachments = EMPTY_ATTACHMENTS,
    tasks = EMPTY_TASKS,
}: IntendedParentActivityTimelineProps) {
    const [showFullJourney, setShowFullJourney] = useState(false)
    const [openStageIds, setOpenStageIds] = useState<Set<string>>(() => new Set())
    const lastDefaultStageKey = useRef<string | null>(null)

    const stageGroups = useMemo(
        () => buildTimelineData(stages, history, notes, attachments, currentStageId),
        [stages, history, notes, attachments, currentStageId],
    )

    const visibleStages = useMemo(
        () => getVisibleStages(stageGroups, showFullJourney, currentStageId),
        [stageGroups, showFullJourney, currentStageId],
    )

    const hasCurrentStage = useMemo(
        () => stageGroups.some((stage) => stage.id === currentStageId),
        [stageGroups, currentStageId],
    )

    useEffect(() => {
        const defaultStageKey = hasCurrentStage ? currentStageId : `missing:${currentStageId}`
        if (lastDefaultStageKey.current === defaultStageKey) return
        lastDefaultStageKey.current = defaultStageKey
        setOpenStageIds(hasCurrentStage ? new Set([currentStageId]) : new Set())
    }, [currentStageId, hasCurrentStage])

    const { overdueTasks, upcomingTasks } = useMemo(() => {
        const today = startOfToday()
        const pending = tasks
            .filter((task) => !task.is_completed && task.due_date)
            .map((task) => ({ task, dueDate: parseISO(task.due_date as string) }))
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
        setOpenStageIds((previous) => {
            const next = new Set(previous)
            if (isOpen) next.add(stageId)
            else next.delete(stageId)
            return next
        })
    }

    return (
        <Card className="gap-4 py-4">
            <CardHeader className="px-4 pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <ActivityIcon className="size-4" />
                        Activity
                    </CardTitle>
                    {stageGroups.length > 5 ? (
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs"
                            onClick={() => setShowFullJourney(!showFullJourney)}
                        >
                            {showFullJourney ? "Collapse journey" : "Show full journey"}
                        </Button>
                    ) : null}
                </div>
            </CardHeader>
            <CardContent className="space-y-4 px-4">
                <div className="space-y-0">
                    {visibleStages.map((stage) => {
                        const hasContent = stage.activityCount > 0 || stage.isBackdated || stage.isCurrent
                        const showStageEntryRow =
                            !!stage.rawDate &&
                            (stage.isBackdated || stage.activityCount > 0 || stage.isCurrent)

                        if (!hasContent && !stage.isCurrent) {
                            return (
                                <div key={stage.id} className="flex items-center gap-2 py-1.5 pl-5">
                                    <div
                                        className={cn(
                                            "size-2 rounded-full",
                                            stage.isUpcoming && "bg-muted-foreground/30",
                                        )}
                                        style={
                                            !stage.isUpcoming ? { backgroundColor: stage.color } : undefined
                                        }
                                    />
                                    <span className="text-sm text-muted-foreground">{stage.label}</span>
                                </div>
                            )
                        }

                        return (
                            <Collapsible
                                key={stage.id}
                                open={openStageIds.has(stage.id)}
                                onOpenChange={(open) => handleStageToggle(stage.id, open)}
                            >
                                <CollapsibleTrigger className="group flex w-full items-center gap-2 rounded py-2 text-left hover:bg-muted/50">
                                    <ChevronRightIcon className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
                                    <div
                                        className={cn(
                                            "rounded-full",
                                            stage.isCurrent ? "size-2.5" : "size-2",
                                            stage.isUpcoming && "bg-muted-foreground/30",
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
                                            !stage.isCurrent && "text-muted-foreground",
                                        )}
                                    >
                                        {stage.label}
                                    </span>
                                    {stage.activityCount > 0 ? (
                                        <Badge variant="secondary" className="text-xs">
                                            {stage.activityCount}
                                        </Badge>
                                    ) : null}
                                    {!stage.isUpcoming ? (
                                        <span className="ml-auto text-xs text-muted-foreground">
                                            {stage.date || "—"}
                                        </span>
                                    ) : null}
                                </CollapsibleTrigger>

                                <CollapsibleContent>
                                    <div className="ml-6 border-l border-border/50 pl-4">
                                        {showStageEntryRow && stage.date ? (
                                            <StageEntryRow
                                                entryTitle="Entered stage"
                                                entryLabel={stage.date}
                                                isBackdated={stage.isBackdated}
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

                {(overdueTasks.length > 0 || upcomingTasks.length > 0) ? (
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
                ) : null}
            </CardContent>
        </Card>
    )
}
