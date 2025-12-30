/**
 * React Query hooks for Notes module.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as notesApi from '../api/notes';

// Query keys
export const noteKeys = {
    all: ['notes'] as const,
    lists: () => [...noteKeys.all, 'list'] as const,
    forCase: (caseId: string) => [...noteKeys.lists(), caseId] as const,
};

/**
 * Fetch notes for a case.
 */
export function useNotes(caseId: string) {
    return useQuery({
        queryKey: noteKeys.forCase(caseId),
        queryFn: () => notesApi.getNotes(caseId),
        enabled: !!caseId,
    });
}

/**
 * Create a note for a case.
 */
export function useCreateNote() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ caseId, body }: { caseId: string; body: string }) =>
            notesApi.createNote(caseId, body),
        onSuccess: (newNote) => {
            queryClient.invalidateQueries({ queryKey: noteKeys.forCase(newNote.case_id) });
        },
    });
}

/**
 * Delete a note.
 */
export function useDeleteNote() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ noteId, caseId: _caseId }: { noteId: string; caseId: string }) =>
            notesApi.deleteNote(noteId),
        onSuccess: (_, { caseId }) => {
            queryClient.invalidateQueries({ queryKey: noteKeys.forCase(caseId) });
        },
    });
}
