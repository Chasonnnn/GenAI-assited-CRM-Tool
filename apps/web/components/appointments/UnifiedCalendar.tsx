"use client"

/**
 * Unified Calendar View - Combined view of appointments and tasks
 * 
 * Features:
 * - Month/week/day view toggle
 * - Appointments color-coded by status
 * - Tasks with scheduled times
 * - Click to view details
 */

import { useState, useMemo, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    ChevronLeftIcon,
    ChevronRightIcon,
    CalendarIcon,
    ClockIcon,
    VideoIcon,
    PhoneIcon,
    MapPinIcon,
    CheckSquareIcon,
    UserIcon,
    LoaderIcon,
} from "lucide-react"
import { useAppointments, useRescheduleAppointment, useGoogleCalendarEvents } from "@/lib/hooks/use-appointments"
import { useTasks } from "@/lib/hooks/use-tasks"
import type { AppointmentListItem, GoogleCalendarEvent } from "@/lib/api/appointments"
import type { TaskListItem } from "@/lib/api/tasks"
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

// Status colors for appointments
const STATUS_COLORS = {
    pending: "bg-yellow-500",
    confirmed: "bg-green-500",
    completed: "bg-blue-500",
    cancelled: "bg-red-500",
    no_show: "bg-gray-500",
    expired: "bg-gray-500",
}

// Task color
const TASK_COLOR = "bg-purple-500"

// Google Calendar event color
const GOOGLE_EVENT_COLOR = "bg-slate-400"

// Meeting mode icons
const MEETING_MODE_ICONS = {
    zoom: VideoIcon,
    phone: PhoneIcon,
    in_person: MapPinIcon,
}

// View type
type ViewType = "month" | "week" | "day"

// =============================================================================
// Task Item Component
// =============================================================================

function TaskItem({
    task,
    compact = false,
}: {
    task: TaskListItem
    compact?: boolean
}) {
    const time = task.due_time ? format(parseISO(`2000-01-01T${task.due_time}`), "h:mm a") : ""

    if (compact) {
        return (
            <div className={`w-full text-left px-2 py-1 rounded text-xs truncate ${TASK_COLOR} text-white`}>
                {time && `${time} - `}📋 {task.title}
            </div>
        )
    }

    return (
        <div className={`w-full text-left p-2 rounded-lg border-l-4 border-purple-500 bg-muted/50`}>
            <p className="font-medium text-sm truncate flex items-center gap-1">
                <CheckSquareIcon className="size-3" />
                {task.title}
            </p>
            {time && <p className="text-xs text-muted-foreground">{time}</p>}
            {task.case_number && (
                <p className="text-xs text-muted-foreground">Case #{task.case_number}</p>
            )}
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

    const handleClick = () => {
        if (event.html_link) {
            window.open(event.html_link, "_blank", "noopener,noreferrer")
        }
    }

    if (compact) {
        return (
            <div
                onClick={handleClick}
                className={`w-full text-left px-2 py-1 rounded text-xs truncate ${GOOGLE_EVENT_COLOR} text-white cursor-pointer hover:opacity-90`}
                title="Click to open in Google Calendar"
            >
                {time} - 🌐 {event.summary}
            </div>
        )
    }

    return (
        <div
            onClick={handleClick}
            className={`w-full text-left p-2 rounded-lg border-l-4 border-slate-400 bg-muted/50 cursor-pointer hover:bg-muted`}
            title="Click to open in Google Calendar"
        >
            <p className="font-medium text-sm truncate flex items-center gap-1">
                🌐 {event.summary}
            </p>
            <p className="text-xs text-muted-foreground">{time}</p>
            <p className="text-xs text-muted-foreground/70">Google Calendar</p>
        </div>
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
    onClick: () => void
    compact?: boolean
    draggable?: boolean
    onDragStart?: (e: React.DragEvent, appointment: AppointmentListItem) => void
}) {
    const statusColor = STATUS_COLORS[appointment.status as keyof typeof STATUS_COLORS] || "bg-gray-500"
    const time = format(parseISO(appointment.scheduled_start), "h:mm a")
    const canDrag = draggable && (appointment.status === "pending" || appointment.status === "confirmed")

    const handleDragStart = (e: React.DragEvent) => {
        if (onDragStart && canDrag) {
            onDragStart(e, appointment)
        }
    }

    if (compact) {
        return (
            <div
                draggable={canDrag}
                onDragStart={handleDragStart}
                onClick={onClick}
                className={`w-full text-left px-2 py-1 rounded text-xs truncate ${statusColor} text-white hover:opacity-90 transition-opacity ${canDrag ? "cursor-grab active:cursor-grabbing" : "cursor-pointer"}`}
            >
                {time} - {appointment.client_name}
            </div>
        )
    }

    return (
        <div
            draggable={canDrag}
            onDragStart={handleDragStart}
            onClick={onClick}
            className={`w-full text-left p-2 rounded-lg border-l-4 ${statusColor.replace('bg-', 'border-')} bg-muted/50 hover:bg-muted transition-colors ${canDrag ? "cursor-grab active:cursor-grabbing" : "cursor-pointer"}`}
        >
            <p className="font-medium text-sm truncate">{appointment.client_name}</p>
            <p className="text-xs text-muted-foreground">{time}</p>
            {appointment.appointment_type_name && (
                <p className="text-xs text-muted-foreground truncate">{appointment.appointment_type_name}</p>
            )}
        </div>
    )
}

// =============================================================================
// Appointment Detail Dialog
// =============================================================================

function AppointmentDetailDialog({
    appointment,
    open,
    onOpenChange,
}: {
    appointment: AppointmentListItem | null
    open: boolean
    onOpenChange: (open: boolean) => void
}) {
    if (!appointment) return null

    const ModeIcon = MEETING_MODE_ICONS[appointment.meeting_mode as keyof typeof MEETING_MODE_ICONS] || VideoIcon
    const statusColor = STATUS_COLORS[appointment.status as keyof typeof STATUS_COLORS] || "bg-gray-500"

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <CalendarIcon className="size-5" />
                        Appointment Details
                    </DialogTitle>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    <div className="flex items-center gap-2">
                        <Badge className={`${statusColor} text-white`}>
                            {appointment.status.replace("_", " ")}
                        </Badge>
                    </div>

                    <div>
                        <p className="text-sm text-muted-foreground">Client</p>
                        <p className="font-medium flex items-center gap-2">
                            <UserIcon className="size-4" />
                            {appointment.client_name}
                        </p>
                        <p className="text-sm text-muted-foreground">{appointment.client_email}</p>
                        <p className="text-sm text-muted-foreground">{appointment.client_phone}</p>
                    </div>

                    <div>
                        <p className="text-sm text-muted-foreground">Date & Time</p>
                        <p className="font-medium flex items-center gap-2">
                            <CalendarIcon className="size-4" />
                            {format(parseISO(appointment.scheduled_start), "EEEE, MMMM d, yyyy")}
                        </p>
                        <p className="flex items-center gap-2 text-muted-foreground">
                            <ClockIcon className="size-4" />
                            {format(parseISO(appointment.scheduled_start), "h:mm a")} - {format(parseISO(appointment.scheduled_end), "h:mm a")}
                        </p>
                    </div>

                    <div>
                        <p className="text-sm text-muted-foreground">Meeting Type</p>
                        <p className="font-medium flex items-center gap-2 capitalize">
                            <ModeIcon className="size-4" />
                            {appointment.meeting_mode.replace("_", " ")}
                        </p>
                    </div>

                    {appointment.appointment_type_name && (
                        <div>
                            <p className="text-sm text-muted-foreground">Appointment Type</p>
                            <p className="font-medium">{appointment.appointment_type_name}</p>
                        </div>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    )
}

// =============================================================================
// Month View
// =============================================================================

function MonthView({
    currentDate,
    appointments,
    googleEvents = [],
    onEventClick,
    onDragStart,
    onDrop,
    dragOverDate,
    onDragOver,
    onDragLeave,
}: {
    currentDate: Date
    appointments: AppointmentListItem[]
    googleEvents?: GoogleCalendarEvent[]
    onEventClick: (appt: AppointmentListItem) => void
    onDragStart?: (e: React.DragEvent, appointment: AppointmentListItem) => void
    onDrop?: (e: React.DragEvent, date: Date) => void
    dragOverDate?: string | null
    onDragOver?: (e: React.DragEvent, date: Date) => void
    onDragLeave?: (e: React.DragEvent) => void
}) {
    const days = useMemo(() => {
        const monthStart = startOfMonth(currentDate)
        const monthEnd = endOfMonth(currentDate)
        const calendarStart = startOfWeek(monthStart)
        const calendarEnd = endOfWeek(monthEnd)

        return eachDayOfInterval({ start: calendarStart, end: calendarEnd })
    }, [currentDate])

    const appointmentsByDate = useMemo(() => {
        const map = new Map<string, AppointmentListItem[]>()
        appointments.forEach((appt) => {
            const dateStr = format(parseISO(appt.scheduled_start), "yyyy-MM-dd")
            if (!map.has(dateStr)) map.set(dateStr, [])
            map.get(dateStr)!.push(appt)
        })
        return map
    }, [appointments])

    const googleEventsByDate = useMemo(() => {
        const map = new Map<string, GoogleCalendarEvent[]>()
        googleEvents.forEach((event) => {
            // For all-day events, extract date directly from ISO string to avoid TZ shift
            // All-day: "2025-01-15" vs timed: "2025-01-15T10:00:00+00:00"
            const dateStr = event.is_all_day
                ? event.start.slice(0, 10)  // Extract YYYY-MM-DD directly
                : format(parseISO(event.start), "yyyy-MM-dd")
            if (!map.has(dateStr)) map.set(dateStr, [])
            map.get(dateStr)!.push(event)
        })
        return map
    }, [googleEvents])

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
                {days.map((day, i) => {
                    const dateStr = format(day, "yyyy-MM-dd")
                    const dayAppointments = appointmentsByDate.get(dateStr) || []
                    const dayGoogleEvents = googleEventsByDate.get(dateStr) || []
                    const totalEvents = dayAppointments.length + dayGoogleEvents.length
                    const isCurrentMonth = isSameMonth(day, currentDate)
                    const isCurrentDay = isToday(day)
                    const isDropTarget = dragOverDate === dateStr

                    return (
                        <div
                            key={i}
                            className={`min-h-[100px] p-1 border-b border-r border-border transition-colors ${!isCurrentMonth ? "bg-muted/30" : ""} ${isDropTarget ? "bg-primary/10 ring-2 ring-primary/50 ring-inset" : ""}`}
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
                            <div className={`text-sm p-1 ${isCurrentDay ? "bg-primary text-primary-foreground rounded-full w-7 h-7 flex items-center justify-center" : ""} ${!isCurrentMonth ? "text-muted-foreground" : ""}`}>
                                {format(day, "d")}
                            </div>
                            <div className="space-y-1 mt-1">
                                {/* CRM Appointments */}
                                {dayAppointments.slice(0, 2).map((appt) => (
                                    <EventItem
                                        key={appt.id}
                                        appointment={appt}
                                        onClick={() => onEventClick(appt)}
                                        compact
                                        draggable
                                        onDragStart={onDragStart}
                                    />
                                ))}
                                {/* Google Calendar Events */}
                                {dayGoogleEvents.slice(0, Math.max(0, 3 - dayAppointments.length)).map((event) => (
                                    <GoogleEventItem
                                        key={`gcal-${event.id}`}
                                        event={event}
                                        compact
                                    />
                                ))}
                                {totalEvents > 3 && (
                                    <p className="text-xs text-muted-foreground text-center">
                                        +{totalEvents - 3} more
                                    </p>
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
// Week View
// =============================================================================

function WeekView({
    currentDate,
    appointments,
    googleEvents = [],
    onEventClick,
}: {
    currentDate: Date
    appointments: AppointmentListItem[]
    googleEvents?: GoogleCalendarEvent[]
    onEventClick: (appt: AppointmentListItem) => void
}) {
    const days = useMemo(() => {
        const weekStart = startOfWeek(currentDate)
        const weekEnd = endOfWeek(currentDate)
        return eachDayOfInterval({ start: weekStart, end: weekEnd })
    }, [currentDate])

    const appointmentsByDate = useMemo(() => {
        const map = new Map<string, AppointmentListItem[]>()
        appointments.forEach((appt) => {
            const dateStr = format(parseISO(appt.scheduled_start), "yyyy-MM-dd")
            if (!map.has(dateStr)) map.set(dateStr, [])
            map.get(dateStr)!.push(appt)
        })
        return map
    }, [appointments])

    const googleEventsByDate = useMemo(() => {
        const map = new Map<string, GoogleCalendarEvent[]>()
        googleEvents.forEach((event) => {
            const dateStr = event.is_all_day
                ? event.start.slice(0, 10)
                : format(parseISO(event.start), "yyyy-MM-dd")
            if (!map.has(dateStr)) map.set(dateStr, [])
            map.get(dateStr)!.push(event)
        })
        return map
    }, [googleEvents])

    return (
        <div className="grid grid-cols-7 gap-2">
            {days.map((day) => {
                const dateStr = format(day, "yyyy-MM-dd")
                const dayAppointments = appointmentsByDate.get(dateStr) || []
                const dayGoogleEvents = googleEventsByDate.get(dateStr) || []
                const hasEvents = dayAppointments.length > 0 || dayGoogleEvents.length > 0
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
                                    onClick={() => onEventClick(appt)}
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
    )
}

// =============================================================================
// Day View
// =============================================================================

function DayView({
    currentDate,
    appointments,
    googleEvents = [],
    onEventClick,
}: {
    currentDate: Date
    appointments: AppointmentListItem[]
    googleEvents?: GoogleCalendarEvent[]
    onEventClick: (appt: AppointmentListItem) => void
}) {
    const dateStr = format(currentDate, "yyyy-MM-dd")

    const dayAppointments = useMemo(() => {
        return appointments.filter((appt) =>
            format(parseISO(appt.scheduled_start), "yyyy-MM-dd") === dateStr
        ).sort((a, b) => a.scheduled_start.localeCompare(b.scheduled_start))
    }, [dateStr, appointments])

    const dayGoogleEvents = useMemo(() => {
        return googleEvents.filter((event) => {
            const eventDate = event.is_all_day
                ? event.start.slice(0, 10)
                : format(parseISO(event.start), "yyyy-MM-dd")
            return eventDate === dateStr
        })
    }, [dateStr, googleEvents])

    const allDayEvents = dayGoogleEvents.filter(e => e.is_all_day)
    const timedGoogleEvents = dayGoogleEvents.filter(e => !e.is_all_day)

    // Time slots (8am - 8pm)
    const hours = Array.from({ length: 13 }, (_, i) => i + 8)

    return (
        <div className="border border-border rounded-lg overflow-hidden">
            <div className="p-3 bg-muted border-b border-border text-center">
                <p className="font-medium">{format(currentDate, "EEEE, MMMM d, yyyy")}</p>
            </div>
            {/* All-day events section */}
            {allDayEvents.length > 0 && (
                <div className="p-2 bg-muted/50 border-b border-border">
                    <p className="text-xs text-muted-foreground mb-1">All day</p>
                    <div className="space-y-1">
                        {allDayEvents.map((event) => (
                            <GoogleEventItem key={`gcal-${event.id}`} event={event} compact />
                        ))}
                    </div>
                </div>
            )}
            <div className="divide-y divide-border">
                {hours.map((hour) => {
                    const hourAppointments = dayAppointments.filter((appt) => {
                        const apptHour = parseISO(appt.scheduled_start).getHours()
                        return apptHour === hour
                    })
                    const hourGoogleEvents = timedGoogleEvents.filter((event) => {
                        const eventHour = parseISO(event.start).getHours()
                        return eventHour === hour
                    })

                    return (
                        <div key={hour} className="flex min-h-[60px]">
                            <div className="w-20 p-2 text-sm text-muted-foreground border-r border-border flex-shrink-0">
                                {format(new Date(2000, 0, 1, hour), "h:mm a")}
                            </div>
                            <div className="flex-1 p-2 space-y-1">
                                {hourAppointments.map((appt) => (
                                    <EventItem
                                        key={appt.id}
                                        appointment={appt}
                                        onClick={() => onEventClick(appt)}
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

// =============================================================================
// Main Export
// =============================================================================

export function UnifiedCalendar() {
    const [currentDate, setCurrentDate] = useState(new Date())
    const [viewType, setViewType] = useState<ViewType>("month")
    const [selectedAppointment, setSelectedAppointment] = useState<AppointmentListItem | null>(null)
    const [dialogOpen, setDialogOpen] = useState(false)

    // Drag and drop state
    const [draggedAppointment, setDraggedAppointment] = useState<AppointmentListItem | null>(null)
    const [dragOverDate, setDragOverDate] = useState<string | null>(null)

    // Reschedule mutation
    const rescheduleMutation = useRescheduleAppointment()

    // Fetch appointments for current view range
    const dateRange = useMemo(() => {
        const start = startOfMonth(subMonths(currentDate, 1))
        const end = endOfMonth(addMonths(currentDate, 1))
        return {
            date_start: format(start, "yyyy-MM-dd"),
            date_end: format(end, "yyyy-MM-dd"),
        }
    }, [currentDate])

    const { data, isLoading } = useAppointments({
        ...dateRange,
        per_page: 100,
    })

    const appointments = data?.items || []

    // Fetch Google Calendar events
    const { data: googleEventsData } = useGoogleCalendarEvents(
        dateRange.date_start,
        dateRange.date_end
    )
    const googleEvents = googleEventsData || []

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
        setSelectedAppointment(appt)
        setDialogOpen(true)
    }

    // Drag handlers
    const handleDragStart = useCallback((e: React.DragEvent, appointment: AppointmentListItem) => {
        setDraggedAppointment(appointment)
        e.dataTransfer.effectAllowed = "move"
        e.dataTransfer.setData("text/plain", appointment.id)
    }, [])

    const handleDragOver = useCallback((e: React.DragEvent, date: Date) => {
        e.preventDefault()
        setDragOverDate(format(date, "yyyy-MM-dd"))
    }, [])

    const handleDragLeave = useCallback(() => {
        setDragOverDate(null)
    }, [])

    const handleDrop = useCallback((e: React.DragEvent, date: Date) => {
        e.preventDefault()
        setDragOverDate(null)

        if (!draggedAppointment) return

        // Calculate new scheduled start by preserving the original time
        const originalStart = parseISO(draggedAppointment.scheduled_start)
        const newStart = new Date(
            date.getFullYear(),
            date.getMonth(),
            date.getDate(),
            originalStart.getHours(),
            originalStart.getMinutes(),
            0,
            0
        )

        // Don't reschedule if same day
        if (isSameDay(originalStart, newStart)) {
            setDraggedAppointment(null)
            return
        }

        rescheduleMutation.mutate({
            appointmentId: draggedAppointment.id,
            scheduledStart: newStart.toISOString(),
        }, {
            onSettled: () => {
                setDraggedAppointment(null)
            }
        })
    }, [draggedAppointment, rescheduleMutation])

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
                <div className="flex items-center gap-4">
                    <Button variant="outline" size="sm" onClick={() => navigate("prev")}>
                        <ChevronLeftIcon className="size-4" />
                    </Button>
                    <h2 className="text-lg font-semibold min-w-[200px] text-center">
                        {viewType === "month" && format(currentDate, "MMMM yyyy")}
                        {viewType === "week" && `Week of ${format(startOfWeek(currentDate), "MMM d")}`}
                        {viewType === "day" && format(currentDate, "MMMM d, yyyy")}
                    </h2>
                    <Button variant="outline" size="sm" onClick={() => navigate("next")}>
                        <ChevronRightIcon className="size-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setCurrentDate(new Date())}>
                        Today
                    </Button>
                </div>

                <Select value={viewType} onValueChange={(v) => v && setViewType(v as ViewType)}>
                    <SelectTrigger className="w-32">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="month">Month</SelectItem>
                        <SelectItem value="week">Week</SelectItem>
                        <SelectItem value="day">Day</SelectItem>
                    </SelectContent>
                </Select>
            </CardHeader>

            <CardContent>
                {isLoading ? (
                    <div className="py-12 flex items-center justify-center">
                        <LoaderIcon className="size-8 animate-spin text-muted-foreground" />
                    </div>
                ) : (
                    <>
                        {viewType === "month" && (
                            <MonthView
                                currentDate={currentDate}
                                appointments={appointments}
                                googleEvents={googleEvents}
                                onEventClick={handleEventClick}
                                onDragStart={handleDragStart}
                                onDrop={handleDrop}
                                dragOverDate={dragOverDate}
                                onDragOver={handleDragOver}
                                onDragLeave={handleDragLeave}
                            />
                        )}
                        {viewType === "week" && (
                            <WeekView
                                currentDate={currentDate}
                                appointments={appointments}
                                googleEvents={googleEvents}
                                onEventClick={handleEventClick}
                            />
                        )}
                        {viewType === "day" && (
                            <DayView
                                currentDate={currentDate}
                                appointments={appointments}
                                googleEvents={googleEvents}
                                onEventClick={handleEventClick}
                            />
                        )}
                    </>
                )}

                {/* Legend */}
                <div className="flex flex-wrap items-center gap-4 mt-4 pt-4 border-t border-border">
                    <span className="text-sm text-muted-foreground">Status:</span>
                    {Object.entries(STATUS_COLORS).map(([status, color]) => (
                        <div key={status} className="flex items-center gap-1.5">
                            <div className={`size-3 rounded-full ${color}`} />
                            <span className="text-xs capitalize">{status.replace("_", " ")}</span>
                        </div>
                    ))}
                    <div className="flex items-center gap-1.5">
                        <div className={`size-3 rounded-full ${GOOGLE_EVENT_COLOR}`} />
                        <span className="text-xs">🌐 Google Calendar</span>
                    </div>
                    <span className="text-xs text-muted-foreground ml-auto">
                        💡 Drag pending/confirmed appointments to reschedule
                    </span>
                </div>
            </CardContent>

            <AppointmentDetailDialog
                appointment={selectedAppointment}
                open={dialogOpen}
                onOpenChange={setDialogOpen}
            />
        </Card>
    )
}

