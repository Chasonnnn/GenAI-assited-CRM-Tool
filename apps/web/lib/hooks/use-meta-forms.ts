import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    getMetaFormMapping,
    reconvertMetaFormLeads,
    getMetaFormUnconvertedLeads,
    listMetaForms,
    syncMetaForms,
    updateMetaFormMapping,
    deleteMetaForm,
    type MetaFormMappingUpdate,
} from '@/lib/api/meta-forms'

export const metaFormsKeys = {
    all: ['meta-forms'] as const,
    list: () => [...metaFormsKeys.all, 'list'] as const,
    mapping: (formId: string) => [...metaFormsKeys.all, 'mapping', formId] as const,
    unconvertedLeads: (formId: string) => [...metaFormsKeys.all, 'unconverted-leads', formId] as const,
}

export function useMetaForms(enabled = true) {
    return useQuery({
        queryKey: metaFormsKeys.list(),
        queryFn: listMetaForms,
        enabled,
    })
}

export function useMetaFormMapping(formId: string) {
    return useQuery({
        queryKey: metaFormsKeys.mapping(formId),
        queryFn: () => getMetaFormMapping(formId),
        enabled: !!formId,
    })
}

export function useMetaFormUnconvertedLeads(formId: string, enabled = true) {
    return useQuery({
        queryKey: metaFormsKeys.unconvertedLeads(formId),
        queryFn: () => getMetaFormUnconvertedLeads(formId),
        enabled: !!formId && enabled,
    })
}

export function useSyncMetaForms() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (payload?: { page_id?: string }) => syncMetaForms(payload),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: metaFormsKeys.list() })
        },
    })
}

export function useUpdateMetaFormMapping(formId: string) {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (payload: MetaFormMappingUpdate) => updateMetaFormMapping(formId, payload),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: metaFormsKeys.mapping(formId) })
            void queryClient.invalidateQueries({ queryKey: metaFormsKeys.list() })
            void queryClient.invalidateQueries({ queryKey: metaFormsKeys.unconvertedLeads(formId) })
        },
    })
}

export function useReconvertMetaFormLeads(formId: string) {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: () => reconvertMetaFormLeads(formId),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: metaFormsKeys.mapping(formId) })
            void queryClient.invalidateQueries({ queryKey: metaFormsKeys.list() })
            void queryClient.invalidateQueries({ queryKey: metaFormsKeys.unconvertedLeads(formId) })
        },
    })
}

export function useDeleteMetaForm() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (formId: string) => deleteMetaForm(formId),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: metaFormsKeys.list() })
        },
    })
}
