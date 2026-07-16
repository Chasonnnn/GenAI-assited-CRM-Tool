"use client"

import { useReducer, useState } from "react"

import type { FormPurpose, FormRead } from "@/lib/api/forms"
import { schemaToMetadata } from "@/lib/forms/form-builder-document"

type WorkspaceTab = "edit" | "preview" | "settings" | "submissions"
type SubmissionHistoryFilter = "all" | "pending" | "processed"
type AutoSaveStatus = "idle" | "saving" | "saved" | "error"
type PreviewDevice = "desktop" | "mobile"

type AutomationBuilderState = {
    baselineFormKey: string | null
    formKey: string
    hasHydrated: boolean
    formName: string
    formDescription: string
    formPurpose: FormPurpose
    publicEyebrow: string
    publicTitle: string
    publicSubtitle: string
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
    showPublishDialog: boolean
    showDeletePageDialog: boolean
    pageToDelete: number | null
    isPublished: boolean
    isSaving: boolean
    isPublishing: boolean
    useOrgLogo: boolean
    customLogoUrl: string
    previewDevice: PreviewDevice
    fieldLibrarySearch: string
    fieldLibraryCategory: string
    autoSaveStatus: AutoSaveStatus
    lastSavedAt: Date | null
    lastSavedFingerprint: string
}

type AutomationBuilderAction =
    | { type: "patch"; payload: Partial<AutomationBuilderState> }
    | { type: "reset_for_form"; payload: { formKey: string; isNewForm: boolean } }
    | {
        type: "hydrate_from_form"
        payload: {
            form: FormRead
            orgLogoPath: string
        }
    }

const buildInitialState = (formKey: string, isNewForm: boolean): AutomationBuilderState => ({
    baselineFormKey: null,
    formKey,
    hasHydrated: isNewForm,
    formName: isNewForm ? "" : "Surrogate Application Form",
    formDescription: "",
    formPurpose: "surrogate_application",
    publicEyebrow: "",
    publicTitle: "",
    publicSubtitle: "",
    logoUrl: "",
    privacyNotice: "",
    maxFileSizeMb: 10,
    maxFileCount: 10,
    allowedMimeTypesText: "",
    defaultTemplateId: "",
    workspaceTab: "edit",
    submissionHistoryFilter: "all",
    selectedQueueSubmissionId: null,
    manualSurrogateId: "",
    resolveReviewNotes: "",
    showSharePrompt: false,
    showPublishDialog: false,
    showDeletePageDialog: false,
    pageToDelete: null,
    isPublished: false,
    isSaving: false,
    isPublishing: false,
    useOrgLogo: false,
    customLogoUrl: "",
    previewDevice: "desktop",
    fieldLibrarySearch: "",
    fieldLibraryCategory: "all",
    autoSaveStatus: "idle",
    lastSavedAt: null,
    lastSavedFingerprint: "",
})

function reducer(state: AutomationBuilderState, action: AutomationBuilderAction): AutomationBuilderState {
    switch (action.type) {
        case "patch":
            return { ...state, ...action.payload }
        case "reset_for_form":
            return buildInitialState(action.payload.formKey, action.payload.isNewForm)
        case "hydrate_from_form": {
            const schema = action.payload.form.form_schema ?? action.payload.form.published_schema ?? null
            const metadata = schemaToMetadata(schema)
            const isOrgLogo =
                Boolean(action.payload.orgLogoPath) &&
                metadata.logoUrl === action.payload.orgLogoPath
            return {
                ...state,
                hasHydrated: true,
                formName: action.payload.form.name,
                formDescription: action.payload.form.description ?? "",
                formPurpose: action.payload.form.purpose ?? "surrogate_application",
                publicEyebrow: metadata.publicEyebrow,
                publicTitle: metadata.publicTitle,
                publicSubtitle: metadata.publicSubtitle,
                logoUrl: metadata.logoUrl,
                privacyNotice: metadata.privacyNotice,
                maxFileSizeMb: Math.max(1, Math.round((action.payload.form.max_file_size_bytes ?? 10485760) / (1024 * 1024))),
                maxFileCount: Math.max(0, Math.round(action.payload.form.max_file_count ?? 10)),
                allowedMimeTypesText: Array.isArray(action.payload.form.allowed_mime_types)
                    ? action.payload.form.allowed_mime_types.join(", ")
                    : "",
                defaultTemplateId: action.payload.form.default_application_email_template_id ?? "",
                isPublished: action.payload.form.status === "published",
                useOrgLogo: isOrgLogo,
                customLogoUrl: isOrgLogo ? "" : metadata.logoUrl,
            }
        }
        default:
            return state
    }
}

export function useAutomationFormBuilderState(formKey: string, isNewForm: boolean) {
    const [state, dispatch] = useReducer(reducer, buildInitialState(formKey, isNewForm))

    const [patchState] = useState(() => (payload: Partial<AutomationBuilderState>) => {
        dispatch({ type: "patch", payload })
    })

    const [resetForForm] = useState(() => (nextFormKey: string, nextIsNewForm: boolean) => {
        dispatch({
            type: "reset_for_form",
            payload: { formKey: nextFormKey, isNewForm: nextIsNewForm },
        })
    })

    const [hydrateFromForm] = useState(
        () => (payload: { form: FormRead; orgLogoPath: string }) => {
            dispatch({ type: "hydrate_from_form", payload })
        },
    )

    return {
        state,
        patchState,
        resetForForm,
        hydrateFromForm,
    }
}

export type { AutomationBuilderState }
