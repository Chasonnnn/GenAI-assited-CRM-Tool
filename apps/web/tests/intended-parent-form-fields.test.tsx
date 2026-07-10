import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { IntendedParentFormFields } from "@/components/intended-parents/IntendedParentFormFields"
import { EMPTY_INTENDED_PARENT_FORM_VALUES } from "@/components/intended-parents/intended-parent-form-values"

function chooseBaseUiOption(trigger: HTMLElement, optionName: string) {
    fireEvent.click(trigger)
    const option = screen.getByRole("option", { name: optionName })
    fireEvent.mouseMove(option)
    fireEvent.click(option)
}

describe("IntendedParentFormFields", () => {
    it("uses shared Base UI selects for pronouns and state values", () => {
        const onChange = vi.fn()

        render(
            <IntendedParentFormFields
                values={{ ...EMPTY_INTENDED_PARENT_FORM_VALUES }}
                onChange={onChange}
                idPrefix="test_"
                showClinicSection={false}
                showInternalNotes={false}
            />,
        )

        const pronouns = screen.getByRole("combobox", { name: "Pronouns" })
        const state = screen.getByRole("combobox", { name: "State" })
        expect(pronouns).toHaveAttribute("data-slot", "select-trigger")
        expect(state).toHaveAttribute("data-slot", "select-trigger")

        chooseBaseUiOption(pronouns, "They/Them")
        chooseBaseUiOption(state, "California (CA)")

        expect(onChange).toHaveBeenCalledWith("pronouns", "They/Them")
        expect(onChange).toHaveBeenCalledWith("state", "CA")
    })
})
