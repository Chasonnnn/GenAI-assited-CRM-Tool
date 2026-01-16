/**
 * React Query hooks for Intended Parents
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    listIntendedParents,
    getIntendedParent,
    getIntendedParentStats,
    createIntendedParent,
    updateIntendedParent,
    updateIntendedParentStatus,
    archiveIntendedParent,
    restoreIntendedParent,
    deleteIntendedParent,
    getIntendedParentHistory,
    listIntendedParentNotes,
    createIntendedParentNote,
    deleteIntendedParentNote,
    IntendedParentFilters,
} from '@/lib/api/intended-parents'
import type {
    IntendedParentCreate,
    IntendedParentUpdate,
    IntendedParentStatusUpdate,
    EntityNoteCreate,
} from '@/lib/types/intended-parent'

// Query keys
export const intendedParentKeys = {
    all: ['intended-parents'] as const,
    lists: () => [...intendedParentKeys.all, 'list'] as const,
    list: (filters: IntendedParentFilters) => [...intendedParentKeys.lists(), filters] as const,
    details: () => [...intendedParentKeys.all, 'detail'] as const,
    detail: (id: string) => [...intendedParentKeys.details(), id] as const,
    stats: () => [...intendedParentKeys.all, 'stats'] as const,
    history: (id: string) => [...intendedParentKeys.all, 'history', id] as const,
    notes: (id: string) => [...intendedParentKeys.all, 'notes', id] as const,
}

// List hook
export function useIntendedParents(filters: IntendedParentFilters = {}) {
    return useQuery({
        queryKey: intendedParentKeys.list(filters),
        queryFn: () => listIntendedParents(filters),
    })
}

// Stats hook
export function useIntendedParentStats() {
    return useQuery({
        queryKey: intendedParentKeys.stats(),
        queryFn: getIntendedParentStats,
    })
}

// Detail hook
export function useIntendedParent(id: string | null) {
    return useQuery({
        queryKey: intendedParentKeys.detail(id || ''),
        queryFn: () => getIntendedParent(id!),
        enabled: !!id,
    })
}

// History hook
export function useIntendedParentHistory(id: string | null) {
    return useQuery({
        queryKey: intendedParentKeys.history(id || ''),
        queryFn: () => getIntendedParentHistory(id!),
        enabled: !!id,
    })
}

// Notes hooks
export function useIntendedParentNotes(id: string | null) {
    return useQuery({
        queryKey: intendedParentKeys.notes(id || ''),
        queryFn: () => listIntendedParentNotes(id!),
        enabled: !!id,
    })
}

// Mutations
export function useCreateIntendedParent() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: IntendedParentCreate) => createIntendedParent(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.lists() })
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.stats() })
        },
    })
}

export function useUpdateIntendedParent() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: IntendedParentUpdate }) =>
            updateIntendedParent(id, data),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.lists() })
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.detail(id) })
        },
    })
}

export function useUpdateIntendedParentStatus() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: IntendedParentStatusUpdate }) =>
            updateIntendedParentStatus(id, data),
        onSuccess: (response, { id }) => {
            if (response.status === 'applied' && response.intended_parent) {
                queryClient.setQueryData(
                    intendedParentKeys.detail(response.intended_parent.id),
                    response.intended_parent
                )
            }
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.lists() })
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.detail(id) })
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.stats() })
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.history(id) })
        },
    })
}

export function useArchiveIntendedParent() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (id: string) => archiveIntendedParent(id),
        onSuccess: (_, id) => {
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.lists() })
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.detail(id) })
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.stats() })
        },
    })
}

export function useRestoreIntendedParent() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (id: string) => restoreIntendedParent(id),
        onSuccess: (_, id) => {
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.lists() })
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.detail(id) })
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.stats() })
        },
    })
}

export function useDeleteIntendedParent() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (id: string) => deleteIntendedParent(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.lists() })
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.stats() })
        },
    })
}

// Notes mutations
export function useCreateIntendedParentNote() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: EntityNoteCreate }) =>
            createIntendedParentNote(id, data),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.notes(id) })
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.detail(id) })
        },
    })
}

export function useDeleteIntendedParentNote() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ ipId, noteId }: { ipId: string; noteId: string }) =>
            deleteIntendedParentNote(ipId, noteId),
        onSuccess: (_, { ipId }) => {
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.notes(ipId) })
        },
    })
}
