/**
 * React Query hooks for automation workflows.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
    listWorkflows,
    getWorkflow,
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
    toggleWorkflow,
    duplicateWorkflow,
    testWorkflow,
    getWorkflowStats,
    getWorkflowOptions,
    listExecutions,
    retryWorkflowExecution,
    getUserPreferences,
    updateUserPreference,
    type WorkflowCreate,
    type WorkflowUpdate,
    type ListWorkflowsParams,
} from "@/lib/api/workflows"

// =============================================================================
// Query Keys
// =============================================================================

const workflowKeys = {
    all: ["workflows"] as const,
    lists: () => [...workflowKeys.all, "list"] as const,
    list: (filters: ListWorkflowsParams) =>
        [...workflowKeys.lists(), filters] as const,
    details: () => [...workflowKeys.all, "detail"] as const,
    detail: (id: string) => [...workflowKeys.details(), id] as const,
    stats: () => [...workflowKeys.all, "stats"] as const,
    options: (workflowScope?: string) => [...workflowKeys.all, "options", workflowScope] as const,
    executions: (workflowId: string) =>
        [...workflowKeys.all, "executions", workflowId] as const,
    preferences: () => [...workflowKeys.all, "preferences"] as const,
}

// =============================================================================
// List Hooks
// =============================================================================

export function useWorkflows(params?: ListWorkflowsParams) {
    return useQuery({
        queryKey: workflowKeys.list(params || {}),
        queryFn: () => listWorkflows(params),
    })
}

export function useWorkflow(id: string) {
    return useQuery({
        queryKey: workflowKeys.detail(id),
        queryFn: () => getWorkflow(id),
        enabled: !!id,
    })
}

export function useWorkflowStats() {
    return useQuery({
        queryKey: workflowKeys.stats(),
        queryFn: getWorkflowStats,
    })
}

export function useWorkflowOptions(workflowScope?: string) {
    return useQuery({
        queryKey: workflowKeys.options(workflowScope),
        queryFn: () => getWorkflowOptions(workflowScope as 'org' | 'personal' | undefined),
        staleTime: 5 * 60 * 1000, // 5 minutes - options don't change often
    })
}

export function useWorkflowExecutions(
    workflowId: string,
    params?: { limit?: number; offset?: number }
) {
    return useQuery({
        queryKey: [...workflowKeys.executions(workflowId), params],
        queryFn: () => listExecutions(workflowId, params),
        enabled: !!workflowId,
    })
}

export function useUserWorkflowPreferences() {
    return useQuery({
        queryKey: workflowKeys.preferences(),
        queryFn: getUserPreferences,
    })
}

// =============================================================================
// Mutation Hooks
// =============================================================================

export function useRetryWorkflowExecution() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (executionId: string) => retryWorkflowExecution(executionId),
        onSuccess: (execution) => {
            void queryClient.invalidateQueries({ queryKey: workflowKeys.executions(execution.workflow_id) })
            void queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: workflowKeys.stats() })
            // Org executions dashboard uses its own query keys.
            void queryClient.invalidateQueries({ queryKey: ["workflow-executions"] })
            void queryClient.invalidateQueries({ queryKey: ["workflow-execution-stats"] })
        },
    })
}

export function useCreateWorkflow() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: WorkflowCreate) => createWorkflow(data),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: workflowKeys.stats() })
        },
    })
}

export function useUpdateWorkflow() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: WorkflowUpdate }) =>
            updateWorkflow(id, data),
        onSuccess: (updated) => {
            void queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: workflowKeys.stats() })
            queryClient.setQueryData(workflowKeys.detail(updated.id), updated)
            void queryClient.invalidateQueries({ queryKey: workflowKeys.detail(updated.id) })
        },
    })
}

export function useDeleteWorkflow() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (id: string) => deleteWorkflow(id),
        onSuccess: (_result, id) => {
            void queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: workflowKeys.stats() })
            queryClient.removeQueries({ queryKey: workflowKeys.detail(id) })
        },
    })
}

export function useToggleWorkflow() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (id: string) => toggleWorkflow(id),
        onSuccess: (updated) => {
            void queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: workflowKeys.stats() })
            queryClient.setQueryData(workflowKeys.detail(updated.id), updated)
            void queryClient.invalidateQueries({ queryKey: workflowKeys.detail(updated.id) })
        },
    })
}

export function useDuplicateWorkflow() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (id: string) => duplicateWorkflow(id),
        onSuccess: (created) => {
            void queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: workflowKeys.stats() })
            queryClient.setQueryData(workflowKeys.detail(created.id), created)
            void queryClient.invalidateQueries({ queryKey: workflowKeys.detail(created.id) })
        },
    })
}

export function useTestWorkflow() {
    return useMutation({
        mutationFn: ({
            id,
            entityId,
            entityType,
        }: {
            id: string
            entityId: string
            entityType?: string
        }) => testWorkflow(id, entityId, entityType),
    })
}

export function useUpdateUserPreference() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            workflowId,
            isOptedOut,
        }: {
            workflowId: string
            isOptedOut: boolean
        }) => updateUserPreference(workflowId, isOptedOut),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: workflowKeys.preferences() })
        },
    })
}
