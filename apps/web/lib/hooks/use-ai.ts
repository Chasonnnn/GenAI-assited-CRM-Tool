/**
 * React Query hooks for AI Assistant.
 */

import { useQuery, useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query';
import * as aiApi from '../api/ai';
import type { AISettingsUpdate, ChatRequest } from '../api/ai';

// Query keys
const aiKeys = {
    all: ['ai'] as const,
    settings: () => [...aiKeys.all, 'settings'] as const,
    consent: () => [...aiKeys.all, 'consent'] as const,
    usageSummary: () => [...aiKeys.all, 'usage', 'summary'] as const,
    conversation: (entityType: string, entityId: string) =>
        [...aiKeys.all, 'conversation', entityType, entityId] as const,
};

function invalidateAIUsageCaches(queryClient: QueryClient) {
    void queryClient.invalidateQueries({
        queryKey: aiKeys.usageSummary(),
        exact: false,
    });
}

// ============================================================================
// Settings Hooks
// ============================================================================

export function useAISettings(enabled = true) {
    return useQuery({
        queryKey: aiKeys.settings(),
        queryFn: aiApi.getAISettings,
        enabled,
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
}

export function useUpdateAISettings() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (update: AISettingsUpdate) => aiApi.updateAISettings(update),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: aiKeys.settings() });
        },
    });
}

export function useTestAPIKey() {
    return useMutation({
        mutationFn: ({
            provider,
            api_key,
            vertex_api_key,
        }: {
            provider: 'gemini' | 'vertex_api_key';
            api_key: string;
            vertex_api_key?: aiApi.VertexAPIKeyConfig;
        }) => aiApi.testAPIKey(provider, api_key, vertex_api_key),
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
            void queryClient.invalidateQueries({ queryKey: aiKeys.consent() });
            void queryClient.invalidateQueries({ queryKey: aiKeys.settings() });
        },
    });
}

// ============================================================================
// Chat Hooks
// ============================================================================

export function useConversation(
    entityType?: string | null,
    entityId?: string | null,
    options?: { enabled?: boolean }
) {
    // Determine if this is global mode
    const isGlobal = !entityType || !entityId || entityType === 'global';

    return useQuery({
        queryKey: isGlobal
            ? [...aiKeys.all, 'conversation', 'global']
            : aiKeys.conversation(entityType!, entityId!),
        queryFn: () => isGlobal
            ? aiApi.getGlobalConversation()
            : aiApi.getConversation(entityType!, entityId!),
        enabled: options?.enabled ?? true,
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
                void queryClient.invalidateQueries({
                    queryKey: [...aiKeys.all, 'conversation', 'global']
                });
            } else {
                void queryClient.invalidateQueries({
                    queryKey: aiKeys.conversation(variables.entity_type!, variables.entity_id!)
                });
            }
            invalidateAIUsageCaches(queryClient);
        },
    });
}

export function useStreamChatMessage() {
    const queryClient = useQueryClient();

    return async function streamChatMessage(
        request: ChatRequest,
        onEvent: (event: aiApi.ChatStreamEvent) => void,
        signal?: AbortSignal
    ) {
        const response = await aiApi.streamChatMessage(
            request,
            onEvent,
            signal ? { signal } : undefined
        );

        const isGlobal =
            !request.entity_type || !request.entity_id || request.entity_type === 'global';
        if (isGlobal) {
            void queryClient.invalidateQueries({
                queryKey: [...aiKeys.all, 'conversation', 'global'],
            });
        } else {
            void queryClient.invalidateQueries({
                queryKey: aiKeys.conversation(request.entity_type!, request.entity_id!),
            });
        }
        invalidateAIUsageCaches(queryClient);

        return response;
    };
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
            void queryClient.invalidateQueries({ queryKey: [...aiKeys.all, 'conversation'] });
        },
    });
}

export function useRejectAction() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (approvalId: string) => aiApi.rejectAction(approvalId),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: [...aiKeys.all, 'conversation'] });
        },
    });
}

// ============================================================================
// Focused AI Hooks (One-shot operations)
// ============================================================================

export function useSummarizeSurrogate() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (surrogateId: string) => aiApi.summarizeSurrogate(surrogateId),
        onSuccess: () => {
            void queryClient.invalidateQueries({
                queryKey: aiKeys.usageSummary(),
                exact: false,
            });
        },
    });
}

export function useDraftEmail() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (request: aiApi.DraftEmailRequest) => aiApi.draftEmail(request),
        onSuccess: () => {
            void queryClient.invalidateQueries({
                queryKey: aiKeys.usageSummary(),
                exact: false,
            });
        },
    });
}

export function useAnalyzeDashboard() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: () => aiApi.analyzeDashboard(),
        onSuccess: () => {
            void queryClient.invalidateQueries({
                queryKey: aiKeys.usageSummary(),
                exact: false,
            });
        },
    });
}

export function useAIUsageSummary(days: number = 30) {
    return useQuery({
        queryKey: [...aiKeys.usageSummary(), days],
        queryFn: () => aiApi.getAIUsageSummary(days),
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
}
