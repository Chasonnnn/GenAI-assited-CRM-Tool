/**
 * Appointments API client.
 * 
 * Handles all appointment-related API calls for both authenticated
 * staff operations and public booking.
 */

import api, { ApiError } from './index';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// Public fetch (no credentials/cookies)
async function publicRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
        ...options,
    });

    if (!response.ok) {
        let message: string | undefined;
        try {
            const err = await response.json();
            message = err.detail || err.message;
        } catch {
            // Ignore JSON parse errors
        }
        throw new ApiError(response.status, response.statusText, message);
    }

    if (response.status === 204) {
        return undefined as T;
    }

    return response.json();
}

// =============================================================================
// Types
// =============================================================================

export interface AppointmentType {
    id: string;
    user_id: string;
    name: string;
    slug: string;
    description: string | null;
    duration_minutes: number;
    buffer_before_minutes: number;
    buffer_after_minutes: number;
    meeting_mode: 'zoom' | 'phone' | 'in_person';
    reminder_hours_before: number;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

export interface AppointmentTypeCreate {
    name: string;
    description?: string;
    duration_minutes?: number;
    buffer_before_minutes?: number;
    buffer_after_minutes?: number;
    meeting_mode?: 'zoom' | 'phone' | 'in_person';
    reminder_hours_before?: number;
}

export interface AvailabilityRule {
    id: string;
    day_of_week: number;
    start_time: string;
    end_time: string;
    timezone: string;
}

export interface AvailabilityRuleInput {
    day_of_week: number;
    start_time: string;
    end_time: string;
}

export interface AvailabilityOverride {
    id: string;
    override_date: string;
    is_unavailable: boolean;
    start_time: string | null;
    end_time: string | null;
    reason: string | null;
    created_at: string;
}

export interface AvailabilityOverrideCreate {
    override_date: string;
    is_unavailable: boolean;
    start_time?: string;
    end_time?: string;
    reason?: string;
}

export interface BookingLink {
    id: string;
    user_id: string;
    public_slug: string;
    is_active: boolean;
    full_url: string | null;
    created_at: string;
    updated_at: string;
}

export interface Appointment {
    id: string;
    user_id: string;
    appointment_type_id: string | null;
    appointment_type_name: string | null;
    client_name: string;
    client_email: string;
    client_phone: string;
    client_timezone: string;
    client_notes: string | null;
    scheduled_start: string;
    scheduled_end: string;
    duration_minutes: number;
    meeting_mode: string;
    status: 'pending' | 'confirmed' | 'completed' | 'cancelled' | 'no_show' | 'expired';
    pending_expires_at: string | null;
    approved_at: string | null;
    approved_by_user_id: string | null;
    approved_by_name: string | null;
    cancelled_at: string | null;
    cancelled_by_client: boolean;
    cancellation_reason: string | null;
    zoom_join_url: string | null;
    google_event_id: string | null;
    created_at: string;
    updated_at: string;
}

export interface AppointmentListItem {
    id: string;
    appointment_type_name: string | null;
    client_name: string;
    client_email: string;
    client_phone: string;
    scheduled_start: string;
    scheduled_end: string;
    duration_minutes: number;
    meeting_mode: string;
    status: 'pending' | 'confirmed' | 'completed' | 'cancelled' | 'no_show' | 'expired';
    created_at: string;
}

export interface AppointmentListResponse {
    items: AppointmentListItem[];
    total: number;
    page: number;
    per_page: number;
    pages: number;
}

export interface TimeSlot {
    start: string;
    end: string;
}

export interface AvailableSlotsResponse {
    slots: TimeSlot[];
    appointment_type: AppointmentType | null;
}

export interface StaffInfo {
    user_id: string;
    display_name: string;
    avatar_url: string | null;
}

export interface PublicBookingPage {
    staff: StaffInfo;
    appointment_types: AppointmentType[];
    org_name: string | null;
}

export interface BookingCreate {
    appointment_type_id: string;
    client_name: string;
    client_email: string;
    client_phone: string;
    client_timezone: string;
    scheduled_start: string;
    client_notes?: string;
    idempotency_key?: string;
}

export interface PublicAppointmentView {
    id: string;
    appointment_type_name: string | null;
    staff_name: string | null;
    client_name: string;
    scheduled_start: string;
    scheduled_end: string;
    duration_minutes: number;
    meeting_mode: string;
    status: string;
    zoom_join_url: string | null;
}

// =============================================================================
// Authenticated API (Staff)
// =============================================================================

// Appointment Types
export function getAppointmentTypes(activeOnly = true): Promise<AppointmentType[]> {
    return api.get<AppointmentType[]>(`/appointments/types?active_only=${activeOnly}`);
}

export function createAppointmentType(data: AppointmentTypeCreate): Promise<AppointmentType> {
    return api.post<AppointmentType>('/appointments/types', data);
}

export function updateAppointmentType(
    typeId: string,
    data: Partial<AppointmentTypeCreate & { is_active: boolean }>
): Promise<AppointmentType> {
    return api.patch<AppointmentType>(`/appointments/types/${typeId}`, data);
}

export function deleteAppointmentType(typeId: string): Promise<void> {
    return api.delete<void>(`/appointments/types/${typeId}`);
}

// Availability Rules
export function getAvailabilityRules(): Promise<AvailabilityRule[]> {
    return api.get<AvailabilityRule[]>('/appointments/availability');
}

export function setAvailabilityRules(
    rules: AvailabilityRuleInput[],
    timezone: string
): Promise<AvailabilityRule[]> {
    return api.put<AvailabilityRule[]>('/appointments/availability', { rules, timezone });
}

// Availability Overrides
export function getAvailabilityOverrides(
    dateStart?: string,
    dateEnd?: string
): Promise<AvailabilityOverride[]> {
    const params = new URLSearchParams();
    if (dateStart) params.append('date_start', dateStart);
    if (dateEnd) params.append('date_end', dateEnd);
    const query = params.toString() ? `?${params}` : '';
    return api.get<AvailabilityOverride[]>(`/appointments/overrides${query}`);
}

export function createAvailabilityOverride(
    data: AvailabilityOverrideCreate
): Promise<AvailabilityOverride> {
    return api.post<AvailabilityOverride>('/appointments/overrides', data);
}

export function deleteAvailabilityOverride(overrideId: string): Promise<void> {
    return api.delete<void>(`/appointments/overrides/${overrideId}`);
}

// Booking Link
export function getBookingLink(): Promise<BookingLink> {
    return api.get<BookingLink>('/appointments/booking-link');
}

export function regenerateBookingLink(): Promise<BookingLink> {
    return api.post<BookingLink>('/appointments/booking-link/regenerate');
}

// Appointments
export function getAppointments(params: {
    page?: number;
    per_page?: number;
    status?: string;
    date_start?: string;
    date_end?: string;
}): Promise<AppointmentListResponse> {
    const searchParams = new URLSearchParams();
    if (params.page) searchParams.append('page', String(params.page));
    if (params.per_page) searchParams.append('per_page', String(params.per_page));
    if (params.status) searchParams.append('status', params.status);
    if (params.date_start) searchParams.append('date_start', params.date_start);
    if (params.date_end) searchParams.append('date_end', params.date_end);
    const query = searchParams.toString() ? `?${searchParams}` : '';
    return api.get<AppointmentListResponse>(`/appointments${query}`);
}

export function getAppointment(appointmentId: string): Promise<Appointment> {
    return api.get<Appointment>(`/appointments/${appointmentId}`);
}

export function approveAppointment(appointmentId: string): Promise<Appointment> {
    return api.post<Appointment>(`/appointments/${appointmentId}/approve`);
}

export function rescheduleAppointment(
    appointmentId: string,
    scheduledStart: string
): Promise<Appointment> {
    return api.post<Appointment>(`/appointments/${appointmentId}/reschedule`, {
        scheduled_start: scheduledStart,
    });
}

export function cancelAppointment(
    appointmentId: string,
    reason?: string
): Promise<Appointment> {
    return api.post<Appointment>(`/appointments/${appointmentId}/cancel`, { reason });
}

// =============================================================================
// Public API (Booking)
// =============================================================================

export function getPublicBookingPage(publicSlug: string): Promise<PublicBookingPage> {
    return publicRequest<PublicBookingPage>(`/book/${publicSlug}`);
}

export function getAvailableSlots(
    publicSlug: string,
    appointmentTypeId: string,
    dateStart: string,
    dateEnd?: string,
    clientTimezone?: string
): Promise<AvailableSlotsResponse> {
    const params = new URLSearchParams({
        appointment_type_id: appointmentTypeId,
        date_start: dateStart,
    });
    if (dateEnd) params.append('date_end', dateEnd);
    if (clientTimezone) params.append('client_timezone', clientTimezone);
    return publicRequest<AvailableSlotsResponse>(`/book/${publicSlug}/slots?${params}`);
}

export function createBooking(
    publicSlug: string,
    data: BookingCreate
): Promise<PublicAppointmentView> {
    return publicRequest<PublicAppointmentView>(`/book/${publicSlug}/book`, {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export function getAppointmentForReschedule(
    token: string
): Promise<PublicAppointmentView> {
    return publicRequest<PublicAppointmentView>(`/book/self-service/reschedule/${token}`);
}

export function rescheduleByToken(
    token: string,
    scheduledStart: string
): Promise<PublicAppointmentView> {
    return publicRequest<PublicAppointmentView>(`/book/self-service/reschedule/${token}`, {
        method: 'POST',
        body: JSON.stringify({ scheduled_start: scheduledStart }),
    });
}

export function getAppointmentForCancel(
    token: string
): Promise<PublicAppointmentView> {
    return publicRequest<PublicAppointmentView>(`/book/self-service/cancel/${token}`);
}

export function cancelByToken(
    token: string,
    reason?: string
): Promise<PublicAppointmentView> {
    return publicRequest<PublicAppointmentView>(`/book/self-service/cancel/${token}`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
    });
}
