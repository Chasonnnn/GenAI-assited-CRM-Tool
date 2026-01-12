/**
 * React Query hooks for AI Assistant.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as aiApi from '../api/ai';
import type { AISettingsUpdate, ChatRequest } from '../api/ai';

// Query keys
export const aiKeys = {
    all: ['ai'] as const,
    settings: () => [...aiKeys.all, 'settings'] as const,
    consent: () => [...aiKeys.all, 'consent'] as const,
    conversation: (entityType: string, entityId: string) =>
        [...aiKeys.all, 'conversation', entityType, entityId] as const,
};

// ============================================================================
// Settings Hooks
// ============================================================================

export function useAISettings() {
    return useQuery({
        queryKey: aiKeys.settings(),
        queryFn: aiApi.getAISettings,
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
}

export function useUpdateAISettings() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (update: AISettingsUpdate) => aiApi.updateAISettings(update),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: aiKeys.settings() });
        },
    });
}

export function useTestAPIKey() {
    return useMutation({
        mutationFn: ({ provider, api_key }: { provider: 'openai' | 'gemini'; api_key: string }) =>
            aiApi.testAPIKey(provider, api_key),
    });
}

// ============================================================================
// Consent Hooks
// ============================================================================

export function useAIConsent() {
    return useQuery({
        queryKey: aiKeys.consent(),
        queryFn: aiApi.getConsent,
        staleTime: 5 * 60 * 1000,
    });
}

export function useAcceptConsent() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: aiApi.acceptConsent,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: aiKeys.consent() });
            queryClient.invalidateQueries({ queryKey: aiKeys.settings() });
        },
    });
}

// ============================================================================
// Chat Hooks
// ============================================================================

export function useConversation(entityType?: string | null, entityId?: string | null) {
    // Determine if this is global mode
    const isGlobal = !entityType || !entityId || entityType === 'global';

    return useQuery({
        queryKey: isGlobal
            ? [...aiKeys.all, 'conversation', 'global']
            : aiKeys.conversation(entityType!, entityId!),
        queryFn: () => isGlobal
            ? aiApi.getGlobalConversation()
            : aiApi.getConversation(entityType!, entityId!),
        staleTime: 30 * 1000, // 30 seconds
    });
}

export function useSendMessage() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (request: ChatRequest) => aiApi.sendChatMessage(request),
        onSuccess: (_data, variables) => {
            // Invalidate conversation to refetch with new message
            const isGlobal = !variables.entity_type || !variables.entity_id || variables.entity_type === 'global';
            if (isGlobal) {
                queryClient.invalidateQueries({
                    queryKey: [...aiKeys.all, 'conversation', 'global']
                });
            } else {
                queryClient.invalidateQueries({
                    queryKey: aiKeys.conversation(variables.entity_type!, variables.entity_id!)
                });
            }
        },
    });
}

// ============================================================================
// Action Approval Hooks
// ============================================================================

export function useApproveAction() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (approvalId: string) => aiApi.approveAction(approvalId),
        onSuccess: () => {
            // Invalidate conversations to update action statuses
            queryClient.invalidateQueries({ queryKey: [...aiKeys.all, 'conversation'] });
        },
    });
}

export function useRejectAction() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (approvalId: string) => aiApi.rejectAction(approvalId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [...aiKeys.all, 'conversation'] });
        },
    });
}

// ============================================================================
// Focused AI Hooks (One-shot operations)
// ============================================================================

export function useSummarizeCase() {
    return useMutation({
        mutationFn: (caseId: string) => aiApi.summarizeCase(caseId),
    });
}

export function useDraftEmail() {
    return useMutation({
        mutationFn: (request: aiApi.DraftEmailRequest) => aiApi.draftEmail(request),
    });
}

export function useAnalyzeDashboard() {
    return useMutation({
        mutationFn: () => aiApi.analyzeDashboard(),
    });
}

export function useAIUsageSummary(days: number = 30) {
    return useQuery({
        queryKey: [...aiKeys.all, 'usage', 'summary', days],
        queryFn: () => aiApi.getAIUsageSummary(days),
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
}
