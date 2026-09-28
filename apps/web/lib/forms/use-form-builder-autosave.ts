"use client"

import { useEffect, useEffectEvent } from "react"

type FormBuilderAutosaveOptions = {
    enabled: boolean
    fingerprint: string
    savedFingerprint: string
    // Queues the save. The builder's save queue applies its result.
    save: () => void
    delayMs?: number
}

export function useFormBuilderAutosave({
    enabled,
    fingerprint,
    savedFingerprint,
    save,
    delayMs = 1200,
}: FormBuilderAutosaveOptions) {
    const saveActiveDraft = useEffectEvent(() => {
        save()
    })

    useEffect(() => {
        if (!enabled) return
        if (fingerprint === savedFingerprint) return

        const timeout = window.setTimeout(() => {
            saveActiveDraft()
        }, delayMs)

        return () => {
            window.clearTimeout(timeout)
        }
    }, [delayMs, enabled, fingerprint, savedFingerprint])
}
