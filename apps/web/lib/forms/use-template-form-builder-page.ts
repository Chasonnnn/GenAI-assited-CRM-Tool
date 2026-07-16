"use client"

import { useRef } from "react"
import { useParams, useRouter } from "next/navigation"
import { toast } from "@/components/ui/toast"

import { DEFAULT_FORM_SURROGATE_FIELD_OPTIONS } from "@/lib/api/forms"
import type { FormSchema } from "@/lib/api/forms"
import type { PlatformFormTemplate } from "@/lib/api/platform"
import {
    FALLBACK_FORM_PAGE,
    buildFormSchema,
    buildMappings,
    schemaToPages,
} from "@/lib/forms/form-builder-document"
import { useFormBuilderAutosave } from "@/lib/forms/use-form-builder-autosave"
import { useFormBuilderDocument } from "@/lib/forms/use-form-builder-document"
import { useTemplateFormBuilderState } from "@/lib/forms/use-template-form-builder-state"
import type { TemplateBuilderState } from "@/lib/forms/use-template-form-builder-state"
import {
    useCreatePlatformFormTemplate,
    useDeletePlatformFormTemplate,
    usePlatformFormTemplate,
    usePublishPlatformFormTemplate,
    useUpdatePlatformFormTemplate,
} from "@/lib/hooks/use-platform-templates"

const surrogateFieldMappings = DEFAULT_FORM_SURROGATE_FIELD_OPTIONS

type TemplateDraftValues = Pick<
    TemplateBuilderState,
    | "allowedMimeTypesText"
    | "formDescription"
    | "formName"
    | "logoUrl"
    | "maxFileCount"
    | "maxFileSizeMb"
    | "privacyNotice"
    | "publicEyebrow"
    | "publicSubtitle"
    | "publicTitle"
>

type TemplateDraftPayload = {
    name: string
    description: string | null
    schema_json: FormSchema
    settings_json: Record<string, unknown>
}

type SaveQueueRef = {
    current: Promise<void> | null
}

type TemplateSaveIdentityRef = {
    current: {
        currentVersion: number | null
        routeKey: string
        templateId: string | null
    } | null
}

type TemplateCreateMutation = {
    mutateAsync: (payload: TemplateDraftPayload) => Promise<PlatformFormTemplate>
}

type TemplateUpdateMutation = {
    mutateAsync: (variables: {
        id: string
        payload: TemplateDraftPayload & { expected_version: number | null }
    }) => Promise<PlatformFormTemplate>
}

type TemplateRouter = ReturnType<typeof useRouter>

const buildTemplateDraftPayload = (
    pages: ReturnType<typeof useFormBuilderDocument>["pages"],
    state: TemplateDraftValues,
): TemplateDraftPayload => {
    const allowedMimeTypes: string[] = []
    for (const entry of state.allowedMimeTypesText.split(",")) {
        const trimmedEntry = entry.trim()
        if (trimmedEntry) allowedMimeTypes.push(trimmedEntry)
    }
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
            publicEyebrow: state.publicEyebrow,
            publicTitle: state.publicTitle,
            publicSubtitle: state.publicSubtitle,
            logoUrl: state.logoUrl,
            privacyNotice: state.privacyNotice,
        }),
        settings_json: settingsJson,
    }
}

const buildSavedState = (fingerprint: string, savedForm?: PlatformFormTemplate): Partial<TemplateBuilderState> => ({
    autoSaveStatus: "saved",
    lastSavedAt: savedForm?.updated_at ? new Date(savedForm.updated_at) : new Date(),
    lastSavedFingerprint: fingerprint,
})

const queueTemplateSave = <T>(saveQueueRef: SaveQueueRef, run: () => Promise<T>): Promise<T> => {
    const currentQueue = saveQueueRef.current ?? Promise.resolve()
    const chained = currentQueue.then(run, run)
    saveQueueRef.current = chained.then(() => {}, () => {})
    return chained
}

const persistTemplatePayload = async ({
    payload,
    templateIdentityRef,
    templateKey,
    routeTemplateId,
    createTemplateMutation,
    updateTemplateMutation,
    router,
    patchState,
    templateCurrentVersion,
}: {
    payload: TemplateDraftPayload
    templateIdentityRef: TemplateSaveIdentityRef
    templateKey: string
    routeTemplateId: string | null
    createTemplateMutation: TemplateCreateMutation
    updateTemplateMutation: TemplateUpdateMutation
    router: TemplateRouter
    patchState: (payload: Partial<TemplateBuilderState>) => void
    templateCurrentVersion: number | null | undefined
}): Promise<PlatformFormTemplate> => {
    let savedTemplate: PlatformFormTemplate
    const trackedIdentity =
        templateIdentityRef.current?.routeKey === templateKey
            ? templateIdentityRef.current
            : null
    const templateId = trackedIdentity?.templateId ?? routeTemplateId
    const expectedVersions = [
        trackedIdentity?.currentVersion,
        templateCurrentVersion,
    ].filter((version): version is number => typeof version === "number")
    const expectedVersion =
        expectedVersions.length > 0 ? Math.max(...expectedVersions) : null
    if (!templateId) {
        savedTemplate = await createTemplateMutation.mutateAsync(payload)
        router.replace(`/ops/templates/forms/${savedTemplate.id}`)
    } else {
        savedTemplate = await updateTemplateMutation.mutateAsync({
            id: templateId,
            payload: {
                ...payload,
                expected_version: expectedVersion,
            },
        })
    }

    patchState({ isPublished: (savedTemplate.published_version ?? 0) > 0 })
    templateIdentityRef.current = {
        currentVersion:
            typeof savedTemplate.current_version === "number"
                ? savedTemplate.current_version
                : expectedVersion,
        routeKey: templateKey,
        templateId: savedTemplate.id,
    }
    return savedTemplate
}

const getAutoSaveLabel = (state: TemplateBuilderState, isDirty: boolean) => {
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

export function useTemplateFormBuilderPage() {
    const params = useParams<{ id: string }>()
    const idParam = params?.id
    const id = Array.isArray(idParam) ? idParam[0] : idParam ?? "new"
    const router = useRouter()
    const isNewForm = id === "new"
    const formId = isNewForm ? null : id
    const templateKey = formId ?? "new"

    const { data: templateData, isLoading: isFormLoading } = usePlatformFormTemplate(formId)
    const createTemplateMutation = useCreatePlatformFormTemplate()
    const updateTemplateMutation = useUpdatePlatformFormTemplate()
    const publishTemplateMutation = usePublishPlatformFormTemplate()
    const deleteTemplateMutation = useDeletePlatformFormTemplate()
    const templateIdentityRef = useRef<TemplateSaveIdentityRef["current"]>(null)
    const saveQueueRef = useRef<Promise<void> | null>(null)

    const { state, patchState, resetForForm, hydrateFromTemplate } =
        useTemplateFormBuilderState(templateKey, isNewForm)
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

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || ""
    const resolvedLogoUrl =
        state.logoUrl && state.logoUrl.startsWith("/") && apiBaseUrl ? `${apiBaseUrl}${state.logoUrl}` : state.logoUrl

    if (state.templateKey !== templateKey) {
        resetForForm(templateKey, isNewForm)
        resetDocument()
    } else if (
        !isNewForm &&
        templateData &&
        templateData.id === formId &&
        !state.hasHydrated
    ) {
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
    }

    const draftPayload = buildTemplateDraftPayload(pages, state)
    const draftFingerprint = JSON.stringify(draftPayload)
    const isDirty = draftFingerprint !== state.lastSavedFingerprint

    if (state.hasHydrated && state.baselineTemplateKey !== templateKey) {
        if (!isNewForm && templateData?.updated_at) {
            patchState({
                autoSaveStatus: "saved",
                baselineTemplateKey: templateKey,
                lastSavedAt: new Date(templateData.updated_at),
                lastSavedFingerprint: draftFingerprint,
            })
        } else {
            patchState({
                autoSaveStatus: "idle",
                baselineTemplateKey: templateKey,
                lastSavedFingerprint: draftFingerprint,
            })
        }
    }

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
            const savedTemplate = await queueTemplateSave(saveQueueRef, () =>
                persistTemplatePayload({
                    payload: draftPayload,
                    templateIdentityRef,
                    templateKey,
                    routeTemplateId: formId,
                    createTemplateMutation,
                    updateTemplateMutation,
                    router,
                    patchState,
                    templateCurrentVersion: templateData?.current_version,
                }),
            )
            patchState(buildSavedState(draftFingerprint, savedTemplate))
            toast.success("Template saved")
            finishSaving()
        } catch {
            patchState({ autoSaveStatus: "error" })
            toast.error("Failed to save template")
            finishSaving()
        }
    }

    useFormBuilderAutosave({
        enabled:
            state.hasHydrated &&
            Boolean(state.formName.trim()) &&
            !state.isSaving &&
            !state.isPublishing,
        fingerprint: draftFingerprint,
        savedFingerprint: state.lastSavedFingerprint,
        save: () => {
            const payload = buildTemplateDraftPayload(pages, {
                allowedMimeTypesText: state.allowedMimeTypesText,
                formDescription: state.formDescription,
                formName: state.formName,
                logoUrl: state.logoUrl,
                maxFileCount: state.maxFileCount,
                maxFileSizeMb: state.maxFileSizeMb,
                privacyNotice: state.privacyNotice,
                publicEyebrow: state.publicEyebrow,
                publicSubtitle: state.publicSubtitle,
                publicTitle: state.publicTitle,
            })
            return queueTemplateSave(saveQueueRef, () =>
                persistTemplatePayload({
                    payload,
                    templateIdentityRef,
                    templateKey,
                    routeTemplateId: formId,
                    createTemplateMutation,
                    updateTemplateMutation,
                    router,
                    patchState,
                    templateCurrentVersion: templateData?.current_version,
                }),
            )
        },
        onSaving: () => patchState({ autoSaveStatus: "saving" }),
        onSaved: (savedForm) => patchState(buildSavedState(draftFingerprint, savedForm)),
        onError: () => patchState({ autoSaveStatus: "error" }),
    })

    const handlePreview = () => {
        if (pages.every((page) => page.fields.length === 0)) {
            toast.error("Add at least one field before previewing")
            return
        }
        patchState({ workspaceTab: "preview" })
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
        patchState({ showPublishDialog: true })
    }

    const confirmPublish = async () => {
        patchState({ isPublishing: true })
        const finishPublishing = () => patchState({ isPublishing: false })
        try {
            const savedTemplate = await queueTemplateSave(saveQueueRef, () =>
                persistTemplatePayload({
                    payload: draftPayload,
                    templateIdentityRef,
                    templateKey,
                    routeTemplateId: formId,
                    createTemplateMutation,
                    updateTemplateMutation,
                    router,
                    patchState,
                    templateCurrentVersion: templateData?.current_version,
                }),
            )
            patchState(buildSavedState(draftFingerprint, savedTemplate))
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
            finishPublishing()
        } catch {
            patchState({ autoSaveStatus: "error" })
            toast.error("Failed to publish template")
            finishPublishing()
        }
    }

    const handleDeleteTemplate = async () => {
        if (isNewForm || deleteTemplateMutation.isPending) return
        try {
            await deleteTemplateMutation.mutateAsync({ id })
            toast.success("Template deleted")
            patchState({ showDeleteTemplateDialog: false })
            router.push("/ops/templates?tab=forms")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to delete template")
        }
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
            desktopCanvasWidthClass: "max-w-[min(100%,76rem)]",
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
            desktopCanvasWidthClass: "max-w-[min(100%,76rem)]",
            mobileCanvasWidthClass: "max-w-sm",
            onSetActivePage: setActivePage,
            onPreviewDeviceChange: (value: "desktop" | "mobile") => patchState({ previewDevice: value }),
        },
        formSettingsProps: {
            formName: state.formName,
            formDescription: state.formDescription,
            publicEyebrow: state.publicEyebrow,
            publicTitle: state.publicTitle,
            publicSubtitle: state.publicSubtitle,
            logoUrl: state.logoUrl,
            resolvedLogoUrl,
            privacyNotice: state.privacyNotice,
            maxFileSizeMb: state.maxFileSizeMb,
            maxFileCount: state.maxFileCount,
            allowedMimeTypesText: state.allowedMimeTypesText,
            onFormNameChange: (value: string) => patchState({ formName: value }),
            onFormDescriptionChange: (value: string) => patchState({ formDescription: value }),
            onPublicEyebrowChange: (value: string) => patchState({ publicEyebrow: value }),
            onPublicTitleChange: (value: string) => patchState({ publicTitle: value }),
            onPublicSubtitleChange: (value: string) => patchState({ publicSubtitle: value }),
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
