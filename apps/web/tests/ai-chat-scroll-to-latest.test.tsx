import { renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { useAIChatScrollToLatest } from "@/lib/hooks/use-ai-chat-scroll-to-latest"

describe("useAIChatScrollToLatest", () => {
    afterEach(() => {
        vi.unstubAllGlobals()
    })

    it("does not schedule a scroll when the user is no longer following the latest message", () => {
        const container = document.createElement("div")
        Object.defineProperty(container, "scrollHeight", {
            configurable: true,
            value: 400,
        })
        Object.defineProperty(container, "scrollTop", {
            configurable: true,
            writable: true,
            value: 120,
        })
        const scrollRef = { current: container }
        const shouldStickToBottomRef = { current: false }
        const requestAnimationFrame = vi.fn()

        vi.stubGlobal("requestAnimationFrame", requestAnimationFrame)

        renderHook(() =>
            useAIChatScrollToLatest(scrollRef, [{ id: "assistant-1", content: "Latest response" }], {
                shouldStickToBottomRef,
            }),
        )

        expect(requestAnimationFrame).not.toHaveBeenCalled()
        expect(container.scrollTop).toBe(120)
    })

    it("scrolls again when streamed message content changes without changing message count", () => {
        const container = document.createElement("div")
        Object.defineProperty(container, "scrollHeight", {
            configurable: true,
            value: 400,
        })
        Object.defineProperty(container, "scrollTop", {
            configurable: true,
            writable: true,
            value: 0,
        })
        const scrollRef = { current: container }

        const { rerender } = renderHook(
            ({ messages }) => useAIChatScrollToLatest(scrollRef, messages),
            {
                initialProps: {
                    messages: [{ id: "assistant-1", content: "" }],
                },
            },
        )

        expect(container.scrollTop).toBe(400)
        container.scrollTop = 0

        rerender({
            messages: [{ id: "assistant-1", content: "Streaming response" }],
        })

        expect(container.scrollTop).toBe(400)
    })
})
