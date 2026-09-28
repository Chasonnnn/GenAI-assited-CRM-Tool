"use client"

import { useEffect, useEffectEvent } from "react"

type FormBuilderAutosaveOptions = {
    enabled: boolean
    fingerprint: string
    savedFingerprint: string
    // The draft whose last save failed. Autosave does not resend it while it is unchanged.
    failedFingerprint: string
    clearFailedFingerprint: () => void
    // Queues the save. The builder's save queue applies its result.
    save: () => void
    delayMs?: number
}

export function useFormBuilderAutosave({
    enabled,
    fingerprint,
    savedFingerprint,
    failedFingerprint,
    clearFailedFingerprint,
    save,
    delayMs = 1200,
}: FormBuilderAutosaveOptions) {
    // Any edit after a failure ends the pause, so returning to the failed content autosaves it
    // again.
    if (failedFingerprint && failedFingerprint !== fingerprint) clearFailedFingerprint()

    const saveActiveDraft = useEffectEvent(() => {
        save()
    })

    useEffect(() => {
        if (!enabled) return
        if (fingerprint === savedFingerprint || fingerprint === failedFingerprint) return

        const timeout = window.setTimeout(() => {
            saveActiveDraft()
        }, delayMs)

        return () => {
            window.clearTimeout(timeout)
        }
    }, [delayMs, enabled, failedFingerprint, fingerprint, savedFingerprint])
}
