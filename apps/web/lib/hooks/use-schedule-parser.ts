/**
 * React Query hooks for schedule parsing
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
    parseSchedule,
    createBulkTasks,
    type ParseScheduleRequest,
    type BulkTaskCreateRequest
} from '@/lib/api/schedule-parser'
import { invalidateSurrogateCrmCaches, surrogateKeys } from './use-surrogates'
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
        onSuccess: (_result, variables) => {
            void queryClient.invalidateQueries({ queryKey: taskKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: surrogateKeys.stats() })
            if (variables.surrogate_id) {
                invalidateSurrogateCrmCaches(queryClient, variables.surrogate_id)
            }
        },
    })
}
