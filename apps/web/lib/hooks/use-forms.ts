/**
 * React Query hooks for forms and submissions.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    listForms,
    getForm,
    createForm,
    updateForm,
    publishForm,
    listFormMappings,
    setFormMappings,
    createFormToken,
    getSurrogateSubmission,
    approveSubmission,
    rejectSubmission,
    uploadFormLogo,
    type FormCreatePayload,
    type FormUpdatePayload,
    type FormFieldMappingItem,
} from '@/lib/api/forms'
import { ApiError } from '@/lib/api'

export const formKeys = {
    all: ['forms'] as const,
    lists: () => [...formKeys.all, 'list'] as const,
    list: () => [...formKeys.lists()] as const,
    details: () => [...formKeys.all, 'detail'] as const,
    detail: (id: string) => [...formKeys.details(), id] as const,
    mappings: (formId: string) => [...formKeys.detail(formId), 'mappings'] as const,
    surrogateSubmission: (formId: string, surrogateId: string) =>
        [...formKeys.detail(formId), 'surrogate-submission', surrogateId] as const,
}

export function useForms() {
    return useQuery({
        queryKey: formKeys.list(),
        queryFn: () => listForms(),
    })
}

export function useForm(formId: string | null) {
    return useQuery({
        queryKey: formKeys.detail(formId || ''),
        queryFn: () => getForm(formId!),
        enabled: !!formId,
    })
}

export function useCreateForm() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (payload: FormCreatePayload) => createForm(payload),
        onSuccess: (form) => {
            queryClient.invalidateQueries({ queryKey: formKeys.lists() })
            queryClient.setQueryData(formKeys.detail(form.id), form)
        },
    })
}

export function useUpdateForm() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ formId, payload }: { formId: string; payload: FormUpdatePayload }) =>
            updateForm(formId, payload),
        onSuccess: (form) => {
            queryClient.invalidateQueries({ queryKey: formKeys.lists() })
            queryClient.setQueryData(formKeys.detail(form.id), form)
        },
    })
}

export function usePublishForm() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (formId: string) => publishForm(formId),
        onSuccess: (_result, formId) => {
            queryClient.invalidateQueries({ queryKey: formKeys.detail(formId) })
            queryClient.invalidateQueries({ queryKey: formKeys.lists() })
        },
    })
}

export function useFormMappings(formId: string | null) {
    return useQuery({
        queryKey: formKeys.mappings(formId || ''),
        queryFn: () => listFormMappings(formId!),
        enabled: !!formId,
    })
}

export function useSetFormMappings() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ formId, mappings }: { formId: string; mappings: FormFieldMappingItem[] }) =>
            setFormMappings(formId, mappings),
        onSuccess: (_data, { formId }) => {
            queryClient.invalidateQueries({ queryKey: formKeys.mappings(formId) })
        },
    })
}

export function useSurrogateFormSubmission(formId: string | null, surrogateId: string | null) {
    return useQuery({
        queryKey: formId && surrogateId ? formKeys.surrogateSubmission(formId, surrogateId) : ['forms', 'surrogate-submission', 'missing'],
        queryFn: async () => {
            try {
                return await getSurrogateSubmission(formId!, surrogateId!)
            } catch (error) {
                if (error instanceof ApiError && error.status === 404) {
                    return null
                }
                throw error
            }
        },
        enabled: !!formId && !!surrogateId,
        retry: false,
    })
}

export function useCreateFormToken() {
    return useMutation({
        mutationFn: ({ formId, surrogateId, expiresInDays }: { formId: string; surrogateId: string; expiresInDays?: number }) =>
            createFormToken(formId, surrogateId, expiresInDays),
    })
}

export function useApproveFormSubmission() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ submissionId, reviewNotes }: { submissionId: string; reviewNotes?: string | null }) =>
            approveSubmission(submissionId, reviewNotes),
        onSuccess: (submission) => {
            queryClient.invalidateQueries({
                queryKey: formKeys.surrogateSubmission(submission.form_id, submission.surrogate_id),
            })
        },
    })
}

export function useRejectFormSubmission() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ submissionId, reviewNotes }: { submissionId: string; reviewNotes?: string | null }) =>
            rejectSubmission(submissionId, reviewNotes),
        onSuccess: (submission) => {
            queryClient.invalidateQueries({
                queryKey: formKeys.surrogateSubmission(submission.form_id, submission.surrogate_id),
            })
        },
    })
}

export function useUploadFormLogo() {
    return useMutation({
        mutationFn: (file: File) => uploadFormLogo(file),
    })
}

export function useUpdateSubmissionAnswers() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: async ({
            submissionId,
            updates,
        }: {
            submissionId: string
            updates: { field_key: string; value: unknown }[]
        }) => {
            const { updateSubmissionAnswers } = await import('@/lib/api/forms')
            return updateSubmissionAnswers(submissionId, updates)
        },
        onSuccess: (result: { submission: { form_id: string; surrogate_id: string }; surrogate_updates: string[] }) => {
            queryClient.invalidateQueries({
                queryKey: formKeys.surrogateSubmission(result.submission.form_id, result.submission.surrogate_id),
            })
        },
    })
}

export function useUploadSubmissionFile() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: async ({
            submissionId,
            file,
            formId,
            surrogateId,
            fieldKey,
        }: {
            submissionId: string
            file: File
            formId: string
            surrogateId: string
            fieldKey?: string | null
        }) => {
            const { uploadSubmissionFile } = await import('@/lib/api/forms')
            return { result: await uploadSubmissionFile(submissionId, file, fieldKey), formId, surrogateId }
        },
        onSuccess: ({ formId, surrogateId }) => {
            queryClient.invalidateQueries({
                queryKey: formKeys.surrogateSubmission(formId, surrogateId),
            })
        },
    })
}

export function useDeleteSubmissionFile() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: async ({
            submissionId,
            fileId,
            formId,
            surrogateId,
        }: {
            submissionId: string
            fileId: string
            formId: string
            surrogateId: string
        }) => {
            const { deleteSubmissionFile } = await import('@/lib/api/forms')
            return { result: await deleteSubmissionFile(submissionId, fileId), formId, surrogateId }
        },
        onSuccess: ({ formId, surrogateId }) => {
            queryClient.invalidateQueries({
                queryKey: formKeys.surrogateSubmission(formId, surrogateId),
            })
        },
    })
}
