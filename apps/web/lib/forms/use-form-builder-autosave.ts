"use client"

import { useEffect, useEffectEvent, useRef } from "react"

type FormBuilderAutosaveOptions<SaveResult> = {
    enabled: boolean
    // Identifies the form being edited. A save that finishes after this changes, or after
    // unmount, is ignored.
    scopeKey: string
    fingerprint: string
    savedFingerprint: string
    // Resolve with the fingerprint of the draft that was submitted, not the latest one, so
    // edits made while the request is in flight stay dirty and autosave again.
    save: () => Promise<SaveResult>
    onSaving: () => void
    onSaved: (result: SaveResult) => void
    onError: () => void
    delayMs?: number
}

export function useFormBuilderAutosave<SaveResult>({
    enabled,
    scopeKey,
    fingerprint,
    savedFingerprint,
    save,
    onSaving,
    onSaved,
    onError,
    delayMs = 1200,
}: FormBuilderAutosaveOptions<SaveResult>) {
    const activeScopeRef = useRef<string | null>(null)

    useEffect(() => {
        activeScopeRef.current = scopeKey
        return () => {
            activeScopeRef.current = null
        }
    }, [scopeKey])

    const saveActiveDraft = useEffectEvent(async () => {
        const scope = activeScopeRef.current
        const isCurrentScope = () => scope !== null && activeScopeRef.current === scope
        onSaving()
        try {
            const result = await save()
            if (isCurrentScope()) onSaved(result)
        } catch {
            if (isCurrentScope()) onError()
        }
    })

    useEffect(() => {
        if (!enabled) return
        if (fingerprint === savedFingerprint) return

        // Cleanup cancels only a save that has not started. A started save disables
        // autosave through its pending mutation, and its completion must still be recorded.
        const timeout = window.setTimeout(() => {
            void saveActiveDraft()
        }, delayMs)

        return () => {
            window.clearTimeout(timeout)
        }
    }, [delayMs, enabled, fingerprint, savedFingerprint])
}
