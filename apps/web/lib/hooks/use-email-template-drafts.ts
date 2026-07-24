/**
 * TanStack Query hooks for isolated email template drafts.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    createEmailTemplateDraft,
    createEmailTemplateDraftFromTemplate,
    discardEmailTemplateDraft,
    getEmailTemplateDraft,
    listEmailTemplateDrafts,
    publishEmailTemplateDraft,
    restoreEmailTemplateDraftVersion,
    sendTestEmailTemplateDraft,
    updateEmailTemplateDraft,
    type EmailTemplateDraftCreate,
    type EmailTemplateDraftPublishRequest,
    type EmailTemplateDraftRestoreVersionRequest,
    type EmailTemplateDraftTestSendRequest,
    type EmailTemplateDraftTestSendResponse,
    type EmailTemplateDraftUpdate,
    type ListEmailTemplateDraftsParams,
} from '@/lib/api/email-template-drafts'

export const emailTemplateDraftKeys = {
    all: ['email-template-drafts'] as const,
    lists: () => [...emailTemplateDraftKeys.all, 'list'] as const,
    list: (params: ListEmailTemplateDraftsParams) =>
        [...emailTemplateDraftKeys.lists(), params] as const,
    details: () => [...emailTemplateDraftKeys.all, 'detail'] as const,
    detail: (id: string) => [...emailTemplateDraftKeys.details(), id] as const,
}

export function useEmailTemplateDrafts(
    params: ListEmailTemplateDraftsParams = {},
    enabled = true,
) {
    return useQuery({
        queryKey: emailTemplateDraftKeys.list(params),
        queryFn: () => listEmailTemplateDrafts(params),
        enabled,
    })
}

export function useEmailTemplateDraft(id: string | null) {
    return useQuery({
        queryKey: emailTemplateDraftKeys.detail(id || ''),
        queryFn: () => getEmailTemplateDraft(id!),
        enabled: !!id,
    })
}

export function useCreateEmailTemplateDraft() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: EmailTemplateDraftCreate) =>
            createEmailTemplateDraft(data),
        onSuccess: () => {
            void queryClient.invalidateQueries({
                queryKey: emailTemplateDraftKeys.lists(),
            })
        },
    })
}

export function useCreateEmailTemplateDraftFromTemplate() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ templateId }: { templateId: string }) =>
            createEmailTemplateDraftFromTemplate(templateId),
        onSuccess: () => {
            void queryClient.invalidateQueries({
                queryKey: emailTemplateDraftKeys.lists(),
            })
        },
    })
}

export function useUpdateEmailTemplateDraft() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            id,
            data,
        }: {
            id: string
            data: EmailTemplateDraftUpdate
        }) => updateEmailTemplateDraft(id, data),
        onSuccess: (_draft, { id }) => {
            void queryClient.invalidateQueries({
                queryKey: emailTemplateDraftKeys.lists(),
            })
            void queryClient.invalidateQueries({
                queryKey: emailTemplateDraftKeys.detail(id),
            })
        },
    })
}

export function useDiscardEmailTemplateDraft() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            id,
            expectedRevision,
        }: {
            id: string
            expectedRevision: number
        }) => discardEmailTemplateDraft(id, expectedRevision),
        onSuccess: (_result, { id }) => {
            void queryClient.invalidateQueries({
                queryKey: emailTemplateDraftKeys.lists(),
            })
            queryClient.removeQueries({
                queryKey: emailTemplateDraftKeys.detail(id),
            })
        },
    })
}

export function usePublishEmailTemplateDraft() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            id,
            data,
        }: {
            id: string
            data: EmailTemplateDraftPublishRequest
        }) => publishEmailTemplateDraft(id, data),
        onSuccess: (_template, { id }) => {
            void queryClient.invalidateQueries({
                queryKey: emailTemplateDraftKeys.lists(),
            })
            queryClient.removeQueries({
                queryKey: emailTemplateDraftKeys.detail(id),
            })
            void queryClient.invalidateQueries({
                queryKey: ['email-templates'],
            })
        },
    })
}

export function useRestoreEmailTemplateDraftVersion() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            id,
            data,
        }: {
            id: string
            data: EmailTemplateDraftRestoreVersionRequest
        }) => restoreEmailTemplateDraftVersion(id, data),
        onSuccess: (_draft, { id }) => {
            void queryClient.invalidateQueries({
                queryKey: emailTemplateDraftKeys.lists(),
            })
            void queryClient.invalidateQueries({
                queryKey: emailTemplateDraftKeys.detail(id),
            })
        },
    })
}

export function useSendTestEmailTemplateDraft() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: async ({
            id,
            payload,
        }: {
            id: string
            payload: EmailTemplateDraftTestSendRequest
        }): Promise<EmailTemplateDraftTestSendResponse> => {
            const result = await sendTestEmailTemplateDraft(id, payload)
            if (!result.success) {
                throw new Error(result.error || 'Failed to send test email')
            }
            return result
        },
        onSuccess: (_result, { id }) => {
            void queryClient.invalidateQueries({
                queryKey: emailTemplateDraftKeys.lists(),
            })
            void queryClient.invalidateQueries({
                queryKey: emailTemplateDraftKeys.detail(id),
            })
        },
    })
}
