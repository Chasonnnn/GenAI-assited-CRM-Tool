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

type NotificationListQueryOptions = {
    unread_only?: boolean
    limit?: number
    notification_types?: string[]
    refetch_interval_ms?: number | false
}

// Query keys
export const notificationKeys = {
    all: ['notifications'] as const,
    list: (options?: NotificationListQueryOptions) =>
        [...notificationKeys.all, 'list', options] as const,
    count: () => [...notificationKeys.all, 'count'] as const,
    settings: () => [...notificationKeys.all, 'settings'] as const,
}

// Hooks

export function useNotifications(options?: NotificationListQueryOptions) {
    const { refetch_interval_ms = false, ...apiOptions } = options ?? {}

    return useQuery<NotificationListResponse>({
        queryKey: notificationKeys.list(options),
        queryFn: () => getNotifications(apiOptions),
        staleTime: 30 * 1000, // 30 seconds
        refetchInterval: refetch_interval_ms,
    })
}

export function useUnreadCount() {
    return useQuery<{ count: number }>({
        queryKey: notificationKeys.count(),
        queryFn: getUnreadCount,
        staleTime: 30 * 1000, // 30 seconds
        refetchInterval: (query) => (query.state.status === "error" ? false : 30 * 1000),
    })
}

export function useMarkRead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: markNotificationRead,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [...notificationKeys.all, "list"] })
            queryClient.invalidateQueries({ queryKey: notificationKeys.count() })
        },
    })
}

export function useMarkAllRead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: markAllNotificationsRead,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [...notificationKeys.all, "list"] })
            queryClient.invalidateQueries({ queryKey: notificationKeys.count() })
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
