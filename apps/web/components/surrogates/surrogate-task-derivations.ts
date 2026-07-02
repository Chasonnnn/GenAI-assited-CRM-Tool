import { isFuture, isPast, isToday, parseISO, startOfDay } from "date-fns"
import {
    AlertCircleIcon,
    CalendarCheckIcon,
    ClockIcon,
    InboxIcon,
} from "lucide-react"

import type { TaskListItem } from "@/lib/api/tasks"

export interface TaskGroup {
    id: string
    label: string
    icon: typeof AlertCircleIcon
    colorClass: string
    bgClass: string
    borderClass: string
    tasks: TaskListItem[]
}

export function formatDueLabel(task: TaskListItem): string {
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

export function buildTaskGroups(tasks: TaskListItem[]): TaskGroup[] {
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
}

export function getOrphanedCompletedTasks(
    taskGroups: TaskGroup[],
    tasks: TaskListItem[],
): TaskListItem[] {
    const groupedTaskIds = new Set<string>()
    for (const group of taskGroups) {
        for (const task of group.tasks) {
            groupedTaskIds.add(task.id)
        }
    }

    const completedTasks: TaskListItem[] = []
    for (const task of tasks) {
        if (task.is_completed && !groupedTaskIds.has(task.id)) {
            completedTasks.push(task)
        }
    }
    return completedTasks
}

export function countCompletedTasks(tasks: TaskListItem[]): number {
    let count = 0
    for (const task of tasks) {
        if (task.is_completed) count += 1
    }
    return count
}
