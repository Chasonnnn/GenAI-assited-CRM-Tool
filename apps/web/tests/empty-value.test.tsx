import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { InlineDateField } from "@/components/inline-date-field"
import { InlineEditField } from "@/components/inline-edit-field"
import { RecordEditingContext } from "@/components/records/RecordEditingContext"
import {
    InlineHeightField,
    InlineRaceField,
    InlineSelectField,
    InlineWeightField,
} from "@/components/records/RecordProfileFields"
import { EMPTY_VALUE_TEXT, EmptyValue, isEmptyValue } from "@/components/ui/empty-value"

const save = () => vi.fn().mockResolvedValue(undefined)

function expectEmptyValue(element: HTMLElement) {
    const token = element.querySelector("[data-slot=empty-value]")
    expect(token).not.toBeNull()
    expect(token).toHaveTextContent("Not provided")
    expect(token?.querySelector("[aria-hidden=true]")).toHaveTextContent(EMPTY_VALUE_TEXT)
}

describe("EmptyValue", () => {
    it("shows a muted dash that screen readers announce as Not provided", () => {
        render(<EmptyValue />)

        const hiddenDash = screen.getByText("—")
        expect(hiddenDash).toHaveAttribute("aria-hidden", "true")
        expect(screen.getByText("Not provided")).toHaveClass("sr-only")
        expect(hiddenDash.parentElement).toHaveClass("text-muted-foreground")
    })

    it("treats null, undefined and blank strings as empty, but not zero", () => {
        expect(isEmptyValue(null)).toBe(true)
        expect(isEmptyValue(undefined)).toBe(true)
        expect(isEmptyValue("   ")).toBe(true)
        expect(isEmptyValue(0)).toBe(false)
        expect(isEmptyValue("VA")).toBe(false)
    })
})

describe("Inline fields show EmptyValue for missing values", () => {
    it("InlineEditField displays EmptyValue and keeps the placeholder inside the active input", () => {
        render(<InlineEditField value={null} label="State" placeholder="XX" onSave={save()} />)

        const trigger = screen.getByRole("button", { name: "Edit State" })
        expectEmptyValue(trigger)
        expect(trigger).not.toHaveTextContent("XX")

        fireEvent.click(trigger)
        expect(screen.getByRole("textbox", { name: "State" })).toHaveAttribute("placeholder", "XX")
    })

    it("InlineEditField does not show the legacy dash placeholder in the active input", () => {
        render(<InlineEditField value={null} label="City" placeholder="-" onSave={save()} />)

        fireEvent.click(screen.getByRole("button", { name: "Edit City" }))
        expect(screen.getByRole("textbox", { name: "City" })).not.toHaveAttribute("placeholder")
    })

    it("InlineEditField read-only mode displays EmptyValue", () => {
        const { container } = render(
            <RecordEditingContext.Provider value={false}>
                <InlineEditField value="" label="Fax" placeholder="Fax" onSave={save()} />
            </RecordEditingContext.Provider>
        )

        expectEmptyValue(container)
        expect(screen.queryByRole("button")).not.toBeInTheDocument()
    })

    it("InlineDateField displays EmptyValue instead of its placeholder", () => {
        render(<InlineDateField value={null} label="Due date" placeholder="Set date" onSave={save()} />)

        const trigger = screen.getByRole("button", { name: "Edit Due date" })
        expectEmptyValue(trigger)
        expect(trigger).not.toHaveTextContent("Set date")
    })

    it("record profile fields display EmptyValue", () => {
        render(
            <div>
                <InlineSelectField
                    value={null}
                    label="Marital Status"
                    options={[{ value: "single", label: "Single" }]}
                    onSave={save()}
                />
                <InlineHeightField value={null} onSave={save()} />
                <InlineWeightField value={null} onSave={save()} />
                <InlineRaceField value={null} onSave={save()} />
            </div>
        )

        for (const name of ["Edit Marital Status", "Edit Height", "Edit Weight", "Edit Race / Ethnicity"]) {
            const trigger = screen.getByRole("button", { name })
            expectEmptyValue(trigger)
            expect(trigger).not.toHaveTextContent("-")
        }
    })

    it("record profile fields keep real values", () => {
        render(
            <div>
                <InlineSelectField
                    value="single"
                    label="Marital Status"
                    options={[{ value: "single", label: "Single" }]}
                    onSave={save()}
                />
                <InlineWeightField value={0} onSave={save()} />
            </div>
        )

        expect(screen.getByRole("button", { name: "Edit Marital Status" })).toHaveTextContent("Single")
        expect(screen.getByRole("button", { name: "Edit Weight" })).toHaveTextContent("0 lb")
    })
})
