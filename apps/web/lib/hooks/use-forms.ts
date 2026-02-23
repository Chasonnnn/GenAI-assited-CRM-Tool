/**
 * React Query hooks for forms and submissions.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    listForms,
    getForm,
    createForm,
    updateForm,
    deleteForm,
    publishForm,
    listFormMappings,
    setFormMappings,
    createFormToken,
    createFormIntakeLink,
    listFormIntakeLinks,
    rotateFormIntakeLink,
    sendFormToken,
    setDefaultSurrogateApplicationForm,
    updateFormDeliverySettings,
    updateFormIntakeLink,
    resolveSubmissionMatch,
    listSubmissionMatchCandidates,
    listFormSubmissions,
    promoteIntakeLead,
    getIntakeLead,
    getSurrogateSubmission,
    getSurrogateDraftStatus,
    approveSubmission,
    rejectSubmission,
    uploadFormLogo,
    listFormTemplates,
    getFormTemplate,
    createFormFromTemplate,
    deleteFormTemplate,
    type FormTemplateLibraryItem,
    type FormTemplateLibraryDetail,
    type FormTemplateUseRequest,
    type FormCreatePayload,
    type FormUpdatePayload,
    type FormFieldMappingItem,
    type FormIntakeLinkCreatePayload,
    type FormIntakeLinkUpdatePayload,
    type FormDeliverySettings,
    type ResolveSubmissionMatchPayload,
    type PromoteIntakeLeadPayload,
    type SubmissionAnswersUpdateResponse,
    type ListFormSubmissionsParams,
} from '@/lib/api/forms'
import { ApiError } from '@/lib/api'

export const formKeys = {
    all: ['forms'] as const,
    lists: () => [...formKeys.all, 'list'] as const,
    list: () => [...formKeys.lists()] as const,
    details: () => [...formKeys.all, 'detail'] as const,
    detail: (id: string) => [...formKeys.details(), id] as const,
    mappings: (formId: string) => [...formKeys.detail(formId), 'mappings'] as const,
    intakeLinks: (formId: string) => [...formKeys.detail(formId), 'intake-links'] as const,
    intakeLead: (leadId: string) => [...formKeys.all, 'intake-lead', leadId] as const,
    submissionMatchCandidates: (submissionId: string) =>
        [...formKeys.all, 'submission-match-candidates', submissionId] as const,
    submissions: (formId: string, params?: ListFormSubmissionsParams) =>
        [...formKeys.detail(formId), 'submissions', params ?? {}] as const,
    surrogateSubmission: (formId: string, surrogateId: string) =>
        [...formKeys.detail(formId), 'surrogate-submission', surrogateId] as const,
    surrogateDraftStatus: (formId: string, surrogateId: string) =>
        [...formKeys.detail(formId), 'surrogate-draft', surrogateId] as const,
    templates: () => [...formKeys.all, 'templates'] as const,
    templateDetail: (id: string) => [...formKeys.templates(), id] as const,
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

export function useDeleteForm() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (formId: string) => deleteForm(formId),
        onSuccess: (_result, formId) => {
            queryClient.invalidateQueries({ queryKey: formKeys.lists() })
            queryClient.removeQueries({ queryKey: formKeys.detail(formId) })
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
            queryClient.invalidateQueries({ queryKey: formKeys.intakeLinks(formId) })
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

export function useFormSubmissions(formId: string | null, params: ListFormSubmissionsParams = {}) {
    return useQuery({
        queryKey: formId ? formKeys.submissions(formId, params) : ['forms', 'submissions', 'missing'],
        queryFn: () => listFormSubmissions(formId!, params),
        enabled: !!formId,
    })
}

export function useCreateFormToken() {
    return useMutation({
        mutationFn: ({
            formId,
            surrogateId,
            expiresInDays,
            allowPurposeOverride,
        }: {
            formId: string
            surrogateId: string
            expiresInDays?: number
            allowPurposeOverride?: boolean
        }) =>
            createFormToken(formId, surrogateId, expiresInDays, allowPurposeOverride),
    })
}

export function useSendFormToken() {
    return useMutation({
        mutationFn: ({
            formId,
            tokenId,
            templateId,
            allowPurposeOverride,
        }: {
            formId: string
            tokenId: string
            templateId?: string | null
            allowPurposeOverride?: boolean
        }) => sendFormToken(formId, tokenId, templateId, allowPurposeOverride),
    })
}

export function useSetDefaultSurrogateApplicationForm() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (formId: string) => setDefaultSurrogateApplicationForm(formId),
        onSuccess: (form) => {
            queryClient.invalidateQueries({ queryKey: formKeys.lists() })
            queryClient.setQueryData(formKeys.detail(form.id), form)
        },
    })
}

export function useUpdateFormDeliverySettings() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            formId,
            payload,
        }: {
            formId: string
            payload: FormDeliverySettings
        }) => updateFormDeliverySettings(formId, payload),
        onSuccess: (_settings, { formId }) => {
            queryClient.invalidateQueries({ queryKey: formKeys.detail(formId) })
        },
    })
}

export function useFormIntakeLinks(formId: string | null, includeInactive = true) {
    return useQuery({
        queryKey: formId ? [...formKeys.intakeLinks(formId), includeInactive] : ['forms', 'intake-links', 'missing'],
        queryFn: () => listFormIntakeLinks(formId!, includeInactive),
        enabled: !!formId,
    })
}

export function useCreateFormIntakeLink() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            formId,
            payload,
        }: {
            formId: string
            payload: FormIntakeLinkCreatePayload
        }) => createFormIntakeLink(formId, payload),
        onSuccess: (_result, { formId }) => {
            queryClient.invalidateQueries({ queryKey: formKeys.intakeLinks(formId) })
        },
    })
}

export function useUpdateFormIntakeLink() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            linkId,
            payload,
        }: {
            formId: string
            linkId: string
            payload: FormIntakeLinkUpdatePayload
        }) => updateFormIntakeLink(linkId, payload),
        onSuccess: (_result, { formId }) => {
            queryClient.invalidateQueries({ queryKey: formKeys.intakeLinks(formId) })
        },
    })
}

export function useRotateFormIntakeLink() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ linkId }: { formId: string; linkId: string }) => rotateFormIntakeLink(linkId),
        onSuccess: (_result, { formId }) => {
            queryClient.invalidateQueries({ queryKey: formKeys.intakeLinks(formId) })
        },
    })
}

export function useSurrogateFormDraftStatus(formId: string | null, surrogateId: string | null) {
    return useQuery({
        queryKey: formId && surrogateId ? formKeys.surrogateDraftStatus(formId, surrogateId) : ['forms', 'surrogate-draft', 'missing'],
        queryFn: async () => {
            try {
                return await getSurrogateDraftStatus(formId!, surrogateId!)
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

export function useApproveFormSubmission() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ submissionId, reviewNotes }: { submissionId: string; reviewNotes?: string | null }) =>
            approveSubmission(submissionId, reviewNotes),
        onSuccess: (submission) => {
            if (!submission.surrogate_id) return
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
            if (!submission.surrogate_id) return
            queryClient.invalidateQueries({
                queryKey: formKeys.surrogateSubmission(submission.form_id, submission.surrogate_id),
            })
        },
    })
}

export function useSubmissionMatchCandidates(submissionId: string | null) {
    return useQuery({
        queryKey: submissionId ? formKeys.submissionMatchCandidates(submissionId) : ['forms', 'submission-match-candidates', 'missing'],
        queryFn: () => listSubmissionMatchCandidates(submissionId!),
        enabled: !!submissionId,
    })
}

export function useResolveSubmissionMatch() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            submissionId,
            payload,
        }: {
            submissionId: string
            payload: ResolveSubmissionMatchPayload
        }) => resolveSubmissionMatch(submissionId, payload),
        onSuccess: (result) => {
            const submission = result.submission
            if (submission.form_id && submission.surrogate_id) {
                queryClient.invalidateQueries({
                    queryKey: formKeys.surrogateSubmission(submission.form_id, submission.surrogate_id),
                })
            }
            queryClient.invalidateQueries({
                queryKey: formKeys.submissionMatchCandidates(submission.id),
            })
        },
    })
}

export function useIntakeLead(leadId: string | null) {
    return useQuery({
        queryKey: leadId ? formKeys.intakeLead(leadId) : ['forms', 'intake-lead', 'missing'],
        queryFn: () => getIntakeLead(leadId!),
        enabled: !!leadId,
    })
}

export function usePromoteIntakeLead() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ leadId, payload }: { leadId: string; payload?: PromoteIntakeLeadPayload }) =>
            promoteIntakeLead(leadId, payload),
        onSuccess: (result) => {
            queryClient.invalidateQueries({ queryKey: formKeys.intakeLead(result.intake_lead_id) })
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
        onSuccess: (result: SubmissionAnswersUpdateResponse) => {
            if (!result.submission.surrogate_id) return
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
            surrogateId?: string | null
            fieldKey?: string | null
        }) => {
            const { uploadSubmissionFile } = await import('@/lib/api/forms')
            return { result: await uploadSubmissionFile(submissionId, file, fieldKey), formId, surrogateId }
        },
        onSuccess: ({ formId, surrogateId }) => {
            if (!surrogateId) return
            queryClient.invalidateQueries({
                queryKey: formKeys.surrogateSubmission(formId, surrogateId),
            })
        },
    })
}

// ============================================================================
// Platform Form Template Library Hooks
// ============================================================================

export function useFormTemplates() {
    return useQuery<FormTemplateLibraryItem[]>({
        queryKey: formKeys.templates(),
        queryFn: () => listFormTemplates(),
    })
}

export function useFormTemplateLibraryItem(templateId: string | null) {
    return useQuery<FormTemplateLibraryDetail>({
        queryKey: formKeys.templateDetail(templateId || ''),
        queryFn: () => getFormTemplate(templateId!),
        enabled: !!templateId,
    })
}

export function useUseFormTemplate() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ templateId, payload }: { templateId: string; payload: FormTemplateUseRequest }) =>
            createFormFromTemplate(templateId, payload),
        onSuccess: (form) => {
            queryClient.invalidateQueries({ queryKey: formKeys.lists() })
            queryClient.setQueryData(formKeys.detail(form.id), form)
        },
    })
}

export function useDeleteFormTemplate() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (templateId: string) => deleteFormTemplate(templateId),
        onSuccess: (_result, templateId) => {
            queryClient.invalidateQueries({ queryKey: formKeys.templates() })
            queryClient.removeQueries({ queryKey: formKeys.templateDetail(templateId) })
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
            surrogateId?: string | null
        }) => {
            const { deleteSubmissionFile } = await import('@/lib/api/forms')
            return { result: await deleteSubmissionFile(submissionId, fileId), formId, surrogateId }
        },
        onSuccess: ({ formId, surrogateId }) => {
            if (!surrogateId) return
            queryClient.invalidateQueries({
                queryKey: formKeys.surrogateSubmission(formId, surrogateId),
            })
        },
    })
}
