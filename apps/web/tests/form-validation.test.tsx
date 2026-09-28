import * as React from "react"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { Button } from "@/components/ui/button"
import { DateTimePicker } from "@/components/ui/date-time-picker"
import { ValidatedField } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { ApiError, RateLimitError, parseApiValidationIssues } from "@/lib/api"
import {
    formatValidationMessage,
    getActionErrorMessage,
    getApiFieldErrors,
} from "@/lib/forms/api-field-errors"
import { focusFirstInvalid, useFormValidation } from "@/lib/forms/use-form-validation"
import {
    EMAIL_INVALID_MESSAGE,
    isValidEmail,
    validateEmail,
    validateIntegerRange,
    validateRequired,
} from "@/lib/forms/validators"

describe("ValidatedField", () => {
    it("wires label, aria-invalid and aria-describedby to the inline error", () => {
        render(
            <ValidatedField label="Email" error="Enter a valid email address.">
                {(control) => <Input {...control} defaultValue="not-an-email" />}
            </ValidatedField>,
        )

        const input = screen.getByLabelText("Email")
        expect(input).toHaveAttribute("aria-invalid", "true")
        expect(input).toHaveAccessibleDescription("Enter a valid email address.")
        expect(screen.getByRole("alert")).toHaveTextContent("Enter a valid email address.")
        expect(input.closest('[data-slot="field"]')).toHaveAttribute("data-invalid", "true")
        expect(screen.getByText("Email")).toHaveClass("group-data-[invalid=true]/field:text-destructive")
    })

    it("renders no error state when the field is valid", () => {
        render(
            <ValidatedField label="Email" error={undefined}>
                {(control) => <Input {...control} />}
            </ValidatedField>,
        )

        const input = screen.getByLabelText("Email")
        expect(input).not.toHaveAttribute("aria-invalid")
        expect(input).not.toHaveAttribute("aria-describedby")
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    })

    it("includes a format description in the accessible description", () => {
        render(
            <ValidatedField label="Slug" description="Lowercase letters, numbers and hyphens." error="Use lowercase letters, numbers and hyphens.">
                {(control) => <Input {...control} />}
            </ValidatedField>,
        )

        expect(screen.getByLabelText("Slug")).toHaveAccessibleDescription(
            "Lowercase letters, numbers and hyphens. Use lowercase letters, numbers and hyphens.",
        )
    })

    it("marks a DateTimePicker trigger invalid through the same control props", () => {
        render(
            <ValidatedField label="Start time" error="Choose a start time.">
                {(control) => (
                    <DateTimePicker
                        value={undefined}
                        onChange={vi.fn()}
                        triggerId={control.id}
                        aria-invalid={control["aria-invalid"]}
                        aria-describedby={control["aria-describedby"]}
                    />
                )}
            </ValidatedField>,
        )

        const trigger = screen.getByLabelText("Start time")
        expect(trigger).toHaveAttribute("aria-invalid", "true")
        expect(trigger).toHaveAccessibleDescription("Choose a start time.")
        expect(trigger).toHaveClass("aria-invalid:border-destructive")
    })
})

type InviteValues = { email: string; name: string }

function InviteForm({
    onSubmit,
    submitError,
}: {
    onSubmit: (values: InviteValues) => void | Promise<unknown>
    submitError?: unknown
}) {
    const [values, setValues] = React.useState<InviteValues>({ email: "", name: "" })
    const [formError, setFormError] = React.useState<string | null>(null)
    const form = useFormValidation({
        values,
        validate: (current) => ({
            name: validateRequired(current.name, "Enter a name."),
            email: validateEmail(current.email, { requiredMessage: "Enter an email address." }),
        }),
    })

    return (
        <form
            noValidate
            onSubmit={form.handleSubmit(async (submitted) => {
                await onSubmit(submitted)
                if (submitError) {
                    setFormError(
                        form.applyApiError(submitError, {
                            fields: ["email", "name"],
                            messages: { email: EMAIL_INVALID_MESSAGE },
                            fallback: "Couldn't send the invitation. Try again.",
                        }),
                    )
                }
            })}
        >
            <ValidatedField label="Name" error={form.errorFor("name")}>
                {(control) => (
                    <Input
                        {...control}
                        value={values.name}
                        onChange={(event) => setValues((current) => ({ ...current, name: event.target.value }))}
                        onBlur={() => form.touch("name")}
                    />
                )}
            </ValidatedField>
            <ValidatedField label="Email" error={form.errorFor("email")}>
                {(control) => (
                    <Input
                        {...control}
                        value={values.email}
                        onChange={(event) => setValues((current) => ({ ...current, email: event.target.value }))}
                        onBlur={() => form.touch("email")}
                    />
                )}
            </ValidatedField>
            {formError ? <p>{formError}</p> : null}
            <span data-testid="valid">{String(form.isValid)}</span>
            <Button type="submit">Send invitation</Button>
        </form>
    )
}

describe("useFormValidation", () => {
    it("hides errors on an untouched form and shows a field error after blur", () => {
        render(<InviteForm onSubmit={vi.fn()} />)

        expect(screen.queryByRole("alert")).not.toBeInTheDocument()
        expect(screen.getByTestId("valid")).toHaveTextContent("false")

        const email = screen.getByLabelText("Email")
        fireEvent.change(email, { target: { value: "not-an-email" } })
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()
        fireEvent.blur(email)

        expect(screen.getByRole("alert")).toHaveTextContent(EMAIL_INVALID_MESSAGE)
        expect(email).toHaveAttribute("aria-invalid", "true")
        expect(screen.getByLabelText("Name")).not.toHaveAttribute("aria-invalid")
    })

    it("keeps an unedited field quiet when it loses focus", () => {
        render(<InviteForm onSubmit={vi.fn()} />)

        const name = screen.getByLabelText("Name")
        fireEvent.focus(name)
        fireEvent.blur(name)

        expect(screen.queryByRole("alert")).not.toBeInTheDocument()
        expect(name).not.toHaveAttribute("aria-invalid")
    })

    it("does not show the error while retyping in a field that was left unedited earlier", () => {
        render(<InviteForm onSubmit={vi.fn()} />)

        const email = screen.getByLabelText("Email")
        fireEvent.blur(email)
        fireEvent.change(email, { target: { value: "j" } })
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()

        fireEvent.blur(email)
        expect(screen.getByRole("alert")).toHaveTextContent(EMAIL_INVALID_MESSAGE)
    })

    it("shows the required error after a field is edited back to empty and left", () => {
        render(<InviteForm onSubmit={vi.fn()} />)

        const name = screen.getByLabelText("Name")
        fireEvent.change(name, { target: { value: "J" } })
        fireEvent.change(name, { target: { value: "" } })
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()

        fireEvent.blur(name)
        expect(screen.getByRole("alert")).toHaveTextContent("Enter a name.")
    })

    it("keeps a touch made in the same handler as the edit", () => {
        function LiveForm() {
            const [values, setValues] = React.useState({ name: "Jordan" })
            const form = useFormValidation({
                values,
                validate: (current) => ({ name: validateRequired(current.name, "Enter a name.") }),
            })
            return (
                <ValidatedField label="Name" error={form.errorFor("name")}>
                    {(control) => (
                        <Input
                            {...control}
                            value={values.name}
                            onChange={(event) => {
                                setValues({ name: event.target.value })
                                form.touch("name")
                            }}
                        />
                    )}
                </ValidatedField>
            )
        }
        render(<LiveForm />)

        fireEvent.change(screen.getByLabelText("Name"), { target: { value: "" } })

        expect(screen.getByRole("alert")).toHaveTextContent("Enter a name.")
    })

    it("still shows every error on submit when no field was edited", async () => {
        render(<InviteForm onSubmit={vi.fn()} />)

        const name = screen.getByLabelText("Name")
        fireEvent.blur(name)
        fireEvent.click(screen.getByRole("button", { name: "Send invitation" }))

        expect(screen.getAllByRole("alert")).toHaveLength(2)
        await waitFor(() => {
            expect(name).toHaveFocus()
        })
    })

    it("treats values set together with reset() as the new starting point", () => {
        function ReopenForm() {
            const [values, setValues] = React.useState({ name: "" })
            const form = useFormValidation({
                values,
                validate: (current) => ({ name: validateRequired(current.name, "Enter a name.") }),
            })
            return (
                <>
                    <ValidatedField label="Name" error={form.errorFor("name")}>
                        {(control) => (
                            <Input
                                {...control}
                                value={values.name}
                                onChange={(event) => setValues({ name: event.target.value })}
                                onBlur={() => form.touch("name")}
                            />
                        )}
                    </ValidatedField>
                    <Button
                        onClick={() => {
                            form.reset()
                            setValues({ name: " " })
                        }}
                    >
                        Reopen
                    </Button>
                </>
            )
        }
        render(<ReopenForm />)

        const name = screen.getByLabelText("Name")
        fireEvent.change(name, { target: { value: "x" } })
        fireEvent.change(name, { target: { value: "" } })
        fireEvent.blur(name)
        expect(screen.getByRole("alert")).toHaveTextContent("Enter a name.")

        fireEvent.click(screen.getByRole("button", { name: "Reopen" }))
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()

        fireEvent.blur(name)
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    })

    it("clears a shown error as soon as the value becomes valid", () => {
        render(<InviteForm onSubmit={vi.fn()} />)

        const email = screen.getByLabelText("Email")
        fireEvent.change(email, { target: { value: "not-an-email" } })
        fireEvent.blur(email)
        fireEvent.change(email, { target: { value: "intake@agency.com" } })

        expect(email).not.toHaveAttribute("aria-invalid")
        expect(screen.queryByText(EMAIL_INVALID_MESSAGE)).not.toBeInTheDocument()
    })

    it("shows every error on submit, skips the handler and focuses the first invalid field", async () => {
        const onSubmit = vi.fn()
        render(<InviteForm onSubmit={onSubmit} />)

        fireEvent.click(screen.getByRole("button", { name: "Send invitation" }))

        expect(onSubmit).not.toHaveBeenCalled()
        expect(screen.getAllByRole("alert").map((alert) => alert.textContent)).toEqual([
            "Enter a name.",
            "Enter an email address.",
        ])
        await waitFor(() => {
            expect(screen.getByLabelText("Name")).toHaveFocus()
        })
    })

    it("submits valid values", async () => {
        const onSubmit = vi.fn()
        render(<InviteForm onSubmit={onSubmit} />)

        fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Jordan Ellis" } })
        fireEvent.change(screen.getByLabelText("Email"), { target: { value: "jordan@agency.com" } })
        expect(screen.getByTestId("valid")).toHaveTextContent("true")

        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Send invitation" }))
        })

        expect(onSubmit).toHaveBeenCalledWith({ name: "Jordan Ellis", email: "jordan@agency.com" })
    })

    it("maps a 422 onto the field and hides it once the field changes", async () => {
        const submitError = new ApiError(422, "Unprocessable Entity", "email: value is not a valid email address", [
            { path: "email", message: "value is not a valid email address: An email address must have an @-sign." },
        ])
        render(<InviteForm onSubmit={vi.fn()} submitError={submitError} />)

        fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Jordan Ellis" } })
        fireEvent.change(screen.getByLabelText("Email"), { target: { value: "jordan@agency" } })
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Send invitation" }))
        })

        const email = screen.getByLabelText("Email")
        expect(await screen.findByRole("alert")).toHaveTextContent(EMAIL_INVALID_MESSAGE)
        expect(email).toHaveAttribute("aria-invalid", "true")
        expect(screen.getByTestId("valid")).toHaveTextContent("false")
        expect(screen.queryByText(/Pydantic|@-sign/)).not.toBeInTheDocument()

        fireEvent.change(email, { target: { value: "jordan@agency.org" } })
        expect(email).not.toHaveAttribute("aria-invalid")
        expect(screen.getByTestId("valid")).toHaveTextContent("true")
    })

    it("returns a sanitized form error for a server failure", async () => {
        render(<InviteForm onSubmit={vi.fn()} submitError={new ApiError(500, "Internal Server Error")} />)

        fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Jordan Ellis" } })
        fireEvent.change(screen.getByLabelText("Email"), { target: { value: "jordan@agency.com" } })
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Send invitation" }))
        })

        expect(await screen.findByText("Couldn't send the invitation. Try again.")).toBeInTheDocument()
        expect(screen.queryByText(/500/)).not.toBeInTheDocument()
    })
})

describe("focusFirstInvalid", () => {
    it("focuses the first enabled invalid control in document order", () => {
        render(
            <div data-testid="root">
                <Input aria-label="Disabled" aria-invalid disabled />
                <Input aria-label="First" aria-invalid />
                <Input aria-label="Second" aria-invalid />
            </div>,
        )

        expect(focusFirstInvalid(screen.getByTestId("root"))).toBe(true)
        expect(screen.getByLabelText("First")).toHaveFocus()
        expect(focusFirstInvalid(null)).toBe(false)
    })
})

describe("API validation errors", () => {
    it("parses FastAPI detail items into issues with the source segment removed", () => {
        expect(
            parseApiValidationIssues({
                detail: [
                    { loc: ["body", "email"], msg: "value is not a valid email address" },
                    { loc: ["body", "items", 0, "name"], msg: "Field required" },
                    { loc: ["body"], msg: "Invalid payload" },
                    { msg: 42 },
                ],
            }),
        ).toEqual([
            { path: "email", message: "value is not a valid email address" },
            { path: "items.0.name", message: "Field required" },
            { path: "", message: "Invalid payload" },
        ])
        expect(parseApiValidationIssues({ detail: "Not found" })).toEqual([])
        expect(parseApiValidationIssues(null)).toEqual([])
    })

    it("maps issues through a path map and reports unmatched issues with the fallback", () => {
        const error = new ApiError(422, "Unprocessable Entity", undefined, [
            { path: "contact_email", message: "value is not a valid email address: An email address must have an @-sign." },
            { path: "internal_flag", message: "Field required" },
        ])

        expect(
            getApiFieldErrors(error, {
                fields: { contact_email: "email" },
                fallback: "Couldn't create the intended parent. Try again.",
            }),
        ).toEqual({
            fieldErrors: { email: "Value is not a valid email address." },
            formError: "Couldn't create the intended parent. Try again.",
        })
    })

    it("keeps the first issue per field and prefers the form's own message", () => {
        const error = new ApiError(422, "Unprocessable Entity", undefined, [
            { path: "email", message: "first" },
            { path: "email", message: "second" },
        ])

        expect(
            getApiFieldErrors(error, { fields: ["email"], messages: { email: EMAIL_INVALID_MESSAGE }, fallback: "x" }),
        ).toEqual({ fieldErrors: { email: EMAIL_INVALID_MESSAGE }, formError: null })
    })

    it("sanitizes non-validation failures", () => {
        const fallback = "Couldn't save. Try again."

        expect(getActionErrorMessage(new ApiError(500, "Internal Server Error"), fallback)).toBe(fallback)
        expect(getActionErrorMessage(new ApiError(404, "Not Found"), fallback)).toBe(fallback)
        expect(getActionErrorMessage(new ApiError(422, "Unprocessable Entity", "email: raw text"), fallback)).toBe(fallback)
        expect(getActionErrorMessage(new ApiError(409, "Conflict", "Email already invited"), fallback)).toBe(
            "Email already invited",
        )
        expect(getActionErrorMessage(new TypeError("Failed to fetch"), fallback)).toBe(fallback)
        expect(getActionErrorMessage(new RateLimitError(3), fallback)).toBeNull()
        expect(getApiFieldErrors(new ApiError(503, "Service Unavailable"), { fields: ["email"], fallback })).toEqual({
            fieldErrors: {},
            formError: fallback,
        })
    })

    it("shortens validator text", () => {
        expect(formatValidationMessage("value is not a valid email address: An email address must have an @-sign.")).toBe(
            "Value is not a valid email address.",
        )
        expect(formatValidationMessage("Value error, Slug is taken")).toBe("Slug is taken.")
        expect(formatValidationMessage("Field required")).toBe("Field required.")
        expect(formatValidationMessage("")).toBe("Check this value.")
    })
})

describe("validators", () => {
    it("checks email, required and integer ranges", () => {
        expect(isValidEmail(" intake@agency.com ")).toBe(true)
        expect(isValidEmail("not-an-email")).toBe(false)
        expect(validateEmail("", { requiredMessage: "Enter an email address." })).toBe("Enter an email address.")
        expect(validateEmail("")).toBeUndefined()
        expect(validateEmail("a@b")).toBe(EMAIL_INVALID_MESSAGE)
        expect(validateRequired("  ", "Enter a name.")).toBe("Enter a name.")
        expect(validateRequired("Jordan", "Enter a name.")).toBeUndefined()

        const days = { min: 1, max: 60, message: "Enter 1 to 60 days." }
        expect(validateIntegerRange("-5", days)).toBe(days.message)
        expect(validateIntegerRange("0", days)).toBe(days.message)
        expect(validateIntegerRange("1.5", days)).toBe(days.message)
        expect(validateIntegerRange(61, days)).toBe(days.message)
        expect(validateIntegerRange("30", days)).toBeUndefined()
    })
})
