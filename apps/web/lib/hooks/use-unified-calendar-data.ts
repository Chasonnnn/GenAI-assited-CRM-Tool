/**
 * Unified Calendar data hook.
 *
 * Centralizes fetching of appointments, tasks, and Google Calendar events
 * for the calendar views.
 */

import { useAppointments, useGoogleCalendarEvents } from "@/lib/hooks/use-appointments"
import { useTasks } from "@/lib/hooks/use-tasks"
import type { AppointmentFilterParams, AppointmentListItem, GoogleCalendarEvent } from "@/lib/api/appointments"
import type { TaskLinkedType, TaskListItem } from "@/lib/api/tasks"

export type UnifiedCalendarTaskFilter = {
    my_tasks?: boolean
    surrogate_id?: string
    intended_parent_id?: string
    donor_id?: string
    q?: string
    owner_id?: string
    linked_type?: TaskLinkedType
    /** Defaults to false (open tasks); null includes completed tasks. */
    is_completed?: boolean | null
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

function getBrowserTimezone(): string {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Los_Angeles"
}

export function useUnifiedCalendarData({
    dateRange,
    includeTasks = true,
    includeAppointments = true,
    includeGoogleEvents = true,
    taskFilter,
    appointmentFilters,
}: {
    dateRange: UnifiedCalendarDateRange
    includeTasks?: boolean
    includeAppointments?: boolean
    includeGoogleEvents?: boolean
    taskFilter?: UnifiedCalendarTaskFilter
    appointmentFilters?: Omit<AppointmentFilterParams, "date_start" | "date_end">
}): UnifiedCalendarData {
    const { data, isLoading: appointmentsLoadingRaw } = useAppointments(
        {
            ...appointmentFilters,
            ...dateRange,
            per_page: 100,
        },
        { enabled: includeAppointments }
    )

    const appointments = includeAppointments ? data?.items || [] : []
    const appointmentsLoading = includeAppointments ? appointmentsLoadingRaw : false

    const userTimezone = getBrowserTimezone()

    const { data: googleEventsData } = useGoogleCalendarEvents(
        dateRange.date_start,
        dateRange.date_end,
        userTimezone,
        { enabled: includeGoogleEvents }
    )
    const googleEvents = includeGoogleEvents ? googleEventsData?.events || [] : []
    const calendarConnected = includeGoogleEvents ? googleEventsData?.connected ?? true : true
    const calendarError = includeGoogleEvents ? googleEventsData?.error ?? null : null

    const isCompleted = taskFilter?.is_completed === undefined ? false : taskFilter.is_completed
    const taskParams = {
        ...(isCompleted === null ? {} : { is_completed: isCompleted }),
        per_page: 100,
        due_after: dateRange.date_start,
        due_before: dateRange.date_end,
        exclude_approvals: true,
        ...(taskFilter?.my_tasks ? { my_tasks: true } : {}),
        ...(taskFilter?.surrogate_id ? { surrogate_id: taskFilter.surrogate_id } : {}),
        ...(taskFilter?.intended_parent_id
            ? { intended_parent_id: taskFilter.intended_parent_id }
            : {}),
        ...(taskFilter?.donor_id ? { donor_id: taskFilter.donor_id } : {}),
        ...(taskFilter?.q ? { q: taskFilter.q } : {}),
        ...(taskFilter?.owner_id ? { owner_id: taskFilter.owner_id } : {}),
        ...(taskFilter?.linked_type ? { linked_type: taskFilter.linked_type } : {}),
    }
    const { data: tasksData, isLoading: tasksLoadingRaw } = useTasks(taskParams, { enabled: includeTasks })
    const tasks = includeTasks ? tasksData?.items || [] : []
    const tasksLoading = includeTasks ? tasksLoadingRaw : false

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
