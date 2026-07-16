"use client"

import { useEffect, type RefObject } from "react"

export function useFocusWhen<T extends HTMLElement & { select?: () => void }>(
    ref: RefObject<T | null>,
    active: boolean,
    options: { select?: boolean } = {},
) {
    const shouldSelect = options.select === true

    useEffect(() => {
        if (!active) return
        const element = ref.current
        if (!element) return
        element.focus()
        if (shouldSelect) element.select?.()
    }, [active, ref, shouldSelect])
}
