/**
 * React Query hooks for MFA (Multi-Factor Authentication).
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as mfaApi from '../api/mfa';

// =============================================================================
// Query Keys
// =============================================================================

const mfaKeys = {
    all: ['mfa'] as const,
    status: () => [...mfaKeys.all, 'status'] as const,
    duoStatus: () => [...mfaKeys.all, 'duo-status'] as const,
};

// =============================================================================
// Hooks
// =============================================================================

/**
 * Get MFA enrollment status for the current user.
 */
export function useMFAStatus() {
    return useQuery({
        queryKey: mfaKeys.status(),
        queryFn: mfaApi.getMFAStatus,
        staleTime: 30 * 1000, // 30 seconds
    });
}

/**
 * Check Duo availability and enrollment status.
 */
export function useDuoStatus() {
    return useQuery({
        queryKey: mfaKeys.duoStatus(),
        queryFn: mfaApi.getDuoStatus,
        staleTime: 30 * 1000,
    });
}

/**
 * Regenerate recovery codes.
 */
export function useRegenerateRecoveryCodes() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: mfaApi.regenerateRecoveryCodes,
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: mfaKeys.status() });
        },
    });
}

/**
 * Complete MFA challenge (verifies code and upgrades session).
 */
export function useCompleteMFAChallenge() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: mfaApi.completeMFAChallenge,
        onSuccess: () => {
            // Invalidate user session to refetch with mfa_verified=true
            void queryClient.invalidateQueries({ queryKey: ['auth', 'me'] });
        },
    });
}

/**
 * Disable MFA for the current user.
 */
export function useDisableMFA() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: mfaApi.disableMFA,
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: mfaKeys.status() });
        },
    });
}

/**
 * Initiate Duo Universal Prompt.
 */
export function useInitiateDuoAuth() {
    return useMutation({
        mutationFn: mfaApi.initiateDuoAuth,
    });
}
