"use client"

import { UnifiedCalendar } from "@/components/appointments/UnifiedCalendar"
import type { TaskListItem } from "@/lib/types/task"

type TasksCalendarViewProps = {
    filter: "my_tasks" | "all"
    onTaskClick: (task: TaskListItem) => void
}

export function TasksCalendarView({ filter, onTaskClick }: TasksCalendarViewProps) {
    return (
        <UnifiedCalendar
            taskFilter={{ my_tasks: filter === "my_tasks" }}
            onTaskClick={onTaskClick}
        />
    )
}
