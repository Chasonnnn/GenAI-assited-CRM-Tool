import { renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useTranscriptViewerListeners } from "@/lib/hooks/use-transcript-viewer-listeners"

describe("useTranscriptViewerListeners", () => {
    it("uses the latest callbacks and removes all listeners on unmount", () => {
        const container = document.createElement("div")
        const containerRef = { current: container }
        const firstMouseUp = vi.fn()
        const firstClick = vi.fn()
        const firstKeyDown = vi.fn()
        const nextMouseUp = vi.fn()
        const nextClick = vi.fn()
        const nextKeyDown = vi.fn()

        const view = renderHook(
            ({ enabled, onMouseUp, onClick, onKeyDown }) =>
                useTranscriptViewerListeners({
                    containerRef,
                    enabled,
                    onMouseUp,
                    onClick,
                    onKeyDown,
                }),
            {
                initialProps: {
                    enabled: false,
                    onMouseUp: firstMouseUp,
                    onClick: firstClick,
                    onKeyDown: firstKeyDown,
                },
            }
        )

        container.dispatchEvent(new MouseEvent("mouseup"))
        expect(firstMouseUp).not.toHaveBeenCalled()

        view.rerender({
            enabled: true,
            onMouseUp: nextMouseUp,
            onClick: nextClick,
            onKeyDown: nextKeyDown,
        })

        container.dispatchEvent(new MouseEvent("mouseup"))
        container.dispatchEvent(new MouseEvent("click"))
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }))

        expect(firstMouseUp).not.toHaveBeenCalled()
        expect(firstClick).not.toHaveBeenCalled()
        expect(firstKeyDown).not.toHaveBeenCalled()
        expect(nextMouseUp).toHaveBeenCalledTimes(1)
        expect(nextClick).toHaveBeenCalledTimes(1)
        expect(nextKeyDown).toHaveBeenCalledTimes(1)

        view.unmount()
        container.dispatchEvent(new MouseEvent("mouseup"))
        container.dispatchEvent(new MouseEvent("click"))
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }))

        expect(nextMouseUp).toHaveBeenCalledTimes(1)
        expect(nextClick).toHaveBeenCalledTimes(1)
        expect(nextKeyDown).toHaveBeenCalledTimes(1)
    })
})
