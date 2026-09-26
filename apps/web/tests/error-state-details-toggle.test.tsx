import { fireEvent, render, screen } from "@testing-library/react"

import { ErrorState } from "@/components/error-state"

vi.mock("@/lib/client-error-telemetry", () => ({ reportClientError: vi.fn() }))

describe("error state details toggle", () => {
    it("rotates one chevron instead of swapping icons", () => {
        render(<ErrorState error={new Error("render failure")} reset={vi.fn()} showDetails />)

        const toggle = screen.getByRole("button", { name: "Error details" })
        expect(toggle.querySelectorAll("svg")).toHaveLength(1)

        const icon = toggle.querySelector("svg")
        expect(icon).toHaveClass("lucide-chevron-down", "transition-transform")
        expect(icon).not.toHaveClass("rotate-180")
        expect(icon).toHaveAttribute("aria-hidden", "true")

        fireEvent.click(toggle)

        expect(toggle).toHaveAttribute("aria-expanded", "true")
        expect(toggle.querySelectorAll("svg")).toHaveLength(1)
        expect(toggle.querySelector("svg")).toBe(icon)
        expect(icon).toHaveClass("rotate-180")
    })
})
