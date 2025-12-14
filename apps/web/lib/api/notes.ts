/**
 * Notes API client - typed functions for case notes endpoints.
 */

import api from './index';

// Note response
export interface NoteRead {
    id: string;
    case_id: string;
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
 * List notes for a case.
 */
export function getNotes(caseId: string): Promise<NoteRead[]> {
    return api.get<NoteRead[]>(`/cases/${caseId}/notes`);
}

/**
 * Create a note for a case.
 */
export function createNote(caseId: string, body: string): Promise<NoteRead> {
    return api.post<NoteRead>(`/cases/${caseId}/notes`, { body });
}

/**
 * Delete a note.
 */
export function deleteNote(noteId: string): Promise<void> {
    return api.delete(`/notes/${noteId}`);
}
