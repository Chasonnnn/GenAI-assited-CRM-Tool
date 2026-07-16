import { renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { useAIChatScrollToLatest } from "@/lib/hooks/use-ai-chat-scroll-to-latest"

describe("useAIChatScrollToLatest", () => {
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
