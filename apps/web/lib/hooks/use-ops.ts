/**
 * React Query hooks for Ops module (integration health, alerts).
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from '@/components/ui/toast';
import * as opsApi from '../api/ops';
import { getErrorMessage } from '../error-utils';
import type { AlertsListParams } from '../api/ops';

// Query keys
const opsKeys = {
    all: ['ops'] as const,
    health: () => [...opsKeys.all, 'health'] as const,
    alertsSummary: () => [...opsKeys.all, 'alerts-summary'] as const,
    alerts: (params?: AlertsListParams) => [...opsKeys.all, 'alerts', params] as const,
};

/**
 * Fetch integration health status.
 */
export function useIntegrationHealth(enabled = true) {
    return useQuery({
        queryKey: opsKeys.health(),
        queryFn: opsApi.getIntegrationHealth,
        enabled,
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
            // Use prefix matching to invalidate all alert queries regardless of params
            void queryClient.invalidateQueries({ queryKey: [...opsKeys.all, 'alerts'] });
            void queryClient.invalidateQueries({ queryKey: opsKeys.alertsSummary() });
        },
        onError: (error) => {
            toast.error(getErrorMessage(error, 'Failed to resolve alert'));
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
            // Use prefix matching to invalidate all alert queries regardless of params
            void queryClient.invalidateQueries({ queryKey: [...opsKeys.all, 'alerts'] });
            // Acknowledge changes status, affecting summary counts
            void queryClient.invalidateQueries({ queryKey: opsKeys.alertsSummary() });
        },
        onError: (error) => {
            toast.error(getErrorMessage(error, 'Failed to acknowledge alert'));
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
            // Use prefix matching to invalidate all alert queries regardless of params
            void queryClient.invalidateQueries({ queryKey: [...opsKeys.all, 'alerts'] });
            void queryClient.invalidateQueries({ queryKey: opsKeys.alertsSummary() });
        },
        onError: (error) => {
            toast.error(getErrorMessage(error, 'Failed to snooze alert'));
        },
    });
}
