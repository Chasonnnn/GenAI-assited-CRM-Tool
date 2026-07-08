import React from "react"
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, within } from "@testing-library/react"

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
            key: "height_ft",
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
        expect(updateField).toHaveBeenLastCalledWith("height_ft", "5.58")
    })

    it("constrains state-code text fields to two uppercase letters", () => {
        const updateField = vi.fn()
        const setDatePickerOpen = vi.fn()
        const field: FormField = {
            key: "state",
            label: "State",
            type: "text",
            required: true,
            validation: {
                min_length: 2,
                max_length: 2,
                pattern: "^[A-Za-z]{2}$",
            },
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

        const stateInput = screen.getByLabelText(/state/i)
        expect(stateInput).toHaveAttribute("maxlength", "2")

        fireEvent.change(stateInput, {
            target: { value: "ca9lifornia" },
        })

        expect(updateField).toHaveBeenLastCalledWith("state", "CA")
    })

    it("applies configured numeric limits to weight fields", () => {
        const updateField = vi.fn()
        const setDatePickerOpen = vi.fn()
        const field: FormField = {
            key: "weight_lb",
            label: "Weight (lb)",
            type: "number",
            required: true,
            validation: {
                min_value: 1,
                max_value: 1000,
            },
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

        const weightInput = screen.getByLabelText(/weight/i)
        expect(weightInput).toHaveAttribute("type", "number")
        expect(weightInput).toHaveAttribute("inputmode", "numeric")
        expect(weightInput).toHaveAttribute("min", "1")
        expect(weightInput).toHaveAttribute("max", "1000")

        fireEvent.change(weightInput, {
            target: { value: "1e2" },
        })

        expect(updateField).toHaveBeenLastCalledWith("weight_lb", "12")
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

    it("renders compact yes/no choices in one row with the question outside option cards", () => {
        const updateField = vi.fn()
        const setDatePickerOpen = vi.fn()
        const field: FormField = {
            key: "age_range",
            label: "Are you currently between the ages of 21 and 36?",
            type: "radio",
            required: true,
            options: [
                { label: "No", value: "no" },
                { label: "Yes", value: "yes" },
            ],
        }

        render(
            <PublicFormFieldRenderer
                field={field}
                value={null}
                updateField={updateField}
                datePickerOpen={{}}
                setDatePickerOpen={setDatePickerOpen}
                density="compact"
            />,
        )

        const question = screen.getByText(/between the ages of 21 and 36/i)
        expect(question).toHaveClass("text-sm", "font-semibold")
        expect(question.closest("button")).toBeNull()

        const group = screen.getByRole("radiogroup", {
            name: /between the ages of 21 and 36/i,
        })
        expect(group).toHaveClass("grid-cols-2")

        const options = within(group).getAllByRole("radio")
        expect(options.map((option) => option.textContent)).toEqual(["Yes", "No"])
        expect(within(options[0]).getByText("Yes")).toHaveClass("text-sm", "font-medium")
        expect(within(options[1]).getByText("No")).toHaveClass("text-sm", "font-medium")
    })

    it("keeps non-binary compact choices stacked on narrow screens", () => {
        const updateField = vi.fn()
        const setDatePickerOpen = vi.fn()
        const field: FormField = {
            key: "race",
            label: "Please specify your race",
            type: "radio",
            required: true,
            options: [
                { label: "Asian", value: "asian" },
                { label: "Black", value: "black" },
                { label: "Hispanic", value: "hispanic" },
            ],
        }

        render(
            <PublicFormFieldRenderer
                field={field}
                value={null}
                updateField={updateField}
                datePickerOpen={{}}
                setDatePickerOpen={setDatePickerOpen}
                density="compact"
            />,
        )

        const group = screen.getByRole("radiogroup", { name: /specify your race/i })
        expect(group).toHaveClass("sm:grid-cols-2")
        expect(group).not.toHaveClass("grid-cols-2")
    })

    it("renders fixed table fields with per-row responses and notes", () => {
        const updateField = vi.fn()
        const setDatePickerOpen = vi.fn()
        const field: FormField = {
            key: "pregnancy_conditions",
            label: "Pregnancy conditions",
            type: "table",
            rows: [
                { key: "gestational_diabetes", label: "Gestational Diabetes" },
                { key: "preeclampsia", label: "Preeclampsia" },
            ],
            columns: [
                {
                    key: "status",
                    label: "Response",
                    type: "radio",
                    required: true,
                    options: [
                        { label: "No", value: "no" },
                        { label: "Yes", value: "yes" },
                    ],
                },
                {
                    key: "details",
                    label: "If yes, explain",
                    type: "textarea",
                    required: false,
                },
            ],
        }

        render(
            <PublicFormFieldRenderer
                field={field}
                value={[
                    { row_key: "gestational_diabetes", status: "no", details: "" },
                    { row_key: "preeclampsia", status: "", details: "" },
                ]}
                updateField={updateField}
                datePickerOpen={{}}
                setDatePickerOpen={setDatePickerOpen}
            />,
        )

        const diabetesRow = screen.getByRole("group", { name: /gestational diabetes row/i })
        expect(diabetesRow).toHaveClass(
            "@container/table-row",
            "@xl/table-row:grid",
            "@xl/table-row:grid-cols-[minmax(0,10rem)_minmax(0,12rem)_minmax(0,1fr)]",
            "@xl/table-row:items-start",
        )
        expect(within(diabetesRow).getByRole("radio", { name: "Yes" })).toHaveClass("rounded-md", "px-3", "py-2")
        const detailsInput = within(diabetesRow).getByPlaceholderText("Share any relevant details")
        expect(detailsInput.tagName).toBe("INPUT")
        expect(detailsInput).toHaveClass("h-11")
        fireEvent.click(within(diabetesRow).getByRole("radio", { name: "Yes" }))

        expect(updateField).toHaveBeenCalledWith(
            "pregnancy_conditions",
            expect.arrayContaining([
                expect.objectContaining({
                    row_key: "gestational_diabetes",
                    status: "yes",
                }),
            ]),
        )

        expect(screen.getByText("Gestational Diabetes")).toBeInTheDocument()
        expect(screen.getByText("Preeclampsia")).toBeInTheDocument()
        expect(screen.getAllByText("If yes, explain").length).toBeGreaterThan(0)
    })

    it("associates fixed table select columns with their visible labels", () => {
        const updateField = vi.fn()
        const setDatePickerOpen = vi.fn()
        const field: FormField = {
            key: "medical_history",
            label: "Medical history",
            type: "table",
            rows: [{ key: "surgeries", label: "Surgeries" }],
            columns: [
                {
                    key: "status",
                    label: "Response",
                    type: "select",
                    required: true,
                    options: [
                        { label: "No", value: "no" },
                        { label: "Yes", value: "yes" },
                    ],
                },
            ],
        }

        render(
            <PublicFormFieldRenderer
                field={field}
                value={[{ row_key: "surgeries", status: "" }]}
                updateField={updateField}
                datePickerOpen={{}}
                setDatePickerOpen={setDatePickerOpen}
            />,
        )

        const row = screen.getByRole("group", { name: /surgeries row/i })
        const responseSelect = within(row).getByRole("combobox", { name: /response/i })

        fireEvent.change(responseSelect, { target: { value: "yes" } })

        expect(updateField).toHaveBeenCalledWith(
            "medical_history",
            expect.arrayContaining([
                expect.objectContaining({
                    row_key: "surgeries",
                    status: "yes",
                }),
            ]),
        )
    })
})
