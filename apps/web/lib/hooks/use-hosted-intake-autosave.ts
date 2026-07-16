"use client"

import { useEffect, useEffectEvent, type RefObject } from "react"

export function useHostedIntakeAutosave({
    enabled,
    scopeKey,
    trigger,
    skipNextSaveRef,
    onSave,
    delay = 1500,
}: {
    enabled: boolean
    scopeKey: string
    trigger: unknown
    skipNextSaveRef: RefObject<boolean>
    onSave: () => void | Promise<void>
    delay?: number
}) {
    const onSaveEvent = useEffectEvent(onSave)

    useEffect(() => {
        if (!enabled) return
        if (skipNextSaveRef.current) {
            skipNextSaveRef.current = false
            return
        }

        const timer = window.setTimeout(() => {
            void onSaveEvent()
        }, delay)

        return () => {
            window.clearTimeout(timer)
        }
    }, [delay, enabled, scopeKey, skipNextSaveRef, trigger])
}
