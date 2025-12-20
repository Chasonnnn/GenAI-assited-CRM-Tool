/**
 * WebSocket hook for real-time notifications.
 * 
 * Usage:
 * const { isConnected, lastNotification, unreadCount } = useNotificationSocket()
 * 
 * The hook automatically:
 * - Connects when user is authenticated
 * - Reconnects on disconnect with exponential backoff
 * - Sends periodic pings to keep connection alive
 * - Invalidates notification queries on new messages
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/lib/auth-context'

export interface NotificationSocketMessage {
    type: 'notification' | 'count_update'
    data: {
        id?: string
        title?: string
        body?: string
        type?: string
        count?: number
    }
}

interface UseNotificationSocketOptions {
    enabled?: boolean
    reconnectInterval?: number
    maxReconnectAttempts?: number
}

export function useNotificationSocket(options: UseNotificationSocketOptions = {}) {
    const {
        enabled = true,
        reconnectInterval = 3000,
        maxReconnectAttempts = 10,
    } = options

    const { user } = useAuth()
    const queryClient = useQueryClient()

    const [isConnected, setIsConnected] = useState(false)
    const [lastNotification, setLastNotification] = useState<NotificationSocketMessage['data'] | null>(null)
    const [unreadCount, setUnreadCount] = useState<number | null>(null)

    const wsRef = useRef<WebSocket | null>(null)
    const reconnectAttempts = useRef(0)
    const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
    const pingInterval = useRef<ReturnType<typeof setInterval> | null>(null)

    const connect = useCallback(() => {
        if (!user || !enabled) return

        // Clear any existing connection
        if (wsRef.current) {
            wsRef.current.close()
        }

        // Determine WebSocket URL
        // In dev: API is on port 8000, frontend on 3000
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        const wsUrl = apiUrl.replace(/^http/, 'ws') + '/ws/notifications'

        try {
            const ws = new WebSocket(wsUrl)
            wsRef.current = ws

            ws.onopen = () => {
                setIsConnected(true)
                reconnectAttempts.current = 0

                // Start ping interval (every 30s)
                pingInterval.current = setInterval(() => {
                    if (ws.readyState === WebSocket.OPEN) {
                        ws.send('ping')
                    }
                }, 30000)
            }

            ws.onmessage = (event) => {
                try {
                    const message: NotificationSocketMessage = JSON.parse(event.data)

                    if (message.type === 'notification') {
                        setLastNotification(message.data)
                        // Invalidate notifications query to trigger refetch
                        queryClient.invalidateQueries({ queryKey: ['notifications'] })
                    } else if (message.type === 'count_update') {
                        setUnreadCount(message.data.count ?? null)
                    }
                } catch (e) {
                    // Handle pong or invalid JSON
                    if (event.data !== 'pong') {
                        console.warn('[WS] Failed to parse message:', e)
                    }
                }
            }

            ws.onclose = () => {
                setIsConnected(false)
                if (pingInterval.current) {
                    clearInterval(pingInterval.current)
                    pingInterval.current = null
                }

                // Attempt reconnect with exponential backoff
                if (reconnectAttempts.current < maxReconnectAttempts) {
                    const delay = reconnectInterval * Math.pow(2, reconnectAttempts.current)
                    reconnectAttempts.current++

                    reconnectTimeout.current = setTimeout(() => {
                        connect()
                    }, delay)
                }
            }

            ws.onerror = () => {
                // Only log on first attempt to avoid console spam
                if (reconnectAttempts.current === 0) {
                    console.warn('[WS] Connection failed - notifications will use polling fallback')
                }
            }
        } catch (e) {
            console.error('[WS] Failed to create WebSocket:', e)
        }
    }, [user, enabled, reconnectInterval, maxReconnectAttempts, queryClient])

    // Connect on mount / when user changes
    useEffect(() => {
        connect()

        return () => {
            if (reconnectTimeout.current) {
                clearTimeout(reconnectTimeout.current)
                reconnectTimeout.current = null
            }
            if (pingInterval.current) {
                clearInterval(pingInterval.current)
                pingInterval.current = null
            }
            if (wsRef.current) {
                wsRef.current.close()
            }
        }
    }, [connect])

    // Manual reconnect function
    const reconnect = useCallback(() => {
        reconnectAttempts.current = 0
        connect()
    }, [connect])

    return {
        isConnected,
        lastNotification,
        unreadCount,
        reconnect,
    }
}
