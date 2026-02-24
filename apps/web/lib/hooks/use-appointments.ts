/**
 * React Query hooks for Appointments module.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import * as appointmentsApi from '../api/appointments';

// =============================================================================
// Query Keys
// =============================================================================

export const appointmentKeys = {
    all: ['appointments'] as const,
    types: () => [...appointmentKeys.all, 'types'] as const,
    typesList: (activeOnly: boolean) => [...appointmentKeys.types(), { activeOnly }] as const,
    availability: () => [...appointmentKeys.all, 'availability'] as const,
    overrides: () => [...appointmentKeys.all, 'overrides'] as const,
    overridesList: (dateStart?: string, dateEnd?: string) =>
        [...appointmentKeys.overrides(), { dateStart, dateEnd }] as const,
    bookingLink: () => [...appointmentKeys.all, 'bookingLink'] as const,
    lists: () => [...appointmentKeys.all, 'list'] as const,
    list: (params: {
        page?: number;
        status?: string;
        date_start?: string;
        date_end?: string;
    }) => [...appointmentKeys.lists(), params] as const,
    details: () => [...appointmentKeys.all, 'detail'] as const,
    detail: (id: string) => [...appointmentKeys.details(), id] as const,
    rescheduleSlots: (
        appointmentId: string,
        dateStart: string,
        dateEnd?: string,
        clientTimezone?: string,
    ) =>
        [
            ...appointmentKeys.all,
            'reschedule-slots',
            { appointmentId, dateStart, dateEnd, clientTimezone },
        ] as const,
};

// =============================================================================
// Appointment Types
// =============================================================================

export function useAppointmentTypes(activeOnly = true) {
    return useQuery({
        queryKey: appointmentKeys.typesList(activeOnly),
        queryFn: () => appointmentsApi.getAppointmentTypes(activeOnly),
    });
}

export function useCreateAppointmentType() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: appointmentsApi.createAppointmentType,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: appointmentKeys.types() });
        },
    });
}

export function useUpdateAppointmentType() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            typeId,
            data,
        }: {
            typeId: string;
            data: Partial<appointmentsApi.AppointmentTypeCreate & { is_active: boolean }>;
        }) => appointmentsApi.updateAppointmentType(typeId, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: appointmentKeys.types() });
        },
    });
}

export function useDeleteAppointmentType() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: appointmentsApi.deleteAppointmentType,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: appointmentKeys.types() });
        },
    });
}

// =============================================================================
// Availability Rules
// =============================================================================

export function useAvailabilityRules() {
    return useQuery({
        queryKey: appointmentKeys.availability(),
        queryFn: appointmentsApi.getAvailabilityRules,
    });
}

export function useSetAvailabilityRules() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            rules,
            timezone,
        }: {
            rules: appointmentsApi.AvailabilityRuleInput[];
            timezone: string;
        }) => appointmentsApi.setAvailabilityRules(rules, timezone),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: appointmentKeys.availability() });
        },
    });
}

// =============================================================================
// Availability Overrides
// =============================================================================

export function useAvailabilityOverrides(dateStart?: string, dateEnd?: string) {
    return useQuery({
        queryKey: appointmentKeys.overridesList(dateStart, dateEnd),
        queryFn: () => appointmentsApi.getAvailabilityOverrides(dateStart, dateEnd),
    });
}

export function useCreateAvailabilityOverride() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: appointmentsApi.createAvailabilityOverride,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: appointmentKeys.overrides() });
        },
    });
}

export function useDeleteAvailabilityOverride() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: appointmentsApi.deleteAvailabilityOverride,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: appointmentKeys.overrides() });
        },
    });
}

// =============================================================================
// Booking Link
// =============================================================================

export function useBookingLink() {
    return useQuery({
        queryKey: appointmentKeys.bookingLink(),
        queryFn: appointmentsApi.getBookingLink,
    });
}

export function useRegenerateBookingLink() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: appointmentsApi.regenerateBookingLink,
        onSuccess: (newLink) => {
            queryClient.setQueryData(appointmentKeys.bookingLink(), newLink);
        },
    });
}

// =============================================================================
// Appointments
// =============================================================================

export function useAppointments(
    params: {
    page?: number;
    per_page?: number;
    status?: string;
    date_start?: string;
    date_end?: string;
    surrogate_id?: string;
    intended_parent_id?: string;
    },
    options?: { enabled?: boolean },
) {
    return useQuery({
        queryKey: appointmentKeys.list(params),
        queryFn: () => appointmentsApi.getAppointments(params),
        enabled: options?.enabled ?? true,
    });
}

export function useAppointment(appointmentId: string) {
    return useQuery({
        queryKey: appointmentKeys.detail(appointmentId),
        queryFn: () => appointmentsApi.getAppointment(appointmentId),
        enabled: !!appointmentId,
    });
}

export function useRescheduleSlots(
    appointmentId: string,
    dateStart: string,
    dateEnd?: string,
    clientTimezone?: string,
    enabled = true,
) {
    return useQuery({
        queryKey: appointmentKeys.rescheduleSlots(
            appointmentId,
            dateStart,
            dateEnd,
            clientTimezone,
        ),
        queryFn: () =>
            appointmentsApi.getRescheduleSlots(
                appointmentId,
                dateStart,
                dateEnd,
                clientTimezone,
            ),
        enabled: enabled && !!appointmentId && !!dateStart,
    })
}

export function useApproveAppointment() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: appointmentsApi.approveAppointment,
        onSuccess: (updatedAppt) => {
            queryClient.setQueryData(appointmentKeys.detail(updatedAppt.id), updatedAppt);
            queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() });
        },
    });
}

export function useRescheduleAppointment() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            appointmentId,
            scheduledStart,
        }: {
            appointmentId: string;
            scheduledStart: string;
        }) => appointmentsApi.rescheduleAppointment(appointmentId, scheduledStart),
        onSuccess: (updatedAppt) => {
            queryClient.setQueryData(appointmentKeys.detail(updatedAppt.id), updatedAppt);
            queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() });
        },
        onError: (error) => {
            const message =
                error instanceof Error && error.message
                    ? error.message
                    : 'Failed to reschedule appointment.';
            toast.error(message);
        },
    });
}

export function useCancelAppointment() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            appointmentId,
            reason,
        }: {
            appointmentId: string;
            reason?: string;
        }) => appointmentsApi.cancelAppointment(appointmentId, reason),
        onSuccess: (updatedAppt) => {
            queryClient.setQueryData(appointmentKeys.detail(updatedAppt.id), updatedAppt);
            queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() });
        },
    });
}

export function useUpdateAppointmentLink() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            appointmentId,
            data,
        }: {
            appointmentId: string;
            data: appointmentsApi.AppointmentLinkUpdate;
        }) => appointmentsApi.updateAppointmentLink(appointmentId, data),
        onSuccess: (updatedAppt) => {
            queryClient.setQueryData(appointmentKeys.detail(updatedAppt.id), updatedAppt);
            queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() });
        },
    });
}

// =============================================================================
// Public Booking Hooks
// =============================================================================

export const bookingKeys = {
    all: ['booking'] as const,
    page: (slug: string) => [...bookingKeys.all, 'page', slug] as const,
    slots: (
        slug: string,
        typeId: string,
        dateStart: string,
        dateEnd?: string,
        clientTimezone?: string
    ) =>
        [
            ...bookingKeys.all,
            'slots',
            { slug, typeId, dateStart, dateEnd, clientTimezone },
        ] as const,
    manage: (orgId: string, token: string) =>
        [...bookingKeys.all, 'manage', { orgId, token }] as const,
};

export function usePublicBookingPage(publicSlug: string, enabled = true) {
    return useQuery({
        queryKey: bookingKeys.page(publicSlug),
        queryFn: () => appointmentsApi.getPublicBookingPage(publicSlug),
        enabled: enabled && !!publicSlug,
    });
}

export function useAvailableSlots(
    publicSlug: string,
    appointmentTypeId: string,
    dateStart: string,
    dateEnd?: string,
    clientTimezone?: string,
    enabled = true
) {
    return useQuery({
        queryKey: bookingKeys.slots(
            publicSlug,
            appointmentTypeId,
            dateStart,
            dateEnd,
            clientTimezone
        ),
        queryFn: () =>
            appointmentsApi.getAvailableSlots(
                publicSlug,
                appointmentTypeId,
                dateStart,
                dateEnd,
                clientTimezone
            ),
        enabled: enabled && !!publicSlug && !!appointmentTypeId && !!dateStart,
    });
}

export function useCreateBooking() {
    return useMutation({
        mutationFn: ({
            publicSlug,
            data,
        }: {
            publicSlug: string;
            data: appointmentsApi.BookingCreate;
        }) => appointmentsApi.createBooking(publicSlug, data),
    });
}

export function useAppointmentForManage(orgId: string, token: string, enabled = true) {
    return useQuery({
        queryKey: bookingKeys.manage(orgId, token),
        queryFn: () => appointmentsApi.getAppointmentForManage(orgId, token),
        enabled: enabled && !!orgId && !!token,
    })
}

export function useRescheduleByManageToken() {
    return useMutation({
        mutationFn: ({
            orgId,
            token,
            scheduledStart,
        }: {
            orgId: string;
            token: string;
            scheduledStart: string;
        }) => appointmentsApi.rescheduleByManageToken(orgId, token, scheduledStart),
    })
}

export function useCancelByManageToken() {
    return useMutation({
        mutationFn: ({
            orgId,
            token,
            reason,
        }: {
            orgId: string;
            token: string;
            reason?: string;
        }) => appointmentsApi.cancelByManageToken(orgId, token, reason),
    })
}

export const bookingPreviewKeys = {
    all: ['booking-preview'] as const,
    page: () => [...bookingPreviewKeys.all, 'page'] as const,
    slots: (
        typeId: string,
        dateStart: string,
        dateEnd?: string,
        clientTimezone?: string
    ) =>
        [
            ...bookingPreviewKeys.all,
            'slots',
            { typeId, dateStart, dateEnd, clientTimezone },
        ] as const,
};

export function useBookingPreviewPage(enabled = true) {
    return useQuery({
        queryKey: bookingPreviewKeys.page(),
        queryFn: appointmentsApi.getBookingPreviewPage,
        enabled,
    });
}

export function useBookingPreviewSlots(
    appointmentTypeId: string,
    dateStart: string,
    dateEnd?: string,
    clientTimezone?: string,
    enabled = true
) {
    return useQuery({
        queryKey: bookingPreviewKeys.slots(
            appointmentTypeId,
            dateStart,
            dateEnd,
            clientTimezone
        ),
        queryFn: () =>
            appointmentsApi.getBookingPreviewSlots(
                appointmentTypeId,
                dateStart,
                dateEnd,
                clientTimezone
            ),
        enabled: enabled && !!appointmentTypeId && !!dateStart,
    });
}

// =============================================================================
// Google Calendar Events
// =============================================================================

export const calendarKeys = {
    googleEvents: (dateStart: string, dateEnd: string, timezone?: string) =>
        ['google-calendar', 'events', { dateStart, dateEnd, timezone }] as const,
};

export function useGoogleCalendarEvents(
    dateStart: string,
    dateEnd: string,
    timezone?: string,
    options?: { enabled?: boolean },
) {
    return useQuery({
        queryKey: calendarKeys.googleEvents(dateStart, dateEnd, timezone),
        queryFn: () => appointmentsApi.getGoogleCalendarEvents(dateStart, dateEnd, timezone),
        enabled: (options?.enabled ?? true) && !!dateStart && !!dateEnd,
        // Keep Google events near-real-time when users update calendars outside the app.
        staleTime: 15 * 1000,
        refetchInterval: 30 * 1000,
        refetchIntervalInBackground: true,
        refetchOnWindowFocus: "always",
    });
}
