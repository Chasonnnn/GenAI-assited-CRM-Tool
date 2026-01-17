import type { PropsWithChildren } from "react"
import { describe, expect, it, vi } from "vitest"
import { render } from "@testing-library/react"
import { ChartContainer } from "@/components/ui/chart"

const responsiveSpy = vi.fn()

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

describe("ChartContainer", () => {
    it("sets min dimensions on ResponsiveContainer", () => {
        render(
            <ChartContainer config={{ series: { label: "Series", color: "#000000" } }}>
                <div>chart</div>
            </ChartContainer>
        )

        expect(responsiveSpy).toHaveBeenCalledWith(
            expect.objectContaining({ minHeight: 1, minWidth: 1 })
        )
    })
})
