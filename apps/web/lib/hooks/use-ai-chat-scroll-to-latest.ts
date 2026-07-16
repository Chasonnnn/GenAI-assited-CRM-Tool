"use client"

import { useEffect, type RefObject } from "react"

export function useAIChatScrollToLatest<Element extends HTMLElement>(
    scrollRef: RefObject<Element | null>,
    messages: readonly unknown[],
) {
    useEffect(() => {
        const container = scrollRef.current
        if (!container) return
        container.scrollTop = container.scrollHeight
    }, [messages, scrollRef])
}
