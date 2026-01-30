/**
 * React Query hooks for Interviews module.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as interviewsApi from '../api/interviews';
import type {
    InterviewCreatePayload,
    InterviewUpdatePayload,
    InterviewNoteCreatePayload,
    InterviewNoteUpdatePayload,
} from '../api/interviews';

// ============================================================================
// Query Keys
// ============================================================================

export const interviewKeys = {
    all: ['interviews'] as const,
    lists: () => [...interviewKeys.all, 'list'] as const,
    forSurrogate: (surrogateId: string) => [...interviewKeys.lists(), surrogateId] as const,
    detail: (interviewId: string) => [...interviewKeys.all, 'detail', interviewId] as const,
    versions: (interviewId: string) => [...interviewKeys.detail(interviewId), 'versions'] as const,
    version: (interviewId: string, version: number) => [...interviewKeys.versions(interviewId), version] as const,
    diff: (interviewId: string, v1: number, v2: number) => [...interviewKeys.detail(interviewId), 'diff', v1, v2] as const,
    notes: (interviewId: string) => [...interviewKeys.detail(interviewId), 'notes'] as const,
    attachments: (interviewId: string) => [...interviewKeys.detail(interviewId), 'attachments'] as const,
    transcription: (interviewId: string, attachmentId: string) =>
        [...interviewKeys.attachments(interviewId), attachmentId, 'transcription'] as const,
};

// ============================================================================
// Interview Queries
// ============================================================================

/**
 * List interviews for a surrogate.
 */
export function useInterviews(surrogateId: string) {
    return useQuery({
        queryKey: interviewKeys.forSurrogate(surrogateId),
        queryFn: () => interviewsApi.listInterviews(surrogateId),
        enabled: !!surrogateId,
    });
}

/**
 * Get interview details.
 */
export function useInterview(interviewId: string) {
    return useQuery({
        queryKey: interviewKeys.detail(interviewId),
        queryFn: () => interviewsApi.getInterview(interviewId),
        enabled: !!interviewId,
    });
}

/**
 * List transcript versions.
 */
export function useInterviewVersions(interviewId: string) {
    return useQuery({
        queryKey: interviewKeys.versions(interviewId),
        queryFn: () => interviewsApi.listVersions(interviewId),
        enabled: !!interviewId,
    });
}

/**
 * Get specific version content.
 */
export function useInterviewVersion(interviewId: string, version: number) {
    return useQuery({
        queryKey: interviewKeys.version(interviewId, version),
        queryFn: () => interviewsApi.getVersion(interviewId, version),
        enabled: !!interviewId && version > 0,
    });
}

/**
 * Get diff between two versions.
 */
export function useInterviewVersionDiff(interviewId: string, v1: number, v2: number) {
    return useQuery({
        queryKey: interviewKeys.diff(interviewId, v1, v2),
        queryFn: () => interviewsApi.getVersionDiff(interviewId, v1, v2),
        enabled: !!interviewId && v1 > 0 && v2 > 0 && v1 !== v2,
    });
}

/**
 * List notes for an interview.
 */
export function useInterviewNotes(interviewId: string) {
    return useQuery({
        queryKey: interviewKeys.notes(interviewId),
        queryFn: () => interviewsApi.listNotes(interviewId),
        enabled: !!interviewId,
    });
}

/**
 * List attachments for an interview.
 */
export function useInterviewAttachments(interviewId: string) {
    return useQuery({
        queryKey: interviewKeys.attachments(interviewId),
        queryFn: () => interviewsApi.listAttachments(interviewId),
        enabled: !!interviewId,
        refetchInterval: (query) => {
            const data = query.state.data;
            const hasPending = data?.some((att) =>
                ["pending", "processing"].includes(att.transcription_status || "")
            );
            return hasPending ? 3000 : false;
        },
    });
}

/**
 * Get transcription status (with polling while processing).
 */
export function useTranscriptionStatus(interviewId: string, attachmentId: string) {
    return useQuery({
        queryKey: interviewKeys.transcription(interviewId, attachmentId),
        queryFn: () => interviewsApi.getTranscriptionStatus(interviewId, attachmentId),
        enabled: !!interviewId && !!attachmentId,
        refetchInterval: (query) => {
            const status = query.state.data?.status;
            return status === 'pending' || status === 'processing' ? 3000 : false;
        },
    });
}

// ============================================================================
// Interview Mutations
// ============================================================================

/**
 * Create a new interview.
 */
export function useCreateInterview() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ surrogateId, data }: { surrogateId: string; data: InterviewCreatePayload }) =>
            interviewsApi.createInterview(surrogateId, data),
        onSuccess: (interview) => {
            queryClient.invalidateQueries({ queryKey: interviewKeys.forSurrogate(interview.surrogate_id) });
        },
    });
}

/**
 * Update an interview.
 */
export function useUpdateInterview() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ interviewId, data }: { interviewId: string; data: InterviewUpdatePayload }) =>
            interviewsApi.updateInterview(interviewId, data),
        onSuccess: (interview) => {
            queryClient.invalidateQueries({ queryKey: interviewKeys.detail(interview.id) });
            queryClient.invalidateQueries({ queryKey: interviewKeys.forSurrogate(interview.surrogate_id) });
            queryClient.invalidateQueries({ queryKey: interviewKeys.versions(interview.id) });
            // Invalidate notes to get recalculated anchors
            queryClient.invalidateQueries({ queryKey: interviewKeys.notes(interview.id) });
        },
    });
}

/**
 * Delete an interview.
 */
export function useDeleteInterview() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ interviewId, surrogateId: _surrogateId }: { interviewId: string; surrogateId: string }) =>
            interviewsApi.deleteInterview(interviewId),
        onSuccess: (_, { interviewId, surrogateId }) => {
            queryClient.invalidateQueries({ queryKey: interviewKeys.forSurrogate(surrogateId) });
            queryClient.removeQueries({ queryKey: interviewKeys.detail(interviewId) });
        },
    });
}

/**
 * Restore transcript to a previous version.
 */
export function useRestoreInterviewVersion() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ interviewId, version }: { interviewId: string; version: number }) =>
            interviewsApi.restoreVersion(interviewId, version),
        onSuccess: (interview) => {
            queryClient.invalidateQueries({ queryKey: interviewKeys.detail(interview.id) });
            queryClient.invalidateQueries({ queryKey: interviewKeys.versions(interview.id) });
            queryClient.invalidateQueries({ queryKey: interviewKeys.notes(interview.id) });
        },
    });
}

// ============================================================================
// Note Mutations
// ============================================================================

/**
 * Create a note on an interview.
 */
export function useCreateInterviewNote() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ interviewId, data }: { interviewId: string; data: InterviewNoteCreatePayload }) =>
            interviewsApi.createNote(interviewId, data),
        onSuccess: (_, { interviewId }) => {
            queryClient.invalidateQueries({ queryKey: interviewKeys.notes(interviewId) });
            queryClient.invalidateQueries({ queryKey: interviewKeys.detail(interviewId) });
        },
    });
}

/**
 * Update a note.
 */
export function useUpdateInterviewNote() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ interviewId, noteId, data }: {
            interviewId: string;
            noteId: string;
            data: InterviewNoteUpdatePayload
        }) => interviewsApi.updateNote(interviewId, noteId, data),
        onSuccess: (_, { interviewId }) => {
            queryClient.invalidateQueries({ queryKey: interviewKeys.notes(interviewId) });
        },
    });
}

/**
 * Delete a note.
 */
export function useDeleteInterviewNote() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ interviewId, noteId }: { interviewId: string; noteId: string }) =>
            interviewsApi.deleteNote(interviewId, noteId),
        onSuccess: (_, { interviewId }) => {
            queryClient.invalidateQueries({ queryKey: interviewKeys.notes(interviewId) });
            queryClient.invalidateQueries({ queryKey: interviewKeys.detail(interviewId) });
        },
    });
}

/**
 * Resolve a note (mark as resolved).
 */
export function useResolveInterviewNote() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ interviewId, noteId }: { interviewId: string; noteId: string }) =>
            interviewsApi.resolveNote(interviewId, noteId),
        onSuccess: (_, { interviewId }) => {
            queryClient.invalidateQueries({ queryKey: interviewKeys.notes(interviewId) });
        },
    });
}

/**
 * Unresolve a note (re-open).
 */
export function useUnresolveInterviewNote() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ interviewId, noteId }: { interviewId: string; noteId: string }) =>
            interviewsApi.unresolveNote(interviewId, noteId),
        onSuccess: (_, { interviewId }) => {
            queryClient.invalidateQueries({ queryKey: interviewKeys.notes(interviewId) });
        },
    });
}

// ============================================================================
// Attachment Mutations
// ============================================================================

/**
 * Upload and link a new attachment.
 */
export function useUploadInterviewAttachment() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ interviewId, file }: { interviewId: string; file: File }) =>
            interviewsApi.uploadAttachment(interviewId, file),
        onSuccess: (_, { interviewId }) => {
            queryClient.invalidateQueries({ queryKey: interviewKeys.attachments(interviewId) });
            queryClient.invalidateQueries({ queryKey: interviewKeys.detail(interviewId) });
        },
    });
}

/**
 * Link an existing attachment.
 */
export function useLinkInterviewAttachment() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ interviewId, attachmentId }: { interviewId: string; attachmentId: string }) =>
            interviewsApi.linkAttachment(interviewId, attachmentId),
        onSuccess: (_, { interviewId }) => {
            queryClient.invalidateQueries({ queryKey: interviewKeys.attachments(interviewId) });
            queryClient.invalidateQueries({ queryKey: interviewKeys.detail(interviewId) });
        },
    });
}

/**
 * Unlink an attachment.
 */
export function useUnlinkInterviewAttachment() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ interviewId, attachmentId }: { interviewId: string; attachmentId: string }) =>
            interviewsApi.unlinkAttachment(interviewId, attachmentId),
        onSuccess: (_, { interviewId }) => {
            queryClient.invalidateQueries({ queryKey: interviewKeys.attachments(interviewId) });
            queryClient.invalidateQueries({ queryKey: interviewKeys.detail(interviewId) });
        },
    });
}

/**
 * Request AI transcription.
 */
export function useRequestTranscription() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ interviewId, attachmentId, options }: {
            interviewId: string;
            attachmentId: string;
            options?: { language?: string; prompt?: string }
        }) => interviewsApi.requestTranscription(interviewId, attachmentId, options),
        onSuccess: (_, { interviewId, attachmentId }) => {
            queryClient.invalidateQueries({
                queryKey: interviewKeys.transcription(interviewId, attachmentId)
            });
            queryClient.invalidateQueries({ queryKey: interviewKeys.attachments(interviewId) });
            queryClient.invalidateQueries({ queryKey: interviewKeys.detail(interviewId) });
        },
    });
}

// ============================================================================
// AI Summary Mutations
// ============================================================================

/**
 * Generate AI summary of a single interview.
 */
export function useSummarizeInterview() {
    return useMutation({
        mutationFn: (interviewId: string) => interviewsApi.summarizeInterview(interviewId),
    });
}

/**
 * Generate AI summary of all interviews for a surrogate.
 */
export function useSummarizeAllInterviews() {
    return useMutation({
        mutationFn: (surrogateId: string) => interviewsApi.summarizeAllInterviews(surrogateId),
    });
}

