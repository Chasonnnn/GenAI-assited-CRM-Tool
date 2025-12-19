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
    getUserPreferences,
    updateUserPreference,
    type WorkflowCreate,
    type WorkflowUpdate,
    type Workflow,
    type WorkflowListItem,
    type WorkflowStats,
    type WorkflowOptions,
    type WorkflowExecution,
    type WorkflowTestResponse,
    type UserWorkflowPreference,
} from "@/lib/api/workflows"

// =============================================================================
// Query Keys
// =============================================================================

export const workflowKeys = {
    all: ["workflows"] as const,
    lists: () => [...workflowKeys.all, "list"] as const,
    list: (filters: { enabled_only?: boolean; trigger_type?: string }) =>
        [...workflowKeys.lists(), filters] as const,
    details: () => [...workflowKeys.all, "detail"] as const,
    detail: (id: string) => [...workflowKeys.details(), id] as const,
    stats: () => [...workflowKeys.all, "stats"] as const,
    options: () => [...workflowKeys.all, "options"] as const,
    executions: (workflowId: string) =>
        [...workflowKeys.all, "executions", workflowId] as const,
    preferences: () => [...workflowKeys.all, "preferences"] as const,
}

// =============================================================================
// List Hooks
// =============================================================================

export function useWorkflows(params?: {
    enabled_only?: boolean
    trigger_type?: string
}) {
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

export function useWorkflowOptions() {
    return useQuery({
        queryKey: workflowKeys.options(),
        queryFn: getWorkflowOptions,
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

export function useCreateWorkflow() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: WorkflowCreate) => createWorkflow(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
            queryClient.invalidateQueries({ queryKey: workflowKeys.stats() })
        },
    })
}

export function useUpdateWorkflow() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: WorkflowUpdate }) =>
            updateWorkflow(id, data),
        onSuccess: (updated) => {
            queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
            queryClient.setQueryData(workflowKeys.detail(updated.id), updated)
        },
    })
}

export function useDeleteWorkflow() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (id: string) => deleteWorkflow(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
            queryClient.invalidateQueries({ queryKey: workflowKeys.stats() })
        },
    })
}

export function useToggleWorkflow() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (id: string) => toggleWorkflow(id),
        onSuccess: (updated) => {
            queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
            queryClient.setQueryData(workflowKeys.detail(updated.id), updated)
            queryClient.invalidateQueries({ queryKey: workflowKeys.stats() })
        },
    })
}

export function useDuplicateWorkflow() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (id: string) => duplicateWorkflow(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
            queryClient.invalidateQueries({ queryKey: workflowKeys.stats() })
        },
    })
}

export function useTestWorkflow() {
    return useMutation({
        mutationFn: ({ id, entityId }: { id: string; entityId: string }) =>
            testWorkflow(id, entityId),
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
            queryClient.invalidateQueries({ queryKey: workflowKeys.preferences() })
        },
    })
}
