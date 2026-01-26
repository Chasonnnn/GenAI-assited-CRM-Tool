/**
 * Unified Calendar data hook.
 *
 * Centralizes fetching of appointments, tasks, and Google Calendar events
 * for the calendar views.
 */

import { useMemo } from "react"
import { useAppointments, useGoogleCalendarEvents } from "@/lib/hooks/use-appointments"
import { useTasks } from "@/lib/hooks/use-tasks"
import type { AppointmentListItem, GoogleCalendarEvent } from "@/lib/api/appointments"
import type { TaskListItem } from "@/lib/api/tasks"

export type UnifiedCalendarTaskFilter = {
    my_tasks?: boolean
    surrogate_id?: string
}

export type UnifiedCalendarDateRange = {
    date_start: string
    date_end: string
}

export type UnifiedCalendarData = {
    appointments: AppointmentListItem[]
    appointmentsLoading: boolean
    tasks: TaskListItem[]
    tasksLoading: boolean
    googleEvents: GoogleCalendarEvent[]
    calendarConnected: boolean
    calendarError: string | null
    userTimezone: string
}

export function useUnifiedCalendarData({
    dateRange,
    includeAppointments = true,
    includeGoogleEvents = true,
    taskFilter,
}: {
    dateRange: UnifiedCalendarDateRange
    includeAppointments?: boolean
    includeGoogleEvents?: boolean
    taskFilter?: UnifiedCalendarTaskFilter
}): UnifiedCalendarData {
    const { data, isLoading: appointmentsLoadingRaw } = useAppointments(
        {
            ...dateRange,
            per_page: 100,
        },
        { enabled: includeAppointments }
    )

    const appointments = includeAppointments ? data?.items || [] : []
    const appointmentsLoading = includeAppointments ? appointmentsLoadingRaw : false

    const userTimezone = useMemo(
        () => Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Los_Angeles",
        []
    )

    const { data: googleEventsData } = useGoogleCalendarEvents(
        dateRange.date_start,
        dateRange.date_end,
        userTimezone,
        { enabled: includeGoogleEvents }
    )
    const googleEvents = includeGoogleEvents ? googleEventsData?.events || [] : []
    const calendarConnected = includeGoogleEvents ? googleEventsData?.connected ?? true : true
    const calendarError = includeGoogleEvents ? googleEventsData?.error ?? null : null

    const taskParams = {
        is_completed: false,
        per_page: 100,
        due_after: dateRange.date_start,
        due_before: dateRange.date_end,
        exclude_approvals: true,
        ...(taskFilter?.my_tasks ? { my_tasks: true } : {}),
        ...(taskFilter?.surrogate_id ? { surrogate_id: taskFilter.surrogate_id } : {}),
    }
    const { data: tasksData, isLoading: tasksLoading } = useTasks(taskParams)
    const tasks = tasksData?.items || []

    return {
        appointments,
        appointmentsLoading,
        tasks,
        tasksLoading,
        googleEvents,
        calendarConnected,
        calendarError,
        userTimezone,
    }
}
