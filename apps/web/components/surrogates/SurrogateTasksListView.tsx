"use client"

import { CalendarCheckIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import type { TaskListItem } from "@/lib/api/tasks"
import { cn } from "@/lib/utils"

import { formatDueLabel, type TaskGroup } from "./surrogate-task-derivations"

interface SurrogateTasksListViewProps {
    taskGroups: TaskGroup[]
    orphanedCompletedTasks: TaskListItem[]
    completedTaskCount: number
    onTaskToggle: (taskId: string, completed: boolean) => void
    onTaskClick?: (task: TaskListItem) => void
}

export function SurrogateTasksListView({
    taskGroups,
    orphanedCompletedTasks,
    completedTaskCount,
    onTaskToggle,
    onTaskClick,
}: SurrogateTasksListViewProps) {
    return (
        <Card className="overflow-hidden">
            <CardContent className="p-0">
                <div className="divide-y">
                    {taskGroups.map((group) => (
                        <div key={group.id} className="py-3 px-4">
                            <div className={cn(
                                "flex items-center gap-2 mb-3 pb-2 border-b",
                                group.colorClass
                            )}>
                                <group.icon className="size-4" />
                                <span className="text-sm font-semibold">
                                    {group.label}
                                </span>
                                <Badge
                                    variant="secondary"
                                    className={cn(
                                        "h-5 min-w-5 px-1.5 text-xs font-medium",
                                        group.bgClass,
                                        group.colorClass
                                    )}
                                >
                                    {group.tasks.length}
                                </Badge>
                            </div>

                            <div className="space-y-1">
                                {group.tasks.map((task) => (
                                    <div
                                        key={task.id}
                                        className={cn(
                                            "flex items-start gap-3 py-2 px-3 rounded-lg border-l-2 transition-all",
                                            "hover:bg-muted/40",
                                            group.borderClass,
                                            task.is_completed && "opacity-60"
                                        )}
                                    >
                                        <Checkbox
                                            id={`task-${task.id}`}
                                            className="mt-0.5"
                                            checked={task.is_completed}
                                            aria-label={
                                                task.is_completed
                                                    ? `Mark ${task.title} as incomplete`
                                                    : `Mark ${task.title} as complete`
                                            }
                                            onCheckedChange={() => onTaskToggle(task.id, task.is_completed)}
                                        />
                                        {onTaskClick ? (
                                            <button
                                                type="button"
                                                className="flex-1 min-w-0 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                                onClick={() => onTaskClick(task)}
                                            >
                                                <span
                                                    className={cn(
                                                        "text-sm font-medium leading-tight block",
                                                        task.is_completed &&
                                                            "line-through text-muted-foreground"
                                                    )}
                                                >
                                                    {task.title}
                                                </span>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <Badge
                                                        variant="outline"
                                                        className="text-xs h-5 px-1.5 font-normal"
                                                    >
                                                        {formatDueLabel(task)}
                                                    </Badge>
                                                    {task.task_type && (
                                                        <Badge
                                                            variant="secondary"
                                                            className="text-xs h-5 px-1.5 font-normal capitalize"
                                                        >
                                                            {task.task_type.replace(/_/g, " ")}
                                                        </Badge>
                                                    )}
                                                </div>
                                            </button>
                                        ) : (
                                            <div className="flex-1 min-w-0">
                                                <span
                                                    className={cn(
                                                        "text-sm font-medium leading-tight block",
                                                        task.is_completed &&
                                                            "line-through text-muted-foreground"
                                                    )}
                                                >
                                                    {task.title}
                                                </span>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <Badge
                                                        variant="outline"
                                                        className="text-xs h-5 px-1.5 font-normal"
                                                    >
                                                        {formatDueLabel(task)}
                                                    </Badge>
                                                    {task.task_type && (
                                                        <Badge
                                                            variant="secondary"
                                                            className="text-xs h-5 px-1.5 font-normal capitalize"
                                                        >
                                                            {task.task_type.replace(/_/g, " ")}
                                                        </Badge>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}

                    {orphanedCompletedTasks.length > 0 && (
                        <details className="py-3 px-4">
                            <summary className="flex items-center gap-2 cursor-pointer text-sm text-muted-foreground hover:text-foreground transition-colors">
                                <CalendarCheckIcon className="size-4" />
                                <span className="font-medium">Completed</span>
                                <Badge variant="secondary" className="h-5 text-xs">
                                    {completedTaskCount}
                                </Badge>
                            </summary>
                            <div className="mt-3 space-y-1">
                                {orphanedCompletedTasks.map((task) => (
                                    <div
                                        key={task.id}
                                        className="flex items-start gap-3 py-2 px-3 rounded-lg opacity-50"
                                    >
                                        <Checkbox
                                            id={`task-completed-${task.id}`}
                                            className="mt-0.5"
                                            checked={true}
                                            aria-label={`Mark ${task.title} as incomplete`}
                                            onCheckedChange={() => onTaskToggle(task.id, true)}
                                        />
                                        {onTaskClick ? (
                                            <button
                                                type="button"
                                                className="flex-1 min-w-0 rounded-md text-left text-sm line-through text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                                onClick={() => onTaskClick(task)}
                                            >
                                                {task.title}
                                            </button>
                                        ) : (
                                            <span className="flex-1 min-w-0 text-sm line-through text-muted-foreground">
                                                {task.title}
                                            </span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </details>
                    )}
                </div>
            </CardContent>
        </Card>
    )
}
