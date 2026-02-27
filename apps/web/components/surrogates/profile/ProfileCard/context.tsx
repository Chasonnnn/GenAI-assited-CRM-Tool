"use client"

import * as React from "react"
import { createContext, use, useState, useCallback, useMemo, useEffect } from "react"
import { toast } from "sonner"
import { useProfile, useSyncProfile, useSaveProfileOverrides, useToggleProfileHidden } from "@/lib/hooks/use-profile"
import { exportProfilePdf } from "@/lib/api/profile"
import type { FormSchema } from "@/lib/api/forms"
import type { JsonObject, JsonValue } from "@/lib/types/json"
import type { ProfileCustomQa } from "@/lib/api/profile"

export const PROFILE_HEADER_NAME_KEY = "__profile_header_name"
export const PROFILE_HEADER_NOTE_KEY = "__profile_header_note"
export const PROFILE_CUSTOM_QAS_KEY = "__profile_custom_qas"

export function renderProfileTemplate(template: string, values: JsonObject): string {
    return template.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_match, token) => {
        const value = values[token]
        if (value === null || value === undefined) {
            return `{{${token}}}`
        }
        return String(value)
    })
}

// ============================================================================
// Types
// ============================================================================

export type CardMode =
    | { type: "view" }
    | { type: "edit"; editingField: string | null }

export interface StagedChange {
    field_key: string
    old_value: unknown
    new_value: unknown
}

export interface ProfileData {
    base_submission_id: string | null
    overrides: JsonObject
    hidden_fields: string[]
    merged_view: JsonObject
    base_answers: JsonObject
    schema_snapshot: FormSchema | null
    header_name_override: string | null
    header_note: string | null
    custom_qas: ProfileCustomQa[]
}

export interface ProfileCardDataContextValue {
    // Data
    surrogateId: string
    profile: ProfileData | null
    isLoading: boolean
    error: Error | null
}

export interface ProfileCardModeContextValue {
    // Mode state
    mode: CardMode
    enterEditMode: () => void
    exitEditMode: () => void
    setEditingField: (fieldKey: string | null) => void
}

export interface ProfileCardEditsContextValue {
    // Field editing
    editedFields: JsonObject
    setFieldValue: (key: string, value: JsonValue) => void
    cancelFieldEdit: (fieldKey?: string) => void

    // Hidden fields
    hiddenFields: string[]
    toggleHidden: (fieldKey: string) => void
    revealedFields: Set<string>
    toggleReveal: (fieldKey: string) => void

    // Staged changes from sync
    stagedChanges: StagedChange[]

    // Derived state
    hasChanges: boolean
}

export interface ProfileCardSectionsContextValue {
    // Section state
    sectionOpen: Record<number, boolean>
    toggleSection: (index: number) => void
}

export interface ProfileCardActionsContextValue {
    // Actions
    syncProfile: () => Promise<void>
    saveChanges: () => Promise<void>
    cancelAllChanges: () => void
    exportProfile: () => Promise<void>

    // Loading states
    isSyncing: boolean
    isSaving: boolean
    isExporting: boolean
}

export type ProfileCardContextValue =
    ProfileCardDataContextValue &
    ProfileCardModeContextValue &
    ProfileCardEditsContextValue &
    ProfileCardSectionsContextValue &
    ProfileCardActionsContextValue

// ============================================================================
// Context
// ============================================================================

const ProfileCardDataContext = createContext<ProfileCardDataContextValue | null>(null)
const ProfileCardModeContext = createContext<ProfileCardModeContextValue | null>(null)
const ProfileCardEditsContext = createContext<ProfileCardEditsContextValue | null>(null)
const ProfileCardSectionsContext = createContext<ProfileCardSectionsContextValue | null>(null)
const ProfileCardActionsContext = createContext<ProfileCardActionsContextValue | null>(null)

function useRequiredContext<T>(context: React.Context<T | null>, hookName: string): T {
    const value = use(context)
    if (!value) {
        throw new Error(`${hookName} must be used within a ProfileCardProvider`)
    }
    return value
}

export function useProfileCardData() {
    return useRequiredContext(ProfileCardDataContext, "useProfileCardData")
}

export function useProfileCardMode() {
    return useRequiredContext(ProfileCardModeContext, "useProfileCardMode")
}

export function useProfileCardEdits() {
    return useRequiredContext(ProfileCardEditsContext, "useProfileCardEdits")
}

export function useProfileCardSections() {
    return useRequiredContext(ProfileCardSectionsContext, "useProfileCardSections")
}

export function useProfileCardActions() {
    return useRequiredContext(ProfileCardActionsContext, "useProfileCardActions")
}

// Legacy combined hook for compatibility with existing imports/tests.
export function useProfileCard(): ProfileCardContextValue {
    return {
        ...useProfileCardData(),
        ...useProfileCardMode(),
        ...useProfileCardEdits(),
        ...useProfileCardSections(),
        ...useProfileCardActions(),
    }
}

// ============================================================================
// Provider
// ============================================================================

interface ProfileCardProviderProps {
    surrogateId: string
    children: React.ReactNode
}

export function ProfileCardProvider({ surrogateId, children }: ProfileCardProviderProps) {
    const { data: profileData, isLoading, error } = useProfile(surrogateId)
    const syncMutation = useSyncProfile()
    const saveMutation = useSaveProfileOverrides()
    const toggleHiddenMutation = useToggleProfileHidden()

    // Mode state
    const [mode, setMode] = useState<CardMode>({ type: "view" })

    // Local edit state
    const [editedFields, setEditedFields] = useState<JsonObject>({})
    const [baselineOverrides, setBaselineOverrides] = useState<JsonObject>({})
    const [hiddenFields, setHiddenFields] = useState<string[]>([])
    const [baselineHidden, setBaselineHidden] = useState<string[]>([])
    const [revealedFields, setRevealedFields] = useState<Set<string>>(new Set())
    const [stagedChanges, setStagedChanges] = useState<StagedChange[]>([])
    const [latestSubmissionId, setLatestSubmissionId] = useState<string | null>(null)
    const [sectionOpen, setSectionOpen] = useState<Record<number, boolean>>({})
    const [isExporting, setIsExporting] = useState(false)

    // Normalize profile data
    const profile = useMemo<ProfileData | null>(() => {
        if (!profileData) return null
        return {
            base_submission_id: profileData.base_submission_id,
            overrides: profileData.overrides || {},
            hidden_fields: profileData.hidden_fields || [],
            merged_view: profileData.merged_view,
            base_answers: profileData.base_answers,
            schema_snapshot: profileData.schema_snapshot as FormSchema | null,
            header_name_override: profileData.header_name_override ?? null,
            header_note: profileData.header_note ?? null,
            custom_qas: profileData.custom_qas ?? [],
        }
    }, [profileData])

    // Reset local state when profile changes
    useEffect(() => {
        if (profile) {
            const overrides: JsonObject = {
                ...profile.overrides,
                [PROFILE_HEADER_NAME_KEY]: profile.header_name_override ?? "",
                [PROFILE_HEADER_NOTE_KEY]: profile.header_note ?? "",
                [PROFILE_CUSTOM_QAS_KEY]: profile.custom_qas ?? [],
            }
            const hidden = profile.hidden_fields
            setEditedFields(overrides)
            setBaselineOverrides(overrides)
            setHiddenFields(hidden)
            setBaselineHidden(hidden)
            setStagedChanges([])
            setLatestSubmissionId(null)
            setRevealedFields(new Set())
            setMode({ type: "view" })
        }
    }, [profile])

    // Initialize section state
    useEffect(() => {
        if (!profile?.schema_snapshot?.pages) return
        const initialState: Record<number, boolean> = {}
        profile.schema_snapshot.pages.forEach((_page, index) => {
            initialState[index] = true
        })
        setSectionOpen(initialState)
    }, [profile?.schema_snapshot])

    // Helpers for change detection
    const isSameOverrides = useCallback((a: JsonObject, b: JsonObject) => {
        const keys = new Set([...Object.keys(a), ...Object.keys(b)])
        for (const key of keys) {
            if (a[key] !== b[key]) return false
        }
        return true
    }, [])

    const isSameHidden = useCallback((a: string[], b: string[]) => {
        if (a.length !== b.length) return false
        const setA = new Set(a)
        return b.every((item) => setA.has(item))
    }, [])

    const hasChanges = useMemo(() =>
        !isSameOverrides(editedFields, baselineOverrides) ||
        !isSameHidden(hiddenFields, baselineHidden) ||
        stagedChanges.length > 0 ||
        !!latestSubmissionId,
        [editedFields, baselineOverrides, hiddenFields, baselineHidden, stagedChanges, latestSubmissionId, isSameOverrides, isSameHidden]
    )

    const hasOverrideChanges = useMemo(() =>
        !isSameOverrides(editedFields, baselineOverrides) || !!latestSubmissionId,
        [editedFields, baselineOverrides, latestSubmissionId, isSameOverrides]
    )

    // Mode actions
    const enterEditMode = useCallback(() => {
        setMode({ type: "edit", editingField: null })
    }, [])

    const exitEditMode = useCallback(() => {
        setMode({ type: "view" })
    }, [])

    const setEditingField = useCallback((fieldKey: string | null) => {
        setMode(prev => {
            if (prev.type === "view") return prev
            return { type: "edit", editingField: fieldKey }
        })
    }, [])

    // Field editing
    const setFieldValue = useCallback((key: string, value: JsonValue) => {
        setEditedFields(prev => ({ ...prev, [key]: value }))
    }, [])

    const cancelFieldEdit = useCallback((fieldKey?: string) => {
        setEditingField(null)
        if (!fieldKey) return
        setEditedFields(prev => {
            const next = { ...prev }
            if (baselineOverrides[fieldKey] === undefined) {
                delete next[fieldKey]
            } else {
                next[fieldKey] = baselineOverrides[fieldKey]
            }
            return next
        })
    }, [baselineOverrides, setEditingField])

    // Hidden fields
    const toggleHidden = useCallback((fieldKey: string) => {
        setHiddenFields(prev =>
            prev.includes(fieldKey) ? prev.filter(key => key !== fieldKey) : [...prev, fieldKey]
        )
        setRevealedFields(prev => {
            const next = new Set(prev)
            next.delete(fieldKey)
            return next
        })
    }, [])

    const toggleReveal = useCallback((fieldKey: string) => {
        setRevealedFields(prev => {
            const next = new Set(prev)
            if (next.has(fieldKey)) {
                next.delete(fieldKey)
            } else {
                next.add(fieldKey)
            }
            return next
        })
    }, [])

    // Section state
    const toggleSection = useCallback((index: number) => {
        setSectionOpen(prev => ({ ...prev, [index]: !prev[index] }))
    }, [])

    // Actions
    const syncProfile = useCallback(async () => {
        try {
            if (mode.type === "view") {
                enterEditMode()
            }
            const result = await syncMutation.mutateAsync(surrogateId)
            if (result.staged_changes.length === 0) {
                toast.info("Profile is already up to date")
                return
            }
            setStagedChanges(result.staged_changes)
            setLatestSubmissionId(result.latest_submission_id)
            // Apply staged changes to editedFields
            const newEdits = { ...editedFields }
            result.staged_changes.forEach(change => {
                newEdits[change.field_key] = change.new_value
            })
            setEditedFields(newEdits)
            toast.success(`${result.staged_changes.length} changes staged. Click Save to apply.`)
        } catch {
            toast.error("Failed to sync profile")
        }
    }, [mode.type, enterEditMode, syncMutation, surrogateId, editedFields])

    const saveChanges = useCallback(async () => {
        try {
            if (hasOverrideChanges) {
                await saveMutation.mutateAsync({
                    surrogateId,
                    overrides: editedFields,
                    newBaseSubmissionId: latestSubmissionId,
                })
            }
            const previousHidden = new Set(baselineHidden)
            const currentHidden = new Set(hiddenFields)
            const hiddenDiff = new Set<string>([
                ...baselineHidden.filter(field => !currentHidden.has(field)),
                ...hiddenFields.filter(field => !previousHidden.has(field)),
            ])

            for (const fieldKey of hiddenDiff) {
                await toggleHiddenMutation.mutateAsync({
                    surrogateId,
                    fieldKey,
                    hidden: currentHidden.has(fieldKey),
                })
            }
            toast.success("Profile saved")
            setStagedChanges([])
            setLatestSubmissionId(null)
            exitEditMode()
            setRevealedFields(new Set())
        } catch {
            toast.error("Failed to save profile")
        }
    }, [hasOverrideChanges, saveMutation, surrogateId, editedFields, latestSubmissionId, baselineHidden, hiddenFields, toggleHiddenMutation, exitEditMode])

    const cancelAllChanges = useCallback(() => {
        setEditedFields(baselineOverrides)
        setHiddenFields(baselineHidden)
        setStagedChanges([])
        setLatestSubmissionId(null)
        exitEditMode()
        setRevealedFields(new Set())
    }, [baselineOverrides, baselineHidden, exitEditMode])

    const exportProfile = useCallback(async () => {
        setIsExporting(true)
        try {
            await exportProfilePdf(surrogateId)
            toast.success("Profile exported as PDF")
        } catch {
            toast.error("Failed to export profile")
        } finally {
            setIsExporting(false)
        }
    }, [surrogateId])

    const dataValue: ProfileCardDataContextValue = useMemo(() => ({
        surrogateId,
        profile,
        isLoading,
        error: error || null,
    }), [
        surrogateId,
        profile,
        isLoading,
        error,
    ])

    const modeValue: ProfileCardModeContextValue = useMemo(() => ({
        mode,
        enterEditMode,
        exitEditMode,
        setEditingField,
    }), [
        mode,
        enterEditMode,
        exitEditMode,
        setEditingField,
    ])

    const editsValue: ProfileCardEditsContextValue = useMemo(() => ({
        editedFields,
        setFieldValue,
        cancelFieldEdit,

        hiddenFields,
        toggleHidden,
        revealedFields,
        toggleReveal,

        stagedChanges,
        hasChanges,
    }), [
        editedFields,
        setFieldValue,
        cancelFieldEdit,
        hiddenFields,
        toggleHidden,
        revealedFields,
        toggleReveal,
        stagedChanges,
        hasChanges,
    ])

    const sectionsValue: ProfileCardSectionsContextValue = useMemo(() => ({
        sectionOpen,
        toggleSection,
    }), [sectionOpen, toggleSection])

    const actionsValue: ProfileCardActionsContextValue = useMemo(() => ({
        syncProfile,
        saveChanges,
        cancelAllChanges,
        exportProfile,
        isSyncing: syncMutation.isPending,
        isSaving: saveMutation.isPending || toggleHiddenMutation.isPending,
        isExporting,
    }), [
        syncProfile,
        saveChanges,
        cancelAllChanges,
        exportProfile,
        syncMutation.isPending,
        saveMutation.isPending,
        toggleHiddenMutation.isPending,
        isExporting,
    ])

    return (
        <ProfileCardDataContext.Provider value={dataValue}>
            <ProfileCardModeContext.Provider value={modeValue}>
                <ProfileCardEditsContext.Provider value={editsValue}>
                    <ProfileCardSectionsContext.Provider value={sectionsValue}>
                        <ProfileCardActionsContext.Provider value={actionsValue}>
                            {children}
                        </ProfileCardActionsContext.Provider>
                    </ProfileCardSectionsContext.Provider>
                </ProfileCardEditsContext.Provider>
            </ProfileCardModeContext.Provider>
        </ProfileCardDataContext.Provider>
    )
}
