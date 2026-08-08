import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
    type MessagingConversationFilters,
    type MessagingConversationLinkRequest,
    type MessagingReconciliationUpdateRequest,
    getCandidateMessagingConversations,
    getMessagingConversation,
    getMessagingConversations,
    linkMessagingConversation,
    markMessagingConversationRead,
    updateMessagingReconciliation,
} from "@/lib/api/messaging-inbox"

export const messagingInboxKeys = {
    all: ["messaging-inbox"] as const,
    conversations: () => [...messagingInboxKeys.all, "conversations"] as const,
    list: (filters: MessagingConversationFilters) =>
        [...messagingInboxKeys.conversations(), "list", filters] as const,
    detail: (conversationId: string | null) =>
        [...messagingInboxKeys.conversations(), "detail", conversationId] as const,
    candidate: (candidateId: string, limit: number, offset: number) =>
        [
            ...messagingInboxKeys.conversations(),
            "candidate",
            candidateId,
            limit,
            offset,
        ] as const,
}

export function useMessagingConversations(
    filters: MessagingConversationFilters,
    enabled = true,
) {
    return useQuery({
        queryKey: messagingInboxKeys.list(filters),
        queryFn: () => getMessagingConversations(filters),
        enabled,
        staleTime: 15_000,
    })
}

export function useCandidateMessagingConversations(
    candidateId: string,
    options: { limit?: number; offset?: number; enabled?: boolean } = {},
) {
    const limit = options.limit ?? 50
    const offset = options.offset ?? 0
    return useQuery({
        queryKey: messagingInboxKeys.candidate(candidateId, limit, offset),
        queryFn: () =>
            getCandidateMessagingConversations(candidateId, { limit, offset }),
        enabled: options.enabled ?? true,
        staleTime: 15_000,
    })
}

export function useMessagingConversation(
    conversationId: string | null,
    enabled = true,
) {
    return useQuery({
        queryKey: messagingInboxKeys.detail(conversationId),
        queryFn: () => getMessagingConversation(conversationId as string),
        enabled: enabled && conversationId !== null,
        staleTime: 15_000,
    })
}

export function useMarkMessagingConversationRead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: markMessagingConversationRead,
        onSuccess: (conversation) => {
            queryClient.setQueryData(
                messagingInboxKeys.detail(conversation.id),
                conversation,
            )
            void queryClient.invalidateQueries({
                queryKey: messagingInboxKeys.conversations(),
            })
        },
    })
}

export function useLinkMessagingConversation() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            conversationId,
            request,
        }: {
            conversationId: string
            request: MessagingConversationLinkRequest
        }) => linkMessagingConversation(conversationId, request),
        onSuccess: (conversation) => {
            queryClient.setQueryData(
                messagingInboxKeys.detail(conversation.id),
                conversation,
            )
            void queryClient.invalidateQueries({
                queryKey: messagingInboxKeys.conversations(),
            })
        },
    })
}

export function useUpdateMessagingReconciliation() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            caseId,
            request,
        }: {
            caseId: string
            request: MessagingReconciliationUpdateRequest
        }) => updateMessagingReconciliation(caseId, request),
        onSuccess: () => {
            void queryClient.invalidateQueries({
                queryKey: messagingInboxKeys.conversations(),
            })
        },
    })
}
