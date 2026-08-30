/**
 * React Query hooks for Tasks module.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as tasksApi from '../api/tasks';
import type { TaskListParams } from '../api/tasks';
import { surrogateKeys } from './use-surrogates';
import { entityActivityKeys } from './use-entity-activity';

// Query keys
export const taskKeys = {
    all: ['tasks'] as const,
    lists: () => [...taskKeys.all, 'list'] as const,
    list: (params: TaskListParams) => [...taskKeys.lists(), params] as const,
    details: () => [...taskKeys.all, 'detail'] as const,
    detail: (id: string) => [...taskKeys.details(), id] as const,
};

function invalidateSurrogateActivity(queryClient: ReturnType<typeof useQueryClient>, surrogateId?: string | null) {
    if (!surrogateId) return;
    void queryClient.invalidateQueries({ queryKey: surrogateKeys.activity(surrogateId) });
}

function invalidateTaskActivity(
    queryClient: ReturnType<typeof useQueryClient>,
    task: { surrogate_id?: string | null; intended_parent_id?: string | null; donor_id?: string | null },
) {
    invalidateSurrogateActivity(queryClient, task.surrogate_id)
    if (task.intended_parent_id) {
        void queryClient.invalidateQueries({
            queryKey: entityActivityKeys.entity('intended_parent', task.intended_parent_id),
        })
    }
    if (task.donor_id) {
        void queryClient.invalidateQueries({
            queryKey: entityActivityKeys.entity('donor', task.donor_id),
        })
    }
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
            void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            invalidateTaskActivity(queryClient, createdTask);
        },
    });
}

/**
 * Create a bounded batch of tasks through the standard task API and refresh caches once.
 */
export function useCreateTaskBatch() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (tasks: tasksApi.TaskCreatePayload[]) =>
            Promise.all(tasks.map((task) => tasksApi.createTask(task))),
        onSuccess: (createdTasks) => {
            void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            const surrogateIds = new Set<string>();
            const intendedParentIds = new Set<string>();
            const donorIds = new Set<string>();
            for (const task of createdTasks) {
                if (task.surrogate_id) surrogateIds.add(task.surrogate_id);
                if (task.intended_parent_id) intendedParentIds.add(task.intended_parent_id);
                if (task.donor_id) donorIds.add(task.donor_id);
            }
            for (const surrogateId of surrogateIds) {
                invalidateSurrogateActivity(queryClient, surrogateId);
            }
            for (const intendedParentId of intendedParentIds) {
                void queryClient.invalidateQueries({
                    queryKey: entityActivityKeys.entity('intended_parent', intendedParentId),
                });
            }
            for (const donorId of donorIds) {
                void queryClient.invalidateQueries({
                    queryKey: entityActivityKeys.entity('donor', donorId),
                });
            }
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
            void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            invalidateTaskActivity(queryClient, updatedTask);
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
            void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            // Also invalidate dashboard stats since pending_tasks count changes
            void queryClient.invalidateQueries({ queryKey: surrogateKeys.stats() });
            invalidateTaskActivity(queryClient, updatedTask);
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
            void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            // Also invalidate dashboard stats since pending_tasks count changes
            void queryClient.invalidateQueries({ queryKey: surrogateKeys.stats() });
            invalidateTaskActivity(queryClient, updatedTask);
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
            void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            void queryClient.invalidateQueries({ queryKey: entityActivityKeys.all });
            void queryClient.invalidateQueries({ queryKey: surrogateKeys.all });
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
            // Invalidate every task list, including related-record filtered lists.
            void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            // Also invalidate dashboard stats since pending_tasks count changes
            void queryClient.invalidateQueries({ queryKey: surrogateKeys.stats() });
            void queryClient.invalidateQueries({ queryKey: entityActivityKeys.all });
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
            void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
            // Also invalidate dashboard stats
            void queryClient.invalidateQueries({ queryKey: surrogateKeys.stats() });
            invalidateTaskActivity(queryClient, updatedTask);
        },
    });
}
