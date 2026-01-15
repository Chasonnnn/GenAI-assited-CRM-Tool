/**
 * Notification API functions
 */

import api from './index'

// Types
export interface Notification {
    id: string
    type: string
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
}

export interface NotificationSettings {
    surrogate_assigned: boolean
    surrogate_status_changed: boolean
    surrogate_claim_available: boolean
    task_assigned: boolean
    workflow_approvals: boolean
    task_reminders: boolean
    appointments: boolean
}

// API Functions

export async function getNotifications(options?: {
    unread_only?: boolean
    limit?: number
    offset?: number
    notification_types?: string[]  // Filter by notification types
}): Promise<NotificationListResponse> {
    const params = new URLSearchParams()
    if (options?.unread_only) params.set('unread_only', 'true')
    if (options?.limit) params.set('limit', String(options.limit))
    if (options?.offset) params.set('offset', String(options.offset))
    if (options?.notification_types?.length) {
        params.set('notification_types', options.notification_types.join(','))
    }

    const query = params.toString() ? `?${params.toString()}` : ''
    return api.get(`/me/notifications${query}`)
}

export async function getUnreadCount(): Promise<{ count: number }> {
    return api.get('/me/notifications/count')
}

export async function markNotificationRead(id: string): Promise<Notification> {
    return api.patch(`/me/notifications/${id}/read`)
}

export async function markAllNotificationsRead(): Promise<{ marked_read: number }> {
    return api.post('/me/notifications/read-all')
}

export async function getNotificationSettings(): Promise<NotificationSettings> {
    return api.get('/me/settings/notifications')
}

export async function updateNotificationSettings(
    settings: Partial<NotificationSettings>
): Promise<NotificationSettings> {
    return api.patch('/me/settings/notifications', settings)
}
