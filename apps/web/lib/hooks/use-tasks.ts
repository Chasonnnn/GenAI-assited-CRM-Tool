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

/**
 * Fetch paginated tasks list.
 */
export function useTasks(params: TaskListParams = {}) {
    return useQuery({
        queryKey: taskKeys.list(params),
        queryFn: () => tasksApi.getTasks(params),
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
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
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
