/**
 * React Query hooks for match management.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    listMatches,
    getMatch,
    createMatch,
    acceptMatch,
    declineMatch,
    cancelMatch,
    updateMatchNotes,
    getMatchStats,
    type ListMatchesParams,
    type MatchCreate,
    type MatchAcceptRequest,
    type MatchDeclineRequest,
    type MatchCancelRequest,
    type MatchUpdateNotesRequest,
    type MatchListItem,
    type MatchStatus,
} from '@/lib/api/matches'
import { matchDetailQueryOptions, matchKeys } from '@/lib/queries/matches'

export { matchDetailQueryOptions, matchKeys } from '@/lib/queries/matches'

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
        ...matchDetailQueryOptions(matchId, () => getMatch(matchId)),
        enabled: !!matchId,
    })
}

/**
 * Get match counts by status.
 */
export function useMatchStats(options: { enabled?: boolean } = {}) {
    return useQuery({
        queryKey: matchKeys.stats(),
        queryFn: getMatchStats,
        enabled: options.enabled ?? true,
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
            void queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: matchKeys.stats() })
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
            void queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: matchKeys.stats() })
            queryClient.setQueryData(matchKeys.detail(result.id), result)
            // Other proposals for the same surrogate gain the conflict flag and lose Accept.
            void queryClient.invalidateQueries({
                queryKey: matchKeys.details(),
                predicate: (query) => query.queryKey[2] !== result.id,
            })
        },
    })
}

/**
 * Decline a match.
 */
export function useDeclineMatch() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ matchId, data }: { matchId: string; data: MatchDeclineRequest }) =>
            declineMatch(matchId, data),
        onSuccess: (result) => {
            void queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: matchKeys.stats() })
            queryClient.setQueryData(matchKeys.detail(result.id), result)
        },
    })
}

/**
 * Request cancellation of an accepted match.
 */
export function useCancelMatch() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ matchId, data }: { matchId: string; data: MatchCancelRequest }) =>
            cancelMatch(matchId, data),
        onSuccess: (result) => {
            void queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: matchKeys.stats() })
            queryClient.setQueryData(matchKeys.detail(result.id), result)
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
export type { MatchListItem, MatchStatus, ListMatchesParams }

// =============================================================================
// Match Events Hooks
// =============================================================================

import {
    listMatchEvents,
    createMatchEvent,
    updateMatchEvent,
    deleteMatchEvent,
    type MatchEventCreate,
    type MatchEventUpdate,
} from '@/lib/api/matches'

const matchEventKeys = {
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
            void queryClient.invalidateQueries({ queryKey: matchEventKeys.list(matchId) })
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
            void queryClient.invalidateQueries({ queryKey: matchEventKeys.list(matchId) })
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
            void queryClient.invalidateQueries({ queryKey: matchEventKeys.list(matchId) })
        },
    })
}

import { getMatchWork, createMatchNote, uploadMatchFile, type MatchWorkSource } from '@/lib/api/matches'

export const matchWorkKeys = {
    all: (matchId: string) => [...matchKeys.detail(matchId), 'work'] as const,
    list: (matchId: string, page = 1) => [...matchWorkKeys.all(matchId), page] as const,
}

export function useMatchWork(matchId: string, page = 1) {
    return useQuery({
        queryKey: matchWorkKeys.list(matchId, page),
        queryFn: () => getMatchWork(matchId, page),
        enabled: !!matchId,
    })
}

export function useCreateMatchNote(matchId: string) {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (data: { content: string; source: MatchWorkSource }) => createMatchNote(matchId, data),
        onSuccess: () => { void queryClient.invalidateQueries({ queryKey: matchWorkKeys.all(matchId) }) },
    })
}

export function useUploadMatchFile(matchId: string) {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ file, source }: { file: File; source: MatchWorkSource }) => uploadMatchFile(matchId, file, source),
        onSuccess: () => { void queryClient.invalidateQueries({ queryKey: matchWorkKeys.all(matchId) }) },
    })
}

import { cancelRequest as cancelStatusChangeRequest } from '@/lib/api/status-change-requests'
export function useWithdrawMatchCancellation() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ requestId }: { matchId: string; requestId: string }) => cancelStatusChangeRequest(requestId),
        onSuccess: (_result, { matchId }) => {
            void queryClient.invalidateQueries({ queryKey: matchKeys.detail(matchId) })
            void queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: matchKeys.stats() })
            void queryClient.invalidateQueries({ queryKey: ['status-change-requests'] })
        },
    })
}
