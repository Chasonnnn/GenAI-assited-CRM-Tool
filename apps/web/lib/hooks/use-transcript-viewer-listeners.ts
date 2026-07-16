"use client"

import { useEffect, useEffectEvent, type RefObject } from "react"

export function useTranscriptViewerListeners({
    containerRef,
    enabled,
    onMouseUp,
    onClick,
    onKeyDown,
}: {
    containerRef: RefObject<HTMLElement | null>
    enabled: boolean
    onMouseUp: (event: MouseEvent) => void
    onClick: (event: MouseEvent) => void
    onKeyDown: (event: KeyboardEvent) => void
}) {
    const onMouseUpEvent = useEffectEvent(onMouseUp)
    const onClickEvent = useEffectEvent(onClick)
    const onKeyDownEvent = useEffectEvent(onKeyDown)

    useEffect(() => {
        const container = containerRef.current
        if (!enabled || !container) return

        const handleMouseUp = (event: MouseEvent) => onMouseUpEvent(event)
        const handleClick = (event: MouseEvent) => onClickEvent(event)
        const handleKeyDown = (event: KeyboardEvent) => onKeyDownEvent(event)

        container.addEventListener("mouseup", handleMouseUp)
        container.addEventListener("click", handleClick)
        document.addEventListener("keydown", handleKeyDown)

        return () => {
            container.removeEventListener("mouseup", handleMouseUp)
            container.removeEventListener("click", handleClick)
            document.removeEventListener("keydown", handleKeyDown)
        }
    }, [containerRef, enabled])
}
