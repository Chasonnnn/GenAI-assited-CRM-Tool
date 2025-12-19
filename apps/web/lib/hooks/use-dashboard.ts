/**
 * React Query hooks for dashboard widgets.
 */

import { useQuery } from '@tanstack/react-query'
import {
    getUpcoming,
    type GetUpcomingParams,
    type UpcomingResponse,
    type UpcomingTask,
    type UpcomingMeeting,
    type UpcomingItem,
} from '@/lib/api/dashboard'

// =============================================================================
// Query Keys
// =============================================================================

export const dashboardKeys = {
    all: ['dashboard'] as const,
    upcoming: (params?: GetUpcomingParams) => [...dashboardKeys.all, 'upcoming', params] as const,
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

// Re-export types
export type { UpcomingResponse, UpcomingTask, UpcomingMeeting, UpcomingItem, GetUpcomingParams }
