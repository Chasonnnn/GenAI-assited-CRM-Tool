"use client"

import { format } from "date-fns"
import { CheckSquareIcon, CircleCheckIcon, Loader2Icon, XIcon } from "lucide-react"

import { EmptyState } from "@/components/empty-state"
import { TaskRelatedRecordLinks } from "@/components/tasks/TaskRelatedRecordLinks"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { EmptyValue } from "@/components/ui/empty-value"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { getTaskTypeLabel, type TaskStatusFilter } from "@/lib/task-labels"
import type { TaskListItem } from "@/lib/types/task"
import { cn } from "@/lib/utils"
import { parseDateInput } from "@/lib/utils/date"
import {
    categoryColors,
    categoryLabels,
    compareTasksByDueTime,
    getDueCategory,
    type DueCategory,
} from "@/lib/utils/task-due"

type TasksListViewProps = {
    status: TaskStatusFilter
    incompleteTasks: TaskListItem[]
    completedTasks: TaskListItem[]
    completedTotal: number
    loadingCompleted: boolean
    completedError: boolean
    onRetryCompleted: () => void
    selectedTaskIds: Set<string>
    onTaskToggle: (taskId: string, isCompleted: boolean) => void
    onTaskClick: (task: TaskListItem) => void
    onSelectTask: (taskId: string, selected: boolean) => void
    onSelectAll: (selected: boolean) => void
    onBulkCompleteSelected: () => void
    bulkCompletePending: boolean
    /** Set while search or filters are active; the empty state then offers Clear filters. */
    onClearFilters: (() => void) | null
}

const TASK_DUE_SECTION_ORDER: DueCategory[] = ["overdue", "today", "tomorrow", "this-week", "later", "no-date"]

// One template for the header, open rows and completed rows: select, complete, task, type, due, owner.
// Below sm the type and owner columns drop out and the due text stays on the right.
const TASK_ROW_GRID =
    "grid grid-cols-[16px_18px_minmax(0,1fr)_auto] items-center gap-x-3 sm:grid-cols-[16px_18px_minmax(0,1fr)_88px_170px_28px]"

const EMPTY_TITLES: Record<TaskStatusFilter, string> = {
    open: "No open tasks",
    completed: "No completed tasks",
    all: "No tasks",
}

function formatDueTime(dueTime: string): string {
    const [hours = 0, minutes = 0] = dueTime.split(":").map(Number)
    return format(new Date(2000, 0, 1, hours, minutes), "h:mm a")
}

/**
 * Due text for a row. Inside the Today and Tomorrow sections the heading carries the day, so the
 * row shows the time; elsewhere it shows the weekday and date, plus the time when set.
 */
function formatTaskDue(task: TaskListItem, section: DueCategory | null): string | null {
    if (!task.due_date) return null
    const time = task.due_time ? formatDueTime(task.due_time) : null
    if (section === "today" || section === "tomorrow") return time ?? categoryLabels[section]
    const date = parseDateInput(task.due_date)
    const dateLabel = format(date, date.getFullYear() === new Date().getFullYear() ? "EEE, MMM d" : "EEE, MMM d, yyyy")
    return time ? `${dateLabel} · ${time}` : dateLabel
}

function getInitials(name: string | null): string {
    if (!name) return "?"
    return name
        .split(" ")
        .map((part) => part[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
}

type TaskRowHandlers = {
    onTaskToggle: (taskId: string, isCompleted: boolean) => void
    onTaskClick: (task: TaskListItem) => void
    onSelectTask: (taskId: string, selected: boolean) => void
}

type TaskListItemRowProps = TaskRowHandlers & {
    task: TaskListItem
    /** Due section the row sits in; null for completed rows. */
    section: DueCategory | null
    isSelected: boolean
    selectionActive: boolean
}

function TaskListItemRow({
    task,
    section,
    isSelected,
    selectionActive,
    onTaskToggle,
    onTaskClick,
    onSelectTask,
}: TaskListItemRowProps) {
    const dueLabel = formatTaskDue(task, section)
    const isOverdue = !task.is_completed && section === "overdue"

    return (
        <div
            data-testid="task-row"
            className={cn(
                TASK_ROW_GRID,
                "group/task-row rounded-lg border border-border bg-card px-3 py-2.5 transition-colors hover:bg-accent/50",
                isSelected && "border-primary/30 bg-primary/5",
                task.is_completed && "opacity-60",
            )}
        >
            {task.is_completed ? (
                <span aria-hidden="true" />
            ) : (
                <Checkbox
                    aria-label={`Select task ${task.title}`}
                    checked={isSelected}
                    onCheckedChange={(checked) => onSelectTask(task.id, checked === true)}
                    // Hidden until hover or focus so it does not read as a second completion box;
                    // always shown once a selection exists and on touch screens.
                    className={cn(
                        "transition-opacity",
                        !selectionActive &&
                            "opacity-0 group-hover/task-row:opacity-100 focus-visible:opacity-100 [@media(hover:none)]:opacity-100",
                    )}
                />
            )}
            <Checkbox
                aria-label={
                    task.is_completed
                        ? `Mark task ${task.title} incomplete`
                        : `Mark task ${task.title} complete`
                }
                checked={task.is_completed}
                onCheckedChange={() => onTaskToggle(task.id, task.is_completed)}
                className="size-[18px] rounded-full border-muted-foreground/60"
            />
            <div className="min-w-0 space-y-0.5">
                <Button unstyled
                    type="button"
                    className="w-full rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    onClick={() => onTaskClick(task)}
                    aria-label={`Open task ${task.title}`}
                >
                    <span
                        className={cn(
                            "block break-words font-medium [overflow-wrap:anywhere]",
                            task.is_completed && "line-through",
                        )}
                    >
                        {task.title}
                    </span>
                </Button>
                <TaskRelatedRecordLinks
                    task={task}
                    className="text-sm text-muted-foreground"
                />
            </div>
            <span className="hidden truncate text-sm text-muted-foreground sm:block">
                {getTaskTypeLabel(task.task_type)}
            </span>
            <span
                className={cn(
                    // Below sm the due text wraps in a narrow column so the title keeps most of the row.
                    "max-w-24 text-right text-xs tabular-nums sm:max-w-none sm:whitespace-nowrap sm:text-sm",
                    isOverdue && "font-medium text-destructive",
                )}
            >
                {dueLabel ?? <EmptyValue label="No due date" />}
            </span>
            <span className="hidden justify-end sm:flex">
                {task.owner_name ? (
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger aria-label={`Assigned to ${task.owner_name}`}>
                                <Avatar className="size-7">
                                    <AvatarFallback className="text-xs">{getInitials(task.owner_name)}</AvatarFallback>
                                </Avatar>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p>{task.owner_name}</p>
                            </TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                ) : null}
            </span>
        </div>
    )
}

function TaskSectionHeading({
    id,
    label,
    count,
    className,
    lineClassName = "bg-border",
}: {
    id: string
    label: string
    count: number
    className?: string
    lineClassName?: string
}) {
    return (
        <div className="flex items-center gap-3">
            <div className={cn("h-px flex-1", lineClassName)} />
            <h3 id={`${id}-heading`} className={cn("text-sm font-medium", className)}>
                {label} ({count})
            </h3>
            <div className={cn("h-px flex-1", lineClassName)} />
        </div>
    )
}

type TaskDueSectionProps = TaskRowHandlers & {
    category: DueCategory
    tasks: TaskListItem[]
    selectedTaskIds: Set<string>
}

function TaskDueSection({
    category,
    tasks,
    selectedTaskIds,
    ...handlers
}: TaskDueSectionProps) {
    if (tasks.length === 0) return null

    return (
        <section id={`tasks-${category}`} aria-labelledby={`tasks-${category}-heading`} className="space-y-2">
            <TaskSectionHeading
                id={`tasks-${category}`}
                label={categoryLabels[category]}
                count={tasks.length}
                className={categoryColors[category].text}
                lineClassName={category === "overdue" ? "bg-destructive" : "bg-border"}
            />
            {tasks.map((task) => (
                <TaskListItemRow
                    key={task.id}
                    task={task}
                    section={category}
                    isSelected={selectedTaskIds.has(task.id)}
                    selectionActive={selectedTaskIds.size > 0}
                    {...handlers}
                />
            ))}
        </section>
    )
}

export function TasksListView({
    status,
    incompleteTasks,
    completedTasks,
    completedTotal,
    loadingCompleted,
    completedError,
    onRetryCompleted,
    selectedTaskIds,
    onTaskToggle,
    onTaskClick,
    onSelectTask,
    onSelectAll,
    onBulkCompleteSelected,
    bulkCompletePending,
    onClearFilters,
}: TasksListViewProps) {
    const showOpen = status !== "completed"
    const showCompleted = status !== "open"
    const openTasks = showOpen ? incompleteTasks : []
    const handlers = { onTaskToggle, onTaskClick, onSelectTask }

    const groupedTasks: Record<DueCategory, TaskListItem[]> = {
        overdue: [],
        today: [],
        tomorrow: [],
        "this-week": [],
        later: [],
        "no-date": [],
    }
    let selectedCount = 0
    // The API returns this order too; sorting here keeps sections stable while an older API is deployed.
    for (const task of openTasks.toSorted(compareTasksByDueTime)) {
        groupedTasks[getDueCategory(task)].push(task)
        if (selectedTaskIds.has(task.id)) selectedCount += 1
    }
    const allVisibleSelected = openTasks.length > 0 && selectedCount === openTasks.length

    const completedSettled = !showCompleted || (!loadingCompleted && !completedError)
    const isEmpty = openTasks.length === 0 && completedSettled && (!showCompleted || completedTasks.length === 0)

    if (isEmpty) {
        return (
            <Card id="tasks-list">
                {onClearFilters ? (
                    <EmptyState icon={CheckSquareIcon} title="No matching tasks" onClearFilters={onClearFilters} />
                ) : (
                    <EmptyState icon={CheckSquareIcon} title={EMPTY_TITLES[status]} />
                )}
            </Card>
        )
    }

    return (
        <Card id="tasks-list" className="gap-0 p-4 sm:p-6">
            <div className="space-y-4">
                <div className={cn(TASK_ROW_GRID, "hidden px-3 text-xs font-medium text-muted-foreground sm:grid")}>
                    {openTasks.length > 0 ? (
                        <Checkbox
                            aria-label="Select all visible tasks"
                            checked={allVisibleSelected}
                            indeterminate={selectedCount > 0 && !allVisibleSelected}
                            onCheckedChange={(checked) => onSelectAll(checked === true)}
                        />
                    ) : (
                        <span />
                    )}
                    <span />
                    <span>Task</span>
                    <span>Type</span>
                    <span className="text-right">Due</span>
                    <span />
                </div>

                {TASK_DUE_SECTION_ORDER.map((category) => (
                    <TaskDueSection
                        key={category}
                        category={category}
                        tasks={groupedTasks[category]}
                        selectedTaskIds={selectedTaskIds}
                        {...handlers}
                    />
                ))}

                {showCompleted ? (
                    <section id="tasks-completed" aria-labelledby="tasks-completed-heading" className="space-y-2">
                        <TaskSectionHeading
                            id="tasks-completed"
                            label="Completed"
                            count={completedTotal}
                            className="text-muted-foreground"
                        />
                        {loadingCompleted ? (
                            <div role="status" className="flex items-center justify-center gap-2 py-4 text-sm text-muted-foreground">
                                <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                                Loading completed tasks…
                            </div>
                        ) : completedError ? (
                            <div className="flex flex-col items-center gap-2 py-4">
                                <p role="alert" className="text-sm text-destructive">Unable to load completed tasks</p>
                                <Button variant="outline" size="sm" onClick={onRetryCompleted}>
                                    Retry
                                </Button>
                            </div>
                        ) : (
                            completedTasks.map((task) => (
                                <TaskListItemRow
                                    key={task.id}
                                    task={task}
                                    section={null}
                                    isSelected={false}
                                    selectionActive={false}
                                    {...handlers}
                                />
                            ))
                        )}
                    </section>
                ) : null}
            </div>

            {selectedCount > 0 ? (
                <div
                    role="toolbar"
                    aria-label="Selected tasks"
                    className="sticky bottom-4 z-20 mx-auto mt-4 flex w-fit max-w-full flex-wrap items-center justify-center gap-x-4 gap-y-2 rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground shadow-lg"
                >
                    <span className="font-medium" aria-live="polite">
                        {selectedCount} {selectedCount === 1 ? "task" : "tasks"} selected
                    </span>
                    <span aria-hidden="true" className="h-4 w-px bg-primary-foreground/30" />
                    <Button
                        size="sm"
                        variant="secondary"
                        disabled={bulkCompletePending}
                        onClick={onBulkCompleteSelected}
                    >
                        {bulkCompletePending ? (
                            <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                        ) : (
                            <CircleCheckIcon className="size-4" aria-hidden="true" />
                        )}
                        {bulkCompletePending ? "Completing…" : "Complete"}
                    </Button>
                    <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onSelectAll(false)}
                        disabled={bulkCompletePending}
                        className="text-primary-foreground hover:bg-primary-foreground/10 hover:text-primary-foreground"
                    >
                        <XIcon className="size-4" aria-hidden="true" />
                        Clear
                    </Button>
                </div>
            ) : null}
        </Card>
    )
}
