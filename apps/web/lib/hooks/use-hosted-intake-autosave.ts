"use client"

import { useEffect, useEffectEvent } from "react"

export function useHostedIntakeAutosave({
    enabled,
    scopeKey,
    trigger,
    skipNextSave,
    onSkipNextSave,
    onSave,
    delay = 1500,
}: {
    enabled: boolean
    scopeKey: string
    trigger: unknown
    skipNextSave: boolean
    onSkipNextSave: () => void
    onSave: () => void | Promise<void>
    delay?: number
}) {
    const onSaveEvent = useEffectEvent(onSave)
    const onSkipNextSaveEvent = useEffectEvent(onSkipNextSave)

    useEffect(() => {
        if (!enabled) return
        if (skipNextSave) {
            onSkipNextSaveEvent()
            return
        }

        const timer = window.setTimeout(() => {
            void onSaveEvent()
        }, delay)

        return () => {
            window.clearTimeout(timer)
        }
    }, [delay, enabled, scopeKey, skipNextSave, trigger])
}
