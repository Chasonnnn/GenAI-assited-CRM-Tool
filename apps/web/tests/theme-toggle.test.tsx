import { fireEvent, render, screen } from "@testing-library/react"
import "@testing-library/jest-dom"
import { describe, expect, it, vi } from "vitest"

import { ThemeToggle } from "@/components/theme-toggle"

const mockSetTheme = vi.fn()

vi.mock("next-themes", () => ({
    useTheme: () => ({
        resolvedTheme: "dark",
        setTheme: mockSetTheme,
    }),
}))

describe("ThemeToggle", () => {
    it("uses a single accessible name source", async () => {
        const { container } = render(<ThemeToggle />)

        expect(await screen.findByRole("button", { name: "Toggle theme" })).toBeInTheDocument()
        expect(container.querySelector(".sr-only")).toBeNull()
        expect(
            Array.from(container.querySelectorAll("svg")).every(
                (icon) => icon.getAttribute("aria-hidden") === "true"
            )
        ).toBe(true)
    })

    it("toggles the theme directly", async () => {
        render(<ThemeToggle />)

        fireEvent.click(screen.getByRole("button", { name: "Toggle theme" }))

        expect(mockSetTheme).toHaveBeenCalledWith("light")
    })
})
