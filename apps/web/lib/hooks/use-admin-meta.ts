/**
 * React Query hooks for Admin Meta Pages
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    listMetaAdAccounts,
    createMetaAdAccount,
    updateMetaAdAccount,
    deleteMetaAdAccount,
    type MetaAdAccountCreate,
    type MetaAdAccountUpdate,
} from '@/lib/api/admin-meta'

export const adminMetaAdAccountKeys = {
    all: ['admin-meta-ad-accounts'] as const,
    lists: () => [...adminMetaAdAccountKeys.all, 'list'] as const,
    list: () => [...adminMetaAdAccountKeys.lists()] as const,
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
