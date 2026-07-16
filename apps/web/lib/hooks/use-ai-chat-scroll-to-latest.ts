"use client"

import { useEffect, type RefObject } from "react"

type AIChatScrollToLatestOptions = {
    shouldStickToBottomRef?: RefObject<boolean>
}

export function useAIChatScrollToLatest<Element extends HTMLElement>(
    scrollRef: RefObject<Element | null>,
    messages: readonly unknown[],
    { shouldStickToBottomRef }: AIChatScrollToLatestOptions = {},
) {
    useEffect(() => {
        if (shouldStickToBottomRef?.current === false) return

        const container = scrollRef.current
        if (!container) return

        if (!shouldStickToBottomRef || typeof window.requestAnimationFrame !== "function") {
            container.scrollTop = container.scrollHeight
            return
        }

        const animationFrame = window.requestAnimationFrame(() => {
            container.scrollTop = container.scrollHeight
        })

        return () => {
            window.cancelAnimationFrame(animationFrame)
        }
    }, [messages, scrollRef, shouldStickToBottomRef])
}
