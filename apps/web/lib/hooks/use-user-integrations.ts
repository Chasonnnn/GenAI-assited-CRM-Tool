/**
 * React Query hooks for user integrations (Zoom, Gmail, etc.)
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ApiError } from '@/lib/api'
import { appointmentKeys } from './use-appointments'
import { invalidateSurrogateCrmCaches } from './use-surrogates'
import { taskKeys } from './use-tasks'
import {
    listUserIntegrations,
    getZoomConnectUrl,
    getGmailConnectUrl,
    getGoogleCalendarConnectUrl,
    getGoogleCalendarStatus,
    getGcpConnectUrl,
    getZoomStatus,
    getZoomMeetings,
    syncGoogleCalendarNow,
    disconnectIntegration,
    createZoomMeeting,
    sendZoomInvite,
    type CreateMeetingRequest,
    type ZoomMeetingRead,
    type SendZoomInviteRequest,
} from '@/lib/api/integrations'

// ============================================================================
// Query Keys
// ============================================================================

const integrationKeys = {
    all: ['user-integrations'] as const,
    list: () => [...integrationKeys.all, 'list'] as const,
    googleCalendarStatus: () => [...integrationKeys.all, 'google-calendar-status'] as const,
    zoomStatus: () => [...integrationKeys.all, 'zoom-status'] as const,
    zoomMeetingsList: () => [...integrationKeys.all, 'zoom-meetings'] as const,
    zoomMeetings: (params?: { limit?: number }) => [...integrationKeys.all, 'zoom-meetings', params] as const,
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Get list of user's connected integrations.
 */
export function useUserIntegrations() {
    return useQuery({
        queryKey: integrationKeys.list(),
        queryFn: async () => {
            const response = await listUserIntegrations()
            return response.integrations
        },
    })
}

/**
 * Get Zoom connection status for current user.
 */
export function useZoomStatus() {
    return useQuery({
        queryKey: integrationKeys.zoomStatus(),
        queryFn: getZoomStatus,
    })
}

/**
 * Get list of user's Zoom meetings.
 */
export function useZoomMeetings(params: { limit?: number } = {}) {
    return useQuery({
        queryKey: integrationKeys.zoomMeetings(params),
        queryFn: () => getZoomMeetings(params),
        staleTime: 60 * 1000, // 1 minute
    })
}

/**
 * Connect Zoom - returns auth URL and redirects user.
 */
export function useConnectZoom() {
    return useMutation({
        mutationFn: async () => {
            const { auth_url } = await getZoomConnectUrl()
            if (!auth_url) {
                throw new Error('Zoom authorization URL is missing.')
            }
            // Redirect user to Zoom OAuth
            window.location.assign(auth_url)
        },
        onError: (error) => {
            const message =
                error instanceof ApiError
                    ? error.message || 'Failed to connect Zoom.'
                    : error instanceof Error
                        ? error.message
                        : 'Failed to connect Zoom.'
            toast.error(message)
        },
    })
}

/**
 * Connect Gmail - returns auth URL and redirects user.
 */
export function useConnectGmail() {
    return useMutation({
        mutationFn: async () => {
            const { auth_url } = await getGmailConnectUrl()
            if (!auth_url) {
                throw new Error('Gmail authorization URL is missing.')
            }
            // Redirect user to Gmail OAuth
            window.location.assign(auth_url)
        },
        onError: (error) => {
            const message =
                error instanceof ApiError
                    ? error.message || 'Failed to connect Gmail.'
                    : error instanceof Error
                        ? error.message
                        : 'Failed to connect Gmail.'
            toast.error(message)
        },
    })
}

/**
 * Connect Google Calendar - returns auth URL and redirects user.
 */
export function useConnectGoogleCalendar() {
    return useMutation({
        mutationFn: async () => {
            const { auth_url } = await getGoogleCalendarConnectUrl()
            if (!auth_url) {
                throw new Error('Google Calendar authorization URL is missing.')
            }
            window.location.assign(auth_url)
        },
        onError: (error) => {
            const message =
                error instanceof ApiError
                    ? error.message || 'Failed to connect Google Calendar.'
                    : error instanceof Error
                        ? error.message
                        : 'Failed to connect Google Calendar.'
            toast.error(message)
        },
    })
}

/**
 * Get Google Calendar connection diagnostics including last sync timestamp.
 */
export function useGoogleCalendarStatus(enabled = true) {
    return useQuery({
        queryKey: integrationKeys.googleCalendarStatus(),
        queryFn: getGoogleCalendarStatus,
        enabled,
        staleTime: 15 * 1000,
    })
}

/**
 * Trigger an immediate Google Calendar/Tasks reconciliation.
 */
export function useSyncGoogleCalendarNow() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: syncGoogleCalendarNow,
        onSuccess: (result) => {
            void queryClient.invalidateQueries({ queryKey: integrationKeys.list() })
            void queryClient.invalidateQueries({ queryKey: integrationKeys.googleCalendarStatus() })
            void queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: taskKeys.lists() })

            if (result.warnings?.length) {
                toast.warning('Google sync completed with warnings.')
                return
            }

            const totalChanges =
                (result.outbound_backfilled ?? 0)
                + (result.appointment_changes ?? 0)
                + (result.task_changes ?? 0)
            toast.success(
                totalChanges > 0
                    ? `Google sync complete (${totalChanges} changes).`
                    : 'Google sync complete. No changes detected.'
            )
        },
        onError: (error) => {
            const message =
                error instanceof ApiError
                    ? error.message || 'Failed to sync Google Calendar.'
                    : error instanceof Error
                        ? error.message
                        : 'Failed to sync Google Calendar.'
            toast.error(message)
        },
    })
}

/**
 * Connect Google Cloud - returns auth URL and redirects user.
 */
export function useConnectGcp() {
    return useMutation({
        mutationFn: async () => {
            const { auth_url } = await getGcpConnectUrl()
            if (!auth_url) {
                throw new Error('Google Cloud authorization URL is missing.')
            }
            window.location.assign(auth_url)
        },
        onError: (error) => {
            const message =
                error instanceof ApiError
                    ? error.message || 'Failed to connect Google Cloud.'
                    : error instanceof Error
                        ? error.message
                        : 'Failed to connect Google Cloud.'
            toast.error(message)
        },
    })
}

/**
 * Disconnect an integration.
 */
export function useDisconnectIntegration() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: disconnectIntegration,
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: integrationKeys.all })
        },
    })
}

/**
 * Create a Zoom meeting.
 */
export function useCreateZoomMeeting() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: CreateMeetingRequest) => createZoomMeeting(data),
        onSuccess: (_data, variables) => {
            void queryClient.invalidateQueries({ queryKey: ['notes'] })
            void queryClient.invalidateQueries({ queryKey: taskKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: integrationKeys.zoomMeetingsList() })
            if (variables.entity_type === 'surrogate') {
                invalidateSurrogateCrmCaches(queryClient, variables.entity_id)
            }
        },
    })
}

/**
 * Send a Zoom meeting invite email.
 */
export function useSendZoomInvite() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: SendZoomInviteRequest) => sendZoomInvite(data),
        onSuccess: (_data, variables) => {
            if (variables.surrogate_id) {
                invalidateSurrogateCrmCaches(queryClient, variables.surrogate_id)
            }
        },
    })
}

// Re-export types for convenience
export type {
    ZoomMeetingRead,
    CreateMeetingRequest,
    SendZoomInviteRequest,
}
