import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { ConditionValueInput } from "@/components/automation/workflow-editor/shared"
import type { Condition } from "@/lib/api/workflows"

describe("workflow condition values", () => {
    it.each([
        { field: "full_name", value: "Jane", next: "Alex" },
        { field: "num_deliveries", value: 1, next: 2 },
        { field: "date_of_birth", value: "1990-01-01", next: "1991-02-03" },
    ])("names and edits the $field value", ({ field, value, next }) => {
        const onChange = vi.fn()
        render(
            <ConditionValueInput
                ariaLabel="Condition 2 value"
                condition={{ field, operator: "equals", value }}
                options={null}
                onChange={onChange}
            />,
        )

        const input = screen.getByLabelText("Condition 2 value")
        expect(input).toHaveValue(value)
        fireEvent.change(input, { target: { value: String(next) } })
        expect(onChange).toHaveBeenCalledWith(next)
    })

    it("names the disabled value for a valueless operator", () => {
        render(
            <ConditionValueInput
                ariaLabel="Condition 1 value"
                condition={{ field: "full_name", operator: "is_empty", value: null }}
                options={null}
                onChange={vi.fn()}
            />,
        )

        expect(screen.getByRole("textbox", { name: "Condition 1 value" })).toBeDisabled()
    })

    it("names and toggles a boolean value", () => {
        const onChange = vi.fn()
        render(
            <ConditionValueInput
                ariaLabel="Condition 3 value"
                condition={{ field: "is_priority", operator: "equals", value: false }}
                options={null}
                onChange={onChange}
            />,
        )

        fireEvent.click(screen.getByRole("switch", { name: "Condition 3 value" }))
        expect(onChange).toHaveBeenCalledWith(true, expect.anything())
    })

    it.each(["equals", "in"])("names the %s picker with empty and selected values", (operator) => {
        const props = {
            ariaLabel: "Condition 1 value",
            condition: { field: "state", operator, value: "" } as Condition,
            options: [{ value: "CA", label: "California" }],
            onChange: vi.fn(),
        }
        const { rerender } = render(<ConditionValueInput {...props} />)
        const role = operator === "in" ? "button" : "combobox"
        expect(screen.getByRole(role, { name: /Condition 1 value/ })).toHaveTextContent(
            operator === "in" ? "Select values" : "Select value",
        )

        rerender(
            <ConditionValueInput
                {...props}
                condition={{ ...props.condition, value: operator === "in" ? ["CA"] : "CA" }}
            />,
        )
        expect(screen.getByRole(role, { name: /Condition 1 value/ })).toHaveTextContent(
            operator === "in" ? "1 selected" : "California",
        )
    })
})
