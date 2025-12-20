"use client"

import { useCallback, useState } from "react"
import FullCalendar from "@fullcalendar/react"
import dayGridPlugin from "@fullcalendar/daygrid"
import timeGridPlugin from "@fullcalendar/timegrid"
import interactionPlugin from "@fullcalendar/interaction"
import type { EventDropArg, EventClickArg } from "@fullcalendar/core"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface Task {
    id: string
    title: string
    due_date: string | null
    due_time: string | null
    is_completed: boolean
    task_type: string
    case_id: string | null
}

interface TasksCalendarProps {
    tasks: Task[]
    isLoading?: boolean
    onTaskClick?: (taskId: string) => void
    onTaskReschedule?: (taskId: string, newDate: string, newTime: string | null) => void
    className?: string
}

function getTaskColor(task: Task): string {
    if (task.is_completed) return "#9CA3AF" // gray

    switch (task.task_type) {
        case "call":
            return "#3B82F6" // blue
        case "email":
            return "#10B981" // green
        case "meeting":
            return "#8B5CF6" // purple
        case "follow_up":
            return "#F59E0B" // yellow
        default:
            return "#6366F1" // indigo
    }
}

export function TasksCalendar({
    tasks,
    isLoading = false,
    onTaskClick,
    onTaskReschedule,
    className,
}: TasksCalendarProps) {
    // Convert tasks to FullCalendar events
    const events = tasks
        .filter((task) => task.due_date) // Only show tasks with due dates
        .map((task) => {
            const hasTime = !!task.due_time
            const start = hasTime
                ? `${task.due_date}T${task.due_time}`
                : task.due_date!

            return {
                id: task.id,
                title: task.title,
                start,
                allDay: !hasTime,
                backgroundColor: getTaskColor(task),
                borderColor: getTaskColor(task),
                extendedProps: { task },
                classNames: task.is_completed ? ["opacity-50", "line-through"] : [],
            }
        })

    const handleEventClick = useCallback(
        (info: EventClickArg) => {
            onTaskClick?.(info.event.id)
        },
        [onTaskClick]
    )

    const handleEventDrop = useCallback(
        (info: EventDropArg) => {
            const task = info.event.extendedProps.task as Task
            const newStart = info.event.start

            if (!newStart) {
                info.revert()
                return
            }

            // Format date as YYYY-MM-DD
            const newDate = newStart.toISOString().split("T")[0]

            // Preserve time behavior:
            // - If event was all-day (no time), keep it all-day
            // - If event had a time, preserve the original time unless dropped on a time slot
            let newTime: string | null = null

            if (!info.event.allDay) {
                // Event has a time - check if user dropped it on a new time slot
                const hours = newStart.getHours().toString().padStart(2, "0")
                const minutes = newStart.getMinutes().toString().padStart(2, "0")
                newTime = `${hours}:${minutes}:00`
            } else if (task.due_time && info.oldEvent.allDay) {
                // Was all-day before and after - preserve original time if it had one
                newTime = task.due_time
            }

            onTaskReschedule?.(task.id, newDate, newTime)
        },
        [onTaskReschedule]
    )

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-96">
                <Loader2 className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    return (
        <div className={cn("bg-card rounded-lg border p-4", className)}>
            <FullCalendar
                plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
                initialView="dayGridMonth"
                headerToolbar={{
                    left: "prev,next today",
                    center: "title",
                    right: "dayGridMonth,timeGridWeek,timeGridDay",
                }}
                events={events}
                editable={true}
                droppable={true}
                eventClick={handleEventClick}
                eventDrop={handleEventDrop}
                height="auto"
                dayMaxEvents={3}
                eventDisplay="block"
                nowIndicator={true}
                slotMinTime="07:00:00"
                slotMaxTime="21:00:00"
                weekends={true}
                businessHours={{
                    daysOfWeek: [1, 2, 3, 4, 5],
                    startTime: "09:00",
                    endTime: "17:00",
                }}
            />
        </div>
    )
}
