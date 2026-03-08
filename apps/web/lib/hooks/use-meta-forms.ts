import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    getMetaFormMapping,
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

export function useMetaForms() {
    return useQuery({
        queryKey: metaFormsKeys.list(),
        queryFn: listMetaForms,
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
            queryClient.invalidateQueries({ queryKey: metaFormsKeys.list() })
        },
    })
}

export function useUpdateMetaFormMapping(formId: string) {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (payload: MetaFormMappingUpdate) => updateMetaFormMapping(formId, payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: metaFormsKeys.mapping(formId) })
            queryClient.invalidateQueries({ queryKey: metaFormsKeys.list() })
            queryClient.invalidateQueries({ queryKey: metaFormsKeys.unconvertedLeads(formId) })
        },
    })
}

export function useDeleteMetaForm() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (formId: string) => deleteMetaForm(formId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: metaFormsKeys.list() })
        },
    })
}
