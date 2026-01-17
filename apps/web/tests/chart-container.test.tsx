import type { PropsWithChildren } from "react"
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest"
import { render, waitFor } from "@testing-library/react"
import { ChartContainer } from "@/components/ui/chart"

const responsiveSpy = vi.fn()
let rectSpy: ReturnType<typeof vi.spyOn> | null = null

vi.mock("recharts", () => ({
    ResponsiveContainer: ({
        children,
        minHeight,
        minWidth,
    }: PropsWithChildren<{ minHeight?: number; minWidth?: number }>) => {
        responsiveSpy({ minHeight, minWidth })
        return <div data-testid="responsive-container">{children}</div>
    },
    Tooltip: ({ children }: PropsWithChildren) => <div>{children}</div>,
    Legend: ({ children }: PropsWithChildren) => <div>{children}</div>,
}))

// Mock ResizeObserver since JSDOM doesn't have it
class MockResizeObserver {
    callback: ResizeObserverCallback
    constructor(callback: ResizeObserverCallback) {
        this.callback = callback
    }
    observe(element: Element) {
        // Simulate element having size
        this.callback(
            [{ target: element, contentRect: { width: 100, height: 100 } } as ResizeObserverEntry],
            this
        )
    }
    unobserve() { }
    disconnect() { }
}

vi.stubGlobal("ResizeObserver", MockResizeObserver)

describe("ChartContainer", () => {
    beforeEach(() => {
        responsiveSpy.mockClear()
        rectSpy = vi
            .spyOn(HTMLElement.prototype, "getBoundingClientRect")
            .mockReturnValue({
                width: 100,
                height: 100,
                top: 0,
                left: 0,
                right: 100,
                bottom: 100,
                x: 0,
                y: 0,
                toJSON: () => ({}),
            } as DOMRect)
    })

    afterEach(() => {
        rectSpy?.mockRestore()
        rectSpy = null
    })

    it("sets min dimensions on ResponsiveContainer", async () => {
        render(
            <ChartContainer config={{ series: { label: "Series", color: "#000000" } }}>
                <div>chart</div>
            </ChartContainer>
        )

        await waitFor(() => {
            expect(responsiveSpy).toHaveBeenCalledWith(
                expect.objectContaining({ minHeight: 1, minWidth: 1 })
            )
        })
    })
})
