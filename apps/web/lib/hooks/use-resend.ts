/**
 * React Query hooks for Resend email configuration.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as resendApi from '../api/resend';
import type { ResendSettingsUpdate } from '../api/resend';

// Query keys
export const resendKeys = {
    all: ['resend'] as const,
    settings: () => [...resendKeys.all, 'settings'] as const,
    eligibleSenders: () => [...resendKeys.all, 'eligible-senders'] as const,
};

// ============================================================================
// Settings Hooks
// ============================================================================

export function useResendSettings() {
    return useQuery({
        queryKey: resendKeys.settings(),
        queryFn: resendApi.getResendSettings,
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
}

export function useUpdateResendSettings() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (update: ResendSettingsUpdate) => resendApi.updateResendSettings(update),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: resendKeys.settings() });
        },
    });
}

export function useTestResendKey() {
    return useMutation({
        mutationFn: (api_key: string) => resendApi.testResendKey(api_key),
    });
}

export function useRotateWebhook() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: resendApi.rotateWebhook,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: resendKeys.settings() });
        },
    });
}

// ============================================================================
// Gmail Senders Hooks
// ============================================================================

export function useEligibleSenders(enabled = true) {
    return useQuery({
        queryKey: resendKeys.eligibleSenders(),
        queryFn: resendApi.listEligibleSenders,
        enabled,
        staleTime: 60 * 1000, // 1 minute
    });
}
