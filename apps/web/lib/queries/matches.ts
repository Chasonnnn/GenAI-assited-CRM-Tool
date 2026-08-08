import type { MatchRead, ListMatchesParams } from "@/lib/api/matches"

export const matchKeys = {
    all: ["matches"] as const,
    lists: () => [...matchKeys.all, "list"] as const,
    list: (params: ListMatchesParams) => [...matchKeys.lists(), params] as const,
    details: () => [...matchKeys.all, "detail"] as const,
    detail: (id: string) => [...matchKeys.details(), id] as const,
    stats: () => [...matchKeys.all, "stats"] as const,
}

export function matchDetailQueryOptions(
    matchId: string,
    queryFn: () => Promise<MatchRead>,
) {
    return {
        queryKey: matchKeys.detail(matchId),
        queryFn,
    }
}
