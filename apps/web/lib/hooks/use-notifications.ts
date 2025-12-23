/**
 * Notification hooks using React Query
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
    getNotifications,
    getUnreadCount,
    markNotificationRead,
    markAllNotificationsRead,
    getNotificationSettings,
    updateNotificationSettings,
    type NotificationListResponse,
    type NotificationSettings,
} from '../api/notifications'

// Query keys
export const notificationKeys = {
    all: ['notifications'] as const,
    list: (options?: { unread_only?: boolean }) =>
        [...notificationKeys.all, 'list', options] as const,
    count: () => [...notificationKeys.all, 'count'] as const,
    settings: () => [...notificationKeys.all, 'settings'] as const,
}

// Hooks

export function useNotifications(options?: { unread_only?: boolean; limit?: number; notification_types?: string[] }) {
    return useQuery<NotificationListResponse>({
        queryKey: notificationKeys.list(options),
        queryFn: () => getNotifications(options),
        staleTime: 30 * 1000, // 30 seconds
    })
}

export function useUnreadCount() {
    return useQuery<{ count: number }>({
        queryKey: notificationKeys.count(),
        queryFn: getUnreadCount,
        staleTime: 30 * 1000, // 30 seconds
        refetchInterval: 30 * 1000, // Poll every 30 seconds
    })
}

export function useMarkRead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: markNotificationRead,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: notificationKeys.all })
        },
    })
}

export function useMarkAllRead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: markAllNotificationsRead,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: notificationKeys.all })
        },
    })
}

export function useNotificationSettings() {
    return useQuery<NotificationSettings>({
        queryKey: notificationKeys.settings(),
        queryFn: getNotificationSettings,
    })
}

export function useUpdateNotificationSettings() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: updateNotificationSettings,
        onSuccess: (data) => {
            queryClient.setQueryData(notificationKeys.settings(), data)
        },
    })
}
