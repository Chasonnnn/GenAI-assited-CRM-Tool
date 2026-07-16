import { renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { useEmbedFormResizeReporting } from "@/lib/hooks/use-embed-form-resize-reporting"

describe("useEmbedFormResizeReporting", () => {
    afterEach(() => {
        vi.unstubAllGlobals()
    })

    it("reports the current height and disconnects its observer on unmount", () => {
        const element = document.createElement("div")
        vi.spyOn(element, "getBoundingClientRect").mockReturnValue({
            bottom: 123.4,
            height: 123.4,
            left: 0,
            right: 0,
            top: 0,
            width: 0,
            x: 0,
            y: 0,
            toJSON: () => ({}),
        })
        const observe = vi.fn()
        const disconnect = vi.fn()
        const ResizeObserver = vi.fn(function ResizeObserver() {
            return { observe, disconnect }
        })
        const postMessage = vi.fn()
        const originalParent = Object.getOwnPropertyDescriptor(window, "parent")

        vi.stubGlobal("ResizeObserver", ResizeObserver)
        Object.defineProperty(window, "parent", {
            configurable: true,
            value: { postMessage },
        })

        try {
            const containerRef = { current: element }
            const { unmount } = renderHook(() =>
                useEmbedFormResizeReporting(
                    containerRef,
                    "https://www.ewisurrogacy.com",
                ),
            )

            expect(observe).toHaveBeenCalledWith(element)
            expect(postMessage).toHaveBeenCalledWith(
                { type: "sf:form:resize", height: 124 },
                "https://www.ewisurrogacy.com",
            )

            unmount()

            expect(disconnect).toHaveBeenCalledTimes(1)
        } finally {
            if (originalParent) {
                Object.defineProperty(window, "parent", originalParent)
            }
        }
    })
})
