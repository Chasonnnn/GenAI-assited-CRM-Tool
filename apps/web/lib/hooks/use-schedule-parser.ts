/**
 * React Query hooks for schedule parsing
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
    parseSchedule,
    createBulkTasks,
    ParseScheduleRequest,
    BulkTaskCreateRequest
} from '@/lib/api/schedule-parser'
import { taskKeys } from './use-tasks'

// Hooks
export function useParseSchedule() {
    return useMutation({
        mutationFn: (data: ParseScheduleRequest) => parseSchedule(data),
    })
}

export function useCreateBulkTasks() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: BulkTaskCreateRequest) => createBulkTasks(data),
        onSuccess: () => {
            // Invalidate tasks list to show newly created tasks
            queryClient.invalidateQueries({ queryKey: taskKeys.lists() })
        },
    })
}
