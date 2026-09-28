import { act, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { SurrogatesFloatingScrollbar } from "@/components/surrogates/SurrogatesFloatingScrollbar"

function setFinePointer() {
    Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: (query: string) => ({
            matches: /\((any-)?(hover: hover|pointer: fine)\)/.test(query),
            media: query,
            onchange: null,
            addListener: vi.fn(),
            removeListener: vi.fn(),
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
            dispatchEvent: vi.fn(),
        }),
    })
}

function setOverflowingMetrics(element: HTMLElement) {
    const left = 24
    const top = 760
    const width = 500
    const height = 280

    Object.defineProperty(element, "clientWidth", { configurable: true, value: width })
    Object.defineProperty(element, "scrollWidth", { configurable: true, value: 1200 })
    Object.defineProperty(element, "scrollLeft", { configurable: true, writable: true, value: 0 })
    Object.defineProperty(element, "getBoundingClientRect", {
        configurable: true,
        value: () =>
            ({
                x: left,
                y: top,
                top,
                left,
                right: left + width,
                bottom: top + height,
                width,
                height,
                toJSON: () => ({}),
            }) as DOMRect,
    })
}

function transitionProperties(element: Element) {
    const token = Array.from(element.classList).find((name) => name.startsWith("transition-["))
    return token ? token.slice("transition-[".length, -1).split(",") : []
}

describe("SurrogatesFloatingScrollbar motion", () => {
    beforeEach(() => {
        setFinePointer()
    })

    afterEach(() => {
        vi.useRealTimers()
        vi.restoreAllMocks()
    })

    it("transitions the translate offset that the surface drops by when it fades out", async () => {
        vi.useFakeTimers()
        render(
            <div data-testid="scroll-host">
                <SurrogatesFloatingScrollbar>
                    <div data-slot="table-container" data-testid="table-container" />
                </SurrogatesFloatingScrollbar>
            </div>
        )
        setOverflowingMetrics(screen.getByTestId("table-container"))

        act(() => {
            fireEvent.scroll(screen.getByTestId("scroll-host"))
        })

        const shell = screen.getByTestId("surrogates-floating-scrollbar")
        const surface = shell.firstElementChild!
        // The positioned wrapper only changes left/width, which must follow scrolling without lag.
        expect(transitionProperties(shell)).toEqual([])
        expect(surface).toHaveClass("translate-y-0", "opacity-100")
        expect(transitionProperties(surface)).toEqual(expect.arrayContaining(["translate", "opacity"]))

        await act(async () => {
            await vi.advanceTimersByTimeAsync(1_500)
        })

        expect(surface).toHaveClass("translate-y-1", "opacity-0")
        expect(transitionProperties(surface)).toEqual(expect.arrayContaining(["translate", "opacity"]))
    })
})
