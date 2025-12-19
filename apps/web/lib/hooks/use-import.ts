/**
 * React Query hooks for CSV Import
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    previewImport,
    executeImport,
    listImports,
    getImportDetails,
    type ImportPreview,
} from '@/lib/api/import'

// Re-export types for convenience
export type { ImportPreview }

// Query keys
export const importKeys = {
    all: ['imports'] as const,
    lists: () => [...importKeys.all, 'list'] as const,
    list: () => [...importKeys.lists()] as const,
    details: () => [...importKeys.all, 'detail'] as const,
    detail: (id: string) => [...importKeys.details(), id] as const,
}

// Hooks
export function useImports() {
    return useQuery({
        queryKey: importKeys.list(),
        queryFn: listImports,
    })
}

export function useImportDetails(importId: string | null) {
    return useQuery({
        queryKey: importKeys.detail(importId || ''),
        queryFn: () => getImportDetails(importId!),
        enabled: !!importId,
    })
}

export function usePreviewImport() {
    return useMutation({
        mutationFn: (file: File) => previewImport(file),
    })
}

export function useExecuteImport() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (file: File) => executeImport(file),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: importKeys.lists() })
        },
    })
}
