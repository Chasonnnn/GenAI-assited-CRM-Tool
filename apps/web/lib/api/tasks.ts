/**
 * Tasks API client - typed functions for task management endpoints.
 */

import api from './index';

// Task type enum - matches backend apps/api/app/db/enums.py
export type TaskType =
    | 'meeting'
    | 'follow_up'
    | 'contact'
    | 'review'
    | 'medication'
    | 'exam'
    | 'appointment'
    | 'workflow_approval'
    | 'other';

export type TaskStatus =
    | 'pending'
    | 'in_progress'
    | 'completed'
    | 'denied'
    | 'expired';

// Task list item for table display
export interface TaskListItem {
    id: string;
    title: string;
    description: string | null;
    task_type: TaskType;
    surrogate_id: string | null;
    surrogate_number: string | null;
    owner_type: 'user' | 'queue';
    owner_id: string;
    owner_name: string | null;
    created_by_user_id: string;
    created_by_name: string | null;
    due_date: string | null;
    due_time: string | null;
    duration_minutes: number | null;
    is_completed: boolean;
    status?: TaskStatus | null;
    // Workflow approval fields
    workflow_action_type?: string | null;
    workflow_action_preview?: string | null;
    due_at?: string | null;
    completed_at: string | null;
    completed_by_name: string | null;
    created_at: string;
}

// Full task detail
export interface TaskRead extends TaskListItem {
    completed_by_user_id: string | null;
    updated_at: string;
    workflow_execution_id?: string | null;
    workflow_action_preview?: string | null;
    workflow_denial_reason?: string | null;
    workflow_triggered_by_user_id?: string | null;
    workflow_triggered_by_name?: string | null;
    is_workflow_approval?: boolean;
}

// Paginated task list response
export interface TaskListResponse {
    items: TaskListItem[];
    total: number;
    page: number;
    per_page: number;
    pages: number;
}

// Query params for listing tasks
export interface TaskListParams {
    page?: number;
    per_page?: number;
    q?: string;
    owner_id?: string;
    surrogate_id?: string;
    intended_parent_id?: string;
    pipeline_id?: string;
    is_completed?: boolean;
    task_type?: TaskType;
    status?: TaskStatus | TaskStatus[];
    due_before?: string;
    due_after?: string;
    my_tasks?: boolean;
    exclude_approvals?: boolean;
}

// Create task payload
export interface TaskCreatePayload {
    title: string;
    description?: string;
    task_type?: TaskType;
    surrogate_id?: string;
    intended_parent_id?: string;
    owner_type?: 'user' | 'queue';
    owner_id?: string;
    due_date?: string;
    due_time?: string;
    duration_minutes?: number;
}

// Update task payload
export type TaskUpdatePayload = Partial<TaskCreatePayload>;

/**
 * List tasks with filters and pagination.
 */
export function getTasks(params: TaskListParams = {}): Promise<TaskListResponse> {
    const searchParams = new URLSearchParams();

    if (params.page) searchParams.set('page', String(params.page));
    if (params.per_page) searchParams.set('per_page', String(params.per_page));
    if (params.q) searchParams.set('q', params.q);
    if (params.owner_id) searchParams.set('owner_id', params.owner_id);
    if (params.surrogate_id) searchParams.set('surrogate_id', params.surrogate_id);
    if (params.intended_parent_id) searchParams.set('intended_parent_id', params.intended_parent_id);
    if (params.pipeline_id) searchParams.set('pipeline_id', params.pipeline_id);
    if (params.is_completed !== undefined) searchParams.set('is_completed', String(params.is_completed));
    if (params.task_type) searchParams.set('task_type', params.task_type);
    if (params.status) {
        const statusValue = Array.isArray(params.status) ? params.status.join(',') : params.status;
        searchParams.set('status', statusValue);
    }
    if (params.due_before) searchParams.set('due_before', params.due_before);
    if (params.due_after) searchParams.set('due_after', params.due_after);
    if (params.my_tasks) searchParams.set('my_tasks', 'true');
    if (params.exclude_approvals) searchParams.set('exclude_approvals', 'true');

    const query = searchParams.toString();
    return api.get<TaskListResponse>(`/tasks${query ? `?${query}` : ''}`);
}

/**
 * Get single task by ID.
 */
export function getTask(taskId: string): Promise<TaskRead> {
    return api.get<TaskRead>(`/tasks/${taskId}`);
}

/**
 * Create a new task.
 */
export function createTask(data: TaskCreatePayload): Promise<TaskRead> {
    return api.post<TaskRead>('/tasks', data);
}

/**
 * Update task fields.
 */
export function updateTask(taskId: string, data: TaskUpdatePayload): Promise<TaskRead> {
    return api.patch<TaskRead>(`/tasks/${taskId}`, data);
}

/**
 * Mark task as completed.
 */
export function completeTask(taskId: string): Promise<TaskRead> {
    return api.post<TaskRead>(`/tasks/${taskId}/complete`);
}

/**
 * Mark task as not completed.
 */
export function uncompleteTask(taskId: string): Promise<TaskRead> {
    return api.post<TaskRead>(`/tasks/${taskId}/uncomplete`);
}

/**
 * Delete a task.
 */
export function deleteTask(taskId: string): Promise<void> {
    return api.delete(`/tasks/${taskId}`);
}

// Bulk complete response type
export interface BulkCompleteResponse {
    completed: number;
    failed: { task_id: string; reason: string }[];
}

/**
 * Mark multiple tasks as completed.
 */
export function bulkCompleteTasks(taskIds: string[]): Promise<BulkCompleteResponse> {
    return api.post<BulkCompleteResponse>('/tasks/bulk-complete', { task_ids: taskIds });
}

/**
 * Resolve a workflow approval task.
 */
export function resolveWorkflowApproval(
    taskId: string,
    decision: 'approve' | 'deny',
    reason?: string
): Promise<TaskRead> {
    return api.post<TaskRead>(`/tasks/${taskId}/resolve`, {
        decision,
        reason,
    });
}
