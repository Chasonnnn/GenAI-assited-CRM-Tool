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

    it("keeps InlineEditField draft edits stable while parent data refreshes", () => {
        const { rerender } = render(
            <InlineEditField
                value="old@example.com"
                label="Email"
                onSave={vi.fn().mockResolvedValue(undefined)}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: "Edit Email" }))
        const input = screen.getByRole("textbox", { name: "Email" })
        fireEvent.change(input, { target: { value: "draft@example.com" } })

        rerender(
            <InlineEditField
                value="fresh@example.com"
                label="Email"
                onSave={vi.fn().mockResolvedValue(undefined)}
            />
        )

        expect(screen.getByRole("textbox", { name: "Email" })).toHaveValue("draft@example.com")
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

    it("keeps InlineDateField save and cancel controls together under the calendar picker", () => {
        render(
            <InlineDateField
                value="1990-05-27"
                label="Date of Birth"
                onSave={vi.fn().mockResolvedValue(undefined)}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: "Edit Date of Birth" }))

        const saveButton = screen.getByRole("button", { name: "Save Date of Birth" })
        const cancelButton = screen.getByRole("button", { name: "Cancel Date of Birth" })
        const datePicker = screen.getByRole("button", { name: "Date of Birth" })
        const actionRow = saveButton.parentElement

        expect(saveButton).toBeVisible()
        expect(cancelButton).toBeVisible()
        expect(actionRow).toBe(cancelButton.parentElement)
        expect(actionRow).toHaveClass("flex", "items-center")
        expect(actionRow?.previousElementSibling).toContainElement(datePicker)
        expect(actionRow?.parentElement).toHaveClass("flex-col")
    })

    it("adds focus-visible styles to inline display triggers", () => {
        render(
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

        expect(screen.getByRole("button", { name: "Edit Email" })).toHaveClass(
            "focus-visible:ring-2",
            "focus-visible:ring-ring"
        )
        expect(screen.getByRole("button", { name: "Edit Start Date" })).toHaveClass(
            "focus-visible:ring-2",
            "focus-visible:ring-ring"
        )
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
            expect(icon).toHaveClass("group-focus-visible:opacity-100")
        })
    })
})
