import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
    getPlatformEmailReadiness,
    getPlatformEmailStatus,
    requestPlatformEmailReadinessCheck,
} from "@/lib/api/platform"

export const platformEmailKeys = {
    all: ["platform", "email"] as const,
    status: () => ["platform", "email-status"] as const,
    readiness: () => [...platformEmailKeys.all, "readiness"] as const,
}

export function usePlatformEmailStatus({
    enabled = true,
}: { enabled?: boolean } = {}) {
    return useQuery({
        queryKey: platformEmailKeys.status(),
        queryFn: getPlatformEmailStatus,
        enabled,
        retry: false,
        staleTime: 30_000,
    })
}

export function usePlatformEmailReadiness({
    enabled = true,
}: { enabled?: boolean } = {}) {
    return useQuery({
        queryKey: platformEmailKeys.readiness(),
        queryFn: getPlatformEmailReadiness,
        enabled,
        staleTime: 30_000,
        refetchInterval: (query) => {
            const status = query.state.data?.check_status
            return status === "queued" || status === "running" ? 5_000 : false
        },
        refetchIntervalInBackground: false,
    })
}

export function useRequestPlatformEmailReadinessCheck() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: requestPlatformEmailReadinessCheck,
        onSuccess: (readiness) => {
            queryClient.setQueryData(platformEmailKeys.readiness(), readiness)
            void queryClient.invalidateQueries({
                queryKey: platformEmailKeys.readiness(),
            })
        },
    })
}
