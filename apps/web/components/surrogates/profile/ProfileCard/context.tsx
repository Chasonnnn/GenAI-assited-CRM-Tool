"use client"

import * as React from "react"
import { createContext, use, useState, useCallback, useMemo, useEffect } from "react"
import { toast } from "sonner"
import { useProfile, useSyncProfile, useSaveProfileOverrides, useToggleProfileHidden } from "@/lib/hooks/use-profile"
import { exportProfilePdf } from "@/lib/api/profile"
import type { FormSchema } from "@/lib/api/forms"
import type { JsonObject, JsonValue } from "@/lib/types/json"

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
}

export interface ProfileCardContextValue {
    // Data
    surrogateId: string
    profile: ProfileData | null
    isLoading: boolean
    error: Error | null

    // Mode state (consolidated)
    mode: CardMode
    enterEditMode: () => void
    exitEditMode: () => void
    setEditingField: (fieldKey: string | null) => void

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

    // Section state
    sectionOpen: Record<number, boolean>
    toggleSection: (index: number) => void

    // Actions
    syncProfile: () => Promise<void>
    saveChanges: () => Promise<void>
    cancelAllChanges: () => void
    exportProfile: () => Promise<void>

    // Derived state
    hasChanges: boolean

    // Loading states
    isSyncing: boolean
    isSaving: boolean
    isExporting: boolean
}

// ============================================================================
// Context
// ============================================================================

const ProfileCardContext = createContext<ProfileCardContextValue | null>(null)

export function useProfileCard() {
    const context = use(ProfileCardContext)
    if (!context) {
        throw new Error("useProfileCard must be used within a ProfileCardProvider")
    }
    return context
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
        }
    }, [profileData])

    // Reset local state when profile changes
    useEffect(() => {
        if (profile) {
            const overrides = profile.overrides
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

    const value: ProfileCardContextValue = useMemo(() => ({
        surrogateId,
        profile,
        isLoading,
        error: error || null,

        mode,
        enterEditMode,
        exitEditMode,
        setEditingField,

        editedFields,
        setFieldValue,
        cancelFieldEdit,

        hiddenFields,
        toggleHidden,
        revealedFields,
        toggleReveal,

        stagedChanges,

        sectionOpen,
        toggleSection,

        syncProfile,
        saveChanges,
        cancelAllChanges,
        exportProfile,

        hasChanges,

        isSyncing: syncMutation.isPending,
        isSaving: saveMutation.isPending || toggleHiddenMutation.isPending,
        isExporting,
    }), [
        surrogateId,
        profile,
        isLoading,
        error,
        mode,
        enterEditMode,
        exitEditMode,
        setEditingField,
        editedFields,
        setFieldValue,
        cancelFieldEdit,
        hiddenFields,
        toggleHidden,
        revealedFields,
        toggleReveal,
        stagedChanges,
        sectionOpen,
        toggleSection,
        syncProfile,
        saveChanges,
        cancelAllChanges,
        exportProfile,
        hasChanges,
        syncMutation.isPending,
        saveMutation.isPending,
        toggleHiddenMutation.isPending,
        isExporting,
    ])

    return (
        <ProfileCardContext.Provider value={value}>
            {children}
        </ProfileCardContext.Provider>
    )
}
