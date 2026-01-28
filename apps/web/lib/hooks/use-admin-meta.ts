/**
 * React Query hooks for Admin Meta Pages
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    listMetaPages,
    createMetaPage,
    updateMetaPage,
    deleteMetaPage,
    listMetaAdAccounts,
    createMetaAdAccount,
    updateMetaAdAccount,
    deleteMetaAdAccount,
    type MetaPageCreate,
    type MetaPageUpdate,
    type MetaAdAccountCreate,
    type MetaAdAccountUpdate,
} from '@/lib/api/admin-meta'

// Query keys
export const adminMetaKeys = {
    all: ['admin-meta-pages'] as const,
    lists: () => [...adminMetaKeys.all, 'list'] as const,
    list: () => [...adminMetaKeys.lists()] as const,
}

export const adminMetaAdAccountKeys = {
    all: ['admin-meta-ad-accounts'] as const,
    lists: () => [...adminMetaAdAccountKeys.all, 'list'] as const,
    list: () => [...adminMetaAdAccountKeys.lists()] as const,
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

export function useAdminMetaAdAccounts() {
    return useQuery({
        queryKey: adminMetaAdAccountKeys.list(),
        queryFn: listMetaAdAccounts,
    })
}

export function useCreateMetaAdAccount() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: MetaAdAccountCreate) => createMetaAdAccount(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: adminMetaAdAccountKeys.lists() })
        },
    })
}

export function useUpdateMetaAdAccount() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            accountId,
            data,
        }: {
            accountId: string
            data: MetaAdAccountUpdate
        }) => updateMetaAdAccount(accountId, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: adminMetaAdAccountKeys.lists() })
        },
    })
}

export function useDeleteMetaAdAccount() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (accountId: string) => deleteMetaAdAccount(accountId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: adminMetaAdAccountKeys.lists() })
        },
    })
}
