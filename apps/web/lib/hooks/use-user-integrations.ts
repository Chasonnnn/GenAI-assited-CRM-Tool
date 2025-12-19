/**
 * React Query hooks for user integrations (Zoom, Gmail, etc.)
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    listUserIntegrations,
    getZoomConnectUrl,
    getGmailConnectUrl,
    getZoomStatus,
    getZoomMeetings,
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
} from '@/lib/api/integrations'

// ============================================================================
// Query Keys
// ============================================================================

export const integrationKeys = {
    all: ['user-integrations'] as const,
    list: () => [...integrationKeys.all, 'list'] as const,
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
            // Redirect user to Zoom OAuth
            window.location.href = auth_url
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
            // Redirect user to Gmail OAuth
            window.location.href = auth_url
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
export type { IntegrationStatus, ZoomStatusResponse, ZoomMeetingRead, CreateMeetingRequest, CreateMeetingResponse, SendZoomInviteRequest, SendZoomInviteResponse }
