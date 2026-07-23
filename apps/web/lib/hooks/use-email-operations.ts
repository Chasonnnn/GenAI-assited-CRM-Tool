import {
    type QueryClient,
    useInfiniteQuery,
    useMutation,
    useQuery,
    useQueryClient,
} from "@tanstack/react-query"

import {
    type EmailReconciliationListStatus,
    confirmEmailReconciliationNotSent,
    confirmEmailReconciliationSent,
    dismissEmailReconciliationCase,
    getEmailOperationMessage,
    getEmailOperationsMessages,
    getEmailOperationsReadiness,
    getEmailReconciliationCases,
    linkEmailReconciliationEvent,
    retryEmailReconciliationCorrelation,
} from "@/lib/api/email-operations"

export const emailOperationsKeys = {
    all: ["email-operations"] as const,
    readiness: () => [...emailOperationsKeys.all, "readiness"] as const,
    messages: () => [...emailOperationsKeys.all, "messages"] as const,
    reconciliation: () => [...emailOperationsKeys.all, "reconciliation"] as const,
    reconciliationCases: (status: EmailReconciliationListStatus) =>
        [...emailOperationsKeys.reconciliation(), status] as const,
    detail: (messageId: string | null) =>
        [...emailOperationsKeys.messages(), "detail", messageId] as const,
}

function invalidateReconciliation(queryClient: QueryClient) {
    void queryClient.invalidateQueries({
        queryKey: emailOperationsKeys.reconciliation(),
    })
}

function invalidateReconciliationAndDeliveryEvidence(queryClient: QueryClient) {
    invalidateReconciliation(queryClient)
    void queryClient.invalidateQueries({
        queryKey: emailOperationsKeys.readiness(),
    })
    void queryClient.invalidateQueries({
        queryKey: emailOperationsKeys.messages(),
    })
}

export function useEmailOperationsReadiness() {
    return useQuery({
        queryKey: emailOperationsKeys.readiness(),
        queryFn: getEmailOperationsReadiness,
        staleTime: 30_000,
    })
}

export function useEmailOperationsMessages() {
    return useInfiniteQuery({
        queryKey: emailOperationsKeys.messages(),
        queryFn: ({ pageParam }) =>
            getEmailOperationsMessages({
                limit: 25,
                ...(pageParam ? { cursor: pageParam } : {}),
            }),
        initialPageParam: undefined as string | undefined,
        getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
        staleTime: 30_000,
    })
}

export function useEmailOperationMessage(messageId: string | null) {
    return useQuery({
        queryKey: emailOperationsKeys.detail(messageId),
        queryFn: () => getEmailOperationMessage(messageId as string),
        enabled: messageId !== null,
        staleTime: 30_000,
    })
}

export function useEmailReconciliationCases({
    enabled,
    status = "action_required",
}: {
    enabled: boolean
    status?: EmailReconciliationListStatus
}) {
    return useInfiniteQuery({
        queryKey: emailOperationsKeys.reconciliationCases(status),
        queryFn: ({ pageParam }) =>
            getEmailReconciliationCases({
                limit: 25,
                status,
                ...(pageParam ? { cursor: pageParam } : {}),
            }),
        initialPageParam: undefined as string | undefined,
        getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
        enabled,
        staleTime: 30_000,
    })
}

export function useRetryEmailReconciliationCorrelation() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: retryEmailReconciliationCorrelation,
        onSuccess: () => {
            invalidateReconciliationAndDeliveryEvidence(queryClient)
        },
    })
}

export function useDismissEmailReconciliationCase() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: dismissEmailReconciliationCase,
        onSuccess: () => {
            invalidateReconciliation(queryClient)
        },
    })
}

export function useLinkEmailReconciliationEvent() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: linkEmailReconciliationEvent,
        onSuccess: () => {
            invalidateReconciliationAndDeliveryEvidence(queryClient)
        },
    })
}

export function useConfirmEmailReconciliationSent() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: confirmEmailReconciliationSent,
        onSuccess: () => {
            invalidateReconciliationAndDeliveryEvidence(queryClient)
        },
    })
}

export function useConfirmEmailReconciliationNotSent() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: confirmEmailReconciliationNotSent,
        onSuccess: () => {
            invalidateReconciliationAndDeliveryEvidence(queryClient)
        },
    })
}
