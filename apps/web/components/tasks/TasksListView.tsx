"use client"

import Link from "@/components/app-link"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import type { TaskListItem } from "@/lib/types/task"
import { categoryColors, categoryLabels, getDueCategory, type DueCategory } from "@/lib/utils/task-due"
import { cn } from "@/lib/utils"
import { Loader2Icon } from "lucide-react"

type TasksListViewProps = {
    incompleteTasks: TaskListItem[]
    completedTasks: { items: TaskListItem[]; total?: number } | null
    selectedTaskIds: Set<string>
    showCompleted: boolean
    loadingCompleted: boolean
    completedError: boolean
    onToggleShowCompleted: () => void
    onTaskToggle: (taskId: string, isCompleted: boolean) => void
    onTaskClick: (task: TaskListItem) => void
    onSelectTask: (taskId: string, selected: boolean) => void
    onSelectAll: (selected: boolean) => void
    onBulkCompleteSelected: () => void
    bulkCompletePending: boolean
}

const TASK_DUE_SECTION_ORDER: DueCategory[] = ["overdue", "today", "tomorrow", "this-week", "later", "no-date"]

function getInitials(name: string | null): string {
    if (!name) return "?"
    return name
        .split(" ")
        .map((part) => part[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
}

type TaskListItemRowProps = {
    task: TaskListItem
    showCategory?: boolean
    selectedTaskIds: Set<string>
    onTaskToggle: (taskId: string, isCompleted: boolean) => void
    onTaskClick: (task: TaskListItem) => void
    onSelectTask: (taskId: string, selected: boolean) => void
}

function TaskListItemRow({
    task,
    showCategory = true,
    selectedTaskIds,
    onTaskToggle,
    onTaskClick,
    onSelectTask,
}: TaskListItemRowProps) {
    const category = getDueCategory(task)
    const colors = categoryColors[category]
    const isSelected = selectedTaskIds.has(task.id)

    return (
        <div
            className={`flex min-w-0 items-start gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-accent/50 ${
                task.is_completed ? "opacity-60" : ""
            }`}
        >
            {!task.is_completed && (
                <div>
                    <Checkbox
                        className="mt-0.5"
                        aria-label={`Select task ${task.title}`}
                        checked={isSelected}
                        onCheckedChange={(checked) => onSelectTask(task.id, checked === true)}
                    />
                </div>
            )}
            <div>
                <Checkbox
                    className="mt-0.5"
                    aria-label={
                        task.is_completed
                            ? `Mark task ${task.title} incomplete`
                            : `Mark task ${task.title} complete`
                    }
                    checked={task.is_completed}
                    onCheckedChange={() => onTaskToggle(task.id, task.is_completed)}
                />
            </div>
            <div className="min-w-0 flex-1 space-y-1">
                <Button unstyled
                    type="button"
                    className="w-full rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    onClick={() => onTaskClick(task)}
                    aria-label={`Open task ${task.title}`}
                >
                    <div className="flex min-w-0 items-center gap-2">
                        <span
                            className={cn(
                                "min-w-0 flex-1 break-words font-medium",
                                task.is_completed && "line-through",
                            )}
                        >
                            {task.title}
                        </span>
                        {showCategory && !task.is_completed && (
                            <Badge variant="secondary" className={colors.badge}>
                                {categoryLabels[category]}
                            </Badge>
                        )}
                    </div>
                </Button>
                {task.surrogate_id && (
                    <Link
                        href={`/surrogates/${task.surrogate_id}`}
                        className="text-sm text-muted-foreground hover:underline"
                    >
                        Surrogate #{task.surrogate_number}
                    </Link>
                )}
            </div>
            {task.owner_name && (
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger aria-label={`Assigned to ${task.owner_name}`}>
                            <Avatar className="size-8">
                                <AvatarFallback>{getInitials(task.owner_name)}</AvatarFallback>
                            </Avatar>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>{task.owner_name}</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>
            )}
        </div>
    )
}

type TaskDueSectionProps = {
    category: DueCategory
    tasks: TaskListItem[]
    selectedTaskIds: Set<string>
    onTaskToggle: (taskId: string, isCompleted: boolean) => void
    onTaskClick: (task: TaskListItem) => void
    onSelectTask: (taskId: string, selected: boolean) => void
}

function TaskDueSection({
    category,
    tasks,
    selectedTaskIds,
    onTaskToggle,
    onTaskClick,
    onSelectTask,
}: TaskDueSectionProps) {
    if (tasks.length === 0) return null
    const colors = categoryColors[category]

    return (
        <div id={`tasks-${category}`} className="space-y-3">
            <div className="flex items-center gap-3">
                <div
                    className={`h-px flex-1 ${
                        category === "overdue" ? "bg-destructive" : "bg-border"
                    }`}
                />
                <h3 className={`text-sm font-medium ${colors.text}`}>
                    {categoryLabels[category]} ({tasks.length})
                </h3>
                <div
                    className={`h-px flex-1 ${
                        category === "overdue" ? "bg-destructive" : "bg-border"
                    }`}
                />
            </div>
            <div className="space-y-2">
                {tasks.map((task) => (
                    <TaskListItemRow
                        key={task.id}
                        task={task}
                        showCategory={false}
                        selectedTaskIds={selectedTaskIds}
                        onTaskToggle={onTaskToggle}
                        onTaskClick={onTaskClick}
                        onSelectTask={onSelectTask}
                    />
                ))}
            </div>
        </div>
    )
}

export function TasksListView({
    incompleteTasks,
    completedTasks,
    selectedTaskIds,
    showCompleted,
    loadingCompleted,
    completedError,
    onToggleShowCompleted,
    onTaskToggle,
    onTaskClick,
    onSelectTask,
    onSelectAll,
    onBulkCompleteSelected,
    bulkCompletePending,
}: TasksListViewProps) {
    const groupedTasks: Record<DueCategory, TaskListItem[]> = {
        overdue: [],
        today: [],
        tomorrow: [],
        "this-week": [],
        later: [],
        "no-date": [],
    }
    let selectedIncompleteCount = 0
    for (const task of incompleteTasks) {
        const category = getDueCategory(task)
        groupedTasks[category].push(task)
        if (selectedTaskIds.has(task.id)) {
            selectedIncompleteCount += 1
        }
    }

    const completedTotal = completedTasks?.total ?? 0
    const allVisibleSelected = incompleteTasks.length > 0 && selectedIncompleteCount === incompleteTasks.length

    return (
        <Card id="tasks-list" className="p-6">
            <div className="space-y-6">
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-3">
                    <div className="flex items-center gap-3">
                        <Checkbox
                            aria-label="Select all visible tasks"
                            checked={allVisibleSelected}
                            onCheckedChange={(checked) => onSelectAll(checked === true)}
                        />
                        <span className="text-sm text-muted-foreground">
                            {selectedIncompleteCount > 0
                                ? `${selectedIncompleteCount} selected`
                                : "Select tasks for bulk complete"}
                        </span>
                    </div>
                    <Button
                        size="sm"
                        disabled={selectedIncompleteCount === 0 || bulkCompletePending}
                        onClick={onBulkCompleteSelected}
                    >
                        {bulkCompletePending ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                                Completing…
                            </>
                        ) : (
                            "Complete selected"
                        )}
                    </Button>
                </div>

                {TASK_DUE_SECTION_ORDER.map((category) => (
                    <TaskDueSection
                        key={category}
                        category={category}
                        tasks={groupedTasks[category]}
                        selectedTaskIds={selectedTaskIds}
                        onTaskToggle={onTaskToggle}
                        onTaskClick={onTaskClick}
                        onSelectTask={onSelectTask}
                    />
                ))}

                {incompleteTasks.length === 0 && (
                    <p className="text-center text-muted-foreground py-8">
                        No pending tasks. Nice work!
                    </p>
                )}

                <div className="border-t border-border pt-4">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onToggleShowCompleted}
                        className="w-full justify-center"
                    >
                        {showCompleted ? "Hide" : "Show"} completed tasks ({completedTotal})
                    </Button>

                    {showCompleted && completedTasks && (
                        <div className="mt-4 space-y-2">
                            {loadingCompleted ? (
                                <div className="flex items-center justify-center py-4">
                                    <Loader2Icon className="size-4 animate-spin text-muted-foreground" />
                                </div>
                            ) : completedError ? (
                                <p className="text-center text-destructive py-4">
                                    Unable to load completed tasks
                                </p>
                            ) : completedTasks.items.length === 0 ? (
                                <p className="text-center text-muted-foreground py-4">
                                    No completed tasks
                                </p>
                            ) : (
                                completedTasks.items.map((task) => (
                                    <TaskListItemRow
                                        key={task.id}
                                        task={task}
                                        selectedTaskIds={selectedTaskIds}
                                        onTaskToggle={onTaskToggle}
                                        onTaskClick={onTaskClick}
                                        onSelectTask={onSelectTask}
                                    />
                                ))
                            )}
                        </div>
                    )}
                </div>
            </div>
        </Card>
    )
}
