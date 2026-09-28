"use client"

import { UnifiedCalendar } from "@/components/appointments/UnifiedCalendar"
import type { UnifiedCalendarTaskFilter } from "@/lib/hooks/use-unified-calendar-data"
import type { TaskListItem } from "@/lib/types/task"

type TasksCalendarViewProps = {
    taskFilter: UnifiedCalendarTaskFilter
    onTaskClick: (task: TaskListItem) => void
}

export function TasksCalendarView({ taskFilter, onTaskClick }: TasksCalendarViewProps) {
    return (
        <UnifiedCalendar
            taskFilter={taskFilter}
            onTaskClick={onTaskClick}
        />
    )
}
