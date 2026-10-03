/**
 * Notification API functions
 */

import api from '../api'

// Types
export type NotificationTier = 'action' | 'update'

export interface Notification {
    id: string
    type: string
    tier: NotificationTier
    title: string
    body: string | null
    entity_type: string | null
    entity_id: string | null
    read_at: string | null
    created_at: string
}

export interface NotificationListResponse {
    items: Notification[]
    unread_count: number
    next_cursor?: string | null
}

export interface NotificationCounts {
    action_count: number
    updates_unread: number
}

export interface NotificationSettings {
    surrogate_assigned: boolean
    surrogate_status_changed: boolean
    surrogate_claim_available: boolean
    task_assigned: boolean
    workflow_approvals: boolean
    task_reminders: boolean
    appointments: boolean
    contact_reminder: boolean
    intelligent_suggestion_digest: boolean
    status_change_decisions: boolean
    approval_timeouts: boolean
    security_alerts: boolean
    email_workflow_notifications: boolean
    email_daily_digest: boolean
}

// API Functions

export async function getNotifications(options?: {
    unread_only?: boolean
    limit?: number
    offset?: number
    cursor?: string
    notification_types?: string[]  // Filter by notification types
    tier?: NotificationTier  // 'action' returns open action items only
}): Promise<NotificationListResponse> {
    const params = new URLSearchParams()
    if (options?.unread_only) params.set('unread_only', 'true')
    if (options?.limit) params.set('limit', String(options.limit))
    if (options?.offset) params.set('offset', String(options.offset))
    if (options?.cursor) params.set('cursor', options.cursor)
    if (options?.notification_types?.length) {
        params.set('notification_types', options.notification_types.join(','))
    }
    if (options?.tier) params.set('tier', options.tier)

    const query = params.toString() ? `?${params.toString()}` : ''
    return api.get(`/me/notifications${query}`)
}

export async function getNotificationCounts(): Promise<NotificationCounts> {
    return api.get('/me/notifications/count')
}

export async function markNotificationRead(id: string): Promise<Notification> {
    return api.patch(`/me/notifications/${id}/read`)
}

export async function markAllNotificationsRead(
    tier?: NotificationTier
): Promise<{ marked_read: number }> {
    return api.post(tier ? `/me/notifications/read-all?tier=${tier}` : '/me/notifications/read-all')
}

export async function getNotificationSettings(): Promise<NotificationSettings> {
    return api.get('/me/settings/notifications')
}

export async function updateNotificationSettings(
    settings: Partial<NotificationSettings>
): Promise<NotificationSettings> {
    return api.patch('/me/settings/notifications', settings)
}
