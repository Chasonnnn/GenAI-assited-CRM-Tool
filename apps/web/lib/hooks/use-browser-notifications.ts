/**
 * Browser Notifications hook - shows native desktop notifications.
 * 
 * Usage:
 * const { isSupported, permission, requestPermission, showNotification } = useBrowserNotifications()
 * 
 * Call requestPermission() once (e.g., on settings page or first login)
 * Call showNotification(title, options) to show a notification
 */

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

export type NotificationPermission = 'granted' | 'denied' | 'default'

interface UseBrowserNotificationsOptions {
    /** Called when notification is clicked */
    onNotificationClick?: (notification: Notification, data?: { entityType?: string; entityId?: string }) => void
}

export function useBrowserNotifications(hookOptions: UseBrowserNotificationsOptions = {}) {
    const router = useRouter()
    const [isSupported, setIsSupported] = useState(false)
    const [permission, setPermission] = useState<NotificationPermission>('default')

    // Check support on mount
    useEffect(() => {
        const supported = typeof window !== 'undefined' && 'Notification' in window
        setIsSupported(supported)
        if (supported) {
            setPermission(Notification.permission as NotificationPermission)
        }
    }, [])

    // Request notification permission
    const requestPermission = useCallback(async (): Promise<NotificationPermission> => {
        if (!isSupported) return 'denied'

        try {
            const result = await Notification.requestPermission()
            setPermission(result as NotificationPermission)
            return result as NotificationPermission
        } catch (error) {
            console.error('[Notifications] Failed to request permission:', error)
            return 'denied'
        }
    }, [isSupported])

    // Show a notification
    const showNotification = useCallback((
        title: string,
        options?: {
            body?: string
            icon?: string
            tag?: string
            entityType?: string
            entityId?: string
        }
    ) => {
        if (!isSupported || permission !== 'granted') {
            return null
        }

        try {
            const notificationOptions: NotificationOptions = {
                icon: options?.icon || '/icon-192x192.png',
                ...(options?.body ? { body: options.body } : {}),
                ...(options?.tag ? { tag: options.tag } : {}),
            }
            const notification = new Notification(title, notificationOptions)

            notification.onclick = () => {
                // Focus the window
                window.focus()
                notification.close()

                // Navigate to the entity if provided
                if (options?.entityType && options?.entityId) {
                    if (options.entityType === 'case') {
                        router.push(`/cases/${options.entityId}`)
                    } else if (options.entityType === 'task') {
                        router.push(`/tasks`)
                    } else if (options.entityType === 'appointment') {
                        router.push(`/appointments`)
                    }
                } else {
                    // Default: go to notifications page
                    router.push('/notifications')
                }

                const clickData = options?.entityType && options?.entityId
                    ? { entityType: options.entityType, entityId: options.entityId }
                    : undefined
                hookOptions.onNotificationClick?.(notification, clickData)
            }

            return notification
        } catch (error) {
            console.error('[Notifications] Failed to show notification:', error)
            return null
        }
    }, [hookOptions, isSupported, permission, router])

    return {
        isSupported,
        permission,
        requestPermission,
        showNotification,
    }
}
