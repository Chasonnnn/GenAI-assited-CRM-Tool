"use client"

import { useEffect, useEffectEvent } from "react"

export function useAIToggleHotkey(enabled: boolean, onToggle: () => void) {
    const onToggleEvent = useEffectEvent(onToggle)

    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (
                (event.metaKey || event.ctrlKey) &&
                event.shiftKey &&
                event.key.toLowerCase() === "a"
            ) {
                event.preventDefault()
                if (enabled) {
                    onToggleEvent()
                }
            }
        }

        window.addEventListener("keydown", handleKeyDown)
        return () => {
            window.removeEventListener("keydown", handleKeyDown)
        }
    }, [enabled])
}
