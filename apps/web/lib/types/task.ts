/**
 * TypeScript types for Tasks module.
 * Re-exports from API client for convenience.
 */

// Re-export types from API client
export type {
    TaskType,
    TaskListItem,
    TaskRead,
    TaskListResponse,
    TaskListParams,
    TaskCreatePayload,
    TaskUpdatePayload,
} from '../api/tasks';

// Task type display config
export const TASK_TYPE_CONFIG: Record<string, { label: string; icon: string }> = {
    follow_up: { label: 'Follow Up', icon: '📞' },
    call: { label: 'Call', icon: '☎️' },
    email: { label: 'Email', icon: '✉️' },
    meeting: { label: 'Meeting', icon: '📅' },
    document: { label: 'Document', icon: '📄' },
    other: { label: 'Other', icon: '📋' },
};
