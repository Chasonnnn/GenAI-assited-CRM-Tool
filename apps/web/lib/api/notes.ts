/**
 * Notes API client - typed functions for surrogate notes endpoints.
 */

import api from './index';

// Note response
export interface NoteRead {
    id: string;
    surrogate_id: string;
    author_id: string | null;
    author_name: string | null;
    body: string;
    created_at: string;
}

// Create note payload
export interface NoteCreatePayload {
    body: string;
}

/**
 * List notes for a surrogate.
 */
export function getNotes(surrogateId: string): Promise<NoteRead[]> {
    return api.get<NoteRead[]>(`/surrogates/${surrogateId}/notes`);
}

/**
 * Create a note for a surrogate.
 */
export function createNote(surrogateId: string, body: string): Promise<NoteRead> {
    return api.post<NoteRead>(`/surrogates/${surrogateId}/notes`, { body });
}

/**
 * Delete a note.
 */
export function deleteNote(noteId: string): Promise<void> {
    return api.delete(`/notes/${noteId}`);
}
