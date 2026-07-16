"use client"

import { useEffect, useEffectEvent } from "react"

type AutomationFormAutosaveOptions<SavedForm> = {
    enabled: boolean
    fingerprint: string
    savedFingerprint: string
    save: () => Promise<SavedForm>
    onSaving: () => void
    onSaved: (savedForm: SavedForm) => void
    onError: () => void
    delayMs?: number
}

export function useAutomationFormAutosave<SavedForm>({
    enabled,
    fingerprint,
    savedFingerprint,
    save,
    onSaving,
    onSaved,
    onError,
    delayMs = 1200,
}: AutomationFormAutosaveOptions<SavedForm>) {
    const saveActiveDraft = useEffectEvent(async (isCancelled: () => boolean) => {
        if (isCancelled()) return
        onSaving()
        try {
            const savedForm = await save()
            if (isCancelled()) return
            onSaved(savedForm)
        } catch {
            if (isCancelled()) return
            onError()
        }
    })

    useEffect(() => {
        if (!enabled) return
        if (fingerprint === savedFingerprint) return

        let cancelled = false
        const timeout = window.setTimeout(() => {
            void saveActiveDraft(() => cancelled)
        }, delayMs)

        return () => {
            cancelled = true
            window.clearTimeout(timeout)
        }
    }, [delayMs, enabled, fingerprint, savedFingerprint])
}
