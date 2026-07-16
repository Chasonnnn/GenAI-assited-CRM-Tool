import { renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useAIToggleHotkey } from "@/lib/hooks/use-ai-toggle-hotkey"

describe("useAIToggleHotkey", () => {
    it("uses the latest enabled callback and removes the listener on unmount", () => {
        const firstToggle = vi.fn()
        const secondToggle = vi.fn()
        const { rerender, unmount } = renderHook(
            ({ enabled, onToggle }) => useAIToggleHotkey(enabled, onToggle),
            {
                initialProps: {
                    enabled: false,
                    onToggle: firstToggle,
                },
            },
        )

        window.dispatchEvent(
            new KeyboardEvent("keydown", {
                key: "a",
                metaKey: true,
                shiftKey: true,
            }),
        )
        expect(firstToggle).not.toHaveBeenCalled()

        rerender({ enabled: true, onToggle: secondToggle })
        const enabledHotkey = new KeyboardEvent("keydown", {
            cancelable: true,
            key: "A",
            ctrlKey: true,
            shiftKey: true,
        })
        window.dispatchEvent(enabledHotkey)

        expect(firstToggle).not.toHaveBeenCalled()
        expect(secondToggle).toHaveBeenCalledTimes(1)
        expect(enabledHotkey.defaultPrevented).toBe(true)

        unmount()
        window.dispatchEvent(
            new KeyboardEvent("keydown", {
                key: "a",
                metaKey: true,
                shiftKey: true,
            }),
        )
        expect(secondToggle).toHaveBeenCalledTimes(1)
    })
})
