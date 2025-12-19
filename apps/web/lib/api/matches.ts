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
}

export interface MatchListResponse {
    items: MatchListItem[]
    total: number
    page: number
    per_page: number
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
