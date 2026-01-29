/**
 * React Query hooks for CSV Import
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    previewImport,
    submitImport,
    approveImport,
    rejectImport,
    retryImport,
    runImportInline,
    cancelImport,
    listPendingImportApprovals,
    aiMapColumns,
    listImports,
    getImportDetails,
    type EnhancedImportPreview,
    type ColumnMappingItem,
    type AiMapRequest,
    type AiMapResponse,
    type ImportApprovalItem,
    type ImportSubmitResponse,
    type ImportApprovalResponse,
    type ImportActionResponse,
} from '@/lib/api/import'

// Re-export types for convenience
export type { EnhancedImportPreview, ColumnMappingItem, ImportApprovalItem, ImportSubmitResponse, ImportApprovalResponse, ImportActionResponse }

// Query keys
export const importKeys = {
    all: ['imports'] as const,
    lists: () => [...importKeys.all, 'list'] as const,
    list: () => [...importKeys.lists()] as const,
    pending: () => [...importKeys.all, 'pending'] as const,
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

export function usePendingImportApprovals(enabled = true) {
    return useQuery<ImportApprovalItem[]>({
        queryKey: importKeys.pending(),
        queryFn: listPendingImportApprovals,
        enabled,
    })
}

export function usePreviewImport() {
    return useMutation({
        mutationFn: (params: { file: File; applyTemplate?: boolean; enableAi?: boolean }) =>
            previewImport(
                params.file,
                params.applyTemplate !== undefined || params.enableAi !== undefined
                    ? { applyTemplate: params.applyTemplate, enableAi: params.enableAi }
                    : undefined
            ),
    })
}

export function useSubmitImport() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (params: {
            importId: string
            payload: {
                column_mappings: ColumnMappingItem[]
                unknown_column_behavior?: 'ignore' | 'metadata' | 'warn'
                save_as_template_name?: string | null
                backdate_created_at?: boolean
            }
        }) =>
            submitImport(params.importId, params.payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: importKeys.lists() })
            queryClient.invalidateQueries({ queryKey: importKeys.pending() })
        },
    })
}

export function useApproveImport() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (importId: string) => approveImport(importId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: importKeys.lists() })
            queryClient.invalidateQueries({ queryKey: importKeys.pending() })
        },
    })
}

export function useRejectImport() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (params: { importId: string; reason: string }) =>
            rejectImport(params.importId, params.reason),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: importKeys.lists() })
            queryClient.invalidateQueries({ queryKey: importKeys.pending() })
        },
    })
}

export function useRetryImport() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (importId: string) => retryImport(importId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: importKeys.lists() })
            queryClient.invalidateQueries({ queryKey: importKeys.pending() })
        },
    })
}

export function useRunImportInline() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (importId: string) => runImportInline(importId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: importKeys.lists() })
            queryClient.invalidateQueries({ queryKey: importKeys.pending() })
        },
    })
}

export function useCancelImport() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (importId: string) => cancelImport(importId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: importKeys.lists() })
            queryClient.invalidateQueries({ queryKey: importKeys.pending() })
        },
    })
}

export function useAiMapImport() {
    return useMutation<AiMapResponse, Error, AiMapRequest>({
        mutationFn: (payload) => aiMapColumns(payload),
    })
}
