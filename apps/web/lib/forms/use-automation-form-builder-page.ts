"use client"

import { useCallback, useEffect, useMemo, useRef } from "react"
import type { ChangeEvent } from "react"
import { useParams, useRouter } from "next/navigation"
import { toast } from "sonner"

import { useAuth } from "@/lib/auth-context"
import { DEFAULT_FORM_SURROGATE_FIELD_OPTIONS } from "@/lib/api/forms"
import type {
    FieldType,
    FormCreatePayload,
    FormIntakeLinkRead,
    FormPurpose,
    FormRead,
    FormSubmissionRead,
    FormSurrogateFieldOption,
} from "@/lib/api/forms"
import {
    FALLBACK_FORM_PAGE,
    buildFormSchema,
    buildMappings,
    schemaToPages,
    type BuilderFormPage,
} from "@/lib/forms/form-builder-document"
import { useAutomationFormBuilderState } from "@/lib/forms/use-automation-form-builder-state"
import { useFormBuilderDocument } from "@/lib/forms/use-form-builder-document"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import { useEmailTemplates } from "@/lib/hooks/use-email-templates"
import { useFormMappingOptions } from "@/lib/hooks/use-form-mapping-options"
import {
    useCreateForm,
    useForm,
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
    useUploadFormLogo,
} from "@/lib/hooks/use-forms"
import { useOrgSignature } from "@/lib/hooks/use-signature"

function getMissingCriticalMappings(
    pages: BuilderFormPage[],
    mappingOptions: FormSurrogateFieldOption[],
): FormSurrogateFieldOption[] {
    const criticalFieldTypeHints: Record<string, FieldType[]> = {
        full_name: ["text", "textarea"],
        email: ["email"],
        phone: ["phone"],
    }
    const hasCandidateField = (target: string) => {
        const hintedTypes = criticalFieldTypeHints[target]
        if (!hintedTypes || hintedTypes.length === 0) {
            return true
        }
        return pages.some((page) =>
            page.fields.some((field) => hintedTypes.includes(field.type)),
        )
    }

    const mappedFields = new Set(buildMappings(pages).map((mapping) => mapping.surrogate_field))
    const criticalMappings = mappingOptions.filter((option) => option.is_critical)
    const criticalValues =
        criticalMappings.length > 0
            ? criticalMappings.map((option) => option.value)
            : DEFAULT_FORM_SURROGATE_FIELD_OPTIONS.filter((option) => option.is_critical).map((option) => option.value)
    const optionByValue = new Map(mappingOptions.map((option) => [option.value, option]))
    const fallbackByValue = new Map(DEFAULT_FORM_SURROGATE_FIELD_OPTIONS.map((option) => [option.value, option]))

    return criticalValues
        .filter((value) => !mappedFields.has(value))
        .filter((value) => hasCandidateField(value))
        .map(
            (value) =>
                optionByValue.get(value) ??
                fallbackByValue.get(value) ??
                ({ value, label: value, is_critical: true } as FormSurrogateFieldOption),
        )
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
    const lastSavedFingerprintRef = useRef<string>("")
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
    const surrogateFieldMappings = useMemo(
        () =>
            mappingOptionsData && mappingOptionsData.length > 0
                ? mappingOptionsData
                : DEFAULT_FORM_SURROGATE_FIELD_OPTIONS,
        [mappingOptionsData],
    )

    const syncAutosaveMeta = useCallback((status: "idle" | "saved", savedAt: Date | null) => {
        patchState({
            autoSaveStatus: status,
            lastSavedAt: savedAt,
        })
    }, [patchState])

    useEffect(() => {
        resetForForm(isNewForm)
        hydratedFormRef.current = null
        lastSavedFingerprintRef.current = ""
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

    const draftPayload = useMemo<FormCreatePayload>(() => {
        const allowedMimeTypes = state.allowedMimeTypesText
            .split(",")
            .map((entry) => entry.trim())
            .filter(Boolean)
        return {
            name: state.formName.trim(),
            description: state.formDescription.trim() || null,
            purpose: state.formPurpose,
            form_schema: buildFormSchema(pages, {
                publicTitle: state.publicTitle,
                logoUrl: state.logoUrl,
                privacyNotice: state.privacyNotice,
            }),
            max_file_size_bytes: Math.max(1, Math.round(state.maxFileSizeMb * 1024 * 1024)),
            max_file_count: Math.max(0, Math.round(state.maxFileCount)),
            allowed_mime_types: allowedMimeTypes.length > 0 ? allowedMimeTypes : null,
            default_application_email_template_id: state.defaultTemplateId || null,
        }
    }, [
        pages,
        state.allowedMimeTypesText,
        state.defaultTemplateId,
        state.formDescription,
        state.formName,
        state.formPurpose,
        state.logoUrl,
        state.maxFileCount,
        state.maxFileSizeMb,
        state.privacyNotice,
        state.publicTitle,
    ])
    const debouncedPayload = useDebouncedValue(draftPayload, 1200)
    const debouncedFingerprint = useMemo(
        () => JSON.stringify(debouncedPayload),
        [debouncedPayload],
    )
    const draftIsDebounced = draftPayload === debouncedPayload
    const isDirty = !draftIsDebounced || debouncedFingerprint !== lastSavedFingerprintRef.current

    useEffect(() => {
        if (!state.hasHydrated) return
        const identity = isNewForm ? "new" : formId || "unknown"
        if (hydratedFormRef.current === identity) return
        hydratedFormRef.current = identity
        lastSavedFingerprintRef.current = debouncedFingerprint
        if (!isNewForm && formData?.updated_at) {
            syncAutosaveMeta("saved", new Date(formData.updated_at))
            return
        }
        syncAutosaveMeta("idle", null)
    }, [debouncedFingerprint, formData?.updated_at, formId, isNewForm, state.hasHydrated, syncAutosaveMeta])

    const requestDeletePage = useCallback((pageId: number) => {
        patchState({
            pageToDelete: pageId,
            showDeletePageDialog: true,
        })
    }, [patchState])

    const confirmDeletePage = useCallback(() => {
        if (state.pageToDelete === null) {
            patchState({ showDeletePageDialog: false })
            return
        }
        deletePage(state.pageToDelete)
        patchState({
            showDeletePageDialog: false,
            pageToDelete: null,
        })
    }, [deletePage, patchState, state.pageToDelete])

    const markSaved = useCallback((fingerprint: string, savedForm?: FormRead) => {
        lastSavedFingerprintRef.current = fingerprint
        patchState({
            autoSaveStatus: "saved",
            lastSavedAt: savedForm?.updated_at ? new Date(savedForm.updated_at) : new Date(),
        })
    }, [patchState])

    const persistForm = useCallback(
        async (payloadOverride?: FormCreatePayload): Promise<FormRead> => {
            const payload = payloadOverride ?? draftPayload

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
        },
        [
            createFormMutation,
            draftPayload,
            id,
            isNewForm,
            pages,
            patchState,
            router,
            setMappingsMutation,
            updateFormMutation,
        ],
    )

    const handleSave = useCallback(async () => {
        if (!state.formName.trim()) {
            toast.error("Form name is required")
            return
        }
        patchState({ isSaving: true })
        try {
            const savedForm = await persistForm(draftPayload)
            markSaved(JSON.stringify(draftPayload), savedForm)
            toast.success("Form saved")
        } catch {
            patchState({ autoSaveStatus: "error" })
            toast.error("Failed to save form")
        } finally {
            patchState({ isSaving: false })
        }
    }, [draftPayload, markSaved, patchState, persistForm, state.formName])

    useEffect(() => {
        if (!state.hasHydrated) return
        if (!state.formName.trim()) return
        if (draftPayload !== debouncedPayload) return
        if (debouncedFingerprint === lastSavedFingerprintRef.current) return
        if (state.isSaving || state.isPublishing) return
        if (
            createFormMutation.isPending ||
            updateFormMutation.isPending ||
            setMappingsMutation.isPending
        ) {
            return
        }

        let cancelled = false
        patchState({ autoSaveStatus: "saving" })

        persistForm(debouncedPayload)
            .then((savedForm) => {
                if (cancelled) return
                markSaved(debouncedFingerprint, savedForm)
            })
            .catch(() => {
                if (cancelled) return
                patchState({ autoSaveStatus: "error" })
            })

        return () => {
            cancelled = true
        }
    }, [
        createFormMutation.isPending,
        debouncedFingerprint,
        debouncedPayload,
        draftPayload,
        markSaved,
        patchState,
        persistForm,
        setMappingsMutation.isPending,
        state.formName,
        state.hasHydrated,
        state.isPublishing,
        state.isSaving,
        updateFormMutation.isPending,
    ])

    const handleLogoUploadClick = useCallback(() => {
        logoInputRef.current?.click()
    }, [])

    const handleLogoFileChange = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
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
    }, [patchState, uploadLogoMutation])

    const handleLogoUrlChange = useCallback((value: string) => {
        patchState({
            logoUrl: value,
            ...(state.useOrgLogo ? {} : { customLogoUrl: value }),
        })
    }, [patchState, state.useOrgLogo])

    const handleUseOrgLogoChange = useCallback((checked: boolean) => {
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
    }, [orgLogoAvailable, orgLogoPath, patchState, state.customLogoUrl, state.logoUrl])

    const handleDefaultTemplateSelection = useCallback(async (nextTemplateId: string | null) => {
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
    }, [formId, patchState, updateDeliverySettingsMutation])

    const handleSetDefaultSurrogateApplication = useCallback(async () => {
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
    }, [formId, setDefaultSurrogateApplicationMutation, state.formPurpose, state.isPublished])

    const hasMissingCriticalMappings = useCallback(() => {
        const missingCriticalMappings = getMissingCriticalMappings(pages, surrogateFieldMappings)
        if (missingCriticalMappings.length === 0) {
            return false
        }

        const missingLabels = missingCriticalMappings.map((mapping) => mapping.label).join(", ")
        toast.error(`Map required surrogate fields before publishing: ${missingLabels}.`)
        return true
    }, [pages, surrogateFieldMappings])

    const handlePublish = useCallback(() => {
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
    }, [hasMissingCriticalMappings, pages, patchState, state.formName])

    const handlePreview = useCallback(() => {
        if (pages.every((page) => page.fields.length === 0)) {
            toast.error("Add at least one field before previewing")
            return
        }

        const previewKey = formId || "draft"
        const previewPayload = {
            form_id: previewKey,
            name: state.formName.trim() || "Untitled Form",
            description: state.formDescription.trim() || null,
            form_schema: buildFormSchema(pages, {
                publicTitle: state.publicTitle,
                logoUrl: state.logoUrl,
                privacyNotice: state.privacyNotice,
            }),
            max_file_size_bytes: Math.max(1, Math.round(state.maxFileSizeMb * 1024 * 1024)),
            max_file_count: Math.max(0, Math.round(state.maxFileCount)),
            allowed_mime_types: (() => {
                const parsed = state.allowedMimeTypesText
                    .split(",")
                    .map((entry) => entry.trim())
                    .filter(Boolean)
                return parsed.length > 0 ? parsed : null
            })(),
            generated_at: new Date().toISOString(),
        }

        try {
            window.localStorage.setItem(`form-preview:${previewKey}`, JSON.stringify(previewPayload))
            window.open(`/apply/preview?formId=${encodeURIComponent(previewKey)}`, "_blank")
        } catch {
            toast.error("Failed to open preview")
        }
    }, [
        formId,
        pages,
        state.allowedMimeTypesText,
        state.formDescription,
        state.formName,
        state.logoUrl,
        state.maxFileCount,
        state.maxFileSizeMb,
        state.privacyNotice,
        state.publicTitle,
    ])

    const confirmPublish = useCallback(async () => {
        if (hasMissingCriticalMappings()) {
            return
        }

        patchState({ isPublishing: true })
        try {
            const savedForm = await persistForm(draftPayload)
            markSaved(JSON.stringify(draftPayload), savedForm)
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
        } catch {
            patchState({ autoSaveStatus: "error" })
            toast.error("Failed to publish form")
        } finally {
            patchState({ isPublishing: false })
        }
    }, [draftPayload, hasMissingCriticalMappings, markSaved, patchState, persistForm, publishFormMutation, refetchIntakeLinks])

    const sortedIntakeLinks = useMemo(
        () =>
            [...intakeLinks].sort((a, b) => {
                const left = new Date(a.created_at).getTime()
                const right = new Date(b.created_at).getTime()
                return right - left
            }),
        [intakeLinks],
    )
    const selectedQrLink = sortedIntakeLinks.find((link) => link.is_active) || sortedIntakeLinks[0] || null

    const processedSubmissionHistory = useMemo(
        () =>
            submissionHistory.filter(
                (submission) =>
                    submission.match_status === "linked" || submission.match_status === "lead_created",
            ),
        [submissionHistory],
    )
    const pendingSubmissionHistory = useMemo(
        () =>
            submissionHistory.filter(
                (submission) =>
                    submission.match_status !== "linked" && submission.match_status !== "lead_created",
            ),
        [submissionHistory],
    )
    const visibleSubmissionHistory = useMemo(() => {
        if (state.submissionHistoryFilter === "pending") return pendingSubmissionHistory
        if (state.submissionHistoryFilter === "processed") return processedSubmissionHistory
        return submissionHistory
    }, [
        pendingSubmissionHistory,
        processedSubmissionHistory,
        state.submissionHistoryFilter,
        submissionHistory,
    ])

    useEffect(() => {
        if (!state.pendingSharePrompt) return
        if (sortedIntakeLinks.length === 0) return
        patchState({
            showSharePrompt: true,
            pendingSharePrompt: false,
        })
    }, [patchState, sortedIntakeLinks, state.pendingSharePrompt])

    const handleCopySharedLink = useCallback(async (link: FormIntakeLinkRead) => {
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
    }, [])

    const getQrSvgMarkup = useCallback(() => {
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
    }, [])

    const buildQrFilename = useCallback((extension: "svg" | "png") => {
        const baseRaw = selectedQrLink?.campaign_name || selectedQrLink?.event_name || selectedQrLink?.slug || "intake-link"
        const base = baseRaw
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "")
        return `${base || "intake-link"}-qr.${extension}`
    }, [selectedQrLink])

    const downloadBlob = useCallback((blob: Blob, filename: string) => {
        const downloadUrl = URL.createObjectURL(blob)
        const anchor = document.createElement("a")
        anchor.href = downloadUrl
        anchor.download = filename
        document.body.appendChild(anchor)
        anchor.click()
        anchor.remove()
        URL.revokeObjectURL(downloadUrl)
    }, [])

    const handleDownloadQrSvg = useCallback(() => {
        const markup = getQrSvgMarkup()
        if (!markup) return

        const blob = new Blob([markup], { type: "image/svg+xml;charset=utf-8" })
        downloadBlob(blob, buildQrFilename("svg"))
    }, [buildQrFilename, downloadBlob, getQrSvgMarkup])

    const handleDownloadQrPng = useCallback(async () => {
        const markup = getQrSvgMarkup()
        if (!markup) return

        const svgBlob = new Blob([markup], { type: "image/svg+xml;charset=utf-8" })
        const svgUrl = URL.createObjectURL(svgBlob)
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
                return
            }
            context.drawImage(image, 0, 0)

            const blob = await new Promise<Blob | null>((resolve) =>
                canvas.toBlob((result) => resolve(result), "image/png"),
            )
            if (!blob) {
                toast.error("Could not generate PNG")
                return
            }
            downloadBlob(blob, buildQrFilename("png"))
        } catch {
            toast.error("Failed to download PNG")
        } finally {
            URL.revokeObjectURL(svgUrl)
        }
    }, [buildQrFilename, downloadBlob, getQrSvgMarkup])

    const readAnswerValue = useCallback((submission: FormSubmissionRead, keys: string[]) => {
        for (const key of keys) {
            const rawValue = submission.answers?.[key]
            if (typeof rawValue === "string" && rawValue.trim()) {
                return rawValue.trim()
            }
        }
        return "—"
    }, [])

    const formatSubmissionDateTime = useCallback((isoString: string) => {
        const value = new Date(isoString)
        if (Number.isNaN(value.getTime())) return "—"
        return value.toLocaleString()
    }, [])

    const submissionOutcomeLabel = useCallback((submission: FormSubmissionRead) => {
        if (submission.match_status === "linked") return "Matched"
        if (submission.match_status === "lead_created") return "Lead Created"
        return "Pending Match"
    }, [])

    const submissionOutcomeBadgeClass = useCallback((submission: FormSubmissionRead) => {
        if (submission.match_status === "linked") {
            return "border-emerald-200 bg-emerald-50 text-emerald-700"
        }
        if (submission.match_status === "lead_created") {
            return "border-blue-200 bg-blue-50 text-blue-700"
        }
        return "border-amber-200 bg-amber-50 text-amber-700"
    }, [])

    const submissionReviewLabel = useCallback((submission: FormSubmissionRead) => {
        if (submission.status === "approved") return "Approved"
        if (submission.status === "rejected") return "Rejected"
        return "Pending Review"
    }, [])

    const submissionReviewBadgeClass = useCallback((submission: FormSubmissionRead) => {
        if (submission.status === "approved") {
            return "border-emerald-200 bg-emerald-50 text-emerald-700"
        }
        if (submission.status === "rejected") {
            return "border-red-200 bg-red-50 text-red-700"
        }
        return "border-stone-200 bg-stone-100 text-stone-700"
    }, [])

    const refreshSubmissionQueues = useCallback(async () => {
        await Promise.all([
            refetchAmbiguousSubmissions(),
            refetchLeadQueueSubmissions(),
            refetchSubmissionHistory(),
        ])
    }, [refetchAmbiguousSubmissions, refetchLeadQueueSubmissions, refetchSubmissionHistory])

    const clearSubmissionSelection = useCallback(() => {
        patchState({
            selectedQueueSubmissionId: null,
            manualSurrogateId: "",
            resolveReviewNotes: "",
        })
    }, [patchState])

    const handleResolveSubmissionToSurrogate = useCallback(async (submissionId: string, surrogateId: string) => {
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
    }, [clearSubmissionSelection, refreshSubmissionQueues, resolveSubmissionMatchMutation, state.resolveReviewNotes])

    const handleResolveSubmissionToLead = useCallback(async (submissionId: string) => {
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
    }, [clearSubmissionSelection, refreshSubmissionQueues, resolveSubmissionMatchMutation, state.resolveReviewNotes])

    const handlePromoteLeadFromSubmission = useCallback(async (submission: FormSubmissionRead) => {
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
    }, [promoteIntakeLeadMutation, refreshSubmissionQueues])

    const handleRetrySubmissionMatch = useCallback(async (
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
    }, [patchState, refreshSubmissionQueues, retrySubmissionMatchMutation, state.resolveReviewNotes])

    const handleLinkByManualSurrogateId = useCallback(async () => {
        const submissionId = state.selectedQueueSubmissionId
        const surrogateId = state.manualSurrogateId.trim()
        if (!submissionId) return
        if (!surrogateId) {
            toast.error("Enter a surrogate ID")
            return
        }
        await handleResolveSubmissionToSurrogate(submissionId, surrogateId)
        patchState({ manualSurrogateId: "" })
    }, [handleResolveSubmissionToSurrogate, patchState, state.manualSurrogateId, state.selectedQueueSubmissionId])

    const autoSaveLabel = useMemo(() => {
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
    }, [isDirty, state.autoSaveStatus, state.hasHydrated, state.isSaving, state.lastSavedAt])

    const workspaceDocument = useMemo(
        () => ({
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
            handleShowIfChange,
            handleMappingChange,
            syncOptionKeys,
            addOption,
            removeOption,
            handleRenamePage,
            handleMovePage,
        }),
        [
            activePage,
            addOption,
            currentPage,
            dropIndicatorId,
            handleAddColumn,
            handleAddPage,
            handleCanvasDragOver,
            handleDeleteField,
            handleDragEnd,
            handleDragOver,
            handleDragStart,
            handleDrop,
            handleDropOnField,
            handleDuplicateField,
            handleDuplicatePage,
            handleFieldDragOver,
            handleFieldDragStart,
            handleInsertField,
            handleMappingChange,
            handleMovePage,
            handleRemoveColumn,
            handleRenamePage,
            handleShowIfChange,
            handleUpdateColumn,
            handleUpdateField,
            handleValidationChange,
            isDragging,
            pages,
            removeOption,
            requestDeletePage,
            selectField,
            selectedField,
            selectedFieldData,
            setActivePage,
            syncOptionKeys,
        ],
    )

    return {
        formId,
        isNewForm,
        showLoading: !isNewForm && (isFormLoading || isMappingsLoading),
        shouldRenderNull: !isNewForm && !formData,
        state,
        patchState,
        autoSaveLabel,
        workspaceProps: {
            desktopCanvasWidthClass: "max-w-3xl",
            mobileCanvasWidthClass: "max-w-sm",
            canvasFrameClass: "rounded-3xl border border-border bg-card p-6 shadow-sm sm:p-8",
            mappingOptions: surrogateFieldMappings,
            formName: state.formName,
            formDescription: state.formDescription,
            publicTitle: state.publicTitle,
            resolvedLogoUrl,
            privacyNotice: state.privacyNotice,
            canvasMode: state.canvasMode,
            previewDevice: state.previewDevice,
            fieldLibraryOpen: state.fieldLibraryOpen,
            fieldLibrarySearch: state.fieldLibrarySearch,
            fieldLibraryCategory: state.fieldLibraryCategory,
            onCanvasModeChange: (value: "compose" | "preview") => patchState({ canvasMode: value }),
            onPreviewDeviceChange: (value: "desktop" | "mobile") => patchState({ previewDevice: value }),
            onFieldLibraryOpenChange: (open: boolean) => patchState({ fieldLibraryOpen: open }),
            onFieldLibrarySearchChange: (value: string) => patchState({ fieldLibrarySearch: value }),
            onFieldLibraryCategoryChange: (value: string) => patchState({ fieldLibraryCategory: value }),
            document: workspaceDocument,
        },
        settingsPanelProps: {
            formName: state.formName,
            formDescription: state.formDescription,
            formPurpose: state.formPurpose,
            publicTitle: state.publicTitle,
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
            onFormNameChange: (value: string) => patchState({ formName: value }),
            onFormDescriptionChange: (value: string) => patchState({ formDescription: value }),
            onFormPurposeChange: (value: FormPurpose) => patchState({ formPurpose: value }),
            onPublicTitleChange: (value: string) => patchState({ publicTitle: value }),
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
    }
}

export type AutomationFormBuilderPageController = ReturnType<typeof useAutomationFormBuilderPage>
