/**
 * API client for user integrations (Zoom, Gmail, etc.)
 */

import api from './index'

// ============================================================================
// Types
// ============================================================================

export interface IntegrationStatus {
    integration_type: string
    connected: boolean
    account_email: string | null
    expires_at: string | null
}

export interface IntegrationListResponse {
    integrations: IntegrationStatus[]
}

export interface ZoomConnectResponse {
    auth_url: string
}

export interface ZoomStatusResponse {
    connected: boolean
    account_email: string | null
    connected_at: string | null
    token_expires_at: string | null
}

export interface ZoomMeetingRead {
    id: string
    topic: string
    start_time: string | null
    duration: number
    join_url: string
    surrogate_id: string | null
    intended_parent_id: string | null
    created_at: string
}

export interface CreateMeetingRequest {
    entity_type: 'surrogate' | 'intended_parent'
    entity_id: string
    topic: string
    start_time?: string // ISO format
    timezone?: string // IANA timezone name (e.g. America/Los_Angeles)
    duration?: number // minutes, default 30
    contact_name?: string
    idempotency_key?: string
}

export interface CreateMeetingResponse {
    join_url: string
    start_url: string
    meeting_id: number
    password: string | null
    note_id: string | null
    task_id: string | null
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List all connected integrations for current user.
 */
export async function listUserIntegrations(): Promise<IntegrationListResponse> {
    return api.get<IntegrationListResponse>('/integrations/')
}

/**
 * Get Zoom OAuth authorization URL.
 */
export async function getZoomConnectUrl(): Promise<ZoomConnectResponse> {
    return api.get<ZoomConnectResponse>('/integrations/zoom/connect')
}

/**
 * Get Gmail OAuth authorization URL.
 */
export async function getGmailConnectUrl(): Promise<{ auth_url: string }> {
    return api.get<{ auth_url: string }>('/integrations/gmail/connect')
}

/**
 * Get Google Calendar OAuth authorization URL.
 */
export async function getGoogleCalendarConnectUrl(): Promise<{ auth_url: string }> {
    return api.get<{ auth_url: string }>('/integrations/google-calendar/connect')
}

/**
 * Check if current user has Zoom connected.
 */
export async function getZoomStatus(): Promise<ZoomStatusResponse> {
    return api.get<ZoomStatusResponse>('/integrations/zoom/status')
}

/**
 * Get list of user's Zoom meetings.
 */
export async function getZoomMeetings(params: { limit?: number } = {}): Promise<ZoomMeetingRead[]> {
    const searchParams = new URLSearchParams()
    if (params.limit) searchParams.set('limit', params.limit.toString())
    const query = searchParams.toString()
    return api.get<ZoomMeetingRead[]>(`/integrations/zoom/meetings${query ? `?${query}` : ''}`)
}

/**
 * Disconnect an integration.
 */
export async function disconnectIntegration(integrationType: string): Promise<void> {
    await api.delete(`/integrations/${integrationType}`)
}

/**
 * Create a Zoom meeting for a surrogate or intended parent.
 */
export async function createZoomMeeting(data: CreateMeetingRequest): Promise<CreateMeetingResponse> {
    return api.post<CreateMeetingResponse>('/integrations/zoom/meetings', data)
}

export interface SendZoomInviteRequest {
    recipient_email: string
    meeting_id: number
    join_url: string
    topic: string
    start_time?: string
    duration?: number
    password?: string
    contact_name: string
    surrogate_id?: string
}

export interface SendZoomInviteResponse {
    email_log_id: string
    success: boolean
}

/**
 * Send a Zoom meeting invite email using the org's template.
 */
export async function sendZoomInvite(data: SendZoomInviteRequest): Promise<SendZoomInviteResponse> {
    return api.post<SendZoomInviteResponse>('/integrations/zoom/send-invite', data)
}
