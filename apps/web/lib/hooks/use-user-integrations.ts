/**
 * React Query hooks for user integrations (Zoom, Gmail, etc.)
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ApiError } from '@/lib/api'
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
    type CreateMeetingResponse,
    type IntegrationStatus,
    type ZoomStatusResponse,
    type ZoomMeetingRead,
    type SendZoomInviteRequest,
    type SendZoomInviteResponse,
    type GoogleCalendarStatusResponse,
    type GoogleCalendarSyncResponse,
} from '@/lib/api/integrations'

// ============================================================================
// Query Keys
// ============================================================================

export const integrationKeys = {
    all: ['user-integrations'] as const,
    list: () => [...integrationKeys.all, 'list'] as const,
    googleCalendarStatus: () => [...integrationKeys.all, 'google-calendar-status'] as const,
    zoomStatus: () => [...integrationKeys.all, 'zoom-status'] as const,
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
            queryClient.invalidateQueries({ queryKey: integrationKeys.list() })
            queryClient.invalidateQueries({ queryKey: integrationKeys.googleCalendarStatus() })

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
            queryClient.invalidateQueries({ queryKey: integrationKeys.all })
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
        onSuccess: () => {
            // Invalidate notes/tasks and meetings list
            queryClient.invalidateQueries({ queryKey: ['notes'] })
            queryClient.invalidateQueries({ queryKey: ['tasks'] })
            queryClient.invalidateQueries({ queryKey: integrationKeys.zoomMeetings() })
        },
    })
}

/**
 * Send a Zoom meeting invite email.
 */
export function useSendZoomInvite() {
    return useMutation({
        mutationFn: (data: SendZoomInviteRequest) => sendZoomInvite(data),
    })
}

// Re-export types for convenience
export type {
    IntegrationStatus,
    ZoomStatusResponse,
    ZoomMeetingRead,
    CreateMeetingRequest,
    CreateMeetingResponse,
    SendZoomInviteRequest,
    SendZoomInviteResponse,
    GoogleCalendarStatusResponse,
    GoogleCalendarSyncResponse,
}
