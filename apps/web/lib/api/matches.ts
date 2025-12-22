/**
 * API client for match management.
 */

import api from './index'

// =============================================================================
// Types
// =============================================================================

export interface MatchCreate {
    case_id: string
    intended_parent_id: string
    compatibility_score?: number
    notes?: string
}

export interface MatchRead {
    id: string
    case_id: string
    intended_parent_id: string
    status: string
    compatibility_score: number | null
    proposed_by_user_id: string | null
    proposed_at: string
    reviewed_by_user_id: string | null
    reviewed_at: string | null
    notes: string | null
    rejection_reason: string | null
    created_at: string
    updated_at: string
    case_number: string | null
    case_name: string | null
    ip_name: string | null
    // Case stage info for status sync
    case_stage_id: string | null
    case_stage_slug: string | null
    case_stage_label: string | null
}

export interface MatchListItem {
    id: string
    case_id: string
    case_number: string | null
    case_name: string | null
    intended_parent_id: string
    ip_name: string | null
    status: string
    compatibility_score: number | null
    proposed_at: string
    // Case stage info for status sync
    case_stage_id: string | null
    case_stage_slug: string | null
    case_stage_label: string | null
}

export interface MatchListResponse {
    items: MatchListItem[]
    total: number
    page: number
    per_page: number
}

export interface MatchStatsResponse {
    total: number
    by_status: Record<MatchStatus, number>
}

export interface MatchAcceptRequest {
    notes?: string
}

export interface MatchRejectRequest {
    notes?: string
    rejection_reason: string
}

export interface MatchUpdateNotesRequest {
    notes: string
}

export type MatchStatus = 'proposed' | 'reviewing' | 'accepted' | 'rejected' | 'cancelled'

// =============================================================================
// API Functions
// =============================================================================

export interface ListMatchesParams {
    status?: MatchStatus
    case_id?: string
    intended_parent_id?: string
    page?: number
    per_page?: number
}

/**
 * List matches with optional filters.
 */
export async function listMatches(params: ListMatchesParams = {}): Promise<MatchListResponse> {
    const searchParams = new URLSearchParams()
    if (params.status) searchParams.set('status', params.status)
    if (params.case_id) searchParams.set('case_id', params.case_id)
    if (params.intended_parent_id) searchParams.set('intended_parent_id', params.intended_parent_id)
    if (params.page) searchParams.set('page', params.page.toString())
    if (params.per_page) searchParams.set('per_page', params.per_page.toString())
    const query = searchParams.toString()
    return api.get<MatchListResponse>(`/matches/${query ? `?${query}` : ''}`)
}

/**
 * Get match counts by status.
 */
export async function getMatchStats(): Promise<MatchStatsResponse> {
    return api.get<MatchStatsResponse>('/matches/stats')
}

/**
 * Get match by ID.
 */
export async function getMatch(matchId: string): Promise<MatchRead> {
    return api.get<MatchRead>(`/matches/${matchId}`)
}

/**
 * Create a new match proposal.
 */
export async function createMatch(data: MatchCreate): Promise<MatchRead> {
    return api.post<MatchRead>('/matches/', data)
}

/**
 * Accept a match.
 */
export async function acceptMatch(matchId: string, data: MatchAcceptRequest = {}): Promise<MatchRead> {
    return api.put<MatchRead>(`/matches/${matchId}/accept`, data)
}

/**
 * Reject a match with reason.
 */
export async function rejectMatch(matchId: string, data: MatchRejectRequest): Promise<MatchRead> {
    return api.put<MatchRead>(`/matches/${matchId}/reject`, data)
}

/**
 * Cancel a proposed match.
 */
export async function cancelMatch(matchId: string): Promise<void> {
    await api.delete(`/matches/${matchId}`)
}

/**
 * Update match notes.
 */
export async function updateMatchNotes(matchId: string, data: MatchUpdateNotesRequest): Promise<MatchRead> {
    return api.patch<MatchRead>(`/matches/${matchId}/notes`, data)
}

// =============================================================================
// Match Events Types
// =============================================================================

export type MatchEventPersonType = 'surrogate' | 'ip'
export type MatchEventType = 'medication' | 'medical_exam' | 'legal' | 'delivery' | 'custom'

export interface MatchEventCreate {
    person_type: MatchEventPersonType
    event_type: MatchEventType
    title: string
    description?: string | null
    starts_at?: string | null
    ends_at?: string | null
    timezone?: string
    all_day?: boolean
    start_date?: string | null
    end_date?: string | null
}

export interface MatchEventUpdate extends Partial<MatchEventCreate> { }

export interface MatchEventRead {
    id: string
    match_id: string
    person_type: MatchEventPersonType
    event_type: MatchEventType
    title: string
    description: string | null
    starts_at: string | null
    ends_at: string | null
    timezone: string
    all_day: boolean
    start_date: string | null
    end_date: string | null
    created_by_user_id: string | null
    created_at: string
    updated_at: string
}

// =============================================================================
// Match Events API Functions
// =============================================================================

/**
 * List events for a match.
 */
export async function listMatchEvents(matchId: string): Promise<MatchEventRead[]> {
    return api.get<MatchEventRead[]>(`/matches/${matchId}/events`)
}

/**
 * Get a specific match event.
 */
export async function getMatchEvent(matchId: string, eventId: string): Promise<MatchEventRead> {
    return api.get<MatchEventRead>(`/matches/${matchId}/events/${eventId}`)
}

/**
 * Create a match event.
 */
export async function createMatchEvent(matchId: string, data: MatchEventCreate): Promise<MatchEventRead> {
    return api.post<MatchEventRead>(`/matches/${matchId}/events`, data)
}

/**
 * Update a match event.
 */
export async function updateMatchEvent(matchId: string, eventId: string, data: MatchEventUpdate): Promise<MatchEventRead> {
    return api.put<MatchEventRead>(`/matches/${matchId}/events/${eventId}`, data)
}

/**
 * Delete a match event.
 */
export async function deleteMatchEvent(matchId: string, eventId: string): Promise<void> {
    await api.delete(`/matches/${matchId}/events/${eventId}`)
}

// =============================================================================
// Color Utilities
// =============================================================================

export const EVENT_TYPE_COLORS: Record<MatchEventType, string> = {
    medication: '#f97316',
    medical_exam: '#3b82f6',
    legal: '#eab308',
    delivery: '#ef4444',
    custom: '#6b7280',
}

export const PERSON_TYPE_COLORS: Record<MatchEventPersonType, string> = {
    surrogate: '#a855f7',
    ip: '#22c55e',
}
