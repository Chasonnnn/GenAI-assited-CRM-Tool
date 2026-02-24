import { describe, it, expect, vi } from "vitest"
import { createEvent, fireEvent, render, screen } from "@testing-library/react"

import { InlineEditField } from "@/components/inline-edit-field"
import { InlineDateField } from "@/components/inline-date-field"

describe("Inline field accessibility", () => {
    it("activates InlineEditField with Enter", () => {
        render(
            <InlineEditField
                value="test@example.com"
                label="Email"
                onSave={vi.fn().mockResolvedValue(undefined)}
            />
        )

        const trigger = screen.getByRole("button", { name: "Edit Email" })
        fireEvent.keyDown(trigger, { key: "Enter" })

        expect(screen.getByRole("textbox", { name: "Email" })).toBeInTheDocument()
    })

    it("activates InlineEditField with Space and prevents default scrolling", () => {
        render(
            <InlineEditField
                value="test@example.com"
                label="Email"
                onSave={vi.fn().mockResolvedValue(undefined)}
            />
        )

        const trigger = screen.getByRole("button", { name: "Edit Email" })
        const event = createEvent.keyDown(trigger, { key: " ", code: "Space", charCode: 32 })
        fireEvent(trigger, event)

        expect(event.defaultPrevented).toBe(true)
        expect(screen.getByRole("textbox", { name: "Email" })).toBeInTheDocument()
    })

    it("provides aria-label on InlineDateField display mode", () => {
        render(
            <InlineDateField
                value="2026-01-05"
                label="Start Date"
                onSave={vi.fn().mockResolvedValue(undefined)}
            />
        )

        expect(screen.getByRole("button", { name: "Edit Start Date" })).toBeInTheDocument()
    })

    it("hides decorative pencil icons from screen readers", () => {
        const { container } = render(
            <div>
                <InlineEditField
                    value="test@example.com"
                    label="Email"
                    onSave={vi.fn().mockResolvedValue(undefined)}
                />
                <InlineDateField
                    value="2026-01-05"
                    label="Start Date"
                    onSave={vi.fn().mockResolvedValue(undefined)}
                />
            </div>
        )

        const pencilIcons = container.querySelectorAll("svg.lucide-pencil")
        expect(pencilIcons.length).toBeGreaterThan(0)
        pencilIcons.forEach((icon) => {
            expect(icon).toHaveAttribute("aria-hidden", "true")
        })
    })
})
