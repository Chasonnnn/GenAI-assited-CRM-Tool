"use client"

import * as React from "react"

import { getApiFieldErrors, type ApiFieldErrorOptions } from "@/lib/forms/api-field-errors"

type FieldName<TValues> = Extract<keyof TValues, string>

export type FormFieldErrors<TValues> = Partial<Record<FieldName<TValues>, string | null | undefined>>

type ServerFieldError = {
    message: string
    /** The value that was submitted; the error hides once the field no longer holds it. */
    value: unknown
}

// `object` rather than Record<string, unknown> so interface-typed values (generated API types) fit.
export type UseFormValidationOptions<TValues extends object> = {
    /** Current form values. Errors are derived from them on every render, so they never go stale. */
    values: TValues
    /** Returns a message for each invalid field. Omit or return undefined for valid fields. */
    validate: (values: TValues) => FormFieldErrors<TValues>
}

const INVALID_CONTROL_SELECTOR = '[aria-invalid="true"]:not([disabled])'
const SUBMIT_ROOT_SELECTOR = 'form, [role="dialog"], [role="alertdialog"]'

/** Focuses the first control marked aria-invalid inside `root`, in document order. */
export function focusFirstInvalid(root: ParentNode | null | undefined): boolean {
    if (!root) return false
    const control = root.querySelector<HTMLElement>(INVALID_CONTROL_SELECTOR)
    if (!control) return false
    control.focus()
    return true
}

function focusFirstInvalidAfterRender(getRoot: () => ParentNode | null) {
    if (typeof window === "undefined") return
    // Errors render in the commit that follows the submit handler; aria-invalid exists after it.
    window.requestAnimationFrame(() => {
        focusFirstInvalid(getRoot() ?? document)
    })
}

/**
 * Field validation for forms that keep values in component state.
 *
 * - A field shows its error after it loses focus once, or after the first submit attempt.
 * - Errors are recomputed from `values`, so fixing a field clears its error on the next render.
 * - A failed submit focuses the first invalid control.
 * - API validation errors attach to fields and hide once the user edits that field.
 */
export function useFormValidation<TValues extends object>({
    values,
    validate,
}: UseFormValidationOptions<TValues>) {
    type Name = FieldName<TValues>

    const [touched, setTouched] = React.useState<ReadonlySet<Name>>(() => new Set())
    const [submitAttempted, setSubmitAttempted] = React.useState(false)
    const [serverErrors, setServerErrorsState] = React.useState<Partial<Record<Name, ServerFieldError>>>({})
    // The form or dialog of the last submit, so later API errors focus inside it. It is read only in
    // event and async callbacks; the hook returns no ref because call sites spread its result in render.
    const submitRootRef = React.useRef<ParentNode | null>(null)

    const clientErrors = validate(values)

    const activeServerError = (name: Name): string | undefined => {
        const serverError = serverErrors[name]
        return serverError && Object.is(serverError.value, values[name]) ? serverError.message : undefined
    }

    const errorFor = (name: Name): string | undefined => {
        const clientError = clientErrors[name]
        if (clientError && (submitAttempted || touched.has(name))) return clientError
        return activeServerError(name)
    }

    const hasClientErrors = Object.values(clientErrors).some(Boolean)
    const hasServerErrors = (Object.keys(serverErrors) as Name[]).some(
        (name) => activeServerError(name) !== undefined,
    )
    const isValid = !hasClientErrors && !hasServerErrors

    const touch = (name: Name) => {
        setTouched((current) => (current.has(name) ? current : new Set(current).add(name)))
    }

    const setServerErrors = (errors: Partial<Record<Name, string>>) => {
        const names = (Object.keys(errors) as Name[]).filter((name) => Boolean(errors[name]))
        if (names.length === 0) return
        setServerErrorsState((current) => {
            const next = { ...current }
            for (const name of names) {
                next[name] = { message: errors[name] as string, value: values[name] }
            }
            return next
        })
        focusFirstInvalidAfterRender(() => submitRootRef.current)
    }

    /**
     * Shows a failed request on the form: 422 issues go to their fields, and the return value is
     * the form-level message to show (toast or inline alert), or null when nothing else is needed.
     */
    const applyApiError = (error: unknown, options: ApiFieldErrorOptions<Name>): string | null => {
        const { fieldErrors, formError } = getApiFieldErrors(error, options)
        setServerErrors(fieldErrors)
        return formError
    }

    const handleSubmit =
        (onValid: (values: TValues) => void | Promise<unknown>) =>
        (event?: React.SyntheticEvent) => {
            event?.preventDefault()
            const eventTarget = event?.currentTarget
            submitRootRef.current =
                eventTarget instanceof Element ? eventTarget.closest(SUBMIT_ROOT_SELECTOR) : null
            setSubmitAttempted(true)
            if (!isValid) {
                focusFirstInvalidAfterRender(() => submitRootRef.current)
                return undefined
            }
            return onValid(values)
        }

    const reset = () => {
        setTouched(new Set())
        setSubmitAttempted(false)
        setServerErrorsState({})
    }

    return {
        /** The message to show under a field, or undefined. */
        errorFor,
        /** Call from the control's onBlur. */
        touch,
        /** True when no field has a client or server error, whether or not it is shown yet. */
        isValid,
        submitAttempted,
        /**
         * Wraps a submit handler: validates, focuses the first invalid control, or calls onValid.
         * Use it as the form's onSubmit, or as onClick of a button inside the dialog, so focus
         * moves stay inside that form or dialog.
         */
        handleSubmit,
        applyApiError,
        setServerErrors,
        /** Clears touched, submit and server state, for example when a dialog reopens. */
        reset,
    }
}
