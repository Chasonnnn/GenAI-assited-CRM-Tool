/**
 * React Query hooks for match management.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    listMatches,
    getMatch,
    createMatch,
    acceptMatch,
    rejectMatch,
    cancelMatch,
    updateMatchNotes,
    type ListMatchesParams,
    type MatchCreate,
    type MatchAcceptRequest,
    type MatchRejectRequest,
    type MatchUpdateNotesRequest,
    type MatchListResponse,
    type MatchRead,
    type MatchListItem,
    type MatchStatus,
} from '@/lib/api/matches'

// =============================================================================
// Query Keys
// =============================================================================

export const matchKeys = {
    all: ['matches'] as const,
    lists: () => [...matchKeys.all, 'list'] as const,
    list: (params: ListMatchesParams) => [...matchKeys.lists(), params] as const,
    details: () => [...matchKeys.all, 'detail'] as const,
    detail: (id: string) => [...matchKeys.details(), id] as const,
}

// =============================================================================
// Hooks
// =============================================================================

/**
 * List matches with optional filters.
 */
export function useMatches(params: ListMatchesParams = {}) {
    return useQuery({
        queryKey: matchKeys.list(params),
        queryFn: () => listMatches(params),
    })
}

/**
 * Get match by ID.
 */
export function useMatch(matchId: string) {
    return useQuery({
        queryKey: matchKeys.detail(matchId),
        queryFn: () => getMatch(matchId),
        enabled: !!matchId,
    })
}

/**
 * Create a new match proposal.
 */
export function useCreateMatch() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: MatchCreate) => createMatch(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
        },
    })
}

/**
 * Accept a match.
 */
export function useAcceptMatch() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ matchId, data }: { matchId: string; data?: MatchAcceptRequest }) =>
            acceptMatch(matchId, data),
        onSuccess: (result) => {
            queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
            queryClient.setQueryData(matchKeys.detail(result.id), result)
        },
    })
}

/**
 * Reject a match.
 */
export function useRejectMatch() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ matchId, data }: { matchId: string; data: MatchRejectRequest }) =>
            rejectMatch(matchId, data),
        onSuccess: (result) => {
            queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
            queryClient.setQueryData(matchKeys.detail(result.id), result)
        },
    })
}

/**
 * Cancel a proposed match.
 */
export function useCancelMatch() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (matchId: string) => cancelMatch(matchId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
        },
    })
}

/**
 * Update match notes.
 */
export function useUpdateMatchNotes() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ matchId, data }: { matchId: string; data: MatchUpdateNotesRequest }) =>
            updateMatchNotes(matchId, data),
        onSuccess: (result) => {
            queryClient.setQueryData(matchKeys.detail(result.id), result)
        },
    })
}

// Re-export types
export type { MatchListResponse, MatchRead, MatchListItem, MatchStatus, ListMatchesParams }

// =============================================================================
// Match Events Hooks
// =============================================================================

import {
    listMatchEvents,
    getMatchEvent,
    createMatchEvent,
    updateMatchEvent,
    deleteMatchEvent,
    type MatchEventCreate,
    type MatchEventUpdate,
    type MatchEventRead,
    type MatchEventType,
    type MatchEventPersonType,
    EVENT_TYPE_COLORS,
    PERSON_TYPE_COLORS,
} from '@/lib/api/matches'

export const matchEventKeys = {
    all: (matchId: string) => ['matches', matchId, 'events'] as const,
    list: (matchId: string) => [...matchEventKeys.all(matchId), 'list'] as const,
    detail: (matchId: string, eventId: string) => [...matchEventKeys.all(matchId), eventId] as const,
}

/**
 * List events for a match.
 */
export function useMatchEvents(matchId: string) {
    return useQuery({
        queryKey: matchEventKeys.list(matchId),
        queryFn: () => listMatchEvents(matchId),
        enabled: !!matchId,
    })
}

/**
 * Create a match event.
 */
export function useCreateMatchEvent(matchId: string) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: MatchEventCreate) => createMatchEvent(matchId, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: matchEventKeys.list(matchId) })
        },
    })
}

/**
 * Update a match event.
 */
export function useUpdateMatchEvent(matchId: string) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ eventId, data }: { eventId: string; data: MatchEventUpdate }) =>
            updateMatchEvent(matchId, eventId, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: matchEventKeys.list(matchId) })
        },
    })
}

/**
 * Delete a match event.
 */
export function useDeleteMatchEvent(matchId: string) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (eventId: string) => deleteMatchEvent(matchId, eventId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: matchEventKeys.list(matchId) })
        },
    })
}

// Re-export event types and colors
export type { MatchEventCreate, MatchEventUpdate, MatchEventRead, MatchEventType, MatchEventPersonType }
export { EVENT_TYPE_COLORS, PERSON_TYPE_COLORS }
