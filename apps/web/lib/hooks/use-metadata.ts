import { useQuery } from "@tanstack/react-query"

import { getIntendedParentStatuses, getMatchStatuses } from "@/lib/api/metadata"

export const metadataKeys = {
    all: ["metadata"] as const,
    intendedParentStatuses: () => [...metadataKeys.all, "intended-parent-statuses"] as const,
    matchStatuses: () => [...metadataKeys.all, "match-statuses"] as const,
}

export function useIntendedParentStatuses() {
    return useQuery({
        queryKey: metadataKeys.intendedParentStatuses(),
        queryFn: getIntendedParentStatuses,
        staleTime: 60_000,
    })
}

export function useMatchStatuses() {
    return useQuery({
        queryKey: metadataKeys.matchStatuses(),
        queryFn: getMatchStatuses,
        staleTime: 60_000,
    })
}
