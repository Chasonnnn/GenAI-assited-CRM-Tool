import { ApiError, RateLimitError } from "@/lib/api"

type ApiFieldMap<TField extends string> = readonly TField[] | Readonly<Record<string, TField>>

export type ApiFieldErrorOptions<TField extends string> = {
    /**
     * Form fields that can receive API validation errors. Pass a list when API paths equal the
     * field names, or a map from API path (for example "address.city") to field name.
     */
    fields: ApiFieldMap<TField>
    /** User-facing message per field. It replaces the validator text that the API returns. */
    messages?: Partial<Record<TField, string>> | undefined
    /** Message for server errors, network failures and validation errors that match no field. */
    fallback: string
}

export type ApiFieldErrorResult<TField extends string> = {
    fieldErrors: Partial<Record<TField, string>>
    /** Message for the whole form. Null when every problem maps to a field or was already shown. */
    formError: string | null
}

/**
 * Returns a message that is safe to show for a failed action.
 * Server errors, raw validation text and bare status lines become `fallback`.
 * Returns null for rate limits because the API client already shows a toast for them.
 */
export function getActionErrorMessage(error: unknown, fallback: string): string | null {
    if (error instanceof RateLimitError) return null
    if (error instanceof ApiError) {
        if (error.status >= 500 || error.status === 422) return fallback
        const statusLine = `${error.status} ${error.statusText}`
        if (!error.message || error.message === statusLine) return fallback
        return error.message
    }
    return fallback
}

/** Maps a 422 response onto form fields; every other failure becomes a form-level message. */
export function getApiFieldErrors<TField extends string>(
    error: unknown,
    options: ApiFieldErrorOptions<TField>,
): ApiFieldErrorResult<TField> {
    if (!(error instanceof ApiError) || error.status !== 422 || error.issues.length === 0) {
        return { fieldErrors: {}, formError: getActionErrorMessage(error, options.fallback) }
    }

    const fieldErrors: Partial<Record<TField, string>> = {}
    let hasUnmatchedIssue = false
    for (const issue of error.issues) {
        const field = resolveField(issue.path, options.fields)
        if (field === undefined) {
            hasUnmatchedIssue = true
            continue
        }
        if (fieldErrors[field] === undefined) {
            fieldErrors[field] = options.messages?.[field] ?? formatValidationMessage(issue.message)
        }
    }

    return { fieldErrors, formError: hasUnmatchedIssue ? options.fallback : null }
}

function resolveField<TField extends string>(path: string, fields: ApiFieldMap<TField>): TField | undefined {
    if (isFieldList(fields)) {
        return fields.find((field) => field === path)
    }
    return Object.hasOwn(fields, path) ? fields[path] : undefined
}

function isFieldList<TField extends string>(fields: ApiFieldMap<TField>): fields is readonly TField[] {
    return Array.isArray(fields)
}

/**
 * Shortens Pydantic validator text for display, for example
 * "value is not a valid email address: An email address must have an @-sign." becomes
 * "Value is not a valid email address." Pass `messages` for wording that matches the form.
 */
export function formatValidationMessage(message: string): string {
    let text = message.replace(/^(value|assertion) error,\s*/i, "").trim()
    const detailStart = text.indexOf(": ")
    if (detailStart > 0 && /^value is not a valid /i.test(text)) {
        text = text.slice(0, detailStart)
    }
    if (!text) return "Check this value."
    text = text.charAt(0).toUpperCase() + text.slice(1)
    return /[.!?]$/.test(text) ? text : `${text}.`
}
