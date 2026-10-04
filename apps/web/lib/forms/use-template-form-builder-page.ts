"use client"

import { useEffect, useRef } from "react"
import { useParams, useRouter } from "next/navigation"
import { toast } from "@/components/ui/toast"

import { DEFAULT_FORM_DONOR_FIELD_OPTIONS, DEFAULT_FORM_SURROGATE_FIELD_OPTIONS } from "@/lib/api/forms"
import type { FormLeadKind, FormSchema } from "@/lib/api/forms"
import type { PlatformFormTemplate } from "@/lib/api/platform"
import {
    FALLBACK_FORM_PAGE,
    buildFormSchema,
    buildMappings,
    schemaToPages,
} from "@/lib/forms/form-builder-document"
import { normalizePagesForLeadKind, getDonorPublishValidationMessage } from "@/lib/forms/form-lead-kind"
import { getFormPublicationStatus, hasSameContent } from "@/lib/forms/form-publication-status"
import { useFormBuilderAutosave } from "@/lib/forms/use-form-builder-autosave"
import { useFormBuilderSaveQueue, type SaveTicket } from "@/lib/forms/use-form-builder-save-queue"
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
    | "templateSettings"
>

type TemplateDraftPayload = {
    name: string
    description: string | null
    schema_json: FormSchema
    settings_json: Record<string, unknown>
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
        payload: TemplateDraftPayload & { expected_version: number }
    }) => Promise<PlatformFormTemplate>
}

type TemplateRouter = ReturnType<typeof useRouter>

function resolveTemplateTarget(settings: Record<string, unknown>) {
    const leadKind: FormLeadKind = settings.lead_kind === "egg_donor" || settings.lead_kind === "sperm_donor"
        ? settings.lead_kind
        : "surrogate"
    return {
        leadKind,
        mappingOptions: leadKind === "surrogate" ? DEFAULT_FORM_SURROGATE_FIELD_OPTIONS : DEFAULT_FORM_DONOR_FIELD_OPTIONS,
    }
}

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
        ...state.templateSettings,
        max_file_size_bytes: Math.max(1, Math.round(state.maxFileSizeMb * 1024 * 1024)),
        max_file_count: Math.max(0, Math.round(state.maxFileCount)),
        allowed_mime_types: allowedMimeTypes.length > 0 ? allowedMimeTypes : null,
    }
    delete settingsJson.mappings
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

// The draft exactly as submitted. The saved fingerprint comes from it, not from the latest
// edits, so edits made while the request is in flight stay dirty.
type TemplateDraft = {
    payload: TemplateDraftPayload
    fingerprint: string
}

const buildSavedState = (draft: TemplateDraft, savedTemplate: PlatformFormTemplate): Partial<TemplateBuilderState> => ({
    autoSaveStatus: "saved",
    isPublished: (savedTemplate.published_version ?? 0) > 0,
    lastSavedAt: savedTemplate.updated_at ? new Date(savedTemplate.updated_at) : new Date(),
    lastSavedFingerprint: draft.fingerprint,
    lastFailedFingerprint: "",
})

// Returns the saved template and leaves builder state to the save queue's handlers. The
// redirect to a newly created template waits until the builder is visible. The template id and
// revision are recorded for every result, keyed by route, so the next save of that template
// updates it with the current expected_version.
const persistTemplateDraft = async ({
    draft,
    ticket,
    templateIdentityRef,
    templateKey,
    routeTemplateId,
    createTemplateMutation,
    updateTemplateMutation,
    router,
    templateCurrentVersion,
}: {
    draft: TemplateDraft
    ticket: SaveTicket
    templateIdentityRef: TemplateSaveIdentityRef
    templateKey: string
    routeTemplateId: string | null
    createTemplateMutation: TemplateCreateMutation
    updateTemplateMutation: TemplateUpdateMutation
    router: TemplateRouter
    templateCurrentVersion: number | null | undefined
}): Promise<PlatformFormTemplate> => {
    let savedTemplate: PlatformFormTemplate
    const trackedIdentity =
        templateIdentityRef.current?.routeKey === templateKey
            ? templateIdentityRef.current
            : null
    const templateId = trackedIdentity?.templateId ?? routeTemplateId
    if (!templateId) {
        savedTemplate = await createTemplateMutation.mutateAsync(draft.payload)
        const createdId = savedTemplate.id
        ticket.recordCreated(createdId, () => router.replace(`/ops/templates/forms/${createdId}`))
    } else {
        const expectedVersion = trackedIdentity?.currentVersion ?? templateCurrentVersion
        if (typeof expectedVersion !== "number") {
            throw new Error("Template revision is unavailable")
        }
        savedTemplate = await updateTemplateMutation.mutateAsync({
            id: templateId,
            payload: {
                ...draft.payload,
                expected_version: expectedVersion,
            },
        })
    }

    templateIdentityRef.current = {
        currentVersion:
            typeof savedTemplate.current_version === "number"
                ? savedTemplate.current_version
                : null,
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

    useEffect(() => {
        if (!templateData || templateIdentityRef.current?.routeKey === templateKey) return
        templateIdentityRef.current = {
            currentVersion: templateData.current_version,
            routeKey: templateKey,
            templateId: templateData.id,
        }
    }, [templateData, templateKey])

    const { state, patchState, resetForForm, hydrateFromTemplate } =
        useTemplateFormBuilderState(templateKey, isNewForm)
    const saveQueue = useFormBuilderSaveQueue(templateKey)
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
    const { leadKind: templateLeadKind, mappingOptions: surrogateFieldMappings } = resolveTemplateTarget(state.templateSettings)
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
    // Template publish copies the whole draft (name, description, schema, settings), so any
    // unsaved or saved draft difference is unpublished.
    const publicationStatus = getFormPublicationStatus(
        state.isPublished,
        isDirty || !hasSameContent(templateData?.draft, templateData?.published),
    )

    // The render that resets for another template still sees the previous template's state and
    // pages, so record the baseline only once the state belongs to this template.
    if (
        state.templateKey === templateKey &&
        state.hasHydrated &&
        state.baselineTemplateKey !== templateKey
    ) {
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

    const captureDraft = (): TemplateDraft => ({
        payload: draftPayload,
        fingerprint: draftFingerprint,
    })

    const persistDraft = (draft: TemplateDraft, ticket: SaveTicket) =>
        persistTemplateDraft({
            draft,
            ticket,
            templateIdentityRef,
            templateKey,
            routeTemplateId: formId,
            createTemplateMutation,
            updateTemplateMutation,
            router,
            templateCurrentVersion: templateData?.current_version,
        })

    const handleSave = () => {
        if (!saveQueue.isIdle()) return
        if (!state.formName.trim()) {
            toast.error("Form name is required")
            return
        }
        const draft = captureDraft()
        patchState({ isSaving: true })
        return saveQueue.enqueue((ticket) => persistDraft(draft, ticket), {
            onSuccess: (savedTemplate, ticket) => {
                patchState({ ...buildSavedState(draft, savedTemplate), isSaving: false })
                if (ticket.isActive()) toast.success("Template saved")
            },
            onError: (_error, ticket) => {
                patchState({ autoSaveStatus: "error", isSaving: false, lastFailedFingerprint: draft.fingerprint })
                if (ticket.isActive()) toast.error("Failed to save template")
            },
        })
    }

    useFormBuilderAutosave({
        enabled:
            state.hasHydrated &&
            Boolean(state.formName.trim()) &&
            !state.isSaving &&
            !state.isPublishing &&
            !saveQueue.isBusy,
        fingerprint: draftFingerprint,
        savedFingerprint: state.lastSavedFingerprint,
        failedFingerprint: state.lastFailedFingerprint,
        clearFailedFingerprint: () => patchState({ lastFailedFingerprint: "" }),
        save: () => {
            const draft = captureDraft()
            patchState({ autoSaveStatus: "saving" })
            void saveQueue.enqueue((ticket) => persistDraft(draft, ticket), {
                onSuccess: (savedTemplate) => patchState(buildSavedState(draft, savedTemplate)),
                onError: () => patchState({ autoSaveStatus: "error", lastFailedFingerprint: draft.fingerprint }),
            })
        },
    })

    const handlePreview = () => {
        if (pages.every((page) => page.fields.length === 0)) {
            toast.error("Add at least one field before previewing")
            return
        }
        patchState({ workspaceTab: "preview" })
    }

    const handleTemplateTypeChange = (value: "surrogate" | "donor") => {
        const leadKind = value === "surrogate" ? "surrogate"
            : templateLeadKind === "surrogate" ? "egg_donor" : templateLeadKind
        patchState({ templateSettings: {
            ...state.templateSettings,
            lead_kind: leadKind,
            purpose: value === "donor" ? "other" : "surrogate_application",
        } })
        resetDocument(normalizePagesForLeadKind(pages, leadKind))
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
        const donorValidation = getDonorPublishValidationMessage(pages, templateLeadKind)
        if (donorValidation) {
            toast.error(donorValidation)
            return
        }
        patchState({ showPublishDialog: true })
    }

    const confirmPublish = () => {
        if (!saveQueue.isIdle()) return
        const draft = captureDraft()
        patchState({ isPublishing: true })
        return saveQueue.enqueue(
            async (ticket) => {
                const savedTemplate = await persistDraft(draft, ticket)
                try {
                    const publishedTemplate = await publishTemplateMutation.mutateAsync({
                        id: savedTemplate.id,
                        payload: {
                            publish_all: true,
                            org_ids: null,
                            expected_version: savedTemplate.current_version,
                        },
                    })
                    templateIdentityRef.current = {
                        currentVersion: publishedTemplate.current_version,
                        routeKey: templateKey,
                        templateId: publishedTemplate.id,
                    }
                } catch {
                    return { savedTemplate, published: false }
                }
                return { savedTemplate, published: true }
            },
            {
                onSuccess: ({ savedTemplate, published }, ticket) => {
                    patchState({ ...buildSavedState(draft, savedTemplate), isPublishing: false })
                    if (!published) {
                        patchState({ autoSaveStatus: "error" })
                        if (ticket.isActive()) toast.error("Failed to publish template")
                        return
                    }
                    patchState({
                        isPublished: true,
                        showPublishDialog: false,
                    })
                    if (ticket.isActive()) toast.success("Template published")
                },
                onError: (_error, ticket) => {
                    patchState({ autoSaveStatus: "error", isPublishing: false, lastFailedFingerprint: draft.fingerprint })
                    if (ticket.isActive()) toast.error("Failed to publish template")
                },
            },
        )
    }

    // Rejections reach ConfirmDialog, which keeps the dialog open and shows a safe message inline.
    const handleDeleteTemplate = async () => {
        if (isNewForm || deleteTemplateMutation.isPending) return
        await deleteTemplateMutation.mutateAsync({ id })
        toast.success("Template deleted")
        router.push("/ops/templates?tab=forms")
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
        publicationStatus,
        hasPendingSave: saveQueue.isBusy,
        resolvedLogoUrl,
        surrogateFieldMappings,
        workspaceDocument,
        workspaceProps: {
            leadKind: templateLeadKind,
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
            publicEyebrow: state.publicEyebrow,
            publicTitle: state.publicTitle,
            publicSubtitle: state.publicSubtitle,
            resolvedLogoUrl,
            privacyNotice: state.privacyNotice,
            previewDevice: state.previewDevice,
            desktopCanvasWidthClass: "max-w-[min(100%,76rem)]",
            mobileCanvasWidthClass: "max-w-sm",
            onPreviewDeviceChange: (value: "desktop" | "mobile") => patchState({ previewDevice: value }),
        },
        formSettingsProps: {
            templateType: templateLeadKind === "surrogate" ? "surrogate" as const : "donor" as const,
            onTemplateTypeChange: handleTemplateTypeChange,
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
