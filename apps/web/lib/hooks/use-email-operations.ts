import { useInfiniteQuery, useQuery } from "@tanstack/react-query"

import {
    getEmailOperationMessage,
    getEmailOperationsMessages,
    getEmailOperationsReadiness,
} from "@/lib/api/email-operations"

export const emailOperationsKeys = {
    all: ["email-operations"] as const,
    readiness: () => [...emailOperationsKeys.all, "readiness"] as const,
    messages: () => [...emailOperationsKeys.all, "messages"] as const,
    detail: (messageId: string | null) =>
        [...emailOperationsKeys.messages(), "detail", messageId] as const,
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
