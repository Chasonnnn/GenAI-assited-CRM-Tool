/**
 * React Query hooks for platform template studio (ops console).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    listPlatformEmailTemplates,
    getPlatformEmailTemplate,
    createPlatformEmailTemplate,
    updatePlatformEmailTemplate,
    publishPlatformEmailTemplate,
    listPlatformFormTemplates,
    getPlatformFormTemplate,
    createPlatformFormTemplate,
    updatePlatformFormTemplate,
    publishPlatformFormTemplate,
    listPlatformWorkflowTemplates,
    getPlatformWorkflowTemplate,
    createPlatformWorkflowTemplate,
    updatePlatformWorkflowTemplate,
    publishPlatformWorkflowTemplate,
    type PlatformEmailTemplateCreate,
    type PlatformEmailTemplateUpdate,
    type PlatformFormTemplateCreate,
    type PlatformFormTemplateUpdate,
    type PlatformWorkflowTemplateCreate,
    type PlatformWorkflowTemplateUpdate,
    type TemplatePublishRequest,
} from '@/lib/api/platform'

export const platformTemplateKeys = {
    all: ['platform-templates'] as const,
    emails: () => [...platformTemplateKeys.all, 'email'] as const,
    emailDetail: (id: string) => [...platformTemplateKeys.emails(), id] as const,
    forms: () => [...platformTemplateKeys.all, 'forms'] as const,
    formDetail: (id: string) => [...platformTemplateKeys.forms(), id] as const,
    workflows: () => [...platformTemplateKeys.all, 'workflows'] as const,
    workflowDetail: (id: string) => [...platformTemplateKeys.workflows(), id] as const,
}

export function usePlatformEmailTemplates() {
    return useQuery({
        queryKey: platformTemplateKeys.emails(),
        queryFn: () => listPlatformEmailTemplates(),
    })
}

export function usePlatformEmailTemplate(id: string | null) {
    return useQuery({
        queryKey: platformTemplateKeys.emailDetail(id || ''),
        queryFn: () => getPlatformEmailTemplate(id!),
        enabled: !!id,
    })
}

export function useCreatePlatformEmailTemplate() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (payload: PlatformEmailTemplateCreate) => createPlatformEmailTemplate(payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.emails() })
        },
    })
}

export function useUpdatePlatformEmailTemplate() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, payload }: { id: string; payload: PlatformEmailTemplateUpdate }) =>
            updatePlatformEmailTemplate(id, payload),
        onSuccess: (_data, { id }) => {
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.emails() })
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.emailDetail(id) })
        },
    })
}

export function usePublishPlatformEmailTemplate() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, payload }: { id: string; payload: TemplatePublishRequest }) =>
            publishPlatformEmailTemplate(id, payload),
        onSuccess: (_data, { id }) => {
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.emails() })
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.emailDetail(id) })
        },
    })
}

export function usePlatformFormTemplates() {
    return useQuery({
        queryKey: platformTemplateKeys.forms(),
        queryFn: () => listPlatformFormTemplates(),
    })
}

export function usePlatformFormTemplate(id: string | null) {
    return useQuery({
        queryKey: platformTemplateKeys.formDetail(id || ''),
        queryFn: () => getPlatformFormTemplate(id!),
        enabled: !!id,
    })
}

export function useCreatePlatformFormTemplate() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (payload: PlatformFormTemplateCreate) => createPlatformFormTemplate(payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.forms() })
        },
    })
}

export function useUpdatePlatformFormTemplate() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, payload }: { id: string; payload: PlatformFormTemplateUpdate }) =>
            updatePlatformFormTemplate(id, payload),
        onSuccess: (_data, { id }) => {
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.forms() })
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.formDetail(id) })
        },
    })
}

export function usePublishPlatformFormTemplate() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, payload }: { id: string; payload: TemplatePublishRequest }) =>
            publishPlatformFormTemplate(id, payload),
        onSuccess: (_data, { id }) => {
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.forms() })
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.formDetail(id) })
        },
    })
}

export function usePlatformWorkflowTemplates() {
    return useQuery({
        queryKey: platformTemplateKeys.workflows(),
        queryFn: () => listPlatformWorkflowTemplates(),
    })
}

export function usePlatformWorkflowTemplate(id: string | null) {
    return useQuery({
        queryKey: platformTemplateKeys.workflowDetail(id || ''),
        queryFn: () => getPlatformWorkflowTemplate(id!),
        enabled: !!id,
    })
}

export function useCreatePlatformWorkflowTemplate() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (payload: PlatformWorkflowTemplateCreate) =>
            createPlatformWorkflowTemplate(payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.workflows() })
        },
    })
}

export function useUpdatePlatformWorkflowTemplate() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, payload }: { id: string; payload: PlatformWorkflowTemplateUpdate }) =>
            updatePlatformWorkflowTemplate(id, payload),
        onSuccess: (_data, { id }) => {
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.workflows() })
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.workflowDetail(id) })
        },
    })
}

export function usePublishPlatformWorkflowTemplate() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, payload }: { id: string; payload: TemplatePublishRequest }) =>
            publishPlatformWorkflowTemplate(id, payload),
        onSuccess: (_data, { id }) => {
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.workflows() })
            queryClient.invalidateQueries({ queryKey: platformTemplateKeys.workflowDetail(id) })
        },
    })
}
