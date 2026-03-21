"use client"

import { useCallback, useEffect, useMemo, useRef } from "react"
import { useParams, useRouter } from "next/navigation"
import { toast } from "sonner"

import { DEFAULT_FORM_SURROGATE_FIELD_OPTIONS } from "@/lib/api/forms"
import type { FormSchema } from "@/lib/api/forms"
import type { PlatformFormTemplate } from "@/lib/api/platform"
import {
    FALLBACK_FORM_PAGE,
    buildFormSchema,
    buildMappings,
    schemaToPages,
} from "@/lib/forms/form-builder-document"
import { useFormBuilderDocument } from "@/lib/forms/use-form-builder-document"
import { useTemplateFormBuilderState } from "@/lib/forms/use-template-form-builder-state"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import {
    useCreatePlatformFormTemplate,
    useDeletePlatformFormTemplate,
    usePlatformFormTemplate,
    usePublishPlatformFormTemplate,
    useUpdatePlatformFormTemplate,
} from "@/lib/hooks/use-platform-templates"

const surrogateFieldMappings = DEFAULT_FORM_SURROGATE_FIELD_OPTIONS

export function useTemplateFormBuilderPage() {
    const params = useParams<{ id: string }>()
    const idParam = params?.id
    const id = Array.isArray(idParam) ? idParam[0] : idParam ?? "new"
    const router = useRouter()
    const isNewForm = id === "new"
    const formId = isNewForm ? null : id

    const { data: templateData, isLoading: isFormLoading } = usePlatformFormTemplate(formId)
    const createTemplateMutation = useCreatePlatformFormTemplate()
    const updateTemplateMutation = useUpdatePlatformFormTemplate()
    const publishTemplateMutation = usePublishPlatformFormTemplate()
    const deleteTemplateMutation = useDeletePlatformFormTemplate()
    const lastSavedFingerprintRef = useRef<string>("")
    const currentVersionRef = useRef<number | null>(null)
    const templateIdRef = useRef<string | null>(isNewForm ? null : id)
    const saveQueueRef = useRef<Promise<void>>(Promise.resolve())
    const hydratedFormRef = useRef<string | null>(null)

    const { state, patchState, resetForForm, hydrateFromTemplate } = useTemplateFormBuilderState(isNewForm)
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
        deletePage,
        addOption,
        removeOption,
    } = useFormBuilderDocument()

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || ""
    const resolvedLogoUrl =
        state.logoUrl && state.logoUrl.startsWith("/") && apiBaseUrl ? `${apiBaseUrl}${state.logoUrl}` : state.logoUrl

    useEffect(() => {
        resetForForm(isNewForm)
        hydratedFormRef.current = null
        currentVersionRef.current = null
        templateIdRef.current = isNewForm ? null : id
        resetDocument()
    }, [formId, id, isNewForm, resetDocument, resetForForm])

    useEffect(() => {
        if (isNewForm || !templateData || state.hasHydrated) return

        const draft = templateData.draft
        const published = templateData.published
        const settings = (draft?.settings_json ?? published?.settings_json ?? {}) as Record<string, unknown>
        const schema = (draft?.schema_json ?? published?.schema_json ?? null) as FormSchema | null
        const mappingsRaw = settings.mappings
        const mappings = Array.isArray(mappingsRaw)
            ? (mappingsRaw as Array<{ field_key: string; surrogate_field: string }>)
            : []
        const mappingMap = new Map(
            mappings.map((mapping) => [mapping.field_key, mapping.surrogate_field]),
        )

        hydrateFromTemplate({
            name: draft?.name ?? published?.name ?? "",
            description: draft?.description ?? published?.description ?? "",
            settings,
            schema,
            mappingMap,
            publishedVersion: templateData.published_version ?? 0,
        })
        resetDocument(schema ? schemaToPages(schema, mappingMap) : [FALLBACK_FORM_PAGE])
    }, [hydrateFromTemplate, isNewForm, resetDocument, state.hasHydrated, templateData])

    useEffect(() => {
        const nextVersion = templateData?.current_version
        if (typeof nextVersion !== "number") return
        if (currentVersionRef.current === null || nextVersion > currentVersionRef.current) {
            currentVersionRef.current = nextVersion
        }
    }, [templateData?.current_version])

    const draftPayload = useMemo(() => {
        const allowedMimeTypes = state.allowedMimeTypesText
            .split(",")
            .map((entry) => entry.trim())
            .filter(Boolean)
        const mappings = buildMappings(pages)
        const settingsJson: Record<string, unknown> = {
            max_file_size_bytes: Math.max(1, Math.round(state.maxFileSizeMb * 1024 * 1024)),
            max_file_count: Math.max(0, Math.round(state.maxFileCount)),
            allowed_mime_types: allowedMimeTypes.length > 0 ? allowedMimeTypes : null,
        }
        if (mappings.length > 0) {
            settingsJson.mappings = mappings
        }

        return {
            name: state.formName.trim(),
            description: state.formDescription.trim() || null,
            schema_json: buildFormSchema(pages, {
                publicTitle: state.publicTitle,
                logoUrl: state.logoUrl,
                privacyNotice: state.privacyNotice,
            }),
            settings_json: settingsJson,
        }
    }, [
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
        if (!isNewForm && templateData?.updated_at) {
            patchState({
                autoSaveStatus: "saved",
                lastSavedAt: new Date(templateData.updated_at),
            })
            return
        }
        patchState({ autoSaveStatus: "idle" })
    }, [debouncedFingerprint, formId, isNewForm, patchState, state.hasHydrated, templateData?.updated_at])

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

    const markSaved = useCallback((fingerprint: string, savedForm?: PlatformFormTemplate) => {
        lastSavedFingerprintRef.current = fingerprint
        patchState({
            autoSaveStatus: "saved",
            lastSavedAt: savedForm?.updated_at ? new Date(savedForm.updated_at) : new Date(),
        })
    }, [patchState])

    const persistTemplate = useCallback(
        async (payloadOverride?: typeof draftPayload): Promise<PlatformFormTemplate> => {
            const payload = payloadOverride ?? draftPayload

            let savedTemplate: PlatformFormTemplate
            const templateId = templateIdRef.current
            if (!templateId) {
                savedTemplate = await createTemplateMutation.mutateAsync(payload)
                templateIdRef.current = savedTemplate.id
                router.replace(`/ops/templates/forms/${savedTemplate.id}`)
            } else {
                savedTemplate = await updateTemplateMutation.mutateAsync({
                    id: templateId,
                    payload: {
                        ...payload,
                        expected_version: currentVersionRef.current ?? templateData?.current_version ?? null,
                    },
                })
            }

            patchState({ isPublished: (savedTemplate.published_version ?? 0) > 0 })
            if (typeof savedTemplate.current_version === "number") {
                currentVersionRef.current = savedTemplate.current_version
            }
            return savedTemplate
        },
        [
            createTemplateMutation,
            draftPayload,
            patchState,
            router,
            templateData?.current_version,
            updateTemplateMutation,
        ],
    )

    const queueSave = useCallback(
        async (payloadOverride?: typeof draftPayload): Promise<PlatformFormTemplate> => {
            const run = () => persistTemplate(payloadOverride)
            const chained = saveQueueRef.current.then(run, run)
            saveQueueRef.current = chained.then(() => {}, () => {})
            return chained
        },
        [persistTemplate],
    )

    const handleSave = useCallback(async () => {
        if (!state.formName.trim()) {
            toast.error("Form name is required")
            return
        }
        patchState({ isSaving: true })
        try {
            const savedTemplate = await queueSave(draftPayload)
            markSaved(JSON.stringify(draftPayload), savedTemplate)
            toast.success("Template saved")
        } catch {
            patchState({ autoSaveStatus: "error" })
            toast.error("Failed to save template")
        } finally {
            patchState({ isSaving: false })
        }
    }, [draftPayload, markSaved, patchState, queueSave, state.formName])

    useEffect(() => {
        if (!state.hasHydrated) return
        if (!state.formName.trim()) return
        if (draftPayload !== debouncedPayload) return
        if (debouncedFingerprint === lastSavedFingerprintRef.current) return
        if (state.isSaving || state.isPublishing) return

        let cancelled = false
        patchState({ autoSaveStatus: "saving" })

        queueSave(debouncedPayload)
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
        debouncedFingerprint,
        debouncedPayload,
        draftPayload,
        markSaved,
        patchState,
        queueSave,
        state.formName,
        state.hasHydrated,
        state.isPublishing,
        state.isSaving,
    ])

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

    const handlePublish = useCallback(() => {
        if (!state.formName.trim()) {
            toast.error("Form name is required")
            return
        }
        if (pages.every((page) => page.fields.length === 0)) {
            toast.error("Add at least one field before publishing")
            return
        }
        patchState({ showPublishDialog: true })
    }, [pages, patchState, state.formName])

    const confirmPublish = useCallback(async () => {
        patchState({ isPublishing: true })
        try {
            const savedTemplate = await queueSave(draftPayload)
            markSaved(JSON.stringify(draftPayload), savedTemplate)
            await publishTemplateMutation.mutateAsync({
                id: savedTemplate.id,
                payload: {
                    publish_all: true,
                    org_ids: null,
                },
            })
            patchState({
                isPublished: true,
                showPublishDialog: false,
            })
            toast.success("Template published")
        } catch {
            patchState({ autoSaveStatus: "error" })
            toast.error("Failed to publish template")
        } finally {
            patchState({ isPublishing: false })
        }
    }, [draftPayload, markSaved, patchState, publishTemplateMutation, queueSave])

    const handleDeleteTemplate = useCallback(async () => {
        if (isNewForm || deleteTemplateMutation.isPending) return
        try {
            await deleteTemplateMutation.mutateAsync({ id })
            toast.success("Template deleted")
            patchState({ showDeleteTemplateDialog: false })
            router.push("/ops/templates?tab=forms")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to delete template")
        }
    }, [deleteTemplateMutation, id, isNewForm, patchState, router])

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
            handleRemoveColumn,
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
        deleteTemplateMutation,
        isNewForm,
        showLoading: !isNewForm && isFormLoading,
        shouldRenderNull: !isNewForm && !templateData,
        templateData,
        state,
        patchState,
        resolvedLogoUrl,
        surrogateFieldMappings,
        workspaceDocument,
        workspaceProps: {
            paletteWidthClass: "xl:w-[320px]",
            canvasWidthClass: state.isMobilePreview ? "max-w-sm" : "max-w-4xl",
            canvasFrameClass: state.isMobilePreview
                ? "rounded-[32px] border border-border bg-card p-6 shadow-sm"
                : "rounded-3xl border border-border bg-card p-6 shadow-sm sm:p-8",
            canvasScaleClass: state.isMobilePreview ? "origin-top scale-[0.96]" : "",
            canvasTypographyClass: state.isMobilePreview
                ? "text-[0.95rem] [&_input]:text-sm [&_textarea]:text-sm [&_label]:text-xs [&_p]:text-xs"
                : "",
            mappingOptions: surrogateFieldMappings,
            document: workspaceDocument,
        },
        formSettingsProps: {
            formName: state.formName,
            formDescription: state.formDescription,
            publicTitle: state.publicTitle,
            logoUrl: state.logoUrl,
            resolvedLogoUrl,
            privacyNotice: state.privacyNotice,
            maxFileSizeMb: state.maxFileSizeMb,
            maxFileCount: state.maxFileCount,
            allowedMimeTypesText: state.allowedMimeTypesText,
            onFormNameChange: (value: string) => patchState({ formName: value }),
            onFormDescriptionChange: (value: string) => patchState({ formDescription: value }),
            onPublicTitleChange: (value: string) => patchState({ publicTitle: value }),
            onLogoUrlChange: (value: string) => patchState({ logoUrl: value }),
            onPrivacyNoticeChange: (value: string) => patchState({ privacyNotice: value }),
            onMaxFileSizeMbChange: (value: number) => patchState({ maxFileSizeMb: value }),
            onMaxFileCountChange: (value: number) => patchState({ maxFileCount: value }),
            onAllowedMimeTypesTextChange: (value: string) => patchState({ allowedMimeTypesText: value }),
        },
        autoSaveLabel,
        handleDeleteTemplate,
        handlePreview,
        handlePublish,
        handleSave,
        confirmDeletePage,
        confirmPublish,
        onBack: () => router.push("/ops/templates?tab=forms"),
        onWorkspaceTabChange: (value: string) =>
            patchState({ workspaceTab: value as typeof state.workspaceTab }),
        onFormNameChange: (value: string) => patchState({ formName: value }),
        onToggleMobilePreview: () => patchState({ isMobilePreview: !state.isMobilePreview }),
        onDeletePageDialogOpenChange: (open: boolean) => {
            patchState({ showDeletePageDialog: open })
            if (!open) {
                patchState({ pageToDelete: null })
            }
        },
        onDeleteTemplateDialogOpenChange: (open: boolean) =>
            patchState({ showDeleteTemplateDialog: open }),
        onPublishDialogOpenChange: (open: boolean) => patchState({ showPublishDialog: open }),
    }
}

export type TemplateFormBuilderPageController = ReturnType<typeof useTemplateFormBuilderPage>
