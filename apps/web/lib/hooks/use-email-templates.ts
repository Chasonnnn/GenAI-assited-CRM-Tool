/**
 * React Query hooks for email templates
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    listTemplates,
    getTemplate,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    sendEmail,
    copyTemplateToPersonal,
    shareTemplateWithOrg,
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailSendRequest,
    EmailTemplateCopyRequest,
    EmailTemplateShareRequest,
    EmailTemplateScope,
    ListTemplatesParams,
} from '@/lib/api/email-templates'

// Query keys
export const emailTemplateKeys = {
    all: ['email-templates'] as const,
    lists: () => [...emailTemplateKeys.all, 'list'] as const,
    list: (params: ListTemplatesParams) => [...emailTemplateKeys.lists(), params] as const,
    details: () => [...emailTemplateKeys.all, 'detail'] as const,
    detail: (id: string) => [...emailTemplateKeys.details(), id] as const,
}

// Hooks
export function useEmailTemplates(params: ListTemplatesParams = {}) {
    return useQuery({
        queryKey: emailTemplateKeys.list(params),
        queryFn: () => listTemplates(params),
    })
}

export function useEmailTemplate(id: string | null) {
    return useQuery({
        queryKey: emailTemplateKeys.detail(id || ''),
        queryFn: () => getTemplate(id!),
        enabled: !!id,
    })
}

export function useCreateEmailTemplate() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: EmailTemplateCreate) => createTemplate(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: emailTemplateKeys.lists() })
        },
    })
}

export function useUpdateEmailTemplate() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: EmailTemplateUpdate }) =>
            updateTemplate(id, data),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: emailTemplateKeys.lists() })
            queryClient.invalidateQueries({ queryKey: emailTemplateKeys.detail(id) })
        },
    })
}

export function useDeleteEmailTemplate() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (id: string) => deleteTemplate(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: emailTemplateKeys.lists() })
        },
    })
}

export function useSendEmail() {
    return useMutation({
        mutationFn: (data: EmailSendRequest) => sendEmail(data),
    })
}

// ============================================================================
// Version History Hooks
// ============================================================================

import { getTemplateVersions, rollbackTemplate } from '@/lib/api/email-templates'

export function useTemplateVersions(id: string | null) {
    return useQuery({
        queryKey: [...emailTemplateKeys.detail(id || ''), 'versions'] as const,
        queryFn: () => getTemplateVersions(id!),
        enabled: !!id,
    })
}

export function useRollbackTemplate() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ id, version }: { id: string; version: number }) =>
            rollbackTemplate(id, version),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: emailTemplateKeys.lists() })
            queryClient.invalidateQueries({ queryKey: emailTemplateKeys.detail(id) })
        },
    })
}

// ============================================================================
// Copy & Share Hooks
// ============================================================================

export function useCopyTemplateToPersonal() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: EmailTemplateCopyRequest }) =>
            copyTemplateToPersonal(id, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: emailTemplateKeys.lists() })
        },
    })
}

export function useShareTemplateWithOrg() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: EmailTemplateShareRequest }) =>
            shareTemplateWithOrg(id, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: emailTemplateKeys.lists() })
        },
    })
}
