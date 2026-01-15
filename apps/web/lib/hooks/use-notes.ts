/**
 * React Query hooks for Notes module.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as notesApi from '../api/notes';
import { surrogateKeys } from './use-surrogates';

// Query keys
export const noteKeys = {
    all: ['notes'] as const,
    lists: () => [...noteKeys.all, 'list'] as const,
    forSurrogate: (surrogateId: string) => [...noteKeys.lists(), surrogateId] as const,
};

/**
 * Fetch notes for a surrogate.
 */
export function useNotes(surrogateId: string) {
    return useQuery({
        queryKey: noteKeys.forSurrogate(surrogateId),
        queryFn: () => notesApi.getNotes(surrogateId),
        enabled: !!surrogateId,
    });
}

/**
 * Create a note for a surrogate.
 */
export function useCreateNote() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ surrogateId, body }: { surrogateId: string; body: string }) =>
            notesApi.createNote(surrogateId, body),
        onSuccess: (newNote) => {
            queryClient.invalidateQueries({ queryKey: noteKeys.forSurrogate(newNote.surrogate_id) });
            // Invalidate history/activity cache to show note_added immediately
            queryClient.invalidateQueries({
                queryKey: [...surrogateKeys.detail(newNote.surrogate_id), 'activity'],
                exact: false,
            });
        },
    });
}

/**
 * Delete a note.
 */
export function useDeleteNote() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ noteId, surrogateId: _surrogateId }: { noteId: string; surrogateId: string }) =>
            notesApi.deleteNote(noteId),
        onSuccess: (_, { surrogateId }) => {
            queryClient.invalidateQueries({ queryKey: noteKeys.forSurrogate(surrogateId) });
            // Invalidate history/activity cache to show note_deleted immediately
            queryClient.invalidateQueries({
                queryKey: [...surrogateKeys.detail(surrogateId), 'activity'],
                exact: false,
            });
        },
    });
}
