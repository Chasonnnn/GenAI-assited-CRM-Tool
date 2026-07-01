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

import { useEffect, useReducer, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/lib/auth-context'
import { getWebSocketUrl } from '@/lib/websocket-url'

export interface NotificationSocketMessage {
    type: 'notification' | 'count_update'
    data: {
        id?: string
        title?: string
        body?: string
        type?: string
        count?: number
        // Entity data for deep-linking
        entity_type?: string
        entity_id?: string
    }
}

interface UseNotificationSocketOptions {
    enabled?: boolean
    reconnectInterval?: number
    maxReconnectAttempts?: number
}

type NotificationSocketState = {
    isConnected: boolean
    lastNotification: NotificationSocketMessage['data'] | null
    unreadCount: number | null
}

type NotificationSocketAction =
    | { type: 'connected' }
    | { type: 'disconnected' }
    | { type: 'notification'; data: NotificationSocketMessage['data'] }
    | { type: 'count_update'; count: number | null }

const initialNotificationSocketState: NotificationSocketState = {
    isConnected: false,
    lastNotification: null,
    unreadCount: null,
}

function notificationSocketReducer(
    state: NotificationSocketState,
    action: NotificationSocketAction
): NotificationSocketState {
    switch (action.type) {
        case 'connected':
            return { ...state, isConnected: true }
        case 'disconnected':
            return { ...state, isConnected: false, unreadCount: null }
        case 'notification':
            return { ...state, lastNotification: action.data }
        case 'count_update':
            return { ...state, unreadCount: action.count }
    }
}

function reconnectRequestReducer(request: number): number {
    return request + 1
}

const AUTH_CLOSE_CODES = new Set([4001, 4003])
const ABNORMAL_CLOSE_CODE = 1006
const HANDSHAKE_RETRY_SUPPRESSION_MS = 5 * 60 * 1000

let handshakeRetrySuppressedUntil = 0

export function useNotificationSocket(options: UseNotificationSocketOptions = {}) {
    const {
        enabled = true,
        reconnectInterval = 3000,
        maxReconnectAttempts = 10,
    } = options

    const { user } = useAuth()
    const queryClient = useQueryClient()

    const [state, dispatch] = useReducer(
        notificationSocketReducer,
        initialNotificationSocketState
    )
    const [reconnectRequest, requestReconnect] = useReducer(reconnectRequestReducer, 0)

    const wsRef = useRef<WebSocket | null>(null)
    const isActiveRef = useRef(true)
    const manualCloseRef = useRef(false)
    const reconnectAttempts = useRef(0)
    const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
    const pingInterval = useRef<ReturnType<typeof setInterval> | null>(null)

    // Connect on mount / when user changes
    useEffect(() => {
        function connectSocket() {
            if (!user || !enabled) return
            if (Date.now() < handshakeRetrySuppressedUntil) return

            const existing = wsRef.current
            if (existing && (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING)) {
                return
            }

            const wsUrl = getWebSocketUrl('/ws/notifications')

            try {
                const ws = new WebSocket(wsUrl)
                let hasOpened = false
                wsRef.current = ws

                ws.onopen = () => {
                    hasOpened = true
                    handshakeRetrySuppressedUntil = 0
                    if (!isActiveRef.current || !enabled || !user) {
                        ws.close(1000, 'Inactive')
                        return
                    }
                    dispatch({ type: 'connected' })
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
                            dispatch({ type: 'notification', data: message.data })
                            // Invalidate notifications query to trigger refetch
                            void queryClient.invalidateQueries({ queryKey: ['notifications'] })
                        } else if (message.type === 'count_update') {
                            dispatch({ type: 'count_update', count: message.data.count ?? null })
                        }
                    } catch (e) {
                        // Handle pong or invalid JSON
                        if (event.data !== 'pong') {
                            console.warn('[WS] Failed to parse message:', e)
                        }
                    }
                }

                ws.onclose = (event) => {
                    dispatch({ type: 'disconnected' })
                    if (pingInterval.current) {
                        clearInterval(pingInterval.current)
                        pingInterval.current = null
                    }
                    wsRef.current = null

                    if (!isActiveRef.current || !enabled || !user) {
                        return
                    }

                    if (AUTH_CLOSE_CODES.has(event.code)) {
                        reconnectAttempts.current = maxReconnectAttempts
                        return
                    }

                    if (!hasOpened && event.code === ABNORMAL_CLOSE_CODE) {
                        reconnectAttempts.current = maxReconnectAttempts
                        handshakeRetrySuppressedUntil = Date.now() + HANDSHAKE_RETRY_SUPPRESSION_MS
                        console.warn('[WS] Handshake rejected - notifications will use polling fallback')
                        return
                    }

                    if (manualCloseRef.current) {
                        manualCloseRef.current = false
                        connectSocket()
                        return
                    }

                    // Attempt reconnect with exponential backoff
                    if (reconnectAttempts.current < maxReconnectAttempts) {
                        const delay = reconnectInterval * Math.pow(2, reconnectAttempts.current)
                        reconnectAttempts.current++

                        reconnectTimeout.current = setTimeout(() => {
                            connectSocket()
                        }, delay)
                    }
                }

                ws.onerror = () => {
                    if (!isActiveRef.current || manualCloseRef.current) {
                        return
                    }
                    // Only log on first attempt to avoid console spam
                    if (reconnectAttempts.current === 0) {
                        console.warn('[WS] Connection failed - notifications will use polling fallback')
                    }
                }
            } catch (e) {
                console.error('[WS] Failed to create WebSocket:', e)
            }
        }

        isActiveRef.current = true
        connectSocket()

        return () => {
            isActiveRef.current = false
            if (reconnectTimeout.current) {
                clearTimeout(reconnectTimeout.current)
                reconnectTimeout.current = null
            }
            if (pingInterval.current) {
                clearInterval(pingInterval.current)
                pingInterval.current = null
            }
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                manualCloseRef.current = true
                wsRef.current.close(1000, 'Component unmounted')
            }
        }
    }, [enabled, maxReconnectAttempts, queryClient, reconnectInterval, reconnectRequest, user])

    // Manual reconnect function
    function reconnect() {
        handshakeRetrySuppressedUntil = 0
        reconnectAttempts.current = 0
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            manualCloseRef.current = true
            wsRef.current.close(1000, 'Manual reconnect')
            return
        }
        requestReconnect()
    }

    return {
        isConnected: state.isConnected,
        lastNotification: state.lastNotification,
        unreadCount: state.unreadCount,
        reconnect,
    }
}
