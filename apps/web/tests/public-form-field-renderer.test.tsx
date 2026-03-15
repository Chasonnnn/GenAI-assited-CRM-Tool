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
})
