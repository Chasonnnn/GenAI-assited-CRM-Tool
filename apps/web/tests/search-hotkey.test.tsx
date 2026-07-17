import { renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useSearchHotkey } from "@/lib/hooks/use-search-hotkey"

describe("useSearchHotkey", () => {
    it("uses the latest callback for command-k and removes the document listener on unmount", () => {
        const firstCallback = vi.fn()
        const secondCallback = vi.fn()
        const view = renderHook(
            ({ callback }) => useSearchHotkey(callback),
            { initialProps: { callback: firstCallback } }
        )

        const firstEvent = new KeyboardEvent("keydown", {
            key: "k",
            ctrlKey: true,
            bubbles: true,
            cancelable: true,
        })
        document.dispatchEvent(firstEvent)

        expect(firstCallback).toHaveBeenCalledTimes(1)
        expect(firstEvent.defaultPrevented).toBe(true)

        view.rerender({ callback: secondCallback })
        document.dispatchEvent(
            new KeyboardEvent("keydown", {
                key: "k",
                metaKey: true,
                bubbles: true,
                cancelable: true,
            })
        )

        expect(firstCallback).toHaveBeenCalledTimes(1)
        expect(secondCallback).toHaveBeenCalledTimes(1)

        view.unmount()
        document.dispatchEvent(
            new KeyboardEvent("keydown", {
                key: "k",
                ctrlKey: true,
                bubbles: true,
                cancelable: true,
            })
        )

        expect(secondCallback).toHaveBeenCalledTimes(1)
    })
})
