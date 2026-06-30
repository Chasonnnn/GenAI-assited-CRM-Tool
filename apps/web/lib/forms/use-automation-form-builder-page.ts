"use client"

import { useEffect, useRef } from "react"
import type { ChangeEvent } from "react"
import { useParams, useRouter } from "next/navigation"
import { toast } from "sonner"

import { useAuth } from "@/lib/auth-context"
import { DEFAULT_FORM_SURROGATE_FIELD_OPTIONS } from "@/lib/api/forms"
import type {
    FormCreatePayload,
    FormIntakeLinkRead,
    FormPurpose,
    FormRead,
    FormSubmissionRead,
    FormSurrogateFieldOption,
    TrackingMode,
} from "@/lib/api/forms"
import {
    FALLBACK_FORM_PAGE,
    buildFormSchema,
    buildMappings,
    schemaToPages,
    type BuilderFormPage,
} from "@/lib/forms/form-builder-document"
import { useAutomationFormBuilderState } from "@/lib/forms/use-automation-form-builder-state"
import type { AutomationBuilderState } from "@/lib/forms/use-automation-form-builder-state"
import { useFormBuilderDocument } from "@/lib/forms/use-form-builder-document"
import { useEmailTemplates } from "@/lib/hooks/use-email-templates"
import { useFormMappingOptions } from "@/lib/hooks/use-form-mapping-options"
import {
    useCreateForm,
    useForm,
    useFormEmbedHealth,
    useFormIntakeLinks,
    useFormMappings,
    useFormSubmissions,
    usePublishForm,
    usePromoteIntakeLead,
    useResolveSubmissionMatch,
    useRetrySubmissionMatch,
    useSetDefaultSurrogateApplicationForm,
    useSetFormMappings,
    useSubmissionMatchCandidates,
    useUpdateForm,
    useUpdateFormDeliverySettings,
    useUpdateFormIntakeLink,
    useUploadFormLogo,
} from "@/lib/hooks/use-forms"
import { useOrgSignature } from "@/lib/hooks/use-signature"

type BuilderPages = ReturnType<typeof useFormBuilderDocument>["pages"]
type AutomationRouter = ReturnType<typeof useRouter>
type AutomationDraftValues = Pick<
    AutomationBuilderState,
    | "allowedMimeTypesText"
    | "defaultTemplateId"
    | "formDescription"
    | "formName"
    | "formPurpose"
    | "logoUrl"
    | "maxFileCount"
    | "maxFileSizeMb"
    | "privacyNotice"
    | "publicEyebrow"
    | "publicSubtitle"
    | "publicTitle"
>

function collectCriticalFieldValues(options: FormSurrogateFieldOption[]): string[] {
    const values: string[] = []
    for (const option of options) {
        if (option.is_critical) values.push(option.value)
    }
    return values
}

function getMissingCriticalMappings(
    pages: BuilderFormPage[],
    mappingOptions: FormSurrogateFieldOption[],
): FormSurrogateFieldOption[] {
    const mappedFields = new Set(buildMappings(pages).map((mapping) => mapping.surrogate_field))
    const fieldKeys = new Set(pages.flatMap((page) => page.fields.map((field) => field.id)))
    const mappingCriticalValues = collectCriticalFieldValues(mappingOptions)
    const criticalValues =
        mappingCriticalValues.length > 0
            ? mappingCriticalValues
            : collectCriticalFieldValues(DEFAULT_FORM_SURROGATE_FIELD_OPTIONS)
    const optionByValue = new Map(mappingOptions.map((option) => [option.value, option]))
    const fallbackByValue = new Map(DEFAULT_FORM_SURROGATE_FIELD_OPTIONS.map((option) => [option.value, option]))
    const missingMappings: FormSurrogateFieldOption[] = []

    for (const value of criticalValues) {
        if (mappedFields.has(value) || fieldKeys.has(value)) continue
        missingMappings.push(
            optionByValue.get(value) ??
                fallbackByValue.get(value) ??
                ({ value, label: value, is_critical: true } as FormSurrogateFieldOption),
        )
    }

    return missingMappings
}

function getMissingLeadCaptureMappings(
    pages: BuilderFormPage[],
    mappingOptions: FormSurrogateFieldOption[],
): FormSurrogateFieldOption[] {
    const mappedFields = new Set(buildMappings(pages).map((mapping) => mapping.surrogate_field))
    const fieldKeys = new Set(pages.flatMap((page) => page.fields.map((field) => field.id)))
    const hasFullName = mappedFields.has("full_name") || fieldKeys.has("full_name")
    const hasEmail = mappedFields.has("email") || fieldKeys.has("email")
    const hasPhone = mappedFields.has("phone") || fieldKeys.has("phone")
    const optionByValue = new Map(mappingOptions.map((option) => [option.value, option]))
    const fallbackByValue = new Map(DEFAULT_FORM_SURROGATE_FIELD_OPTIONS.map((option) => [option.value, option]))
    const missingValues = [
        ...(hasFullName ? [] : ["full_name"]),
        ...(hasEmail || hasPhone ? [] : ["email"]),
    ]

    return missingValues.map(
        (value) =>
            optionByValue.get(value) ??
            fallbackByValue.get(value) ??
            ({ value, label: value, is_critical: true } as FormSurrogateFieldOption),
    )
}

function buildAutomationDraftPayload(pages: BuilderPages, state: AutomationDraftValues): FormCreatePayload {
    const allowedMimeTypes: string[] = []
    for (const entry of state.allowedMimeTypesText.split(",")) {
        const trimmedEntry = entry.trim()
        if (trimmedEntry) allowedMimeTypes.push(trimmedEntry)
    }
    return {
        name: state.formName.trim(),
        description: state.formDescription.trim() || null,
        purpose: state.formPurpose,
        form_schema: buildFormSchema(pages, {
            publicEyebrow: state.publicEyebrow,
            publicTitle: state.publicTitle,
            publicSubtitle: state.publicSubtitle,
            logoUrl: state.logoUrl,
            privacyNotice: state.privacyNotice,
        }),
        max_file_size_bytes: Math.max(1, Math.round(state.maxFileSizeMb * 1024 * 1024)),
        max_file_count: Math.max(0, Math.round(state.maxFileCount)),
        allowed_mime_types: allowedMimeTypes.length > 0 ? allowedMimeTypes : null,
        default_application_email_template_id: state.defaultTemplateId || null,
    }
}

async function persistAutomationFormPayload({
    payload,
    isNewForm,
    id,
    pages,
    createFormMutation,
    updateFormMutation,
    setMappingsMutation,
    router,
    patchState,
}: {
    payload: FormCreatePayload
    isNewForm: boolean
    id: string
    pages: BuilderPages
    createFormMutation: ReturnType<typeof useCreateForm>
    updateFormMutation: ReturnType<typeof useUpdateForm>
    setMappingsMutation: ReturnType<typeof useSetFormMappings>
    router: AutomationRouter
    patchState: (payload: Partial<AutomationBuilderState>) => void
}): Promise<FormRead> {
    let savedForm: FormRead
    if (isNewForm) {
        savedForm = await createFormMutation.mutateAsync(payload)
        router.replace(`/automation/forms/${savedForm.id}`)
    } else {
        savedForm = await updateFormMutation.mutateAsync({
            formId: id,
            payload,
        })
    }

    const mappings = buildMappings(pages)
    await setMappingsMutation.mutateAsync({
        formId: savedForm.id,
        mappings,
    })

    patchState({ isPublished: savedForm.status === "published" })
    return savedForm
}

function buildSavedState(fingerprint: string, savedForm?: FormRead): Partial<AutomationBuilderState> {
    return {
        autoSaveStatus: "saved",
        lastSavedAt: savedForm?.updated_at ? new Date(savedForm.updated_at) : new Date(),
        lastSavedFingerprint: fingerprint,
    }
}

function getAutoSaveLabel(state: AutomationBuilderState, isDirty: boolean) {
    if (!state.hasHydrated) return null
    if (state.isSaving || state.autoSaveStatus === "saving") return "Saving..."
    if (state.autoSaveStatus === "error") return "Autosave failed"
    if (isDirty) return "Unsaved changes"
    if (state.autoSaveStatus === "saved") {
        if (state.lastSavedAt) {
            return `Saved ${state.lastSavedAt.toLocaleTimeString("en-US", {
                hour: "numeric",
                minute: "2-digit",
            })}`
        }
        return "Saved"
    }
    return "Autosave on"
}

function getQrSvgMarkup() {
    const svg = document.querySelector("#shared-intake-qr svg")
    if (!(svg instanceof SVGSVGElement)) {
        toast.error("QR code not ready yet")
        return null
    }

    let markup = new XMLSerializer().serializeToString(svg)
    if (!markup.includes("xmlns=\"http://www.w3.org/2000/svg\"")) {
        markup = markup.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"')
    }
    return markup
}

function buildQrFilename(link: FormIntakeLinkRead | null, extension: "svg" | "png") {
    const baseRaw = link?.campaign_name || link?.event_name || link?.slug || "intake-link"
    const base = baseRaw
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
    return `${base || "intake-link"}-qr.${extension}`
}

function downloadBlob(blob: Blob, filename: string) {
    const downloadUrl = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = downloadUrl
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(downloadUrl)
}

async function handleCopySharedLink(link: FormIntakeLinkRead) {
    const url = link.intake_url?.trim()
    if (!url) {
        toast.error("No intake URL available")
        return
    }
    try {
        await navigator.clipboard.writeText(url)
        toast.success("Shared link copied")
    } catch {
        toast.error("Failed to copy link")
    }
}

function readAnswerValue(submission: FormSubmissionRead, keys: string[]) {
    for (const key of keys) {
        const rawValue = submission.answers?.[key]
        if (typeof rawValue === "string" && rawValue.trim()) {
            return rawValue.trim()
        }
    }
    return "—"
}

function formatSubmissionDateTime(isoString: string) {
    const value = new Date(isoString)
    if (Number.isNaN(value.getTime())) return "—"
    return value.toLocaleString()
}

function submissionOutcomeLabel(submission: FormSubmissionRead) {
    if (submission.match_status === "linked") return "Matched"
    if (submission.match_status === "lead_created") return "Lead Created"
    return "Pending Match"
}

function submissionOutcomeBadgeClass(submission: FormSubmissionRead) {
    if (submission.match_status === "linked") {
        return "border-emerald-200 bg-emerald-50 text-emerald-700"
    }
    if (submission.match_status === "lead_created") {
        return "border-blue-200 bg-blue-50 text-blue-700"
    }
    return "border-amber-200 bg-amber-50 text-amber-700"
}

function submissionReviewLabel(submission: FormSubmissionRead) {
    if (submission.status === "approved") return "Approved"
    if (submission.status === "rejected") return "Rejected"
    return "Pending Review"
}

function submissionReviewBadgeClass(submission: FormSubmissionRead) {
    if (submission.status === "approved") {
        return "border-emerald-200 bg-emerald-50 text-emerald-700"
    }
    if (submission.status === "rejected") {
        return "border-red-200 bg-red-50 text-red-700"
    }
    return "border-stone-200 bg-stone-100 text-stone-700"
}

export function useAutomationFormBuilderPage() {
    const params = useParams<{ id: string }>()
    const idParam = params?.id
    const id = Array.isArray(idParam) ? idParam[0] : idParam ?? "new"
    const router = useRouter()
    const { user } = useAuth()
    const isNewForm = id === "new"
    const formId = isNewForm ? null : id

    const { data: formData, isLoading: isFormLoading } = useForm(formId)
    const { data: mappingData, isLoading: isMappingsLoading } = useFormMappings(formId)
    const { data: mappingOptionsData } = useFormMappingOptions()
    const {
        data: intakeLinks = [],
        refetch: refetchIntakeLinks,
    } = useFormIntakeLinks(formId, true)
    const { data: emailTemplates = [] } = useEmailTemplates({ activeOnly: true })
    const { data: orgSignature } = useOrgSignature()
    const createFormMutation = useCreateForm()
    const updateFormMutation = useUpdateForm()
    const updateIntakeLinkMutation = useUpdateFormIntakeLink()
    const publishFormMutation = usePublishForm()
    const setMappingsMutation = useSetFormMappings()
    const setDefaultSurrogateApplicationMutation = useSetDefaultSurrogateApplicationForm()
    const uploadLogoMutation = useUploadFormLogo()
    const updateDeliverySettingsMutation = useUpdateFormDeliverySettings()
    const resolveSubmissionMatchMutation = useResolveSubmissionMatch()
    const retrySubmissionMatchMutation = useRetrySubmissionMatch()
    const promoteIntakeLeadMutation = usePromoteIntakeLead()
    const {
        data: ambiguousSubmissions = [],
        refetch: refetchAmbiguousSubmissions,
    } = useFormSubmissions(formId, {
        source_mode: "shared",
        match_status: "ambiguous_review",
        limit: 50,
    })
    const {
        data: leadQueueSubmissions = [],
        refetch: refetchLeadQueueSubmissions,
    } = useFormSubmissions(formId, {
        source_mode: "shared",
        status: "pending_review",
        match_status: "lead_created",
        limit: 50,
    })
    const {
        data: submissionHistory = [],
        refetch: refetchSubmissionHistory,
        isLoading: isSubmissionHistoryLoading,
    } = useFormSubmissions(formId, {
        limit: 500,
    })

    const logoInputRef = useRef<HTMLInputElement>(null)
    const hydratedFormRef = useRef<string | null>(null)
    const orgLogoInitRef = useRef(false)
    const { state, patchState, resetForForm, hydrateFromForm } = useAutomationFormBuilderState(isNewForm)
    const {
        pages,
        activePage,
        setActivePage,
        currentPage,
        selectedField,
        selectedFieldData,
        dropIndicatorId,
        isDragging,
        resetDocument,
        selectField,
        syncOptionKeys,
        handleDragStart,
        handleFieldDragStart,
        handleDragOver,
        handleCanvasDragOver,
        handleFieldDragOver,
        handleDrop,
        handleDropOnField,
        handleDragEnd,
        handleInsertField,
        handleDeleteField,
        handleDuplicateField,
        handleUpdateField,
        handleValidationChange,
        handleAddColumn,
        handleUpdateColumn,
        handleRemoveColumn,
        handleAddRow,
        handleUpdateRow,
        handleRemoveRow,
        handleShowIfChange,
        handleMappingChange,
        handleAddPage,
        handleDuplicatePage,
        handleRenamePage,
        handleMovePage,
        deletePage,
        addOption,
        removeOption,
    } = useFormBuilderDocument()

    const { data: selectedMatchCandidates = [], isLoading: isMatchCandidatesLoading } =
        useSubmissionMatchCandidates(state.selectedQueueSubmissionId)

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || ""
    const orgId = user?.org_id || ""
    const orgLogoPath = orgId ? `/forms/public/${orgId}/signature-logo` : ""
    const orgLogoAvailable = Boolean(orgSignature?.signature_logo_url)
    const isDefaultSurrogateApplication = Boolean(formData?.is_default_surrogate_application)
    const resolvedLogoUrl =
        state.logoUrl && state.logoUrl.startsWith("/") && apiBaseUrl ? `${apiBaseUrl}${state.logoUrl}` : state.logoUrl
    const surrogateFieldMappings =
        mappingOptionsData && mappingOptionsData.length > 0
            ? mappingOptionsData
            : DEFAULT_FORM_SURROGATE_FIELD_OPTIONS

    useEffect(() => {
        resetForForm(isNewForm)
        hydratedFormRef.current = null
        orgLogoInitRef.current = false
        resetDocument()
    }, [formId, isNewForm, resetDocument, resetForForm])

    useEffect(() => {
        if (state.workspaceTab !== "submissions") {
            patchState({
                selectedQueueSubmissionId: null,
                manualSurrogateId: "",
            })
        }
    }, [patchState, state.workspaceTab])

    useEffect(() => {
        if (isNewForm || !formData || isMappingsLoading || state.hasHydrated) return

        const mappingMap = new Map(
            (mappingData || []).map((mapping) => [mapping.field_key, mapping.surrogate_field]),
        )
        const schema = formData.form_schema || formData.published_schema

        hydrateFromForm({ form: formData })
        resetDocument(schema ? schemaToPages(schema, mappingMap) : [FALLBACK_FORM_PAGE])
    }, [formData, hydrateFromForm, isMappingsLoading, isNewForm, mappingData, resetDocument, state.hasHydrated])

    useEffect(() => {
        if (!state.hasHydrated || orgLogoInitRef.current) return
        if (!orgLogoPath) return
        const isOrgLogo = state.logoUrl === orgLogoPath
        patchState({
            useOrgLogo: isOrgLogo,
            customLogoUrl: isOrgLogo ? state.customLogoUrl : state.logoUrl,
        })
        orgLogoInitRef.current = true
    }, [orgLogoPath, patchState, state.customLogoUrl, state.hasHydrated, state.logoUrl])

    const draftPayload = buildAutomationDraftPayload(pages, state)
    const draftFingerprint = JSON.stringify(draftPayload)
    const isDirty = draftFingerprint !== state.lastSavedFingerprint

    useEffect(() => {
        if (!state.hasHydrated) return
        const identity = isNewForm ? "new" : formId || "unknown"
        if (hydratedFormRef.current === identity) return
        hydratedFormRef.current = identity
        if (!isNewForm && formData?.updated_at) {
            patchState({
                autoSaveStatus: "saved",
                lastSavedAt: new Date(formData.updated_at),
                lastSavedFingerprint: draftFingerprint,
            })
            return
        }
        patchState({
            autoSaveStatus: "idle",
            lastSavedAt: null,
            lastSavedFingerprint: draftFingerprint,
        })
    }, [draftFingerprint, formData?.updated_at, formId, isNewForm, patchState, state.hasHydrated])

    const requestDeletePage = (pageId: number) => {
        patchState({
            pageToDelete: pageId,
            showDeletePageDialog: true,
        })
    }

    const confirmDeletePage = () => {
        if (state.pageToDelete === null) {
            patchState({ showDeletePageDialog: false })
            return
        }
        deletePage(state.pageToDelete)
        patchState({
            showDeletePageDialog: false,
            pageToDelete: null,
        })
    }

    const handleSave = async () => {
        if (!state.formName.trim()) {
            toast.error("Form name is required")
            return
        }
        patchState({ isSaving: true })
        const finishSaving = () => patchState({ isSaving: false })
        try {
            const savedForm = await persistAutomationFormPayload({
                payload: draftPayload,
                isNewForm,
                id,
                pages,
                createFormMutation,
                updateFormMutation,
                setMappingsMutation,
                router,
                patchState,
            })
            patchState(buildSavedState(draftFingerprint, savedForm))
            toast.success("Form saved")
            finishSaving()
        } catch {
            patchState({ autoSaveStatus: "error" })
            toast.error("Failed to save form")
            finishSaving()
        }
    }

    useEffect(() => {
        if (!state.hasHydrated) return
        if (!state.formName.trim()) return
        if (draftFingerprint === state.lastSavedFingerprint) return
        if (state.isSaving || state.isPublishing) return
        if (
            createFormMutation.isPending ||
            updateFormMutation.isPending ||
            setMappingsMutation.isPending
        ) {
            return
        }

        let cancelled = false
        const timeout = setTimeout(() => {
            if (cancelled) return
            patchState({ autoSaveStatus: "saving" })
            const payload = buildAutomationDraftPayload(pages, {
                allowedMimeTypesText: state.allowedMimeTypesText,
                defaultTemplateId: state.defaultTemplateId,
                formDescription: state.formDescription,
                formName: state.formName,
                formPurpose: state.formPurpose,
                logoUrl: state.logoUrl,
                maxFileCount: state.maxFileCount,
                maxFileSizeMb: state.maxFileSizeMb,
                privacyNotice: state.privacyNotice,
                publicEyebrow: state.publicEyebrow,
                publicSubtitle: state.publicSubtitle,
                publicTitle: state.publicTitle,
            })

            persistAutomationFormPayload({
                payload,
                isNewForm,
                id,
                pages,
                createFormMutation,
                updateFormMutation,
                setMappingsMutation,
                router,
                patchState,
            })
                .then((savedForm) => {
                    if (cancelled) return
                    patchState(buildSavedState(draftFingerprint, savedForm))
                })
                .catch(() => {
                    if (cancelled) return
                    patchState({ autoSaveStatus: "error" })
                })
        }, 1200)

        return () => {
            cancelled = true
            clearTimeout(timeout)
        }
    }, [
        createFormMutation.isPending,
        createFormMutation,
        draftFingerprint,
        id,
        isNewForm,
        pages,
        patchState,
        router,
        setMappingsMutation,
        setMappingsMutation.isPending,
        state.allowedMimeTypesText,
        state.defaultTemplateId,
        state.formDescription,
        state.formName,
        state.formPurpose,
        state.hasHydrated,
        state.isPublishing,
        state.isSaving,
        state.lastSavedFingerprint,
        state.logoUrl,
        state.maxFileCount,
        state.maxFileSizeMb,
        state.privacyNotice,
        state.publicEyebrow,
        state.publicSubtitle,
        state.publicTitle,
        updateFormMutation,
        updateFormMutation.isPending,
    ])

    const handleLogoUploadClick = () => {
        logoInputRef.current?.click()
    }

    const handleLogoFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        event.target.value = ""
        if (!file) return

        try {
            const uploaded = await uploadLogoMutation.mutateAsync(file)
            patchState({
                logoUrl: uploaded.logo_url,
                customLogoUrl: uploaded.logo_url,
                useOrgLogo: false,
            })
            toast.success("Logo uploaded")
        } catch {
            toast.error("Failed to upload logo")
        }
    }

    const handleLogoUrlChange = (value: string) => {
        patchState({
            logoUrl: value,
            ...(state.useOrgLogo ? {} : { customLogoUrl: value }),
        })
    }

    const handleUseOrgLogoChange = (checked: boolean) => {
        if (checked) {
            if (!orgLogoAvailable || !orgLogoPath) {
                toast.error("Add an organization logo in Settings to use this option.")
                return
            }
            patchState({
                useOrgLogo: true,
                logoUrl: orgLogoPath,
                ...(state.logoUrl && state.logoUrl !== orgLogoPath ? { customLogoUrl: state.logoUrl } : {}),
            })
            return
        }

        patchState({
            useOrgLogo: false,
            logoUrl: state.customLogoUrl,
        })
    }

    const handleDefaultTemplateSelection = async (nextTemplateId: string | null) => {
        const normalizedTemplateId = nextTemplateId ?? ""
        patchState({ defaultTemplateId: normalizedTemplateId })
        if (!formId) return
        try {
            await updateDeliverySettingsMutation.mutateAsync({
                formId,
                payload: {
                    default_application_email_template_id: normalizedTemplateId || null,
                },
            })
        } catch {
            toast.error("Failed to update delivery template")
        }
    }

    const handleSetDefaultSurrogateApplication = async () => {
        if (!formId) {
            toast.error("Save the form first")
            return
        }
        if (state.formPurpose !== "surrogate_application") {
            toast.error("Only surrogate application forms can be set as default")
            return
        }
        if (!state.isPublished) {
            toast.error("Publish this form before setting it as default")
            return
        }
        try {
            await setDefaultSurrogateApplicationMutation.mutateAsync(formId)
            toast.success("Set as default surrogate application form")
        } catch {
            toast.error("Failed to set default form")
        }
    }

    const hasMissingCriticalMappings = () => {
        const missingCriticalMappings =
            state.formPurpose === "lead_capture"
                ? getMissingLeadCaptureMappings(pages, surrogateFieldMappings)
                : getMissingCriticalMappings(pages, surrogateFieldMappings)
        if (missingCriticalMappings.length === 0) {
            return false
        }

        const missingLabels = missingCriticalMappings.map((mapping) => mapping.label).join(", ")
        toast.error(`Add or map required identity fields before publishing: ${missingLabels}.`)
        return true
    }

    const handlePublish = () => {
        if (!state.formName.trim()) {
            toast.error("Form name is required")
            return
        }
        if (pages.every((page) => page.fields.length === 0)) {
            toast.error("Add at least one field before publishing")
            return
        }
        if (hasMissingCriticalMappings()) {
            return
        }
        patchState({ showPublishDialog: true })
    }

    const handlePreview = () => {
        if (pages.every((page) => page.fields.length === 0)) {
            toast.error("Add at least one field before previewing")
            return
        }
        patchState({ workspaceTab: "preview" })
    }

    const confirmPublish = async () => {
        if (hasMissingCriticalMappings()) {
            return
        }

        patchState({ isPublishing: true })
        const finishPublishing = () => patchState({ isPublishing: false })
        try {
            const savedForm = await persistAutomationFormPayload({
                payload: draftPayload,
                isNewForm,
                id,
                pages,
                createFormMutation,
                updateFormMutation,
                setMappingsMutation,
                router,
                patchState,
            })
            patchState(buildSavedState(draftFingerprint, savedForm))
            await publishFormMutation.mutateAsync(savedForm.id)
            patchState({
                isPublished: true,
                pendingSharePrompt: true,
            })
            const intakeLinkResult = await refetchIntakeLinks()
            if ((intakeLinkResult.data || []).length === 0) {
                patchState({ pendingSharePrompt: false })
            }
            patchState({ showPublishDialog: false })
            toast.success("Form published")
            finishPublishing()
        } catch {
            patchState({ autoSaveStatus: "error" })
            toast.error("Failed to publish form")
            finishPublishing()
        }
    }

    const sortedIntakeLinks = intakeLinks.toSorted((a, b) => {
        const left = new Date(a.created_at).getTime()
        const right = new Date(b.created_at).getTime()
        return right - left
    })
    const selectedQrLink = sortedIntakeLinks.find((link) => link.is_active) || sortedIntakeLinks[0] || null
    const {
        data: selectedEmbedHealth,
        isFetching: isEmbedHealthFetching,
        refetch: refetchEmbedHealth,
    } = useFormEmbedHealth(selectedQrLink?.id ?? null)

    const processedSubmissionHistory = submissionHistory.filter(
        (submission) =>
            submission.match_status === "linked" || submission.match_status === "lead_created",
    )
    const pendingSubmissionHistory = submissionHistory.filter(
        (submission) =>
            submission.match_status !== "linked" && submission.match_status !== "lead_created",
    )
    const visibleSubmissionHistory =
        state.submissionHistoryFilter === "pending"
            ? pendingSubmissionHistory
            : state.submissionHistoryFilter === "processed"
                ? processedSubmissionHistory
                : submissionHistory

    useEffect(() => {
        if (!state.pendingSharePrompt) return
        if (sortedIntakeLinks.length === 0) return
        patchState({
            showSharePrompt: true,
            pendingSharePrompt: false,
        })
    }, [patchState, sortedIntakeLinks.length, state.pendingSharePrompt])

    const handleUpdateEmbedSettings = async ({
        link,
        embedEnabled,
        allowedOrigins,
        trackingMode,
        consentText,
    }: {
        link: FormIntakeLinkRead
        embedEnabled: boolean
        allowedOrigins: string[]
        trackingMode: TrackingMode
        consentText: string | null
    }) => {
        if (!formId) {
            toast.error("Save the form first")
            return
        }
        try {
            await updateIntakeLinkMutation.mutateAsync({
                formId,
                linkId: link.id,
                payload: {
                    embed_enabled: embedEnabled,
                    allowed_embed_origins: allowedOrigins,
                    tracking_mode: trackingMode,
                    consent_text: consentText,
                },
            })
            await refetchIntakeLinks()
            toast.success("Embed settings updated")
        } catch (error) {
            const message = error instanceof Error ? error.message : "Failed to update embed settings"
            toast.error(message)
        }
    }

    const handleDownloadQrSvg = () => {
        const markup = getQrSvgMarkup()
        if (!markup) return

        const blob = new Blob([markup], { type: "image/svg+xml;charset=utf-8" })
        downloadBlob(blob, buildQrFilename(selectedQrLink, "svg"))
    }

    const handleDownloadQrPng = async () => {
        const markup = getQrSvgMarkup()
        if (!markup) return

        const svgBlob = new Blob([markup], { type: "image/svg+xml;charset=utf-8" })
        const svgUrl = URL.createObjectURL(svgBlob)
        const revokeSvgUrl = () => URL.revokeObjectURL(svgUrl)
        try {
            const image = new Image()
            image.crossOrigin = "anonymous"

            await new Promise<void>((resolve, reject) => {
                image.onload = () => resolve()
                image.onerror = () => reject(new Error("Failed to render QR image"))
                image.src = svgUrl
            })

            const canvas = document.createElement("canvas")
            canvas.width = image.width || 120
            canvas.height = image.height || 120
            const context = canvas.getContext("2d")
            if (!context) {
                toast.error("Could not prepare PNG download")
                revokeSvgUrl()
                return
            }
            context.drawImage(image, 0, 0)

            const blob = await new Promise<Blob | null>((resolve) =>
                canvas.toBlob((result) => resolve(result), "image/png"),
            )
            if (!blob) {
                toast.error("Could not generate PNG")
                revokeSvgUrl()
                return
            }
            downloadBlob(blob, buildQrFilename(selectedQrLink, "png"))
            revokeSvgUrl()
        } catch {
            revokeSvgUrl()
            toast.error("Failed to download PNG")
        }
    }

    const refreshSubmissionQueues = async () => {
        await Promise.all([
            refetchAmbiguousSubmissions(),
            refetchLeadQueueSubmissions(),
            refetchSubmissionHistory(),
        ])
    }

    const clearSubmissionSelection = () => {
        patchState({
            selectedQueueSubmissionId: null,
            manualSurrogateId: "",
            resolveReviewNotes: "",
        })
    }

    const handleResolveSubmissionToSurrogate = async (submissionId: string, surrogateId: string) => {
        try {
            await resolveSubmissionMatchMutation.mutateAsync({
                submissionId,
                payload: {
                    surrogate_id: surrogateId,
                    create_intake_lead: false,
                    review_notes: state.resolveReviewNotes.trim() || null,
                },
            })
            toast.success("Submission linked to surrogate")
            clearSubmissionSelection()
            await refreshSubmissionQueues()
        } catch {
            toast.error("Failed to link submission")
        }
    }

    const handleResolveSubmissionToLead = async (submissionId: string) => {
        try {
            await resolveSubmissionMatchMutation.mutateAsync({
                submissionId,
                payload: {
                    create_intake_lead: true,
                    review_notes: state.resolveReviewNotes.trim() || null,
                },
            })
            toast.success("Submission moved to intake lead")
            clearSubmissionSelection()
            await refreshSubmissionQueues()
        } catch {
            toast.error("Failed to move submission to intake lead")
        }
    }

    const handlePromoteLeadFromSubmission = async (submission: FormSubmissionRead) => {
        if (!submission.intake_lead_id) {
            toast.error("No intake lead linked to this submission")
            return
        }
        try {
            await promoteIntakeLeadMutation.mutateAsync({
                leadId: submission.intake_lead_id,
                payload: {},
            })
            toast.success("Intake lead promoted to surrogate")
            await refreshSubmissionQueues()
        } catch {
            toast.error("Failed to promote intake lead")
        }
    }

    const handleRetrySubmissionMatch = async (
        submission: FormSubmissionRead,
        options: {
            unlinkSurrogate?: boolean
            unlinkIntakeLead?: boolean
            rerunAutoMatch?: boolean
            createIntakeLeadIfUnmatched?: boolean
        },
        successMessage: string,
    ) => {
        try {
            await retrySubmissionMatchMutation.mutateAsync({
                submissionId: submission.id,
                payload: {
                    unlink_surrogate: options.unlinkSurrogate ?? true,
                    unlink_intake_lead: options.unlinkIntakeLead ?? false,
                    rerun_auto_match: options.rerunAutoMatch ?? true,
                    create_intake_lead_if_unmatched: options.createIntakeLeadIfUnmatched ?? false,
                    review_notes: state.resolveReviewNotes.trim() || null,
                },
            })
            toast.success(successMessage)
            patchState({
                selectedQueueSubmissionId: submission.id,
                manualSurrogateId: "",
            })
            await refreshSubmissionQueues()
        } catch {
            toast.error("Failed to reprocess submission")
        }
    }

    const handleLinkByManualSurrogateId = async () => {
        const submissionId = state.selectedQueueSubmissionId
        const surrogateId = state.manualSurrogateId.trim()
        if (!submissionId) return
        if (!surrogateId) {
            toast.error("Enter a surrogate ID")
            return
        }
        await handleResolveSubmissionToSurrogate(submissionId, surrogateId)
        patchState({ manualSurrogateId: "" })
    }

    const autoSaveLabel = getAutoSaveLabel(state, isDirty)

    const workspaceDocument = {
        pages,
        activePage,
        currentPage,
        selectedField,
        selectedFieldData,
        dropIndicatorId,
        isDragging,
        setActivePage,
        selectField,
        requestDeletePage,
        handleAddPage,
        handleDuplicatePage,
        handleDragStart,
        handleFieldDragStart,
        handleDragOver,
        handleCanvasDragOver,
        handleFieldDragOver,
        handleDrop,
        handleDropOnField,
        handleDragEnd,
        handleInsertField,
        handleUpdateField,
        handleDuplicateField,
        handleDeleteField,
        handleValidationChange,
        handleAddColumn,
        handleUpdateColumn,
        handleRemoveColumn,
        handleAddRow,
        handleUpdateRow,
        handleRemoveRow,
        handleShowIfChange,
        handleMappingChange,
        syncOptionKeys,
        addOption,
        removeOption,
        handleRenamePage,
        handleMovePage,
    }

    return {
        formId,
        isNewForm,
        showLoading: !isNewForm && (isFormLoading || isMappingsLoading),
        shouldRenderNull: !isNewForm && !formData,
        state,
        patchState,
        autoSaveLabel,
        workspaceProps: {
            desktopCanvasWidthClass: "max-w-[min(100%,72rem)]",
            canvasFrameClass: "rounded-[24px] border border-stone-200 bg-white p-4 sm:p-5",
            mappingOptions: surrogateFieldMappings,
            publicEyebrow: state.publicEyebrow,
            publicTitle: state.publicTitle,
            publicSubtitle: state.publicSubtitle,
            fieldLibrarySearch: state.fieldLibrarySearch,
            fieldLibraryCategory: state.fieldLibraryCategory,
            onFieldLibrarySearchChange: (value: string) => patchState({ fieldLibrarySearch: value }),
            onFieldLibraryCategoryChange: (value: string) => patchState({ fieldLibraryCategory: value }),
            document: workspaceDocument,
        },
        previewProps: {
            pages,
            activePage,
            publicEyebrow: state.publicEyebrow,
            publicTitle: state.publicTitle,
            publicSubtitle: state.publicSubtitle,
            resolvedLogoUrl,
            privacyNotice: state.privacyNotice,
            previewDevice: state.previewDevice,
            desktopCanvasWidthClass: "max-w-[min(100%,72rem)]",
            mobileCanvasWidthClass: "max-w-sm",
            onSetActivePage: setActivePage,
            onPreviewDeviceChange: (value: "desktop" | "mobile") => patchState({ previewDevice: value }),
        },
        settingsPanelProps: {
            formName: state.formName,
            formDescription: state.formDescription,
            formPurpose: state.formPurpose,
            publicEyebrow: state.publicEyebrow,
            publicTitle: state.publicTitle,
            publicSubtitle: state.publicSubtitle,
            logoUrl: state.logoUrl,
            resolvedLogoUrl,
            privacyNotice: state.privacyNotice,
            defaultTemplateId: state.defaultTemplateId,
            emailTemplates,
            maxFileSizeMb: state.maxFileSizeMb,
            maxFileCount: state.maxFileCount,
            allowedMimeTypesText: state.allowedMimeTypesText,
            useOrgLogo: state.useOrgLogo,
            orgLogoAvailable,
            logoInputRef,
            uploadLogoPending: uploadLogoMutation.isPending,
            isDefaultSurrogateApplication,
            setDefaultSurrogateApplicationPending: setDefaultSurrogateApplicationMutation.isPending,
            isPublished: state.isPublished,
            selectedQrLink,
            selectedEmbedHealth,
            isEmbedHealthFetching,
            onFormNameChange: (value: string) => patchState({ formName: value }),
            onFormDescriptionChange: (value: string) => patchState({ formDescription: value }),
            onFormPurposeChange: (value: FormPurpose) => patchState({ formPurpose: value }),
            onPublicEyebrowChange: (value: string) => patchState({ publicEyebrow: value }),
            onPublicTitleChange: (value: string) => patchState({ publicTitle: value }),
            onPublicSubtitleChange: (value: string) => patchState({ publicSubtitle: value }),
            onLogoUrlChange: handleLogoUrlChange,
            onPrivacyNoticeChange: (value: string) => patchState({ privacyNotice: value }),
            onDefaultTemplateChange: handleDefaultTemplateSelection,
            onUseOrgLogoChange: handleUseOrgLogoChange,
            onLogoUploadClick: handleLogoUploadClick,
            onLogoFileChange: handleLogoFileChange,
            onSetDefaultSurrogateApplication: handleSetDefaultSurrogateApplication,
            onOpenSharePrompt: () => patchState({ showSharePrompt: true }),
            onCopySharedLink: handleCopySharedLink,
            onDownloadQrSvg: handleDownloadQrSvg,
            onDownloadQrPng: handleDownloadQrPng,
            onRefreshEmbedHealth: () => {
                void refetchEmbedHealth()
            },
            onMaxFileSizeMbChange: (value: number) => patchState({ maxFileSizeMb: value }),
            onMaxFileCountChange: (value: number) => patchState({ maxFileCount: value }),
            onAllowedMimeTypesTextChange: (value: string) => patchState({ allowedMimeTypesText: value }),
        },
        submissionsPanelProps: {
            formId,
            pendingSubmissionHistory,
            processedSubmissionHistory,
            ambiguousSubmissions,
            leadQueueSubmissions,
            visibleSubmissionHistory,
            submissionHistoryFilter: state.submissionHistoryFilter,
            selectedQueueSubmissionId: state.selectedQueueSubmissionId,
            selectedMatchCandidates,
            isSubmissionHistoryLoading,
            isMatchCandidatesLoading,
            retrySubmissionMatchPending: retrySubmissionMatchMutation.isPending,
            resolveSubmissionMatchPending: resolveSubmissionMatchMutation.isPending,
            promoteIntakeLeadPending: promoteIntakeLeadMutation.isPending,
            manualSurrogateId: state.manualSurrogateId,
            resolveReviewNotes: state.resolveReviewNotes,
            readAnswerValue,
            formatSubmissionDateTime,
            submissionOutcomeLabel,
            submissionOutcomeBadgeClass,
            submissionReviewLabel,
            submissionReviewBadgeClass,
            onOpenApprovalQueue: () => router.push("/tasks?filter=my_tasks&focus=approvals"),
            onSubmissionHistoryFilterChange: (value: typeof state.submissionHistoryFilter) =>
                patchState({ submissionHistoryFilter: value }),
            onSelectQueueSubmission: (submissionId: string | null) => {
                patchState({
                    selectedQueueSubmissionId: submissionId,
                    manualSurrogateId: "",
                })
            },
            onManualSurrogateIdChange: (value: string) => patchState({ manualSurrogateId: value }),
            onResolveReviewNotesChange: (value: string) => patchState({ resolveReviewNotes: value }),
            onLinkByManualSurrogateId: handleLinkByManualSurrogateId,
            onResolveSubmissionToSurrogate: handleResolveSubmissionToSurrogate,
            onResolveSubmissionToLead: handleResolveSubmissionToLead,
            onRetrySubmissionMatch: handleRetrySubmissionMatch,
            onPromoteLeadFromSubmission: handlePromoteLeadFromSubmission,
        },
        onBack: () => router.push("/automation/forms"),
        onFormNameChange: (value: string) => patchState({ formName: value }),
        onWorkspaceTabChange: (value: string) => patchState({ workspaceTab: value as typeof state.workspaceTab }),
        onShareDialogOpenChange: (open: boolean) => patchState({ showSharePrompt: open }),
        onPublishDialogOpenChange: (open: boolean) => patchState({ showPublishDialog: open }),
        onDeletePageDialogOpenChange: (open: boolean) => {
            patchState({ showDeletePageDialog: open })
            if (!open) {
                patchState({ pageToDelete: null })
            }
        },
        handlePreview,
        handleSave,
        handlePublish,
        confirmPublish,
        confirmDeletePage,
        handleCopySharedLink,
        handleDownloadQrSvg,
        handleDownloadQrPng,
        handleUpdateEmbedSettings,
        updateIntakeLinkPending: updateIntakeLinkMutation.isPending,
    }
}

export type AutomationFormBuilderPageController = ReturnType<typeof useAutomationFormBuilderPage>
