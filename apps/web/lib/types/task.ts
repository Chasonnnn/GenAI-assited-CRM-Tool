/**
 * TypeScript types for Tasks module.
 * Matches backend enums from apps/api/app/db/enums.py
 */

// Task type enum matching backend EXACTLY
export type TaskType = 'meeting' | 'follow_up' | 'contact' | 'review' | 'other';

// Re-export types from API client
export type {
    TaskListItem,
    TaskRead,
    TaskListResponse,
    TaskListParams,
    TaskCreatePayload,
    TaskUpdatePayload,
} from '../api/tasks';

// Task type display config - matches backend TaskType enum
export const TASK_TYPE_CONFIG: Record<TaskType, { label: string; icon: string }> = {
    meeting: { label: 'Meeting', icon: '📅' },
    follow_up: { label: 'Follow Up', icon: '📞' },
    contact: { label: 'Contact', icon: '👤' },
    review: { label: 'Review', icon: '📋' },
    other: { label: 'Other', icon: '📌' },
};
