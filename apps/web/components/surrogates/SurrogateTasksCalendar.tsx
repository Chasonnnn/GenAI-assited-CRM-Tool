"use client"

/**
 * SurrogateTasksCalendar - List/Calendar view for surrogate-specific tasks.
 *
 * Features:
 * - Toggle between list and calendar views (persisted per-surrogate)
 * - List view groups tasks by: Overdue, Today, Upcoming, No Date
 * - Calendar view reuses UnifiedCalendar (same as My Tasks)
 */

import { useState, useEffect, useMemo } from "react"
import { isPast, isToday, isFuture, parseISO, startOfDay } from "date-fns"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import {
    ListIcon,
    CalendarIcon,
    PlusIcon,
    Loader2Icon,
    AlertCircleIcon,
    ClockIcon,
    CalendarCheckIcon,
    InboxIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { UnifiedCalendar } from "@/components/appointments/UnifiedCalendar"
import type { TaskListItem } from "@/lib/api/tasks"

interface SurrogateTasksCalendarProps {
    surrogateId: string
    tasks: TaskListItem[]
    isLoading?: boolean
    onTaskToggle: (taskId: string, completed: boolean) => void
    onAddTask: () => void
    onTaskClick?: (task: TaskListItem) => void
}

type ViewMode = "list" | "calendar"

interface TaskGroup {
    id: string
    label: string
    icon: typeof AlertCircleIcon
    colorClass: string
    bgClass: string
    borderClass: string
    tasks: TaskListItem[]
}

function getStorageKey(surrogateId: string): string {
    return `surrogate-tasks-view-${surrogateId}`
}

function formatDueLabel(task: TaskListItem): string {
    if (!task.due_date) return "No date"

    const date = parseISO(task.due_date)
    const today = startOfDay(new Date())
    const taskDate = startOfDay(date)

    if (isToday(taskDate)) {
        return task.due_time ? `Today at ${task.due_time.slice(0, 5)}` : "Today"
    }

    const diffDays = Math.ceil((taskDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))

    if (diffDays === 1) return "Tomorrow"
    if (diffDays === -1) return "Yesterday"
    if (diffDays < -1) return `${Math.abs(diffDays)} days overdue`
    if (diffDays <= 7) return `In ${diffDays} days`

    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

export function SurrogateTasksCalendar({
    surrogateId,
    tasks,
    isLoading = false,
    onTaskToggle,
    onAddTask,
    onTaskClick,
}: SurrogateTasksCalendarProps) {
    const [viewMode, setViewMode] = useState<ViewMode>("list")
    const [mounted, setMounted] = useState(false)

    // Load persisted view preference
    useEffect(() => {
        setMounted(true)
        const stored = localStorage.getItem(getStorageKey(surrogateId))
        if (stored === "calendar" || stored === "list") {
            setViewMode(stored)
        }
    }, [surrogateId])

    // Persist view preference
    const handleViewChange = (mode: ViewMode) => {
        setViewMode(mode)
        localStorage.setItem(getStorageKey(surrogateId), mode)
    }

    // Group tasks by due status
    const taskGroups = useMemo<TaskGroup[]>(() => {
        const overdue: TaskListItem[] = []
        const todayTasks: TaskListItem[] = []
        const upcoming: TaskListItem[] = []
        const noDate: TaskListItem[] = []

        for (const task of tasks) {
            if (!task.due_date) {
                noDate.push(task)
                continue
            }

            const dueDate = startOfDay(parseISO(task.due_date))

            if (isToday(dueDate)) {
                todayTasks.push(task)
            } else if (isPast(dueDate)) {
                overdue.push(task)
            } else if (isFuture(dueDate)) {
                upcoming.push(task)
            }
        }

        return [
            {
                id: "overdue",
                label: "Overdue",
                icon: AlertCircleIcon,
                colorClass: "text-red-600 dark:text-red-400",
                bgClass: "bg-red-50 dark:bg-red-950/30",
                borderClass: "border-l-red-500",
                tasks: overdue.filter(t => !t.is_completed),
            },
            {
                id: "today",
                label: "Today",
                icon: ClockIcon,
                colorClass: "text-amber-600 dark:text-amber-400",
                bgClass: "bg-amber-50 dark:bg-amber-950/30",
                borderClass: "border-l-amber-500",
                tasks: todayTasks,
            },
            {
                id: "upcoming",
                label: "Upcoming",
                icon: CalendarCheckIcon,
                colorClass: "text-emerald-600 dark:text-emerald-400",
                bgClass: "bg-emerald-50 dark:bg-emerald-950/30",
                borderClass: "border-l-emerald-500",
                tasks: upcoming,
            },
            {
                id: "noDate",
                label: "No Date",
                icon: InboxIcon,
                colorClass: "text-stone-500 dark:text-stone-400",
                bgClass: "bg-stone-50 dark:bg-stone-900/50",
                borderClass: "border-l-stone-400",
                tasks: noDate,
            },
        ].filter(group => group.tasks.length > 0)
    }, [tasks])

    // Don't render until mounted to avoid hydration mismatch
    if (!mounted) {
        return (
            <Card className="flex items-center justify-center py-12">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
            </Card>
        )
    }

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold tracking-tight">Tasks</h3>
                    {tasks.length > 0 && (
                        <span className="text-sm font-normal text-muted-foreground">
                            ({tasks.length})
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <div className="flex gap-1 border rounded-lg p-1 bg-background">
                        <Button
                            variant={viewMode === "list" ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => handleViewChange("list")}
                        >
                            <ListIcon className="size-4 mr-1" />
                            List
                        </Button>
                        <Button
                            variant={viewMode === "calendar" ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => handleViewChange("calendar")}
                        >
                            <CalendarIcon className="size-4 mr-1" />
                            Calendar
                        </Button>
                    </div>
                    <Button size="sm" onClick={onAddTask}>
                        <PlusIcon className="size-4 mr-1.5" />
                        Add Task
                    </Button>
                </div>
            </div>

            {isLoading ? (
                <Card className="flex items-center justify-center py-12">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                </Card>
            ) : tasks.length === 0 ? (
                <Card className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="rounded-full bg-muted/50 p-4 mb-4">
                        <CalendarCheckIcon className="size-8 text-muted-foreground/60" />
                    </div>
                    <p className="text-sm font-medium text-muted-foreground mb-1">
                        No tasks yet
                    </p>
                    <p className="text-xs text-muted-foreground/70 mb-4">
                        Create a task to track work for this surrogate
                    </p>
                    <Button size="sm" variant="outline" onClick={onAddTask}>
                        <PlusIcon className="size-4 mr-1.5" />
                        Add First Task
                    </Button>
                </Card>
            ) : viewMode === "list" ? (
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
                                                    onCheckedChange={() => onTaskToggle(task.id, task.is_completed)}
                                                aria-label={`Mark ${task.title} as complete`}
                                                />
                                            <button
                                                type="button"
                                                className="flex-1 min-w-0 text-left cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                                                    onClick={() => onTaskClick?.(task)}
                                                >
                                                <span
                                                        className={cn(
                                                        "text-sm font-medium leading-tight block",
                                                            task.is_completed && "line-through text-muted-foreground"
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
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}

                            {tasks.some(t => t.is_completed && taskGroups.every(g => !g.tasks.includes(t))) && (
                                <details className="py-3 px-4">
                                    <summary className="flex items-center gap-2 cursor-pointer text-sm text-muted-foreground hover:text-foreground transition-colors">
                                        <CalendarCheckIcon className="size-4" />
                                        <span className="font-medium">Completed</span>
                                        <Badge variant="secondary" className="h-5 text-xs">
                                            {tasks.filter(t => t.is_completed).length}
                                        </Badge>
                                    </summary>
                                    <div className="mt-3 space-y-1">
                                        {tasks.filter(t => t.is_completed).map((task) => (
                                            <div
                                                key={task.id}
                                                className="flex items-start gap-3 py-2 px-3 rounded-lg opacity-50"
                                            >
                                                <Checkbox
                                                    id={`task-completed-${task.id}`}
                                                    className="mt-0.5"
                                                    checked={true}
                                                    onCheckedChange={() => onTaskToggle(task.id, true)}
                                                    aria-label={`Mark ${task.title} as incomplete`}
                                                />
                                                <button
                                                    type="button"
                                                    className="flex-1 min-w-0 text-left cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                                                    onClick={() => onTaskClick?.(task)}
                                                >
                                                    <span className="text-sm line-through text-muted-foreground block">
                                                        {task.title}
                                                    </span>
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                </details>
                            )}
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <UnifiedCalendar
                    taskFilter={{ surrogate_id: surrogateId }}
                    includeAppointments={false}
                    includeGoogleEvents={false}
                    {...(onTaskClick ? { onTaskClick } : {})}
                />
            )}
        </div>
    )
}
