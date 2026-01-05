/**
 * React Query hooks for Queue management (Salesforce-style ownership).
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { caseKeys } from './use-cases';

// =============================================================================
// Types
// =============================================================================

export interface Queue {
    id: string;
    organization_id: string;
    name: string;
    description: string | null;
    is_active: boolean;
    member_ids: string[];
}

export interface QueueMember {
    id: string;
    queue_id: string;
    user_id: string;
    user_name: string | null;
    user_email: string | null;
    created_at: string | null;
}

export interface QueueCreatePayload {
    name: string;
    description?: string;
}

export interface QueueUpdatePayload {
    name?: string;
    description?: string;
    is_active?: boolean;
}

// =============================================================================
// API Functions
// =============================================================================

async function getQueues(includeInactive = false): Promise<Queue[]> {
    return api.get<Queue[]>(`/queues?include_inactive=${includeInactive}`);
}

async function getQueue(queueId: string): Promise<Queue> {
    return api.get<Queue>(`/queues/${queueId}`);
}

async function createQueue(data: QueueCreatePayload): Promise<Queue> {
    return api.post<Queue>('/queues', data);
}

async function updateQueue(queueId: string, data: QueueUpdatePayload): Promise<Queue> {
    return api.patch<Queue>(`/queues/${queueId}`, data);
}

async function deleteQueue(queueId: string): Promise<void> {
    return api.delete(`/queues/${queueId}`);
}

async function claimCase(caseId: string): Promise<{ message: string; case_id: string }> {
    return api.post(`/queues/cases/${caseId}/claim`);
}

async function releaseCase(caseId: string, queueId: string): Promise<{ message: string; case_id: string }> {
    return api.post(`/queues/cases/${caseId}/release`, { queue_id: queueId });
}

async function assignCaseToQueue(caseId: string, queueId: string): Promise<{ message: string; case_id: string }> {
    return api.post(`/queues/cases/${caseId}/assign`, { queue_id: queueId });
}

// =============================================================================
// Query Keys
// =============================================================================

export const queueKeys = {
    all: ['queues'] as const,
    lists: () => [...queueKeys.all, 'list'] as const,
    list: (includeInactive: boolean) => [...queueKeys.lists(), { includeInactive }] as const,
    details: () => [...queueKeys.all, 'detail'] as const,
    detail: (id: string) => [...queueKeys.details(), id] as const,
};

// =============================================================================
// Hooks
// =============================================================================

/**
 * Fetch all queues for the organization.
 */
export function useQueues(includeInactive = false) {
    return useQuery({
        queryKey: queueKeys.list(includeInactive),
        queryFn: () => getQueues(includeInactive),
        staleTime: 60 * 1000, // 1 minute
    });
}

/**
 * Fetch a single queue by ID.
 */
export function useQueue(queueId: string) {
    return useQuery({
        queryKey: queueKeys.detail(queueId),
        queryFn: () => getQueue(queueId),
        enabled: !!queueId,
    });
}

/**
 * Create a new queue.
 */
export function useCreateQueue() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: createQueue,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queueKeys.lists() });
        },
    });
}

/**
 * Update an existing queue.
 */
export function useUpdateQueue() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ queueId, data }: { queueId: string; data: QueueUpdatePayload }) =>
            updateQueue(queueId, data),
        onSuccess: (updatedQueue) => {
            queryClient.setQueryData(queueKeys.detail(updatedQueue.id), updatedQueue);
            queryClient.invalidateQueries({ queryKey: queueKeys.lists() });
        },
    });
}

/**
 * Delete (soft-delete) a queue.
 */
export function useDeleteQueue() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: deleteQueue,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queueKeys.lists() });
        },
    });
}

/**
 * Claim a case from a queue.
 * Transfers ownership from queue to current user.
 */
export function useClaimCase() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: claimCase,
        onSuccess: (_, caseId) => {
            queryClient.invalidateQueries({ queryKey: caseKeys.detail(caseId) });
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
            queryClient.invalidateQueries({ queryKey: queueKeys.all });
        },
    });
}

/**
 * Release a case back to a queue.
 */
export function useReleaseCase() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ caseId, queueId }: { caseId: string; queueId: string }) =>
            releaseCase(caseId, queueId),
        onSuccess: (_, { caseId }) => {
            queryClient.invalidateQueries({ queryKey: caseKeys.detail(caseId) });
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
            queryClient.invalidateQueries({ queryKey: queueKeys.all });
        },
    });
}

/**
 * Assign a case to a queue (admin action).
 */
export function useAssignToQueue() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ caseId, queueId }: { caseId: string; queueId: string }) =>
            assignCaseToQueue(caseId, queueId),
        onSuccess: (_, { caseId }) => {
            queryClient.invalidateQueries({ queryKey: caseKeys.detail(caseId) });
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
            queryClient.invalidateQueries({ queryKey: queueKeys.all });
        },
    });
}

// =============================================================================
// Queue Members API
// =============================================================================

async function getQueueMembers(queueId: string): Promise<QueueMember[]> {
    return api.get<QueueMember[]>(`/queues/${queueId}/members`);
}

async function addQueueMember(queueId: string, userId: string): Promise<QueueMember> {
    return api.post<QueueMember>(`/queues/${queueId}/members`, { user_id: userId });
}

async function removeQueueMember(queueId: string, userId: string): Promise<void> {
    return api.delete(`/queues/${queueId}/members/${userId}`);
}

// =============================================================================
// Queue Members Hooks
// =============================================================================

/**
 * Fetch members of a queue.
 */
export function useQueueMembers(queueId: string | null) {
    return useQuery({
        queryKey: [...queueKeys.detail(queueId || ''), 'members'],
        queryFn: () => getQueueMembers(queueId!),
        enabled: !!queueId,
    });
}

/**
 * Add a member to a queue.
 */
export function useAddQueueMember() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ queueId, userId }: { queueId: string; userId: string }) =>
            addQueueMember(queueId, userId),
        onSuccess: (_, { queueId }) => {
            queryClient.invalidateQueries({ queryKey: [...queueKeys.detail(queueId), 'members'] });
            queryClient.invalidateQueries({ queryKey: queueKeys.lists() });
        },
    });
}

/**
 * Remove a member from a queue.
 */
export function useRemoveQueueMember() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ queueId, userId }: { queueId: string; userId: string }) =>
            removeQueueMember(queueId, userId),
        onSuccess: (_, { queueId }) => {
            queryClient.invalidateQueries({ queryKey: [...queueKeys.detail(queueId), 'members'] });
            queryClient.invalidateQueries({ queryKey: queueKeys.lists() });
        },
    });
}
