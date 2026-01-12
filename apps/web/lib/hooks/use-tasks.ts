/**
 * React Query hooks for Tasks module.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as tasksApi from '../api/tasks';
import type { TaskListParams } from '../api/tasks';
import { caseKeys } from './use-cases';

// Query keys
export const taskKeys = {
    all: ['tasks'] as const,
    lists: () => [...taskKeys.all, 'list'] as const,
    list: (params: TaskListParams) => [...taskKeys.lists(), params] as const,
    details: () => [...taskKeys.all, 'detail'] as const,
    detail: (id: string) => [...taskKeys.details(), id] as const,
};

function invalidateCaseActivity(queryClient: ReturnType<typeof useQueryClient>, caseId?: string | null) {
    if (!caseId) return;
    queryClient.invalidateQueries({ queryKey: [...caseKeys.detail(caseId), 'activity'] });
}

/**
 * Fetch paginated tasks list.
 */
export function useTasks(params: TaskListParams = {}, options?: { enabled?: boolean }) {
    // Default to hiding workflow approvals unless explicitly opted in.
    const effectiveParams: TaskListParams = { exclude_approvals: true, ...params };
    return useQuery({
        queryKey: taskKeys.list(effectiveParams),
        queryFn: () => tasksApi.getTasks(effectiveParams),
        enabled: options?.enabled ?? true,
    });
}

/**
 * Fetch single task by ID.
 */
export function useTask(taskId: string) {
    return useQuery({
        queryKey: taskKeys.detail(taskId),
        queryFn: () => tasksApi.getTask(taskId),
        enabled: !!taskId,
    });
}

/**
 * Create a new task.
 */
export function useCreateTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: tasksApi.createTask,
        onSuccess: (createdTask) => {
            queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            invalidateCaseActivity(queryClient, createdTask.case_id);
        },
    });
}

/**
 * Update task fields.
 */
export function useUpdateTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ taskId, data }: { taskId: string; data: tasksApi.TaskUpdatePayload }) =>
            tasksApi.updateTask(taskId, data),
        onSuccess: (updatedTask) => {
            queryClient.setQueryData(taskKeys.detail(updatedTask.id), updatedTask);
            queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            invalidateCaseActivity(queryClient, updatedTask.case_id);
        },
    });
}

/**
 * Complete a task.
 */
export function useCompleteTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: tasksApi.completeTask,
        onSuccess: (updatedTask) => {
            queryClient.setQueryData(taskKeys.detail(updatedTask.id), updatedTask);
            queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            // Also invalidate dashboard stats since pending_tasks count changes
            queryClient.invalidateQueries({ queryKey: caseKeys.stats() });
            invalidateCaseActivity(queryClient, updatedTask.case_id);
        },
    });
}

/**
 * Uncomplete a task.
 */
export function useUncompleteTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: tasksApi.uncompleteTask,
        onSuccess: (updatedTask) => {
            queryClient.setQueryData(taskKeys.detail(updatedTask.id), updatedTask);
            queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            // Also invalidate dashboard stats since pending_tasks count changes
            queryClient.invalidateQueries({ queryKey: caseKeys.stats() });
            invalidateCaseActivity(queryClient, updatedTask.case_id);
        },
    });
}

/**
 * Delete a task.
 */
export function useDeleteTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: tasksApi.deleteTask,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
        },
    });
}

/**
 * Bulk complete multiple tasks.
 * Invalidates all task list queries to ensure UI refreshes.
 */
export function useBulkCompleteTasks() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: tasksApi.bulkCompleteTasks,
        onSuccess: () => {
            // Invalidate all task list queries (covers both case_id and intended_parent_id)
            queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            // Also invalidate dashboard stats since pending_tasks count changes
            queryClient.invalidateQueries({ queryKey: caseKeys.stats() });
        },
    });
}

/**
 * Resolve a workflow approval task (approve or deny).
 */
export function useResolveWorkflowApproval() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            taskId,
            decision,
            reason,
        }: {
            taskId: string;
            decision: 'approve' | 'deny';
            reason?: string;
        }) => tasksApi.resolveWorkflowApproval(taskId, decision, reason),
        onSuccess: (updatedTask) => {
            queryClient.setQueryData(taskKeys.detail(updatedTask.id), updatedTask);
            queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            // Also invalidate dashboard stats
            queryClient.invalidateQueries({ queryKey: caseKeys.stats() });
            invalidateCaseActivity(queryClient, updatedTask.case_id);
        },
    });
}
