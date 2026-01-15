/**
 * Interviews API client - typed functions for interview endpoints.
 */

import api from './index';
import type { JsonObject } from '../types/json';

// ============================================================================
// Types
// ============================================================================

// Interview types
export type InterviewType = 'phone' | 'video' | 'in_person';
export type InterviewStatus = 'draft' | 'completed';
export type TranscriptionStatus = 'not_started' | 'pending' | 'processing' | 'completed' | 'failed';

// Interview list item
export interface InterviewListItem {
    id: string;
    interview_type: InterviewType;
    conducted_at: string;
    conducted_by_user_id: string;
    conducted_by_name: string;
    duration_minutes: number | null;
    status: InterviewStatus;
    has_transcript: boolean;
    transcript_version: number;
    notes_count: number;
    attachments_count: number;
    created_at: string;
}

// TipTap JSON document type
export interface TipTapDoc {
    type: 'doc';
    content?: TipTapNode[];
}

export interface TipTapNode {
    type: string;
    attrs?: JsonObject;
    content?: TipTapNode[];
    text?: string;
    marks?: TipTapMark[];
}

export interface TipTapMark {
    type: string;
    attrs?: JsonObject;
}

// Full interview
export interface InterviewRead {
    id: string;
    surrogate_id: string;
    interview_type: InterviewType;
    conducted_at: string;
    conducted_by_user_id: string;
    conducted_by_name: string;
    duration_minutes: number | null;
    transcript_json: TipTapDoc | null;  // TipTap JSON (canonical)
    transcript_version: number;
    transcript_size_bytes: number;
    is_transcript_offloaded: boolean;
    status: InterviewStatus;
    notes_count: number;
    attachments_count: number;
    versions_count: number;
    expires_at: string | null;
    created_at: string;
    updated_at: string;
}

// Create/update payloads
export interface InterviewCreatePayload {
    interview_type: InterviewType;
    conducted_at: string;
    duration_minutes?: number | null;
    transcript_json?: TipTapDoc | null;   // TipTap JSON (preferred)
    status?: InterviewStatus;
}

export interface InterviewUpdatePayload {
    interview_type?: InterviewType;
    conducted_at?: string;
    duration_minutes?: number | null;
    transcript_json?: TipTapDoc | null;   // TipTap JSON (preferred)
    status?: InterviewStatus;
    expected_version?: number;
}

// Version types
export interface InterviewVersionListItem {
    version: number;
    author_user_id: string;
    author_name: string;
    source: string;
    content_size_bytes: number;
    created_at: string;
}

export interface InterviewVersionRead {
    version: number;
    content_html: string | null;
    content_text: string | null;
    author_user_id: string;
    author_name: string;
    source: string;
    created_at: string;
}

export interface InterviewVersionDiff {
    version_from: number;
    version_to: number;
    diff_html: string;
    additions: number;
    deletions: number;
}

// Note types
export interface InterviewNoteRead {
    id: string;
    content: string;
    transcript_version: number;
    comment_id: string | null;          // TipTap comment mark ID (stable anchor)
    anchor_text: string | null;          // Anchor text for display
    // Thread support
    parent_id: string | null;
    replies: InterviewNoteRead[];        // Nested replies
    // Resolve support
    resolved_at: string | null;
    resolved_by_user_id: string | null;
    resolved_by_name: string | null;
    // Author
    author_user_id: string;
    author_name: string;
    is_own: boolean;
    created_at: string;
    updated_at: string;
}

export interface InterviewNoteCreatePayload {
    content: string;
    transcript_version?: number;
    comment_id?: string;                 // TipTap comment mark ID (preferred)
    anchor_text?: string;                // Anchor text for display
    parent_id?: string;                  // For replies
}

export interface InterviewNoteUpdatePayload {
    content: string;
}

// Attachment types
export interface InterviewAttachmentRead {
    id: string;
    attachment_id: string;
    filename: string;
    content_type: string;
    file_size: number;
    is_audio_video: boolean;
    transcription_status: TranscriptionStatus | null;
    transcription_error: string | null;
    uploaded_by_name: string;
    created_at: string;
}

export interface TranscriptionStatusRead {
    status: TranscriptionStatus;
    progress: number | null;
    result: string | null;
    error: string | null;
}

// ============================================================================
// Interview CRUD
// ============================================================================

/**
 * List interviews for a surrogate.
 */
export function listInterviews(surrogateId: string): Promise<InterviewListItem[]> {
    return api.get<InterviewListItem[]>(`/surrogates/${surrogateId}/interviews`);
}

/**
 * Get interview details.
 */
export function getInterview(interviewId: string): Promise<InterviewRead> {
    return api.get<InterviewRead>(`/interviews/${interviewId}`);
}

/**
 * Create a new interview.
 */
export function createInterview(surrogateId: string, data: InterviewCreatePayload): Promise<InterviewRead> {
    return api.post<InterviewRead>(`/surrogates/${surrogateId}/interviews`, data);
}

/**
 * Update an interview.
 */
export function updateInterview(interviewId: string, data: InterviewUpdatePayload): Promise<InterviewRead> {
    return api.patch<InterviewRead>(`/interviews/${interviewId}`, data);
}

/**
 * Delete an interview.
 */
export function deleteInterview(interviewId: string): Promise<void> {
    return api.delete(`/interviews/${interviewId}`);
}

// ============================================================================
// Version Management
// ============================================================================

/**
 * List transcript versions.
 */
export function listVersions(interviewId: string): Promise<InterviewVersionListItem[]> {
    return api.get<InterviewVersionListItem[]>(`/interviews/${interviewId}/versions`);
}

/**
 * Get specific version content.
 */
export function getVersion(interviewId: string, version: number): Promise<InterviewVersionRead> {
    return api.get<InterviewVersionRead>(`/interviews/${interviewId}/versions/${version}`);
}

/**
 * Get diff between two versions.
 */
export function getVersionDiff(interviewId: string, v1: number, v2: number): Promise<InterviewVersionDiff> {
    return api.get<InterviewVersionDiff>(`/interviews/${interviewId}/versions/diff?v1=${v1}&v2=${v2}`);
}

/**
 * Restore transcript to a previous version.
 */
export function restoreVersion(interviewId: string, version: number): Promise<InterviewRead> {
    return api.post<InterviewRead>(`/interviews/${interviewId}/versions/${version}/restore`);
}

// ============================================================================
// Notes
// ============================================================================

/**
 * List notes for an interview.
 */
export function listNotes(interviewId: string): Promise<InterviewNoteRead[]> {
    return api.get<InterviewNoteRead[]>(`/interviews/${interviewId}/notes`);
}

/**
 * Create a note on an interview.
 */
export function createNote(interviewId: string, data: InterviewNoteCreatePayload): Promise<InterviewNoteRead> {
    return api.post<InterviewNoteRead>(`/interviews/${interviewId}/notes`, data);
}

/**
 * Update a note.
 */
export function updateNote(interviewId: string, noteId: string, data: InterviewNoteUpdatePayload): Promise<InterviewNoteRead> {
    return api.patch<InterviewNoteRead>(`/interviews/${interviewId}/notes/${noteId}`, data);
}

/**
 * Delete a note.
 */
export function deleteNote(interviewId: string, noteId: string): Promise<void> {
    return api.delete(`/interviews/${interviewId}/notes/${noteId}`);
}

/**
 * Resolve a note (mark as resolved).
 */
export function resolveNote(interviewId: string, noteId: string): Promise<InterviewNoteRead> {
    return api.post<InterviewNoteRead>(`/interviews/${interviewId}/notes/${noteId}/resolve`);
}

/**
 * Unresolve a note (re-open).
 */
export function unresolveNote(interviewId: string, noteId: string): Promise<InterviewNoteRead> {
    return api.post<InterviewNoteRead>(`/interviews/${interviewId}/notes/${noteId}/unresolve`);
}

// ============================================================================
// Attachments
// ============================================================================

/**
 * List attachments linked to an interview.
 */
export function listAttachments(interviewId: string): Promise<InterviewAttachmentRead[]> {
    return api.get<InterviewAttachmentRead[]>(`/interviews/${interviewId}/attachments`);
}

/**
 * Upload and link a new attachment.
 */
export async function uploadAttachment(interviewId: string, file: File): Promise<InterviewAttachmentRead> {
    const formData = new FormData();
    formData.append('file', file);
    return api.upload<InterviewAttachmentRead>(`/interviews/${interviewId}/attachments`, formData);
}

/**
 * Link an existing attachment to an interview.
 */
export function linkAttachment(interviewId: string, attachmentId: string): Promise<InterviewAttachmentRead> {
    return api.post<InterviewAttachmentRead>(`/interviews/${interviewId}/attachments/${attachmentId}/link`);
}

/**
 * Unlink an attachment from an interview.
 */
export function unlinkAttachment(interviewId: string, attachmentId: string): Promise<void> {
    return api.delete(`/interviews/${interviewId}/attachments/${attachmentId}`);
}

// ============================================================================
// Transcription
// ============================================================================

/**
 * Request AI transcription for an audio/video attachment.
 */
export function requestTranscription(
    interviewId: string,
    attachmentId: string,
    options?: { language?: string; prompt?: string }
): Promise<TranscriptionStatusRead> {
    return api.post<TranscriptionStatusRead>(
        `/interviews/${interviewId}/attachments/${attachmentId}/transcribe`,
        options || {}
    );
}

/**
 * Get transcription status.
 */
export function getTranscriptionStatus(interviewId: string, attachmentId: string): Promise<TranscriptionStatusRead> {
    return api.get<TranscriptionStatusRead>(`/interviews/${interviewId}/attachments/${attachmentId}/transcription`);
}

// ============================================================================
// AI Summary
// ============================================================================

// Interview summary response
export interface InterviewSummaryResponse {
    interview_id: string;
    summary: string;
    key_points: string[];
    concerns: string[];
    sentiment: 'positive' | 'neutral' | 'mixed' | 'concerning';
    follow_up_items: string[];
}

// All interviews summary response
export interface AllInterviewsSummaryResponse {
    surrogate_id: string;
    interview_count: number;
    overall_summary: string;
    timeline: Array<{ date: string; type: string; key_point: string }>;
    recurring_themes: string[];
    candidate_strengths: string[];
    areas_of_concern: string[];
    recommended_actions: string[];
}

/**
 * Generate AI summary of a single interview.
 */
export function summarizeInterview(interviewId: string): Promise<InterviewSummaryResponse> {
    return api.post<InterviewSummaryResponse>(`/interviews/${interviewId}/ai/summarize`);
}

/**
 * Generate AI summary of all interviews for a surrogate.
 */
export function summarizeAllInterviews(surrogateId: string): Promise<AllInterviewsSummaryResponse> {
    return api.post<AllInterviewsSummaryResponse>(`/surrogates/${surrogateId}/interviews/ai/summarize-all`);
}
