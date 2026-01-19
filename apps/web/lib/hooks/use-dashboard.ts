/**
 * React Query hooks for dashboard widgets.
 */

import { useQuery } from '@tanstack/react-query'
import {
    getUpcoming,
    getAttention,
    type GetUpcomingParams,
    type GetAttentionParams,
    type UpcomingResponse,
    type UpcomingTask,
    type UpcomingMeeting,
    type UpcomingItem,
    type AttentionResponse,
    type UnreachedLead,
    type OverdueTaskItem,
    type StuckSurrogate,
} from '@/lib/api/dashboard'

// =============================================================================
// Query Keys
// =============================================================================

export const dashboardKeys = {
    all: ['dashboard'] as const,
    upcoming: (params?: GetUpcomingParams) => [...dashboardKeys.all, 'upcoming', params] as const,
    attention: (params?: GetAttentionParams) => [...dashboardKeys.all, 'attention', params] as const,
}

// =============================================================================
// Hooks
// =============================================================================

/**
 * Get upcoming tasks and meetings for dashboard widget.
 */
export function useUpcoming(params: GetUpcomingParams = {}) {
    return useQuery({
        queryKey: dashboardKeys.upcoming(params),
        queryFn: () => getUpcoming(params),
        staleTime: 60 * 1000, // 1 minute
        refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
    })
}

/**
 * Get attention items for dashboard KPI card.
 */
export function useAttention(params: GetAttentionParams = {}) {
    return useQuery({
        queryKey: dashboardKeys.attention(params),
        queryFn: () => getAttention(params),
        staleTime: 60 * 1000, // 1 minute
        refetchInterval: 60 * 1000, // Refetch every minute
    })
}

// Re-export types
export type {
    UpcomingResponse,
    UpcomingTask,
    UpcomingMeeting,
    UpcomingItem,
    GetUpcomingParams,
    AttentionResponse,
    UnreachedLead,
    OverdueTaskItem,
    StuckSurrogate,
    GetAttentionParams,
}
