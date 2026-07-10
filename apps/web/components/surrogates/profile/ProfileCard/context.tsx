"use client"

import * as React from "react"
import { createContext, use, useState } from "react"
import { toast } from "@/components/ui/toast"
import { useProfile, useSyncProfile, useSaveProfileOverrides, useToggleProfileHidden } from "@/lib/hooks/use-profile"
import { exportProfilePdf } from "@/lib/api/profile"
import type { FormSchema } from "@/lib/api/forms"
import type { JsonObject, JsonValue } from "@/lib/types/json"
import type { ProfileCustomQa, ProfileDataResponse } from "@/lib/api/profile"
import {
    PROFILE_CUSTOM_QAS_KEY,
    PROFILE_HEADER_NAME_KEY,
    PROFILE_HEADER_NOTE_KEY,
} from "./profile-template"

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

type ProfileEditableState = {
    profileKey: string | null
    mode: CardMode
    editedFields: JsonObject
    baselineOverrides: JsonObject
    hiddenFields: string[]
    baselineHidden: string[]
    revealedFields: Set<string>
    stagedChanges: StagedChange[]
    latestSubmissionId: string | null
    sectionOpen: Record<number, boolean>
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

function resolveProfileStateUpdate<T>(updater: React.SetStateAction<T>, current: T): T {
    return typeof updater === "function"
        ? (updater as (previous: T) => T)(current)
        : updater
}

function createProfileOverrides(profile: ProfileData | null): JsonObject {
    if (!profile) return {}
    return {
        ...profile.overrides,
        [PROFILE_HEADER_NAME_KEY]: profile.header_name_override ?? "",
        [PROFILE_HEADER_NOTE_KEY]: profile.header_note ?? "",
        [PROFILE_CUSTOM_QAS_KEY]: profile.custom_qas ?? [],
    }
}

function createSectionOpenState(profile: ProfileData | null): Record<number, boolean> {
    const sectionOpen: Record<number, boolean> = {}
    for (const [index] of profile?.schema_snapshot?.pages?.entries() ?? []) {
        sectionOpen[index] = true
    }
    return sectionOpen
}

function getProfileStateKey(profile: ProfileData | null): string | null {
    if (!profile) return null
    return JSON.stringify({
        baseSubmissionId: profile.base_submission_id,
        overrides: profile.overrides,
        hiddenFields: profile.hidden_fields,
        headerNameOverride: profile.header_name_override,
        headerNote: profile.header_note,
        customQas: profile.custom_qas,
        schemaPages: profile.schema_snapshot?.pages?.map((page) => ({
            title: page.title,
            fields: page.fields.map((field) => field.key),
        })) ?? [],
    })
}

function createProfileEditableState(profile: ProfileData | null): ProfileEditableState {
    const baselineOverrides = createProfileOverrides(profile)
    const baselineHidden = profile?.hidden_fields ?? []
    return {
        profileKey: getProfileStateKey(profile),
        mode: { type: "view" },
        editedFields: baselineOverrides,
        baselineOverrides,
        hiddenFields: baselineHidden,
        baselineHidden,
        revealedFields: new Set(),
        stagedChanges: [],
        latestSubmissionId: null,
        sectionOpen: createSectionOpenState(profile),
    }
}

function createProfileData(profileData: ProfileDataResponse | undefined): ProfileData | null {
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
}

function isSameOverrides(a: JsonObject, b: JsonObject) {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)])
    for (const key of keys) {
        if (a[key] !== b[key]) return false
    }
    return true
}

function isSameHidden(a: string[], b: string[]) {
    if (a.length !== b.length) return false
    const setA = new Set(a)
    return b.every((item) => setA.has(item))
}

export function ProfileCardProvider({ surrogateId, children }: ProfileCardProviderProps) {
    const { data: profileData, isLoading, error } = useProfile(surrogateId)
    const syncMutation = useSyncProfile()
    const saveMutation = useSaveProfileOverrides()
    const toggleHiddenMutation = useToggleProfileHidden()
    const profile = createProfileData(profileData)

    const activeProfileKey = getProfileStateKey(profile)
    const [profileState, setProfileState] = useState<ProfileEditableState>(() => createProfileEditableState(profile))
    const [isExporting, setIsExporting] = useState(false)

    if (profileState.profileKey !== activeProfileKey) {
        setProfileState(createProfileEditableState(profile))
    }

    const {
        mode,
        editedFields,
        baselineOverrides,
        hiddenFields,
        baselineHidden,
        revealedFields,
        stagedChanges,
        latestSubmissionId,
        sectionOpen,
    } = profileState

    const setMode = (updater: React.SetStateAction<CardMode>) => {
        setProfileState((current) => ({
            ...current,
            mode: resolveProfileStateUpdate(updater, current.mode),
        }))
    }

    const setEditedFields = (updater: React.SetStateAction<JsonObject>) => {
        setProfileState((current) => ({
            ...current,
            editedFields: resolveProfileStateUpdate(updater, current.editedFields),
        }))
    }

    const setHiddenFields = (updater: React.SetStateAction<string[]>) => {
        setProfileState((current) => ({
            ...current,
            hiddenFields: resolveProfileStateUpdate(updater, current.hiddenFields),
        }))
    }

    const setRevealedFields = (updater: React.SetStateAction<Set<string>>) => {
        setProfileState((current) => ({
            ...current,
            revealedFields: resolveProfileStateUpdate(updater, current.revealedFields),
        }))
    }

    const setStagedChanges = (updater: React.SetStateAction<StagedChange[]>) => {
        setProfileState((current) => ({
            ...current,
            stagedChanges: resolveProfileStateUpdate(updater, current.stagedChanges),
        }))
    }

    const setLatestSubmissionId = (updater: React.SetStateAction<string | null>) => {
        setProfileState((current) => ({
            ...current,
            latestSubmissionId: resolveProfileStateUpdate(updater, current.latestSubmissionId),
        }))
    }

    const setSectionOpen = (updater: React.SetStateAction<Record<number, boolean>>) => {
        setProfileState((current) => ({
            ...current,
            sectionOpen: resolveProfileStateUpdate(updater, current.sectionOpen),
        }))
    }

    const hasChanges =
        !isSameOverrides(editedFields, baselineOverrides) ||
        !isSameHidden(hiddenFields, baselineHidden) ||
        stagedChanges.length > 0 ||
        !!latestSubmissionId

    const hasOverrideChanges = !isSameOverrides(editedFields, baselineOverrides) || !!latestSubmissionId

    // Mode actions
    const enterEditMode = () => {
        setMode({ type: "edit", editingField: null })
    }

    const exitEditMode = () => {
        setMode({ type: "view" })
    }

    const setEditingField = (fieldKey: string | null) => {
        setMode(prev => {
            if (prev.type === "view") return prev
            return { type: "edit", editingField: fieldKey }
        })
    }

    // Field editing
    const setFieldValue = (key: string, value: JsonValue) => {
        setEditedFields(prev => ({ ...prev, [key]: value }))
    }

    const cancelFieldEdit = (fieldKey?: string) => {
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
    }

    // Hidden fields
    const toggleHidden = (fieldKey: string) => {
        setHiddenFields(prev =>
            prev.includes(fieldKey) ? prev.filter(key => key !== fieldKey) : [...prev, fieldKey]
        )
        setRevealedFields(prev => {
            const next = new Set(prev)
            next.delete(fieldKey)
            return next
        })
    }

    const toggleReveal = (fieldKey: string) => {
        setRevealedFields(prev => {
            const next = new Set(prev)
            if (next.has(fieldKey)) {
                next.delete(fieldKey)
            } else {
                next.add(fieldKey)
            }
            return next
        })
    }

    // Section state
    const toggleSection = (index: number) => {
        setSectionOpen(prev => ({ ...prev, [index]: !prev[index] }))
    }

    // Actions
    const syncProfile = async () => {
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
    }

    const saveChanges = async () => {
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

            await Promise.all(
                Array.from(hiddenDiff, (fieldKey) =>
                    toggleHiddenMutation.mutateAsync({
                        surrogateId,
                        fieldKey,
                        hidden: currentHidden.has(fieldKey),
                    })
                )
            )
            toast.success("Profile saved")
            setStagedChanges([])
            setLatestSubmissionId(null)
            exitEditMode()
            setRevealedFields(new Set())
        } catch {
            toast.error("Failed to save profile")
        }
    }

    const cancelAllChanges = () => {
        setEditedFields(baselineOverrides)
        setHiddenFields(baselineHidden)
        setStagedChanges([])
        setLatestSubmissionId(null)
        exitEditMode()
        setRevealedFields(new Set())
    }

    const exportProfile = async () => {
        setIsExporting(true)
        try {
            await exportProfilePdf(surrogateId)
            toast.success("Profile exported as PDF")
        } catch {
            toast.error("Failed to export profile")
            setIsExporting(false)
            return
        }
        setIsExporting(false)
    }

    const dataValue: ProfileCardDataContextValue = {
        surrogateId,
        profile,
        isLoading,
        error: error || null,
    }

    const modeValue: ProfileCardModeContextValue = {
        mode,
        enterEditMode,
        exitEditMode,
        setEditingField,
    }

    const editsValue: ProfileCardEditsContextValue = {
        editedFields,
        setFieldValue,
        cancelFieldEdit,

        hiddenFields,
        toggleHidden,
        revealedFields,
        toggleReveal,

        stagedChanges,
        hasChanges,
    }

    const sectionsValue: ProfileCardSectionsContextValue = {
        sectionOpen,
        toggleSection,
    }

    const actionsValue: ProfileCardActionsContextValue = {
        syncProfile,
        saveChanges,
        cancelAllChanges,
        exportProfile,
        isSyncing: syncMutation.isPending,
        isSaving: saveMutation.isPending || toggleHiddenMutation.isPending,
        isExporting,
    }

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
