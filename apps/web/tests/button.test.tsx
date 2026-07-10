import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Button } from "@/components/ui/button"

describe("Button", () => {
    it("uses Base UI button semantics by default", () => {
        render(<Button disabled>Continue</Button>)

        const button = screen.getByRole("button", { name: "Continue" })
        expect(button).toHaveAttribute("type", "button")
        expect(button).toHaveAttribute("data-disabled")
    })

    it("supports custom interactive surfaces without applying visual variants", () => {
        render(
            <Button unstyled className="custom-surface">
                Open record
            </Button>,
        )

        const button = screen.getByRole("button", { name: "Open record" })
        expect(button).toHaveClass("custom-surface")
        expect(button).not.toHaveClass("h-9", "px-4")
    })

    it("preserves link semantics when a button style renders an anchor", () => {
        render(
            <Button render={<a href="/settings" />} variant="outline">
                Settings
            </Button>,
        )

        const link = screen.getByRole("link", { name: "Settings" })
        expect(link).toHaveAttribute("href", "/settings")
        expect(link).not.toHaveAttribute("role", "button")
        expect(screen.queryByRole("button", { name: "Settings" })).not.toBeInTheDocument()
    })
})
