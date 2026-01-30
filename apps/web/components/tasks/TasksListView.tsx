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
import { useMemo } from "react"
import { Loader2Icon } from "lucide-react"

type TasksListViewProps = {
    incompleteTasks: TaskListItem[]
    completedTasks: { items: TaskListItem[]; total?: number } | null
    showCompleted: boolean
    loadingCompleted: boolean
    completedError: boolean
    onToggleShowCompleted: () => void
    onTaskToggle: (taskId: string, isCompleted: boolean) => void
    onTaskClick: (task: TaskListItem) => void
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

export function TasksListView({
    incompleteTasks,
    completedTasks,
    showCompleted,
    loadingCompleted,
    completedError,
    onToggleShowCompleted,
    onTaskToggle,
    onTaskClick,
}: TasksListViewProps) {
    const groupedTasks = useMemo(() => {
        const grouped: Record<DueCategory, TaskListItem[]> = {
            overdue: [],
            today: [],
            tomorrow: [],
            "this-week": [],
            later: [],
            "no-date": [],
        }
        for (const task of incompleteTasks) {
            const category = getDueCategory(task)
            grouped[category].push(task)
        }
        return grouped
    }, [incompleteTasks])

    const renderTaskItem = (task: TaskListItem, showCategory = true) => {
        const category = getDueCategory(task)
        const colors = categoryColors[category]

        return (
            <div
                key={task.id}
                className={`flex items-start gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-accent/50 ${
                    task.is_completed ? "opacity-60" : ""
                }`}
                role="button"
                tabIndex={0}
                onClick={() => onTaskClick(task)}
                onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault()
                        onTaskClick(task)
                    }
                }}
            >
                <Checkbox
                    className="mt-0.5"
                    checked={task.is_completed}
                    onCheckedChange={() => onTaskToggle(task.id, task.is_completed)}
                    onClick={(event) => event.stopPropagation()}
                />
                <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                        <span className={`font-medium ${task.is_completed ? "line-through" : ""}`}>
                            {task.title}
                        </span>
                        {showCategory && !task.is_completed && (
                            <Badge variant="secondary" className={colors.badge}>
                                {categoryLabels[category]}
                            </Badge>
                        )}
                    </div>
                    {task.surrogate_id && (
                        <Link
                            href={`/surrogates/${task.surrogate_id}`}
                            className="text-sm text-muted-foreground hover:underline"
                            onClick={(event) => event.stopPropagation()}
                        >
                            Surrogate #{task.surrogate_number}
                        </Link>
                    )}
                </div>
                {task.owner_name && (
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger>
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

    const renderSection = (category: DueCategory, tasks: TaskListItem[]) => {
        if (tasks.length === 0) return null
        const colors = categoryColors[category]

        return (
            <div key={category} id={`tasks-${category}`} className="space-y-3">
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
                    {tasks.map((task) => renderTaskItem(task, false))}
                </div>
            </div>
        )
    }

    const completedTotal = completedTasks?.total ?? 0

    return (
        <Card id="tasks-list" className="p-6">
            <div className="space-y-6">
                {renderSection("overdue", groupedTasks.overdue)}
                {renderSection("today", groupedTasks.today)}
                {renderSection("tomorrow", groupedTasks.tomorrow)}
                {renderSection("this-week", groupedTasks["this-week"])}
                {renderSection("later", groupedTasks.later)}
                {renderSection("no-date", groupedTasks["no-date"])}

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
                                completedTasks.items.map((task) => renderTaskItem(task))
                            )}
                        </div>
                    )}
                </div>
            </div>
        </Card>
    )
}
