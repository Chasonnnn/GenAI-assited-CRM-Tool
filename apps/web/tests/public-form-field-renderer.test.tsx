import React from "react"
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import type { FormField } from "@/lib/api/forms"
import { PublicFormFieldRenderer } from "@/components/forms/PublicFormFieldRenderer"

vi.mock("@/components/ui/calendar", () => ({
    Calendar: ({
        captionLayout,
        startMonth,
        endMonth,
    }: {
        captionLayout?: string
        startMonth?: Date
        endMonth?: Date
    }) => (
        <div
            data-testid="calendar"
            data-caption-layout={captionLayout}
            data-start-month={startMonth?.toISOString()}
            data-end-month={endMonth?.toISOString()}
        />
    ),
}))

describe("PublicFormFieldRenderer", () => {
    it("renders date fields with month/year dropdown navigation", () => {
        const updateField = vi.fn()
        const setDatePickerOpen = vi.fn()
        const field: FormField = {
            key: "date_of_birth",
            label: "Date of Birth",
            type: "date",
            required: true,
        }

        render(
            <PublicFormFieldRenderer
                field={field}
                value={null}
                updateField={updateField}
                datePickerOpen={{ date_of_birth: true }}
                setDatePickerOpen={setDatePickerOpen}
            />,
        )

        expect(screen.getByTestId("calendar")).toHaveAttribute("data-caption-layout", "dropdown")
        expect(screen.getByTestId("calendar")).toHaveAttribute(
            "data-start-month",
            expect.stringContaining("1950-01-01"),
        )
        expect(screen.getByTestId("calendar")).toHaveAttribute(
            "data-end-month",
            expect.stringContaining(new Date().getFullYear().toString()),
        )
    })

    it("does not cap non-dob date fields to today", () => {
        const updateField = vi.fn()
        const setDatePickerOpen = vi.fn()
        const field: FormField = {
            key: "transfer_date",
            label: "Transfer Date",
            type: "date",
            required: true,
        }

        render(
            <PublicFormFieldRenderer
                field={field}
                value={null}
                updateField={updateField}
                datePickerOpen={{ transfer_date: true }}
                setDatePickerOpen={setDatePickerOpen}
            />,
        )

        expect(screen.getByTestId("calendar")).not.toHaveAttribute("data-caption-layout", "dropdown")
        expect(screen.getByTestId("calendar")).not.toHaveAttribute("data-start-month")
        expect(screen.getByTestId("calendar")).not.toHaveAttribute("data-end-month")
    })

    it("renders height fields as separate feet and inches controls", () => {
        const updateField = vi.fn()
        const setDatePickerOpen = vi.fn()
        const field: FormField = {
            key: "height",
            label: "Height",
            type: "height",
        }

        render(
            <PublicFormFieldRenderer
                field={field}
                value={"5.50"}
                updateField={updateField}
                datePickerOpen={{}}
                setDatePickerOpen={setDatePickerOpen}
            />,
        )

        fireEvent.change(screen.getByLabelText(/height feet/i), {
            target: { value: "5" },
        })
        fireEvent.change(screen.getByLabelText(/height inches/i), {
            target: { value: "7" },
        })

        expect(screen.getByLabelText(/height feet/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/height inches/i)).toBeInTheDocument()
        expect(updateField).toHaveBeenLastCalledWith("height", "5.58")
    })

    it("normalizes height values that would otherwise round to 12 inches", () => {
        const updateField = vi.fn()
        const setDatePickerOpen = vi.fn()
        const field: FormField = {
            key: "height",
            label: "Height",
            type: "height",
        }

        render(
            <PublicFormFieldRenderer
                field={field}
                value={"5.999"}
                updateField={updateField}
                datePickerOpen={{}}
                setDatePickerOpen={setDatePickerOpen}
            />,
        )

        expect(screen.getByLabelText(/height feet/i)).toHaveValue("6")
        expect(screen.getByLabelText(/height inches/i)).toHaveValue("0")
    })

    it("clears the stored height when both selects are reset", () => {
        const field: FormField = {
            key: "height",
            label: "Height",
            type: "height",
        }

        function Wrapper() {
            const [value, setValue] = React.useState<string | null>("5.50")

            return (
                <PublicFormFieldRenderer
                    field={field}
                    value={value}
                    updateField={(_fieldKey, nextValue) =>
                        setValue(typeof nextValue === "string" ? nextValue : null)
                    }
                    datePickerOpen={{}}
                    setDatePickerOpen={() => undefined}
                />
            )
        }

        render(<Wrapper />)

        fireEvent.change(screen.getByLabelText(/height inches/i), {
            target: { value: "" },
        })
        fireEvent.change(screen.getByLabelText(/height feet/i), {
            target: { value: "" },
        })

        expect(screen.getByLabelText(/height feet/i)).toHaveValue("")
        expect(screen.getByLabelText(/height inches/i)).toHaveValue("")
    })

    it("renders select option labels with the same small type scale as other controls", () => {
        const updateField = vi.fn()
        const setDatePickerOpen = vi.fn()
        const field: FormField = {
            key: "race",
            label: "What is your race",
            type: "radio",
            required: true,
            options: [
                { label: "Asian", value: "asian" },
                { label: "Black", value: "black" },
                { label: "Option 3", value: "option_3" },
            ],
        }

        render(
            <PublicFormFieldRenderer
                field={field}
                value={null}
                updateField={updateField}
                datePickerOpen={{}}
                setDatePickerOpen={setDatePickerOpen}
            />,
        )

        expect(screen.getByText("Asian")).toHaveClass("text-sm")
        expect(screen.getByText("Black")).toHaveClass("text-sm")
        expect(screen.getByText("Option 3")).toHaveClass("text-sm")
    })
})
