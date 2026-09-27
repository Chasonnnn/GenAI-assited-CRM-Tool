"use client"

import { getAppointmentStatusLabel } from "@/lib/appointment-status-labels"
import { APPOINTMENT_STATUSES, getAppointmentStatusTone } from "@/lib/appointment-status-tones"

/**
 * Unified Calendar View - Combined view of appointments and tasks
 * 
 * Features:
 * - Month/week/day view toggle
 * - Appointments color-coded by status
 * - Tasks with scheduled times
 * - Click to view details
 */

import { useEffect, useRef, useState } from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { TaskRelatedRecordLinks } from "@/components/tasks/TaskRelatedRecordLinks"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
    ChevronLeftIcon,
    ChevronRightIcon,
    CalendarIcon,
    CheckSquareIcon,
    Loader2Icon,
} from "lucide-react"
import type { UnifiedCalendarTaskFilter } from "@/lib/hooks/use-unified-calendar-data"
import { useUnifiedCalendarData } from "@/lib/hooks/use-unified-calendar-data"
import { AppointmentDetailDialog } from "@/components/appointments/AppointmentDetailDialog"
import type { AppointmentFilterParams, AppointmentListItem, GoogleCalendarEvent } from "@/lib/api/appointments"
import type { TaskListItem } from "@/lib/api/tasks"
import { compareTasksByDueTime } from "@/lib/utils/task-due"
import Link from "@/components/app-link"
import {
    format,
    startOfMonth,
    endOfMonth,
    startOfWeek,
    endOfWeek,
    eachDayOfInterval,
    isSameMonth,
    isSameDay,
    addMonths,
    subMonths,
    parseISO,
    isToday,
} from "date-fns"
import { cn } from "@/lib/utils"

// Task color
const TASK_COLOR = "bg-purple-500"

// Google Calendar event color
const GOOGLE_EVENT_COLOR = "bg-neutral-400"
const EMPTY_GOOGLE_EVENTS: GoogleCalendarEvent[] = []

function formatItemCount(count: number) {
    return `${count} item${count === 1 ? "" : "s"}`
}

/** Month cells show this many items before "+N more". */
const MONTH_CELL_ITEM_LIMIT = 3

// The day view covers the full day; it scrolls to DAY_VIEW_DEFAULT_SCROLL_HOUR or the first timed item.
const DAY_VIEW_HOURS = Array.from({ length: 24 }, (_, i) => i)
const DAY_VIEW_DEFAULT_SCROLL_HOUR = 7
const DAY_VIEW_HOUR_LABELS = DAY_VIEW_HOURS.reduce<Record<number, string>>((labels, hour) => {
    const displayHour = hour % 12 === 0 ? 12 : hour % 12
    labels[hour] = `${displayHour} ${hour >= 12 ? "PM" : "AM"}`
    return labels
}, {})

function groupTasksByDueDate(tasks: TaskListItem[]) {
    const tasksByDate = new Map<string, TaskListItem[]>()
    for (const task of tasks.toSorted(compareTasksByDueTime)) {
        if (!task.due_date) continue
        const bucket = tasksByDate.get(task.due_date)
        if (bucket) bucket.push(task)
        else tasksByDate.set(task.due_date, [task])
    }
    return tasksByDate
}

// View type
type ViewType = "month" | "week" | "day"

// =============================================================================
// Task Item Component
// =============================================================================

export function TaskItem({
    task,
    compact = false,
    onClick,
}: {
    task: TaskListItem
    compact?: boolean
    onClick?: (task: TaskListItem) => void
}) {
    const time = task.due_time ? format(parseISO(`2000-01-01T${task.due_time}`), "h:mm a") : ""
    const clickable = typeof onClick === "function"
    const handleTaskClick = () => onClick?.(task)

    if (compact) {
        const compactContent = (
            <>
                <CheckSquareIcon className="size-3 shrink-0" />
                <span className="truncate">{time ? `${time} - ${task.title}` : task.title}</span>
            </>
        )

        if (clickable) {
            return (
                <div className="w-full rounded-md border border-purple-500/20 bg-purple-500/10 px-2 py-1 text-[11px] text-purple-950 dark:text-purple-100">
                    <Button unstyled type="button" onClick={handleTaskClick} className="flex w-full items-center gap-1.5 text-left font-medium transition-opacity hover:opacity-90">
                        {compactContent}
                    </Button>
                    <TaskRelatedRecordLinks task={task} className="text-[10px] text-muted-foreground" />
                </div>
            )
        }

        return (
            <div className="w-full rounded-md border border-purple-500/20 bg-purple-500/10 px-2 py-1 text-left text-[11px] text-purple-950 dark:text-purple-100">
                <div className="flex items-center gap-1.5 font-medium">{compactContent}</div>
                <TaskRelatedRecordLinks task={task} className="text-[10px] text-muted-foreground" />
            </div>
        )
    }

    const fullContent = (
        <div className="min-w-0 flex-1">
            <p className="font-medium text-sm truncate flex items-center gap-1">
                <CheckSquareIcon className="size-3" />
                {task.title}
            </p>
            {time && <p className="text-xs text-muted-foreground">{time}</p>}
        </div>
    )

    if (clickable) {
        return (
            <div className="w-full rounded-lg border border-purple-500/20 bg-muted/50 p-2 text-left shadow-[inset_3px_0_0_rgb(168_85_247)] hover:bg-muted">
                <Button unstyled type="button" onClick={handleTaskClick} className="w-full text-left">
                    {fullContent}
                </Button>
                <TaskRelatedRecordLinks task={task} className="text-xs text-muted-foreground" />
            </div>
        )
    }

    return (
        <div className="w-full rounded-lg border border-purple-500/20 bg-muted/50 p-2 text-left shadow-[inset_3px_0_0_rgb(168_85_247)]">
            {fullContent}
            <TaskRelatedRecordLinks task={task} className="text-xs text-muted-foreground" />
        </div>
    )
}

// =============================================================================
// Google Calendar Event Component
// =============================================================================

function GoogleEventItem({
    event,
    compact = false,
}: {
    event: GoogleCalendarEvent
    compact?: boolean
}) {
    const time = event.is_all_day
        ? "All day"
        : format(parseISO(event.start), "h:mm a")

    if (compact) {
        return (
            <a
                href={event.html_link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex w-full items-center gap-1.5 rounded-md border border-border bg-muted/70 px-2 py-1 text-left text-[11px] font-medium text-foreground hover:bg-muted"
                title="Open in Google Calendar"
            >
                <CalendarIcon className="size-3 shrink-0" />
                <span className="truncate">{time} - {event.summary}</span>
            </a>
        )
    }

    return (
        <a
            href={event.html_link}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full rounded-lg border border-border bg-muted/50 p-2 text-left hover:bg-muted"
            title="Open in Google Calendar"
        >
            <p className="font-medium text-sm truncate flex items-center gap-1">
                <CalendarIcon className="size-3" />
                {event.summary}
            </p>
            <p className="text-xs text-muted-foreground">{time}</p>
            <p className="text-xs text-muted-foreground/70">Google Calendar</p>
        </a>
    )
}

// =============================================================================
// Event Item Component
// =============================================================================

function EventItem({
    appointment,
    onClick,
    compact = false,
    draggable = false,
    onDragStart,
}: {
    appointment: AppointmentListItem
    onClick?: (appointment: AppointmentListItem) => void
    compact?: boolean
    draggable?: boolean
    onDragStart?: (e: React.DragEvent, appointment: AppointmentListItem) => void
}) {
    const statusTone = getAppointmentStatusTone(appointment.status)
    const time = format(parseISO(appointment.scheduled_start), "h:mm a")
    const canDrag = draggable && (appointment.status === "pending" || appointment.status === "confirmed")
    const handleAppointmentClick = () => onClick?.(appointment)

    const handleDragStart = (e: React.DragEvent) => {
        if (onDragStart && canDrag) {
            onDragStart(e, appointment)
        }
    }

    if (compact) {
        const compactClassName = `w-full text-left px-2 py-1 rounded border text-xs font-medium truncate ${statusTone.tint} hover:opacity-90 transition-opacity ${canDrag ? "cursor-grab active:cursor-grabbing" : onClick ? "cursor-pointer" : ""}`

        if (onClick) {
            return (
                <Button unstyled
                    type="button"
                    draggable={canDrag}
                    onDragStart={handleDragStart}
                    onClick={handleAppointmentClick}
                    className={compactClassName}
                >
                    {time} - {appointment.client_name}
                </Button>
            )
        }

        return (
            <div
                draggable={canDrag}
                onDragStart={handleDragStart}
                className={compactClassName}
            >
                {time} - {appointment.client_name}
            </div>
        )
    }

    const fullClassName = `w-full text-left p-2 rounded-lg border-l-4 ${statusTone.accent} bg-muted/50 hover:bg-muted transition-colors ${canDrag ? "cursor-grab active:cursor-grabbing" : onClick ? "cursor-pointer" : ""}`
    const fullContent = (
        <>
            <p className="font-medium text-sm truncate">{appointment.client_name}</p>
            <p className="text-xs text-muted-foreground">{time}</p>
            {appointment.appointment_type_name && (
                <p className="text-xs text-muted-foreground truncate">{appointment.appointment_type_name}</p>
            )}
        </>
    )

    if (onClick) {
        return (
            <Button unstyled
                type="button"
                draggable={canDrag}
                onDragStart={handleDragStart}
                onClick={handleAppointmentClick}
                className={fullClassName}
            >
                {fullContent}
            </Button>
        )
    }

    return (
        <div
            draggable={canDrag}
            onDragStart={handleDragStart}
            className={fullClassName}
        >
            {fullContent}
        </div>
    )
}

// =============================================================================
// Month View
// =============================================================================

function MonthView({
    currentDate,
    appointments,
    tasks,
    googleEvents = EMPTY_GOOGLE_EVENTS,
    onEventClick,
    onTaskClick,
    onDragStart,
    onDrop,
    dragOverDate,
    onDragOver,
    onDragLeave,
    onOpenDayAgenda,
}: {
    currentDate: Date
    appointments: AppointmentListItem[]
    tasks: TaskListItem[]
    googleEvents?: GoogleCalendarEvent[]
    onEventClick: (appt: AppointmentListItem) => void
    onTaskClick?: (task: TaskListItem) => void
    onDragStart?: (e: React.DragEvent, appointment: AppointmentListItem) => void
    onDrop?: (e: React.DragEvent, date: Date) => void
    dragOverDate?: string | null
    onDragOver?: (e: React.DragEvent, date: Date) => void
    onDragLeave?: (e: React.DragEvent) => void
    onOpenDayAgenda?: (day: Date) => void
}) {
    const monthStart = startOfMonth(currentDate)
    const monthEnd = endOfMonth(currentDate)
    const calendarStart = startOfWeek(monthStart)
    const calendarEnd = endOfWeek(monthEnd)
    const days = eachDayOfInterval({ start: calendarStart, end: calendarEnd })

    const appointmentsByDate = new Map<string, AppointmentListItem[]>()
    appointments.forEach((appt) => {
        const dateStr = format(parseISO(appt.scheduled_start), "yyyy-MM-dd")
        if (!appointmentsByDate.has(dateStr)) appointmentsByDate.set(dateStr, [])
        appointmentsByDate.get(dateStr)!.push(appt)
    })

    const tasksByDate = groupTasksByDueDate(tasks)

    const googleEventsByDate = new Map<string, GoogleCalendarEvent[]>()
    googleEvents.forEach((event) => {
        if (event.is_all_day) {
            // All-day events can span multiple days. Google's end date is exclusive.
            // Extract dates directly to avoid TZ shift
            const startDate = event.start.slice(0, 10)  // YYYY-MM-DD
            const endDate = event.end.slice(0, 10)      // YYYY-MM-DD (exclusive)

            // Expand across all days the event spans
            const start = parseISO(startDate)
            const end = parseISO(endDate)
            // End is exclusive, so we go up to but not including end
            const daysToShow = eachDayOfInterval({
                start,
                end: new Date(end.getTime() - 86400000), // Subtract 1 day
            })

            daysToShow.forEach((day) => {
                const dateStr = format(day, "yyyy-MM-dd")
                if (!googleEventsByDate.has(dateStr)) googleEventsByDate.set(dateStr, [])
                googleEventsByDate.get(dateStr)!.push(event)
            })
        } else {
            // Timed events: use parsed date
            const dateStr = format(parseISO(event.start), "yyyy-MM-dd")
            if (!googleEventsByDate.has(dateStr)) googleEventsByDate.set(dateStr, [])
            googleEventsByDate.get(dateStr)!.push(event)
        }
    })

    return (
        <div className="border border-border rounded-lg overflow-hidden">
            {/* Day Headers */}
            <div className="grid grid-cols-7 bg-muted">
                {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
                    <div key={day} className="p-2 text-center text-sm font-medium text-muted-foreground border-b border-border">
                        {day}
                    </div>
                ))}
            </div>

            {/* Days Grid */}
            <div className="grid grid-cols-7">
                {days.map((day) => {
                    const dateStr = format(day, "yyyy-MM-dd")
                    const dayAppointments = appointmentsByDate.get(dateStr) || []
                    const dayTasks = tasksByDate.get(dateStr) || []
                    const dayGoogleEvents = googleEventsByDate.get(dateStr) || []
                    const totalEvents = dayAppointments.length + dayTasks.length + dayGoogleEvents.length
                    const isCurrentMonth = isSameMonth(day, currentDate)
                    const isCurrentDay = isToday(day)
                    const isDropTarget = dragOverDate === dateStr
                    const appointmentSlots = 2
                    const shownAppointments = dayAppointments.slice(0, appointmentSlots)
                    const remainingSlots = Math.max(0, MONTH_CELL_ITEM_LIMIT - shownAppointments.length)
                    const shownTasks = dayTasks.slice(0, remainingSlots)
                    const remainingAfterTasks = Math.max(0, remainingSlots - shownTasks.length)
                    const shownGoogleEvents = dayGoogleEvents.slice(0, remainingAfterTasks)
                    const hiddenCount =
                        totalEvents - shownAppointments.length - shownTasks.length - shownGoogleEvents.length
                    const canOpenDayAgenda = totalEvents > 0 && typeof onOpenDayAgenda === "function"
                    // Below sm a cell is too narrow for item labels, so it shows one dot per item.
                    const dotColors = [
                        ...dayAppointments.map((appt) => getAppointmentStatusTone(appt.status).dot),
                        ...dayTasks.map(() => TASK_COLOR),
                        ...dayGoogleEvents.map(() => GOOGLE_EVENT_COLOR),
                    ]

                    return (
                        <div
                            key={dateStr}
                            className={cn(
                                "min-h-16 min-w-0 border-b border-r border-border p-1 transition-colors sm:min-h-[128px] sm:p-2",
                                !isCurrentMonth && "bg-muted/20",
                                isDropTarget && "bg-primary/10 ring-2 ring-primary/50 ring-inset"
                            )}
                            onDragOver={(e) => {
                                e.preventDefault()
                                onDragOver?.(e, day)
                            }}
                            onDragLeave={onDragLeave}
                            onDrop={(e) => {
                                e.preventDefault()
                                onDrop?.(e, day)
                            }}
                        >
                            <div className="flex items-start justify-center sm:justify-start">
                                <Button unstyled
                                    type="button"
                                    onClick={() => onOpenDayAgenda?.(day)}
                                    disabled={!canOpenDayAgenda}
                                    aria-label={
                                        canOpenDayAgenda
                                            ? `Open agenda for ${format(day, "EEEE, MMMM d")}, ${formatItemCount(totalEvents)}`
                                            : undefined
                                    }
                                    className={cn(
                                        "flex h-8 min-w-8 items-center justify-center rounded-full px-2 text-sm font-medium transition-colors",
                                        isCurrentDay
                                            ? "bg-primary text-primary-foreground shadow-sm"
                                            : "text-foreground",
                                        !isCurrentMonth && "text-muted-foreground",
                                        canOpenDayAgenda && "hover:bg-muted"
                                    )}
                                >
                                    {format(day, "d")}
                                </Button>
                            </div>
                            {dotColors.length > 0 && (
                                <div aria-hidden="true" className="mt-1 flex flex-wrap justify-center gap-1 sm:hidden">
                                    {dotColors.slice(0, MONTH_CELL_ITEM_LIMIT).map((color, index) => (
                                        <span key={index} className={cn("size-1.5 rounded-full", color)} />
                                    ))}
                                </div>
                            )}
                            <div className="mt-2 hidden space-y-1 sm:block">
                                {/* Surrogacy Force Appointments */}
                                {shownAppointments.map((appt) => (
                                    <EventItem
                                        appointment={appt}
                                        onClick={onEventClick}
                                        compact
                                        draggable
                                        {...(onDragStart ? { onDragStart } : {})}
                                        key={appt.id}
                                    />
                                ))}
                                {/* Tasks */}
                                {shownTasks.map((task) => (
                                    <TaskItem
                                        task={task}
                                        compact
                                        {...(onTaskClick ? { onClick: onTaskClick } : {})}
                                        key={task.id}
                                    />
                                ))}
                                {/* Google Calendar Events */}
                                {shownGoogleEvents.map((event) => (
                                    <GoogleEventItem
                                        key={`gcal-${event.id}`}
                                        event={event}
                                        compact
                                    />
                                ))}
                                {hiddenCount > 0 && (
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        type="button"
                                        onClick={() => onOpenDayAgenda?.(day)}
                                        aria-label={`+${hiddenCount} more items`}
                                        className="h-7 w-full justify-start rounded-md px-2 text-[11px] font-medium text-muted-foreground hover:text-foreground"
                                    >
                                        +{hiddenCount} more
                                    </Button>
                                )}
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}

function DayAgendaSheet({
    day,
    appointments,
    tasks,
    googleEvents = EMPTY_GOOGLE_EVENTS,
    open,
    onOpenChange,
    onEventClick,
    onTaskClick,
}: {
    day: Date | null
    appointments: AppointmentListItem[]
    tasks: TaskListItem[]
    googleEvents?: GoogleCalendarEvent[]
    open: boolean
    onOpenChange: (open: boolean) => void
    onEventClick: (appt: AppointmentListItem) => void
    onTaskClick?: (task: TaskListItem) => void
}) {
    const dateStr = day ? format(day, "yyyy-MM-dd") : null

    const dayAppointments = dateStr
        ? appointments
            .filter((appt) => format(parseISO(appt.scheduled_start), "yyyy-MM-dd") === dateStr)
            .toSorted((a, b) => a.scheduled_start.localeCompare(b.scheduled_start))
        : []

    const dayTasks = dateStr
        ? tasks
            .filter((task) => task.due_date === dateStr)
            .toSorted(compareTasksByDueTime)
        : []

    const dayGoogleEvents = dateStr
        ? googleEvents
            .filter((event) => {
                if (event.is_all_day) {
                    const startDate = event.start.slice(0, 10)
                    const endDate = event.end.slice(0, 10)
                    return dateStr >= startDate && dateStr < endDate
                }
                return format(parseISO(event.start), "yyyy-MM-dd") === dateStr
            })
            .toSorted((a, b) => {
                if (a.is_all_day && !b.is_all_day) return -1
                if (!a.is_all_day && b.is_all_day) return 1
                return a.start.localeCompare(b.start)
            })
        : []

    const totalItems = dayAppointments.length + dayTasks.length + dayGoogleEvents.length
    const handleAgendaAppointmentClick = (appointment: AppointmentListItem) => {
        onOpenChange(false)
        onEventClick(appointment)
    }
    const handleAgendaTaskClick = (task: TaskListItem) => {
        onOpenChange(false)
        onTaskClick?.(task)
    }

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent side="right" className="w-full sm:max-w-xl">
                <SheetHeader className="border-b border-border/70 pb-4">
                    <SheetTitle>{day ? format(day, "EEEE, MMMM d") : "Day agenda"}</SheetTitle>
                    <SheetDescription>
                        {totalItems > 0
                            ? `${formatItemCount(totalItems)} scheduled in this calendar day.`
                            : "No tasks, appointments, or external events on this day."}
                    </SheetDescription>
                </SheetHeader>
                <ScrollArea className="h-[calc(100vh-7rem)] px-6 pb-6">
                    <div className="space-y-6 pt-6">
                        {dayAppointments.length > 0 && (
                            <section className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-sm font-semibold">Appointments</h3>
                                    <Badge variant="secondary">{dayAppointments.length}</Badge>
                                </div>
                                <div className="space-y-2">
                                    {dayAppointments.map((appointment) => (
                                        <EventItem
                                            key={appointment.id}
                                            appointment={appointment}
                                            onClick={handleAgendaAppointmentClick}
                                        />
                                    ))}
                                </div>
                            </section>
                        )}

                        {dayTasks.length > 0 && (
                            <section className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-sm font-semibold">Tasks</h3>
                                    <Badge variant="secondary">{dayTasks.length}</Badge>
                                </div>
                                <div className="space-y-2">
                                    {dayTasks.map((task) => (
                                        <TaskItem
                                            task={task}
                                            {...(onTaskClick ? { onClick: handleAgendaTaskClick } : {})}
                                            key={task.id}
                                        />
                                    ))}
                                </div>
                            </section>
                        )}

                        {dayGoogleEvents.length > 0 && (
                            <section className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-sm font-semibold">Google Calendar</h3>
                                    <Badge variant="secondary">{dayGoogleEvents.length}</Badge>
                                </div>
                                <div className="space-y-2">
                                    {dayGoogleEvents.map((event) => (
                                        <GoogleEventItem key={`agenda-${event.id}`} event={event} />
                                    ))}
                                </div>
                            </section>
                        )}

                        {totalItems === 0 && (
                            <div className="rounded-xl border border-dashed border-border bg-muted/20 px-4 py-10 text-center">
                                <p className="text-sm font-medium">Nothing scheduled</p>
                                <p className="mt-1 text-sm text-muted-foreground">
                                    Use week or day view if you want more room to plan around this date.
                                </p>
                            </div>
                        )}
                    </div>
                </ScrollArea>
            </SheetContent>
        </Sheet>
    )
}

// =============================================================================
// Week View
// =============================================================================

function WeekView({
    currentDate,
    appointments,
    tasks,
    googleEvents = EMPTY_GOOGLE_EVENTS,
    onEventClick,
    onTaskClick,
}: {
    currentDate: Date
    appointments: AppointmentListItem[]
    tasks: TaskListItem[]
    googleEvents?: GoogleCalendarEvent[]
    onEventClick: (appt: AppointmentListItem) => void
    onTaskClick?: (task: TaskListItem) => void
}) {
    const weekStart = startOfWeek(currentDate)
    const weekEnd = endOfWeek(currentDate)
    const days = eachDayOfInterval({ start: weekStart, end: weekEnd })

    const appointmentsByDate = new Map<string, AppointmentListItem[]>()
    appointments.forEach((appt) => {
        const dateStr = format(parseISO(appt.scheduled_start), "yyyy-MM-dd")
        if (!appointmentsByDate.has(dateStr)) appointmentsByDate.set(dateStr, [])
        appointmentsByDate.get(dateStr)!.push(appt)
    })

    const tasksByDate = groupTasksByDueDate(tasks)

    const googleEventsByDate = new Map<string, GoogleCalendarEvent[]>()
    googleEvents.forEach((event) => {
        if (event.is_all_day) {
            const startDate = event.start.slice(0, 10)
            const endDate = event.end.slice(0, 10)
            const start = parseISO(startDate)
            const end = parseISO(endDate)
            const daysToShow = eachDayOfInterval({
                start,
                end: new Date(end.getTime() - 86400000),
            })
            daysToShow.forEach((day) => {
                const dateStr = format(day, "yyyy-MM-dd")
                if (!googleEventsByDate.has(dateStr)) googleEventsByDate.set(dateStr, [])
                googleEventsByDate.get(dateStr)!.push(event)
            })
        } else {
            const dateStr = format(parseISO(event.start), "yyyy-MM-dd")
            if (!googleEventsByDate.has(dateStr)) googleEventsByDate.set(dateStr, [])
            googleEventsByDate.get(dateStr)!.push(event)
        }
    })

    return (
        // Seven readable columns need about 640px; narrower screens scroll the week sideways.
        <div className="overflow-x-auto">
        <div className="grid min-w-[640px] grid-cols-7 gap-2">
            {days.map((day) => {
                const dateStr = format(day, "yyyy-MM-dd")
                const dayAppointments = appointmentsByDate.get(dateStr) || []
                const dayTasks = tasksByDate.get(dateStr) || []
                const dayGoogleEvents = googleEventsByDate.get(dateStr) || []
                const hasEvents = dayAppointments.length > 0 || dayTasks.length > 0 || dayGoogleEvents.length > 0
                const isCurrentDay = isToday(day)

                return (
                    <div key={dateStr} className="border border-border rounded-lg overflow-hidden">
                        <div className={`p-2 text-center border-b ${isCurrentDay ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
                            <p className="text-xs font-medium">{format(day, "EEE")}</p>
                            <p className="text-lg font-semibold">{format(day, "d")}</p>
                        </div>
                        <div className="p-2 space-y-2 min-h-[200px]">
                            {dayAppointments.map((appt) => (
                                <EventItem
                                    key={appt.id}
                                    appointment={appt}
                                    onClick={onEventClick}
                                />
                            ))}
                            {dayTasks.map((task) => (
                                <TaskItem
                                    task={task}
                                    {...(onTaskClick ? { onClick: onTaskClick } : {})}
                                    key={task.id}
                                />
                            ))}
                            {dayGoogleEvents.map((event) => (
                                <GoogleEventItem
                                    key={`gcal-${event.id}`}
                                    event={event}
                                />
                            ))}
                            {!hasEvents && (
                                <p className="text-xs text-muted-foreground text-center py-4">No events</p>
                            )}
                        </div>
                    </div>
                )
            })}
        </div>
        </div>
    )
}

// =============================================================================
// Day View
// =============================================================================

function DayView({
    currentDate,
    appointments,
    tasks,
    googleEvents = EMPTY_GOOGLE_EVENTS,
    onEventClick,
    onTaskClick,
}: {
    currentDate: Date
    appointments: AppointmentListItem[]
    tasks: TaskListItem[]
    googleEvents?: GoogleCalendarEvent[]
    onEventClick: (appt: AppointmentListItem) => void
    onTaskClick?: (task: TaskListItem) => void
}) {
    const dateStr = format(currentDate, "yyyy-MM-dd")

    const dayAppointments = appointments.filter((appt) =>
        format(parseISO(appt.scheduled_start), "yyyy-MM-dd") === dateStr
    ).toSorted((a, b) => a.scheduled_start.localeCompare(b.scheduled_start))

    const dayTasks = tasks.filter((task) => task.due_date === dateStr).toSorted(compareTasksByDueTime)

    const dayGoogleEvents = googleEvents.filter((event) => {
        if (event.is_all_day) {
            // Multi-day all-day events: check if dateStr falls within range
            const startDate = event.start.slice(0, 10)
            const endDate = event.end.slice(0, 10)  // Exclusive
            // dateStr should be >= start and < end
            return dateStr >= startDate && dateStr < endDate
        } else {
            const eventDate = format(parseISO(event.start), "yyyy-MM-dd")
            return eventDate === dateStr
        }
    })

    const allDayEvents = dayGoogleEvents.filter(e => e.is_all_day)
    const timedGoogleEvents = dayGoogleEvents.filter(e => !e.is_all_day)
    const allDayTasks = dayTasks.filter((task) => !task.due_time)
    const timedTasks = dayTasks.filter((task) => task.due_time)

    const appointmentHour = (appt: AppointmentListItem) => parseISO(appt.scheduled_start).getHours()
    const taskHour = (task: TaskListItem) => parseISO(`2000-01-01T${task.due_time}`).getHours()
    const googleEventHour = (event: GoogleCalendarEvent) => parseISO(event.start).getHours()
    const timedHours = [
        ...dayAppointments.map(appointmentHour),
        ...timedTasks.map(taskHour),
        ...timedGoogleEvents.map(googleEventHour),
    ]
    // Show the hour before the first item for context, but never start later than the default hour.
    const scrollHour = timedHours.length > 0
        ? Math.max(0, Math.min(DAY_VIEW_DEFAULT_SCROLL_HOUR, Math.min(...timedHours) - 1))
        : DAY_VIEW_DEFAULT_SCROLL_HOUR
    const hourGridRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        const grid = hourGridRef.current
        const row = grid?.querySelector<HTMLElement>(`[data-hour="${scrollHour}"]`)
        if (grid && row) grid.scrollTop = row.offsetTop
    }, [dateStr, scrollHour])

    return (
        <div className="border border-border rounded-lg overflow-hidden">
            <div className="p-3 bg-muted border-b border-border text-center">
                <p className="font-medium">{format(currentDate, "EEEE, MMMM d, yyyy")}</p>
            </div>
            {(allDayEvents.length > 0 || allDayTasks.length > 0) && (
                <div className="flex border-b border-border bg-muted/50">
                    <div className="w-20 flex-shrink-0 border-r border-border p-2 text-xs text-muted-foreground">
                        All day
                    </div>
                    <div className="min-w-0 flex-1 space-y-1 p-2">
                        {allDayEvents.map((event) => (
                            <GoogleEventItem key={`gcal-${event.id}`} event={event} compact />
                        ))}
                        {allDayTasks.map((task) => (
                            <TaskItem
                                task={task}
                                compact
                                {...(onTaskClick ? { onClick: onTaskClick } : {})}
                                key={task.id}
                            />
                        ))}
                    </div>
                </div>
            )}
            <div
                ref={hourGridRef}
                data-testid="day-view-hours"
                className="relative max-h-[600px] divide-y divide-border overflow-y-auto"
            >
                {DAY_VIEW_HOURS.map((hour) => {
                    const hourAppointments = dayAppointments.filter((appt) => appointmentHour(appt) === hour)
                    const hourTasks = timedTasks.filter((task) => taskHour(task) === hour)
                    const hourGoogleEvents = timedGoogleEvents.filter((event) => googleEventHour(event) === hour)

                    return (
                        <div key={hour} data-hour={hour} className="flex min-h-[60px]">
                            <div className="w-20 p-2 text-sm text-muted-foreground border-r border-border flex-shrink-0">
                                {DAY_VIEW_HOUR_LABELS[hour]}
                            </div>
                            <div className="flex-1 p-2 space-y-1">
                                {hourAppointments.map((appt) => (
                                    <EventItem
                                        key={appt.id}
                                        appointment={appt}
                                        onClick={onEventClick}
                                    />
                                ))}
                                {hourTasks.map((task) => (
                                    <TaskItem
                                        task={task}
                                        compact
                                        {...(onTaskClick ? { onClick: onTaskClick } : {})}
                                        key={task.id}
                                    />
                                ))}
                                {hourGoogleEvents.map((event) => (
                                    <GoogleEventItem
                                        key={`gcal-${event.id}`}
                                        event={event}
                                    />
                                ))}
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}

function UnifiedCalendarHeader({
    currentDate,
    viewType,
    onNavigate,
    onTodayClick,
    onViewTypeChange,
}: {
    currentDate: Date
    viewType: ViewType
    onNavigate: (direction: "prev" | "next") => void
    onTodayClick: () => void
    onViewTypeChange: (viewType: ViewType) => void
}) {
    return (
        // Below sm the navigation takes the full first row so the period title is not cut off, and
        // Today shares the second row with the period switcher.
        <CardHeader className="flex flex-wrap items-center gap-3 border-b border-border/70 bg-muted/20 pb-4">
            <div
                data-testid="calendar-period-nav"
                className="flex w-full min-w-0 items-center rounded-xl border border-border/70 bg-background p-1 shadow-sm sm:w-auto"
            >
                <Button variant="ghost" size="sm" onClick={() => onNavigate("prev")} aria-label="Previous period">
                    <ChevronLeftIcon className="size-4" aria-hidden="true" />
                </Button>
                <div className="min-w-0 flex-1 px-2 text-center sm:min-w-[200px]">
                    <h2 className="truncate text-lg font-semibold" aria-live="polite">
                        {viewType === "month" && format(currentDate, "MMMM yyyy")}
                        {viewType === "week" && `Week of ${format(startOfWeek(currentDate), "MMM d")}`}
                        {viewType === "day" && format(currentDate, "MMMM d, yyyy")}
                    </h2>
                </div>
                <Button variant="ghost" size="sm" onClick={() => onNavigate("next")} aria-label="Next period">
                    <ChevronRightIcon className="size-4" aria-hidden="true" />
                </Button>
            </div>
            <Button variant="outline" size="sm" onClick={onTodayClick}>
                Today
            </Button>

            <Select value={viewType} onValueChange={(value) => value && onViewTypeChange(value as ViewType)}>
                <SelectTrigger aria-label="Calendar period" className="min-w-0 flex-1 bg-background sm:ml-auto sm:w-36 sm:flex-none">
                    <SelectValue placeholder="View">
                        {(value: string | null) => {
                            if (value === "month") return "Month"
                            if (value === "week") return "Week"
                            if (value === "day") return "Day"
                            return "View"
                        }}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="month">Month</SelectItem>
                    <SelectItem value="week">Week</SelectItem>
                    <SelectItem value="day">Day</SelectItem>
                </SelectContent>
            </Select>
        </CardHeader>
    )
}

function UnifiedCalendarLoadingState() {
    return (
        <div className="py-12 flex items-center justify-center">
            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
        </div>
    )
}

function GoogleCalendarDisconnectedAlert({
    calendarError,
}: {
    calendarError: string | null | undefined
}) {
    return (
        <Alert className="mb-4 border-amber-500/60 bg-amber-50 text-amber-900">
            <CalendarIcon className="size-4" />
            <AlertTitle>Google Calendar not connected</AlertTitle>
            <AlertDescription>
                {calendarError === "token_expired"
                    ? "Your Google Calendar token expired. Reconnect to show Google Calendar events."
                    : "Connect Google Calendar to show Google Calendar events alongside appointments."}
            </AlertDescription>
            <AlertAction>
                <Button size="sm" variant="outline" render={<Link href="/settings/integrations" />}>
                    Reconnect
                </Button>
            </AlertAction>
        </Alert>
    )
}

type UnifiedCalendarViewData = {
    appointments: AppointmentListItem[]
    tasks: TaskListItem[]
    googleEvents: GoogleCalendarEvent[]
}

type UnifiedCalendarViewHandlers = {
    onEventClick: (appt: AppointmentListItem) => void
    onOpenDayAgenda: (day: Date) => void
    onDragStart: (e: React.DragEvent, appointment: AppointmentListItem) => void
    onDrop: (e: React.DragEvent, date: Date) => void
    onDragOver: (e: React.DragEvent, date: Date) => void
    onDragLeave: () => void
    onTaskClick?: (task: TaskListItem) => void
}

function UnifiedCalendarViewContent({
    viewType,
    currentDate,
    includeAppointments,
    dragOverDate,
    data,
    handlers,
}: {
    viewType: ViewType
    currentDate: Date
    includeAppointments: boolean
    dragOverDate: string | null
    data: UnifiedCalendarViewData
    handlers: UnifiedCalendarViewHandlers
}) {
    if (viewType === "month") {
        return (
            <MonthView
                currentDate={currentDate}
                appointments={data.appointments}
                tasks={data.tasks}
                googleEvents={data.googleEvents}
                onEventClick={handlers.onEventClick}
                dragOverDate={dragOverDate}
                onOpenDayAgenda={handlers.onOpenDayAgenda}
                {...(handlers.onTaskClick ? { onTaskClick: handlers.onTaskClick } : {})}
                {...(includeAppointments ? {
                    onDragStart: handlers.onDragStart,
                    onDrop: handlers.onDrop,
                    onDragOver: handlers.onDragOver,
                    onDragLeave: handlers.onDragLeave,
                } : {})}
            />
        )
    }

    if (viewType === "week") {
        return (
            <WeekView
                currentDate={currentDate}
                appointments={data.appointments}
                tasks={data.tasks}
                googleEvents={data.googleEvents}
                onEventClick={handlers.onEventClick}
                {...(handlers.onTaskClick ? { onTaskClick: handlers.onTaskClick } : {})}
            />
        )
    }

    return (
        <DayView
            currentDate={currentDate}
            appointments={data.appointments}
            tasks={data.tasks}
            googleEvents={data.googleEvents}
            onEventClick={handlers.onEventClick}
            {...(handlers.onTaskClick ? { onTaskClick: handlers.onTaskClick } : {})}
        />
    )
}

function UnifiedCalendarLegend({
    includeTasks,
    includeAppointments,
    includeGoogleEvents,
}: {
    includeTasks: boolean
    includeAppointments: boolean
    includeGoogleEvents: boolean
}) {
    return (
        <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-border pt-4">
            <span className="mr-2 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                Legend
            </span>
            {includeAppointments && APPOINTMENT_STATUSES.map((status) => (
                <Badge key={status} variant="outline" className="gap-1.5 rounded-full font-normal">
                    <span className={`size-2 rounded-full ${getAppointmentStatusTone(status).dot}`} />
                    <span className="capitalize">{getAppointmentStatusLabel(status)}</span>
                </Badge>
            ))}
            {includeGoogleEvents && (
                <Badge variant="outline" className="gap-1.5 rounded-full font-normal">
                    <span className={`size-2 rounded-full ${GOOGLE_EVENT_COLOR}`} />
                    <span>Google Calendar</span>
                </Badge>
            )}
            {includeTasks && (
                <Badge variant="outline" className="gap-1.5 rounded-full font-normal">
                    <span className={`size-2 rounded-full ${TASK_COLOR}`} />
                    <span>Tasks</span>
                </Badge>
            )}
            {includeAppointments && (
                <span className="ml-auto text-xs text-muted-foreground">
                    Drag pending or confirmed appointments to open the reschedule picker.
                </span>
            )}
        </div>
    )
}

type AppointmentDetailDialogState = {
    enabled: boolean
    appointmentId: string | null
    open: boolean
    onOpenChange: (open: boolean) => void
}

type DragRescheduleDialogState = {
    enabled: boolean
    appointmentId: string | null
    open: boolean
    onOpenChange: (open: boolean) => void
    initialDateSeed: string | null
    onInitialDateSeedChange: (dateSeed: string | null) => void
}

type DayAgendaDialogState = {
    day: Date | null
    appointments: AppointmentListItem[]
    tasks: TaskListItem[]
    googleEvents: GoogleCalendarEvent[]
    open: boolean
    onOpenChange: (open: boolean) => void
    onEventClick: (appt: AppointmentListItem) => void
    onTaskClick?: (task: TaskListItem) => void
}

function UnifiedCalendarDialogs({
    appointmentDetail,
    dragReschedule,
    dayAgenda,
}: {
    appointmentDetail: AppointmentDetailDialogState
    dragReschedule: DragRescheduleDialogState
    dayAgenda: DayAgendaDialogState
}) {
    return (
        <>
            {appointmentDetail.enabled && (
                <AppointmentDetailDialog
                    appointmentId={appointmentDetail.appointmentId}
                    open={appointmentDetail.open}
                    onOpenChange={appointmentDetail.onOpenChange}
                />
            )}
            {dragReschedule.enabled && (
                <AppointmentDetailDialog
                    appointmentId={dragReschedule.appointmentId}
                    open={dragReschedule.open}
                    onOpenChange={(open) => {
                        dragReschedule.onOpenChange(open)
                        if (!open) {
                            dragReschedule.onInitialDateSeedChange(null)
                        }
                    }}
                    initialRescheduleDate={dragReschedule.initialDateSeed}
                    startInRescheduleMode={!!dragReschedule.initialDateSeed}
                />
            )}
            <DayAgendaSheet
                day={dayAgenda.day}
                appointments={dayAgenda.appointments}
                tasks={dayAgenda.tasks}
                googleEvents={dayAgenda.googleEvents}
                open={dayAgenda.open}
                onOpenChange={dayAgenda.onOpenChange}
                onEventClick={dayAgenda.onEventClick}
                {...(dayAgenda.onTaskClick ? { onTaskClick: dayAgenda.onTaskClick } : {})}
            />
        </>
    )
}

// =============================================================================
// Main Export
// =============================================================================

export function UnifiedCalendar({
    taskFilter,
    appointmentFilters,
    includeTasks = true,
    includeAppointments = true,
    includeGoogleEvents = true,
    onTaskClick,
}: {
    taskFilter?: UnifiedCalendarTaskFilter
    /** Search, type and format filters from the Appointments toolbar. */
    appointmentFilters?: Omit<AppointmentFilterParams, "date_start" | "date_end">
    includeTasks?: boolean
    includeAppointments?: boolean
    includeGoogleEvents?: boolean
    onTaskClick?: (task: TaskListItem) => void
} = {}) {
    const [currentDate, setCurrentDate] = useState(new Date())
    const [viewType, setViewType] = useState<ViewType>("month")
    const [selectedAppointmentId, setSelectedAppointmentId] = useState<string | null>(null)
    const [dialogOpen, setDialogOpen] = useState(false)
    const [dayAgendaDate, setDayAgendaDate] = useState<Date | null>(null)
    const [dayAgendaOpen, setDayAgendaOpen] = useState(false)
    const [dragRescheduleDialogOpen, setDragRescheduleDialogOpen] = useState(false)
    const [dragRescheduleAppointmentId, setDragRescheduleAppointmentId] = useState<string | null>(null)
    const [dragRescheduleDateSeed, setDragRescheduleDateSeed] = useState<string | null>(null)

    // Drag and drop state
    const draggedAppointmentRef = useRef<AppointmentListItem | null>(null)
    const [dragOverDate, setDragOverDate] = useState<string | null>(null)

    // Fetch appointments for current view range
    const start = startOfMonth(subMonths(currentDate, 1))
    const end = endOfMonth(addMonths(currentDate, 1))
    const dateRange = {
        date_start: format(start, "yyyy-MM-dd"),
        date_end: format(end, "yyyy-MM-dd"),
    }

    const {
        appointments,
        appointmentsLoading,
        tasks,
        tasksLoading,
        googleEvents,
        calendarConnected,
        calendarError,
    } = useUnifiedCalendarData({
        dateRange,
        includeTasks,
        includeAppointments,
        includeGoogleEvents,
        ...(taskFilter ? { taskFilter } : {}),
        ...(appointmentFilters ? { appointmentFilters } : {}),
    })

    // Navigation
    const navigate = (direction: "prev" | "next") => {
        if (viewType === "month") {
            setCurrentDate(direction === "prev" ? subMonths(currentDate, 1) : addMonths(currentDate, 1))
        } else if (viewType === "week") {
            const days = direction === "prev" ? -7 : 7
            setCurrentDate(new Date(currentDate.getTime() + days * 24 * 60 * 60 * 1000))
        } else {
            const days = direction === "prev" ? -1 : 1
            setCurrentDate(new Date(currentDate.getTime() + days * 24 * 60 * 60 * 1000))
        }
    }

    const handleEventClick = (appt: AppointmentListItem) => {
        if (!includeAppointments) return
        setSelectedAppointmentId(appt.id)
        setDialogOpen(true)
    }

    const handleOpenDayAgenda = (day: Date) => {
        setDayAgendaDate(day)
        setDayAgendaOpen(true)
    }

    // Drag handlers
    const handleDragStart = (e: React.DragEvent, appointment: AppointmentListItem) => {
        draggedAppointmentRef.current = appointment
        e.dataTransfer.effectAllowed = "move"
        e.dataTransfer.setData("text/plain", appointment.id)
    }

    const handleDragOver = (e: React.DragEvent, date: Date) => {
        e.preventDefault()
        setDragOverDate(format(date, "yyyy-MM-dd"))
    }

    const handleDragLeave = () => {
        setDragOverDate(null)
    }

    const handleDrop = (e: React.DragEvent, date: Date) => {
        e.preventDefault()
        setDragOverDate(null)

        const draggedAppointment = draggedAppointmentRef.current
        if (!draggedAppointment) return

        // Keep same-day drops as no-op.
        const originalStart = parseISO(draggedAppointment.scheduled_start)
        const targetDate = new Date(
            date.getFullYear(),
            date.getMonth(),
            date.getDate(),
            originalStart.getHours(),
            originalStart.getMinutes(),
            0,
            0
        )

        if (isSameDay(originalStart, targetDate)) {
            draggedAppointmentRef.current = null
            return
        }

        // Open the existing appointment management dialog in reschedule mode.
        setDragRescheduleAppointmentId(draggedAppointment.id)
        setDragRescheduleDateSeed(format(targetDate, "yyyy-MM-dd"))
        setDragRescheduleDialogOpen(true)
        draggedAppointmentRef.current = null
    }
    const handleTodayClick = () => {
        setCurrentDate(new Date())
    }

    return (
        <Card className="gap-3 overflow-hidden border-border/70">
            <UnifiedCalendarHeader
                currentDate={currentDate}
                viewType={viewType}
                onNavigate={navigate}
                onTodayClick={handleTodayClick}
                onViewTypeChange={setViewType}
            />

            <CardContent className="pt-2">
                {appointmentsLoading || tasksLoading ? (
                    <UnifiedCalendarLoadingState />
                ) : (
                    <>
                        {includeGoogleEvents && !calendarConnected && (
                            <GoogleCalendarDisconnectedAlert calendarError={calendarError} />
                        )}
                        <UnifiedCalendarViewContent
                            viewType={viewType}
                            currentDate={currentDate}
                            includeAppointments={includeAppointments}
                            dragOverDate={dragOverDate}
                            data={{
                                appointments,
                                tasks,
                                googleEvents,
                            }}
                            handlers={{
                                onEventClick: handleEventClick,
                                onOpenDayAgenda: handleOpenDayAgenda,
                                onDragStart: handleDragStart,
                                onDrop: handleDrop,
                                onDragOver: handleDragOver,
                                onDragLeave: handleDragLeave,
                                ...(onTaskClick ? { onTaskClick } : {}),
                            }}
                        />
                    </>
                )}

                {/* A tasks-only calendar has one event type, so a legend adds nothing. */}
                {(includeAppointments || includeGoogleEvents) && (
                    <UnifiedCalendarLegend
                        includeTasks={includeTasks}
                        includeAppointments={includeAppointments}
                        includeGoogleEvents={includeGoogleEvents}
                    />
                )}
            </CardContent>

            <UnifiedCalendarDialogs
                appointmentDetail={{
                    enabled: includeAppointments,
                    appointmentId: selectedAppointmentId,
                    open: dialogOpen,
                    onOpenChange: setDialogOpen,
                }}
                dragReschedule={{
                    enabled: includeAppointments,
                    appointmentId: dragRescheduleAppointmentId,
                    open: dragRescheduleDialogOpen,
                    onOpenChange: setDragRescheduleDialogOpen,
                    initialDateSeed: dragRescheduleDateSeed,
                    onInitialDateSeedChange: setDragRescheduleDateSeed,
                }}
                dayAgenda={{
                    day: dayAgendaDate,
                    appointments,
                    tasks,
                    googleEvents,
                    open: dayAgendaOpen,
                    onOpenChange: setDayAgendaOpen,
                    onEventClick: handleEventClick,
                    ...(onTaskClick ? { onTaskClick } : {}),
                }}
            />
        </Card>
    )
}
