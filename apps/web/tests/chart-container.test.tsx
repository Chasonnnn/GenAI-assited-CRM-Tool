import type { PropsWithChildren } from "react"
import * as React from "react"
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest"
import { render, waitFor } from "@testing-library/react"
import { ChartContainer } from "@/components/ui/chart"

const responsiveSpy = vi.fn()
let rectSpy: ReturnType<typeof vi.spyOn> | null = null

type DynamicComponent = React.ComponentType<Record<string, unknown>>

vi.mock("next/dynamic", () => ({
    __esModule: true,
    default: (loader: () => Promise<DynamicComponent>) => {
        return function DynamicComponentWrapper(props: Record<string, unknown>) {
            const [Component, setComponent] = React.useState<DynamicComponent | null>(null)

            React.useEffect(() => {
                let mounted = true
                loader().then((Resolved) => {
                    if (mounted) {
                        setComponent(() => Resolved)
                    }
                })
                return () => {
                    mounted = false
                }
            }, [])

            if (!Component) return null
            return <Component {...props} />
        }
    },
}))

vi.mock("recharts", () => ({
    ResponsiveContainer: ({
        children,
        height,
        minHeight,
        minWidth,
        width,
    }: PropsWithChildren<{ height?: number | string; minHeight?: number; minWidth?: number; width?: number | string }>) => {
        responsiveSpy({ height, minHeight, minWidth, width })
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
                expect.objectContaining({ height: "100%", minHeight: 1, minWidth: 1, width: "100%" })
            )
        })
    })
})
