/**
 * React Query hooks for audit logs
 */

import { useQuery } from '@tanstack/react-query'
import { listAuditLogs, listEventTypes, AuditLogFilters } from '@/lib/api/audit'

// Query keys
export const auditKeys = {
    all: ['audit'] as const,
    lists: () => [...auditKeys.all, 'list'] as const,
    list: (filters: AuditLogFilters) => [...auditKeys.lists(), filters] as const,
    eventTypes: () => [...auditKeys.all, 'event-types'] as const,
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
