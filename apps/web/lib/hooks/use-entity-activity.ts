import { useInfiniteQuery, useQuery } from "@tanstack/react-query"

import {
    getEntityActivity,
    type ActivityEntityType,
} from "@/lib/api/activity"

export const entityActivityKeys = {
    all: ["entity-activity"] as const,
    entity: (entityType: ActivityEntityType, entityId: string) =>
        [...entityActivityKeys.all, entityType, entityId] as const,
}

export function useInfiniteEntityActivity(
    entityType: ActivityEntityType,
    entityId: string | null,
) {
    return useInfiniteQuery({
        queryKey: [...entityActivityKeys.entity(entityType, entityId ?? ""), "infinite"],
        queryFn: ({ pageParam }) => getEntityActivity(entityType, entityId!, pageParam, 50),
        initialPageParam: 1,
        getNextPageParam: (lastPage) =>
            lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
        enabled: Boolean(entityId),
    })
}

export function useEntityActivity(
    entityType: ActivityEntityType,
    entityId: string | null,
) {
    return useQuery({
        queryKey: entityActivityKeys.entity(entityType, entityId ?? ""),
        queryFn: () => getEntityActivity(entityType, entityId!),
        enabled: Boolean(entityId),
    })
}
