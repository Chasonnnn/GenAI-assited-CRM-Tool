/**
 * Tasks API client - typed functions for task management endpoints.
 */

import api from './index';

// Task type enum - matches backend apps/api/app/db/enums.py
export type TaskType = 'meeting' | 'follow_up' | 'contact' | 'review' | 'other';

// Task list item for table display
export interface TaskListItem {
    id: string;
    title: string;
    description: string | null;
    task_type: TaskType;
    case_id: string | null;
    case_number: string | null;
    assigned_to_user_id: string | null;
    assigned_to_name: string | null;
    created_by_user_id: string;
    created_by_name: string | null;
    due_date: string | null;
    due_time: string | null;
    is_completed: boolean;
    completed_at: string | null;
    completed_by_name: string | null;
    created_at: string;
}

// Full task detail
export interface TaskRead extends TaskListItem {
    completed_by_user_id: string | null;
    updated_at: string;
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
    assigned_to?: string;
    case_id?: string;
    is_completed?: boolean;
    task_type?: TaskType;
    my_tasks?: boolean;
}

// Create task payload
export interface TaskCreatePayload {
    title: string;
    description?: string;
    task_type?: TaskType;
    case_id?: string;
    assigned_to_user_id?: string;
    due_date?: string;
    due_time?: string;
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
    if (params.assigned_to) searchParams.set('assigned_to', params.assigned_to);
    if (params.case_id) searchParams.set('case_id', params.case_id);
    if (params.is_completed !== undefined) searchParams.set('is_completed', String(params.is_completed));
    if (params.task_type) searchParams.set('task_type', params.task_type);
    if (params.my_tasks) searchParams.set('my_tasks', 'true');

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
