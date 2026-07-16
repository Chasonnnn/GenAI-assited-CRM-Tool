import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useObservedScrollHeight } from "@/lib/hooks/use-observed-scroll-height"

const resizeObserverState = vi.hoisted(() => ({
    callback: null as ResizeObserverCallback | null,
    observe: vi.fn(),
    disconnect: vi.fn(),
}))

class ResizeObserverMock {
    constructor(callback: ResizeObserverCallback) {
        resizeObserverState.callback = callback
    }

    observe = resizeObserverState.observe
    disconnect = resizeObserverState.disconnect
    unobserve = vi.fn()
}

describe("useObservedScrollHeight", () => {
    beforeEach(() => {
        resizeObserverState.callback = null
        resizeObserverState.observe.mockReset()
        resizeObserverState.disconnect.mockReset()
        vi.stubGlobal("ResizeObserver", ResizeObserverMock)
    })

    it("observes only while enabled and reports initial and resized heights", () => {
        const element = document.createElement("div")
        let scrollHeight = 240
        Object.defineProperty(element, "scrollHeight", {
            configurable: true,
            get: () => scrollHeight,
        })
        const elementRef = { current: element }
        const view = renderHook(
            ({ enabled }) => useObservedScrollHeight(elementRef, enabled),
            {
                initialProps: {
                    enabled: false,
                },
            }
        )

        expect(view.result.current).toBe(0)
        expect(resizeObserverState.observe).not.toHaveBeenCalled()

        view.rerender({ enabled: true })
        expect(view.result.current).toBe(240)
        expect(resizeObserverState.observe).toHaveBeenCalledWith(element)

        scrollHeight = 480
        act(() => {
            resizeObserverState.callback?.([], {} as ResizeObserver)
        })
        expect(view.result.current).toBe(480)

        view.rerender({ enabled: false })
        expect(resizeObserverState.disconnect).toHaveBeenCalledTimes(1)
    })
})
