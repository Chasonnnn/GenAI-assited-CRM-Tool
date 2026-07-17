/**
 * React Query hooks for audit logs
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    listAuditLogs,
    listEventTypes,
    getAIAuditActivity,
    listAuditExports,
    getAuditExport,
    createAuditExport,
    AuditLogFilters,
    AuditExportCreate,
    type AuditExportJob,
} from '@/lib/api/audit'

// Query keys
const auditKeys = {
    all: ['audit'] as const,
    lists: () => [...auditKeys.all, 'list'] as const,
    list: (filters: AuditLogFilters) => [...auditKeys.lists(), filters] as const,
    eventTypes: () => [...auditKeys.all, 'event-types'] as const,
    aiActivity: () => [...auditKeys.all, 'ai-activity'] as const,
    exports: () => [...auditKeys.all, 'exports'] as const,
    export: (id: string) => [...auditKeys.exports(), id] as const,
}

// Hooks
export function useAuditLogs(filters: AuditLogFilters = {}) {
    return useQuery({
        queryKey: auditKeys.list(filters),
        queryFn: () => listAuditLogs(filters),
    })
}

export function useEventTypes() {
    return useQuery({
        queryKey: auditKeys.eventTypes(),
        queryFn: listEventTypes,
        staleTime: 1000 * 60 * 5, // 5 minutes
    })
}

export function useAIAuditActivity(hours: number = 24) {
    return useQuery({
        queryKey: [...auditKeys.aiActivity(), hours],
        queryFn: () => getAIAuditActivity(hours),
        staleTime: 1000 * 60, // 1 minute
    })
}

function hasPendingAuditExports(
    data: { items: AuditExportJob[] } | undefined,
    includeFull: boolean,
) {
    return (data?.items ?? []).some(
        (job) =>
            (includeFull || job.redact_mode !== 'full') &&
            (job.status === 'pending' || job.status === 'processing'),
    )
}

export function useAuditExports({ includeFull = true }: { includeFull?: boolean } = {}) {
    return useQuery({
        queryKey: auditKeys.exports(),
        queryFn: listAuditExports,
        refetchInterval: (query) =>
            hasPendingAuditExports(query.state.data, includeFull) ? 8000 : false,
    })
}

export function useAuditExport(id: string) {
    return useQuery({
        queryKey: auditKeys.export(id),
        queryFn: () => getAuditExport(id),
        enabled: !!id,
    })
}

export function useCreateAuditExport() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (data: AuditExportCreate) => createAuditExport(data),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: auditKeys.exports() })
        },
    })
}
