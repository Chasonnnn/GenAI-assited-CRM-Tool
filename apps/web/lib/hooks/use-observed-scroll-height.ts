"use client"

import { useEffect, useState, type RefObject } from "react"

export function useObservedScrollHeight(
    elementRef: RefObject<HTMLElement | null>,
    enabled: boolean,
) {
    const [observedHeight, setObservedHeight] = useState(0)

    useEffect(() => {
        const element = elementRef.current
        if (!enabled || !element) return

        const updateHeight = () => {
            setObservedHeight(element.scrollHeight)
        }

        updateHeight()
        const resizeObserver = new ResizeObserver(updateHeight)
        resizeObserver.observe(element)

        return () => {
            resizeObserver.disconnect()
        }
    }, [elementRef, enabled])

    return enabled ? observedHeight : 0
}
