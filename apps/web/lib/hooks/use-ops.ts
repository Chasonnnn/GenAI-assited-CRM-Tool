/**
 * React Query hooks for Ops module (integration health, alerts).
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as opsApi from '../api/ops';
import type { AlertsListParams } from '../api/ops';

// Query keys
export const opsKeys = {
    all: ['ops'] as const,
    health: () => [...opsKeys.all, 'health'] as const,
    alertsSummary: () => [...opsKeys.all, 'alerts-summary'] as const,
    alerts: (params?: AlertsListParams) => [...opsKeys.all, 'alerts', params] as const,
};

/**
 * Fetch integration health status.
 */
export function useIntegrationHealth() {
    return useQuery({
        queryKey: opsKeys.health(),
        queryFn: opsApi.getIntegrationHealth,
        staleTime: 30 * 1000, // 30 seconds
    });
}

/**
 * Fetch alerts summary (counts by severity).
 */
export function useAlertsSummary() {
    return useQuery({
        queryKey: opsKeys.alertsSummary(),
        queryFn: opsApi.getAlertsSummary,
        staleTime: 30 * 1000,
    });
}

/**
 * Fetch alerts list with optional filters.
 */
export function useAlerts(params: AlertsListParams = {}) {
    return useQuery({
        queryKey: opsKeys.alerts(params),
        queryFn: () => opsApi.getAlerts(params),
        staleTime: 30 * 1000,
    });
}

/**
 * Resolve an alert.
 */
export function useResolveAlert() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: opsApi.resolveAlert,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: opsKeys.alerts() });
            queryClient.invalidateQueries({ queryKey: opsKeys.alertsSummary() });
        },
    });
}

/**
 * Acknowledge an alert.
 */
export function useAcknowledgeAlert() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: opsApi.acknowledgeAlert,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: opsKeys.alerts() });
        },
    });
}

/**
 * Snooze an alert.
 */
export function useSnoozeAlert() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ alertId, hours }: { alertId: string; hours?: number }) =>
            opsApi.snoozeAlert(alertId, hours),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: opsKeys.alerts() });
            queryClient.invalidateQueries({ queryKey: opsKeys.alertsSummary() });
        },
    });
}
