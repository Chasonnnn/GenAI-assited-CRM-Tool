import { describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { InlineEditField } from "@/components/inline-edit-field"
import { InlineDateField } from "@/components/inline-date-field"
import { CombinedMedicalInsuranceCard } from "@/components/surrogates/CombinedMedicalInsuranceCard"
import { RecordEditingContext } from "@/components/records/RecordEditingContext"
import { InlineSelectField, InlineHeightField, InlineRaceField, InlineWeightField, SsnField } from "@/components/records/RecordProfileFields"

describe("Inline field accessibility", () => {
    it("closes shared profile editors and disables sensitive reveal after edit access is revoked", () => {
        const onSave = vi.fn()
        const onReveal = vi.fn()
        const fields = <>
            <InlineSelectField label="Education" value="college" options={[{value: "college", label: "College"}]} onSave={onSave} saveOnSelect={false} />
            <InlineHeightField value={5.5} onSave={onSave} />
            <InlineRaceField value="asian" onSave={onSave} />
            <InlineWeightField value={140} onSave={onSave} />
            <SsnField label="SSN" maskedValue="***-**-1234" revealedValue={null} onReveal={onReveal} onSave={onSave} isRevealPending={false} />
        </>
        const view = render(<RecordEditingContext value={true}>{fields}</RecordEditingContext>)
        for (const label of ["Education", "Height", "Race / Ethnicity", "Weight", "SSN"]) {
            fireEvent.click(screen.getByRole("button", {name: `Edit ${label}`}))
            expect(screen.getByRole("button", {name: `Save ${label}`})).toBeEnabled()
        }
        view.rerender(<RecordEditingContext value={false}>{fields}</RecordEditingContext>)
        expect(screen.queryAllByRole("button", {name: /^Save /})).toHaveLength(0)
        expect(screen.queryAllByRole("textbox")).toHaveLength(0)
        expect(screen.getByRole("button", {name: "Reveal SSN"})).toBeDisabled()
        expect(onSave).not.toHaveBeenCalled()
        expect(onReveal).not.toHaveBeenCalled()
    })

    it("disables every insurance field when the shared card is read-only", () => {
        const onUpdate = vi.fn()
        render(<CombinedMedicalInsuranceCard readOnly onUpdate={onUpdate} surrogateData={{
            insurance_company: "Example insurer", insurance_plan_name: "Gold plan",
            insurance_policy_number: "test-policy", insurance_subscriber_dob: "1990-05-14",
        }} />)
        expect(screen.getByText("Gold plan")).toBeInTheDocument()
        expect(screen.getByText("test-policy")).toBeInTheDocument()
        for (const button of screen.queryAllByRole("button", { name: /^Edit / })) {
            expect(button).toBeDisabled()
        }
        expect(onUpdate).not.toHaveBeenCalled()
    })

    it('removes an open inline editor when it becomes read-only', () => {
        const onSave = vi.fn()
        const view = render(<InlineEditField value="Original" label="Name" onSave={onSave} />)
        fireEvent.click(screen.getByRole('button', { name: 'Edit Name' }))
        view.rerender(<InlineEditField value="Original" label="Name" onSave={onSave} readOnly />)
        expect(screen.getByText('Original')).toBeInTheDocument()
        expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Edit Name' })).not.toBeInTheDocument()
        expect(onSave).not.toHaveBeenCalled()
    })

    it("uses a native button trigger for InlineEditField display mode", () => {
        render(
            <InlineEditField
                value="test@example.com"
                label="Email"
                onSave={vi.fn().mockResolvedValue(undefined)}
            />
        )

        const trigger = screen.getByRole("button", { name: "Edit Email" })
        expect(trigger.tagName).toBe("BUTTON")
        expect(trigger).toHaveAttribute("type", "button")
        fireEvent.click(trigger)

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
