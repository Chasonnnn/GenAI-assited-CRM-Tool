/**
 * React Query hooks for ticketing.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as ticketsApi from '../api/tickets'
import type { TicketListParams } from '../api/tickets'

export const ticketKeys = {
    all: ['tickets'] as const,
    lists: () => [...ticketKeys.all, 'list'] as const,
    list: (params: TicketListParams) => [...ticketKeys.lists(), params] as const,
    details: () => [...ticketKeys.all, 'detail'] as const,
    detail: (ticketId: string) => [...ticketKeys.details(), ticketId] as const,
    identities: () => [...ticketKeys.all, 'send-identities'] as const,
}

export function useTickets(params: TicketListParams = {}, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: ticketKeys.list(params),
        queryFn: () => ticketsApi.getTickets(params),
        enabled: options?.enabled ?? true,
    })
}

export function useTicket(ticketId: string) {
    return useQuery({
        queryKey: ticketKeys.detail(ticketId),
        queryFn: () => ticketsApi.getTicket(ticketId),
        enabled: !!ticketId,
    })
}

export function useTicketSendIdentities(options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: ticketKeys.identities(),
        queryFn: ticketsApi.getTicketSendIdentities,
        enabled: options?.enabled ?? true,
    })
}

export function usePatchTicket() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ ticketId, data }: { ticketId: string; data: ticketsApi.TicketPatchRequest }) =>
            ticketsApi.patchTicket(ticketId, data),
        onSuccess: (ticket) => {
            queryClient.invalidateQueries({ queryKey: ticketKeys.lists() })
            queryClient.invalidateQueries({ queryKey: ticketKeys.detail(ticket.id) })
        },
    })
}

export function useReplyTicket() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ ticketId, data }: { ticketId: string; data: ticketsApi.TicketReplyRequest }) =>
            ticketsApi.replyTicket(ticketId, data),
        onSuccess: (result) => {
            queryClient.invalidateQueries({ queryKey: ticketKeys.lists() })
            queryClient.invalidateQueries({ queryKey: ticketKeys.detail(result.ticket_id) })
        },
    })
}

export function useComposeTicket() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ticketsApi.composeTicket,
        onSuccess: (result) => {
            queryClient.invalidateQueries({ queryKey: ticketKeys.lists() })
            queryClient.invalidateQueries({ queryKey: ticketKeys.detail(result.ticket_id) })
        },
    })
}

export function useAddTicketNote() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ ticketId, bodyMarkdown }: { ticketId: string; bodyMarkdown: string }) =>
            ticketsApi.addTicketNote(ticketId, bodyMarkdown),
        onSuccess: (_note, vars) => {
            queryClient.invalidateQueries({ queryKey: ticketKeys.detail(vars.ticketId) })
            queryClient.invalidateQueries({ queryKey: ticketKeys.lists() })
        },
    })
}

export function useLinkTicketSurrogate() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            ticketId,
            surrogateId,
            reason,
        }: {
            ticketId: string
            surrogateId?: string | null
            reason?: string
        }) => {
            const payload: { surrogate_id?: string | null; reason?: string } = {}
            if (surrogateId !== undefined) {
                payload.surrogate_id = surrogateId
            }
            if (reason !== undefined) {
                payload.reason = reason
            }
            return ticketsApi.linkTicketSurrogate(ticketId, payload)
        },
        onSuccess: (ticket) => {
            queryClient.invalidateQueries({ queryKey: ticketKeys.detail(ticket.id) })
            queryClient.invalidateQueries({ queryKey: ticketKeys.lists() })
        },
    })
}
