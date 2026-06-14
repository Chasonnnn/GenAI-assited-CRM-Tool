/**
 * React Query hooks for invitation management
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { invitesApi, type CreateInviteRequest } from "../api/invites"

export function useInvites() {
    return useQuery({
        queryKey: ["invites"],
        queryFn: () => invitesApi.list(),
    })
}

export function useCreateInvite() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: CreateInviteRequest) => invitesApi.create(data),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ["invites"] })
        },
    })
}

export function useResendInvite() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (inviteId: string) => invitesApi.resend(inviteId),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ["invites"] })
        },
    })
}

export function useRevokeInvite() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (inviteId: string) => invitesApi.revoke(inviteId),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ["invites"] })
        },
    })
}
