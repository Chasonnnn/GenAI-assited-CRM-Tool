/**
 * React Query hooks for surrogate emails tab.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as surrogateEmailsApi from '../api/surrogate-emails'

export const surrogateEmailKeys = {
    all: ['surrogate-emails'] as const,
    ticketList: (surrogateId: string) => [...surrogateEmailKeys.all, surrogateId, 'tickets'] as const,
    contacts: (surrogateId: string) => [...surrogateEmailKeys.all, surrogateId, 'contacts'] as const,
}

export function useSurrogateEmails(surrogateId: string) {
    return useQuery({
        queryKey: surrogateEmailKeys.ticketList(surrogateId),
        queryFn: () => surrogateEmailsApi.getSurrogateEmails(surrogateId),
        enabled: !!surrogateId,
    })
}

export function useSurrogateEmailContacts(surrogateId: string) {
    return useQuery({
        queryKey: surrogateEmailKeys.contacts(surrogateId),
        queryFn: () => surrogateEmailsApi.getSurrogateEmailContacts(surrogateId),
        enabled: !!surrogateId,
    })
}

export function useCreateSurrogateEmailContact(surrogateId: string) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: surrogateEmailsApi.SurrogateEmailContactCreatePayload) =>
            surrogateEmailsApi.createSurrogateEmailContact(surrogateId, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: surrogateEmailKeys.contacts(surrogateId) })
        },
    })
}

export function usePatchSurrogateEmailContact(surrogateId: string) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            contactId,
            data,
        }: {
            contactId: string
            data: surrogateEmailsApi.SurrogateEmailContactPatchPayload
        }) => surrogateEmailsApi.patchSurrogateEmailContact(surrogateId, contactId, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: surrogateEmailKeys.contacts(surrogateId) })
        },
    })
}

export function useDeactivateSurrogateEmailContact(surrogateId: string) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (contactId: string) =>
            surrogateEmailsApi.deactivateSurrogateEmailContact(surrogateId, contactId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: surrogateEmailKeys.contacts(surrogateId) })
        },
    })
}
