import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { SurrogatesFloatingScrollbar } from "@/components/surrogates/SurrogatesFloatingScrollbar"

type MediaListener = (event: MediaQueryListEvent) => void

function setFinePointer(matches: boolean) {
    Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: (query: string) => ({
            matches:
                query.includes("(any-hover: hover)") ||
                query.includes("(hover: hover)") ||
                query.includes("(any-pointer: fine)") ||
                query.includes("(pointer: fine)")
                    ? matches
                    : false,
            media: query,
            onchange: null,
            addListener: vi.fn(),
            removeListener: vi.fn(),
            addEventListener: vi.fn((_event: string, _handler: MediaListener) => undefined),
            removeEventListener: vi.fn((_event: string, _handler: MediaListener) => undefined),
            dispatchEvent: vi.fn(),
        }),
    })
}

function setScrollableMetrics(
    element: HTMLElement,
    options: {
        clientWidth: number
        scrollWidth: number
        left?: number
        top?: number
        width?: number
        height?: number
    }
) {
    const left = options.left ?? 24
    const top = options.top ?? 720
    const width = options.width ?? options.clientWidth
    const height = options.height ?? 240
    const right = left + width
    const bottom = top + height

    Object.defineProperty(element, "clientWidth", { configurable: true, value: options.clientWidth })
    Object.defineProperty(element, "scrollWidth", { configurable: true, value: options.scrollWidth })
    Object.defineProperty(element, "scrollLeft", { configurable: true, writable: true, value: 0 })
    Object.defineProperty(element, "getBoundingClientRect", {
        configurable: true,
        value: () =>
            ({
                x: left,
                y: top,
                top,
                left,
                right,
                bottom,
                width,
                height,
                toJSON: () => ({}),
            }) as DOMRect,
    })
}

function renderSubject() {
    return render(
        <div data-testid="scroll-host">
            <SurrogatesFloatingScrollbar>
                <div data-slot="table-container" data-testid="table-container">
                    <table>
                        <tbody>
                            <tr>
                                <td>Row</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </SurrogatesFloatingScrollbar>
        </div>
    )
}

describe("SurrogatesFloatingScrollbar", () => {
    beforeEach(() => {
        setFinePointer(true)
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    it("appears during active scrolling when overflow exists", async () => {
        renderSubject()
        const tableContainer = screen.getByTestId("table-container")
        const scrollHost = screen.getByTestId("scroll-host")
        setScrollableMetrics(tableContainer, { clientWidth: 500, scrollWidth: 1200, top: 760, height: 280 })

        await waitFor(() => {
            fireEvent.scroll(scrollHost)
            expect(screen.getByTestId("surrogates-floating-scrollbar")).toBeInTheDocument()
        })
    })

    it("appears when a parent container scrolls vertically", async () => {
        render(
            <div data-testid="scroll-host">
                <SurrogatesFloatingScrollbar>
                    <div data-slot="table-container" data-testid="table-container">
                        <table>
                            <tbody>
                                <tr>
                                    <td>Row</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </SurrogatesFloatingScrollbar>
            </div>
        )
        const tableContainer = screen.getByTestId("table-container")
        const scrollHost = screen.getByTestId("scroll-host")
        setScrollableMetrics(tableContainer, { clientWidth: 500, scrollWidth: 1200, top: 760, height: 280 })

        await waitFor(() => {
            fireEvent.scroll(scrollHost)
            expect(screen.getByTestId("surrogates-floating-scrollbar")).toBeInTheDocument()
        })
    })

    it("appears when mouse hovers near viewport bottom", async () => {
        renderSubject()
        const tableContainer = screen.getByTestId("table-container")
        setScrollableMetrics(tableContainer, { clientWidth: 500, scrollWidth: 1200, top: 760, height: 280 })

        await waitFor(() => {
            fireEvent.mouseMove(window, { clientY: window.innerHeight - 2, clientX: 240 })
            expect(screen.getByTestId("surrogates-floating-scrollbar")).toBeInTheDocument()
        })
    })

    it("hides after idle with fade-out animation", async () => {
        renderSubject()
        const tableContainer = screen.getByTestId("table-container")
        const scrollHost = screen.getByTestId("scroll-host")
        setScrollableMetrics(tableContainer, { clientWidth: 500, scrollWidth: 1200, top: 760, height: 280 })

        await waitFor(() => {
            fireEvent.scroll(scrollHost)
            expect(screen.getByTestId("surrogates-floating-scrollbar")).toBeInTheDocument()
        })

        await act(async () => {
            await new Promise((resolve) => window.setTimeout(resolve, 1800))
        })

        await waitFor(() => {
            expect(screen.queryByTestId("surrogates-floating-scrollbar")).not.toBeInTheDocument()
        })
    })

    it("does not show when there is no horizontal overflow", async () => {
        renderSubject()
        const tableContainer = screen.getByTestId("table-container")
        const scrollHost = screen.getByTestId("scroll-host")
        setScrollableMetrics(tableContainer, { clientWidth: 500, scrollWidth: 500 })

        fireEvent.scroll(scrollHost)

        await waitFor(() => {
            expect(screen.queryByTestId("surrogates-floating-scrollbar")).not.toBeInTheDocument()
        })
    })

    it("does not show on non fine-pointer devices", async () => {
        setFinePointer(false)
        renderSubject()
        const tableContainer = screen.getByTestId("table-container")
        const scrollHost = screen.getByTestId("scroll-host")
        setScrollableMetrics(tableContainer, { clientWidth: 500, scrollWidth: 1200, top: 760, height: 280 })

        fireEvent.scroll(scrollHost)

        await waitFor(() => {
            expect(screen.queryByTestId("surrogates-floating-scrollbar")).not.toBeInTheDocument()
        })
    })

    it("syncs horizontal scroll in both directions", async () => {
        renderSubject()
        const tableContainer = screen.getByTestId("table-container")
        const scrollHost = screen.getByTestId("scroll-host")
        setScrollableMetrics(tableContainer, { clientWidth: 500, scrollWidth: 1200, top: 760, height: 280 })

        await waitFor(() => {
            fireEvent.scroll(scrollHost)
            expect(screen.getByTestId("surrogates-floating-scrollbar")).toBeInTheDocument()
        })

        const floatingViewport = screen.getByTestId("surrogates-floating-scrollbar-viewport")

        tableContainer.scrollLeft = 120
        fireEvent.scroll(tableContainer)
        expect(floatingViewport.scrollLeft).toBe(120)

        floatingViewport.scrollLeft = 260
        fireEvent.scroll(floatingViewport)
        expect(tableContainer.scrollLeft).toBe(260)
    })

    it("hides floating bar when native table scrollbar is already visible", async () => {
        renderSubject()
        const tableContainer = screen.getByTestId("table-container")
        const scrollHost = screen.getByTestId("scroll-host")
        // Bottom is clearly in viewport, so native table scrollbar should already be accessible.
        setScrollableMetrics(tableContainer, { clientWidth: 500, scrollWidth: 1200, top: 120, height: 240 })

        fireEvent.scroll(scrollHost)

        await waitFor(() => {
            expect(screen.queryByTestId("surrogates-floating-scrollbar")).not.toBeInTheDocument()
        })
    })
})
