/**
 * Notification hooks using React Query
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
    getNotifications,
    getNotificationCounts,
    markNotificationRead,
    markAllNotificationsRead,
    getNotificationSettings,
    updateNotificationSettings,
    type NotificationCounts,
    type NotificationListResponse,
    type NotificationSettings,
    type NotificationTier,
} from '../api/notifications'

type NotificationListQueryOptions = {
    unread_only?: boolean
    limit?: number
    notification_types?: string[]
    tier?: NotificationTier
    enabled?: boolean
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
    const { refetch_interval_ms = false, enabled = true, ...apiOptions } = options ?? {}

    return useQuery<NotificationListResponse>({
        queryKey: notificationKeys.list(apiOptions),
        queryFn: () => getNotifications(apiOptions),
        staleTime: 30 * 1000, // 30 seconds
        refetchInterval: refetch_interval_ms,
        enabled,
    })
}

// Action items clear when anyone finishes the work, and nothing pushes that change,
// so the count keeps polling even while the socket is connected.
export function useNotificationCounts() {
    return useQuery<NotificationCounts>({
        queryKey: notificationKeys.count(),
        queryFn: getNotificationCounts,
        staleTime: 30 * 1000, // 30 seconds
        refetchInterval: (query) => (query.state.status === "error" ? false : 60 * 1000),
    })
}

export function useMarkRead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: markNotificationRead,
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: [...notificationKeys.all, "list"] })
            void queryClient.invalidateQueries({ queryKey: notificationKeys.count() })
        },
    })
}

export function useMarkAllRead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (tier?: NotificationTier) => markAllNotificationsRead(tier),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: [...notificationKeys.all, "list"] })
            void queryClient.invalidateQueries({ queryKey: notificationKeys.count() })
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
