/**
 * React Query hooks for Admin Meta Pages
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    listMetaPages,
    createMetaPage,
    updateMetaPage,
    deleteMetaPage,
    type MetaPageCreate,
    type MetaPageUpdate,
} from '@/lib/api/admin-meta'

// Query keys
export const adminMetaKeys = {
    all: ['admin-meta-pages'] as const,
    lists: () => [...adminMetaKeys.all, 'list'] as const,
    list: () => [...adminMetaKeys.lists()] as const,
}

// Hooks
export function useMetaPages() {
    return useQuery({
        queryKey: adminMetaKeys.list(),
        queryFn: listMetaPages,
    })
}

export function useCreateMetaPage() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: MetaPageCreate) => createMetaPage(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: adminMetaKeys.lists() })
        },
    })
}

export function useUpdateMetaPage() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ pageId, data }: { pageId: string; data: MetaPageUpdate }) =>
            updateMetaPage(pageId, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: adminMetaKeys.lists() })
        },
    })
}

export function useDeleteMetaPage() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (pageId: string) => deleteMetaPage(pageId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: adminMetaKeys.lists() })
        },
    })
}
