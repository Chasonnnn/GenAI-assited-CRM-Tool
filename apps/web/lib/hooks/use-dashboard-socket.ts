/**
 * WebSocket hook for real-time dashboard stats updates.
 * 
 * Connects to /ws/notifications and listens for 'stats_update' messages.
 * Updates React Query cache when new stats are received.
 * Includes auto-reconnect with exponential backoff.
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { surrogateKeys } from './use-surrogates';
import { useAuth } from '@/lib/auth-context';

const WS_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.replace('http', 'ws') || 'ws://localhost:8000';
const MAX_RECONNECT_DELAY = 30000; // 30 seconds max
const INITIAL_RECONNECT_DELAY = 1000; // Start with 1 second

interface WebSocketMessage {
    type: 'notification' | 'count_update' | 'stats_update';
    data: unknown;
}

/**
 * Hook to connect to WebSocket for real-time dashboard updates.
 * 
 * Automatically:
 * - Connects on mount
 * - Reconnects on disconnect with exponential backoff
 * - Updates React Query cache when stats are received
 * - Cleans up on unmount
 */
export function useDashboardSocket(enabled: boolean = true) {
    const queryClient = useQueryClient();
    const { user } = useAuth();
    const wsRef = useRef<WebSocket | null>(null);
    const isActiveRef = useRef(true);
    const manualCloseRef = useRef(false);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY);
    const errorLoggedRef = useRef(false);
    const [isConnected, setIsConnected] = useState(false);

    const connect = useCallback(() => {
        if (!enabled || !user) {
            return;
        }
        const existing = wsRef.current
        if (existing && (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING)) {
            return
        }

        try {
            const ws = new WebSocket(`${WS_URL}/ws/notifications`);

            ws.onopen = () => {
                if (!isActiveRef.current || !enabled || !user) {
                    ws.close(1000, "Inactive");
                    return;
                }
                setIsConnected(true);
                reconnectDelayRef.current = INITIAL_RECONNECT_DELAY; // Reset delay on successful connect
                errorLoggedRef.current = false;
            };

            ws.onmessage = (event) => {
                if (event.data === 'pong') {
                    return;
                }

                if (typeof event.data !== 'string') {
                    return;
                }

                const trimmed = event.data.trim();
                if (!trimmed || (trimmed[0] !== '{' && trimmed[0] !== '[')) {
                    return;
                }

                let parsed: unknown
                try {
                    parsed = JSON.parse(trimmed)
                } catch {
                    return
                }

                if (!parsed || typeof parsed !== 'object') {
                    return
                }

                const message = parsed as WebSocketMessage
                if (message.type === 'stats_update') {
                    // Update React Query cache with new stats
                    queryClient.setQueryData(surrogateKeys.stats(), message.data)
                }
            };

            ws.onerror = () => {
                if (!isActiveRef.current || manualCloseRef.current) {
                    return;
                }
                errorLoggedRef.current = true;
            };

            ws.onclose = (event) => {
                setIsConnected(false);
                wsRef.current = null;

                if (!isActiveRef.current || !enabled || !user) {
                    return;
                }

                if (manualCloseRef.current) {
                    manualCloseRef.current = false;
                    connect();
                    return;
                }

                // Don't reconnect if explicitly closed or disabled
                if (!enabled || event.code === 1000) {
                    return;
                }

                // Reconnect with exponential backoff
                reconnectTimeoutRef.current = setTimeout(() => {
                    connect();
                }, reconnectDelayRef.current);

                // Double the delay for next attempt (up to max)
                reconnectDelayRef.current = Math.min(
                    reconnectDelayRef.current * 2,
                    MAX_RECONNECT_DELAY
                );
            };

            wsRef.current = ws;
        } catch (e) {
            console.error('[Dashboard WS] Failed to connect:', e);
        }
    }, [enabled, user, queryClient]);

    // Keep connection alive with periodic pings
    useEffect(() => {
        if (!enabled) return;

        const pingInterval = setInterval(() => {
            if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send('ping');
            }
        }, 30000); // Ping every 30 seconds

        return () => clearInterval(pingInterval);
    }, [enabled]);

    // Connect on mount, disconnect on unmount
    useEffect(() => {
        isActiveRef.current = true;
        if (enabled && user) {
            connect();
        }

        return () => {
            isActiveRef.current = false;
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                manualCloseRef.current = true;
                wsRef.current.close(1000, 'Component unmounted');
                wsRef.current = null;
            }
        };
    }, [enabled, user, connect]);

    return {
        isConnected,
    };
}
