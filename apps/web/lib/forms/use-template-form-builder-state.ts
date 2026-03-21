"use client"

import { useCallback, useReducer } from "react"

import type { FormSchema } from "@/lib/api/forms"
import { schemaToMetadata } from "@/lib/forms/form-builder-document"

type WorkspaceTab = "builder" | "settings"
type AutoSaveStatus = "idle" | "saving" | "saved" | "error"

type TemplateBuilderState = {
    hasHydrated: boolean
    formName: string
    formDescription: string
    publicTitle: string
    logoUrl: string
    privacyNotice: string
    maxFileSizeMb: number
    maxFileCount: number
    allowedMimeTypesText: string
    workspaceTab: WorkspaceTab
    isPublished: boolean
    isSaving: boolean
    isPublishing: boolean
    isMobilePreview: boolean
    autoSaveStatus: AutoSaveStatus
    lastSavedAt: Date | null
    showPublishDialog: boolean
    showDeleteTemplateDialog: boolean
    showDeletePageDialog: boolean
    pageToDelete: number | null
}

type TemplateBuilderAction =
    | { type: "patch"; payload: Partial<TemplateBuilderState> }
    | { type: "reset_for_form"; payload: { isNewForm: boolean } }
    | {
        type: "hydrate_from_template"
        payload: {
            name: string
            description: string
            settings: Record<string, unknown>
            schema: FormSchema | null
            mappingMap: Map<string, string>
            publishedVersion: number
        }
    }

const buildInitialState = (isNewForm: boolean): TemplateBuilderState => ({
    hasHydrated: isNewForm,
    formName: isNewForm ? "" : "Surrogate Application Form",
    formDescription: "",
    publicTitle: "",
    logoUrl: "",
    privacyNotice: "",
    maxFileSizeMb: 10,
    maxFileCount: 10,
    allowedMimeTypesText: "",
    workspaceTab: "builder",
    isPublished: false,
    isSaving: false,
    isPublishing: false,
    isMobilePreview: false,
    autoSaveStatus: "idle",
    lastSavedAt: null,
    showPublishDialog: false,
    showDeleteTemplateDialog: false,
    showDeletePageDialog: false,
    pageToDelete: null,
})

const extractAllowedMimeTypesText = (settings: Record<string, unknown>) => {
    const allowed = settings.allowed_mime_types
    return Array.isArray(allowed) ? allowed.join(", ") : ""
}

function reducer(state: TemplateBuilderState, action: TemplateBuilderAction): TemplateBuilderState {
    switch (action.type) {
        case "patch":
            return { ...state, ...action.payload }
        case "reset_for_form":
            return buildInitialState(action.payload.isNewForm)
        case "hydrate_from_template": {
            const metadata = schemaToMetadata(action.payload.schema)
            return {
                ...state,
                hasHydrated: true,
                formName: action.payload.name,
                formDescription: action.payload.description,
                publicTitle: metadata.publicTitle,
                logoUrl: metadata.logoUrl,
                privacyNotice: metadata.privacyNotice,
                maxFileSizeMb: Math.max(
                    1,
                    Math.round(((action.payload.settings.max_file_size_bytes as number | undefined) ?? 10485760) / (1024 * 1024)),
                ),
                maxFileCount: Math.max(
                    0,
                    Math.round((action.payload.settings.max_file_count as number | undefined) ?? 10),
                ),
                allowedMimeTypesText: extractAllowedMimeTypesText(action.payload.settings),
                isPublished: action.payload.publishedVersion > 0,
            }
        }
        default:
            return state
    }
}

export function useTemplateFormBuilderState(isNewForm: boolean) {
    const [state, dispatch] = useReducer(reducer, buildInitialState(isNewForm))

    const patchState = useCallback((payload: Partial<TemplateBuilderState>) => {
        dispatch({ type: "patch", payload })
    }, [])

    const resetForForm = useCallback((nextIsNewForm: boolean) => {
        dispatch({ type: "reset_for_form", payload: { isNewForm: nextIsNewForm } })
    }, [])

    const hydrateFromTemplate = useCallback((
        payload: {
            name: string
            description: string
            settings: Record<string, unknown>
            schema: FormSchema | null
            mappingMap: Map<string, string>
            publishedVersion: number
        },
    ) => {
        dispatch({ type: "hydrate_from_template", payload })
    }, [])

    return {
        state,
        patchState,
        resetForForm,
        hydrateFromTemplate,
    }
}

export type { TemplateBuilderState }
