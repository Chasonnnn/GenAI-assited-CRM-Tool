/**
 * TypeScript types for Tasks module.
 * Matches backend enums from apps/api/app/db/enums/*
 */

// Task type enum matching backend EXACTLY
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

// Re-export types from API client
export type {
    TaskListItem,
    TaskRead,
    TaskListResponse,
    TaskListParams,
    TaskCreatePayload,
    TaskUpdatePayload,
} from '../api/tasks';
