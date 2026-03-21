"use client"

import { useCallback, useReducer } from "react"

import type { FormPurpose, FormRead } from "@/lib/api/forms"
import { schemaToMetadata } from "@/lib/forms/form-builder-document"

type WorkspaceTab = "builder" | "settings" | "submissions"
type SubmissionHistoryFilter = "all" | "pending" | "processed"
type AutoSaveStatus = "idle" | "saving" | "saved" | "error"
type CanvasMode = "compose" | "preview"
type PreviewDevice = "desktop" | "mobile"

type AutomationBuilderState = {
    hasHydrated: boolean
    formName: string
    formDescription: string
    formPurpose: FormPurpose
    publicTitle: string
    logoUrl: string
    privacyNotice: string
    maxFileSizeMb: number
    maxFileCount: number
    allowedMimeTypesText: string
    defaultTemplateId: string
    workspaceTab: WorkspaceTab
    submissionHistoryFilter: SubmissionHistoryFilter
    selectedQueueSubmissionId: string | null
    manualSurrogateId: string
    resolveReviewNotes: string
    showSharePrompt: boolean
    pendingSharePrompt: boolean
    showPublishDialog: boolean
    showDeletePageDialog: boolean
    pageToDelete: number | null
    isPublished: boolean
    isSaving: boolean
    isPublishing: boolean
    useOrgLogo: boolean
    customLogoUrl: string
    canvasMode: CanvasMode
    previewDevice: PreviewDevice
    fieldLibraryOpen: boolean
    fieldLibrarySearch: string
    fieldLibraryCategory: string
    autoSaveStatus: AutoSaveStatus
    lastSavedAt: Date | null
}

type AutomationBuilderAction =
    | { type: "patch"; payload: Partial<AutomationBuilderState> }
    | { type: "reset_for_form"; payload: { isNewForm: boolean } }
    | {
        type: "hydrate_from_form"
        payload: {
            form: FormRead
        }
    }

const buildInitialState = (isNewForm: boolean): AutomationBuilderState => ({
    hasHydrated: isNewForm,
    formName: isNewForm ? "" : "Surrogate Application Form",
    formDescription: "",
    formPurpose: "surrogate_application",
    publicTitle: "",
    logoUrl: "",
    privacyNotice: "",
    maxFileSizeMb: 10,
    maxFileCount: 10,
    allowedMimeTypesText: "",
    defaultTemplateId: "",
    workspaceTab: "builder",
    submissionHistoryFilter: "all",
    selectedQueueSubmissionId: null,
    manualSurrogateId: "",
    resolveReviewNotes: "",
    showSharePrompt: false,
    pendingSharePrompt: false,
    showPublishDialog: false,
    showDeletePageDialog: false,
    pageToDelete: null,
    isPublished: false,
    isSaving: false,
    isPublishing: false,
    useOrgLogo: false,
    customLogoUrl: "",
    canvasMode: "compose",
    previewDevice: "desktop",
    fieldLibraryOpen: false,
    fieldLibrarySearch: "",
    fieldLibraryCategory: "all",
    autoSaveStatus: "idle",
    lastSavedAt: null,
})

function reducer(state: AutomationBuilderState, action: AutomationBuilderAction): AutomationBuilderState {
    switch (action.type) {
        case "patch":
            return { ...state, ...action.payload }
        case "reset_for_form":
            return buildInitialState(action.payload.isNewForm)
        case "hydrate_from_form": {
            const schema = action.payload.form.form_schema ?? action.payload.form.published_schema ?? null
            const metadata = schemaToMetadata(schema)
            return {
                ...state,
                hasHydrated: true,
                formName: action.payload.form.name,
                formDescription: action.payload.form.description ?? "",
                formPurpose: action.payload.form.purpose ?? "surrogate_application",
                publicTitle: metadata.publicTitle,
                logoUrl: metadata.logoUrl,
                privacyNotice: metadata.privacyNotice,
                maxFileSizeMb: Math.max(1, Math.round((action.payload.form.max_file_size_bytes ?? 10485760) / (1024 * 1024))),
                maxFileCount: Math.max(0, Math.round(action.payload.form.max_file_count ?? 10)),
                allowedMimeTypesText: Array.isArray(action.payload.form.allowed_mime_types)
                    ? action.payload.form.allowed_mime_types.join(", ")
                    : "",
                defaultTemplateId: action.payload.form.default_application_email_template_id ?? "",
                isPublished: action.payload.form.status === "published",
            }
        }
        default:
            return state
    }
}

export function useAutomationFormBuilderState(isNewForm: boolean) {
    const [state, dispatch] = useReducer(reducer, buildInitialState(isNewForm))

    const patchState = useCallback((payload: Partial<AutomationBuilderState>) => {
        dispatch({ type: "patch", payload })
    }, [])

    const resetForForm = useCallback((nextIsNewForm: boolean) => {
        dispatch({ type: "reset_for_form", payload: { isNewForm: nextIsNewForm } })
    }, [])

    const hydrateFromForm = useCallback((payload: { form: FormRead }) => {
        dispatch({ type: "hydrate_from_form", payload })
    }, [])

    return {
        state,
        patchState,
        resetForForm,
        hydrateFromForm,
    }
}

export type { AutomationBuilderState }
