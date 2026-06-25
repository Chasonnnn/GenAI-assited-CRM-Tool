import type { FormField } from "@/lib/api/forms"

type TableRow = Record<string, string | number | null>
export type PublicFieldValue = string | number | boolean | string[] | TableRow[] | null

export function isEmptyPublicFieldValue(value: PublicFieldValue | undefined): boolean {
    if (value === null || value === undefined) return true
    if (typeof value === "string") return value.trim() === ""
    if (Array.isArray(value)) return value.length === 0
    return false
}

function getAnchoredPattern(pattern: string): string {
    return pattern.startsWith("^") && pattern.endsWith("$") ? pattern : `^(?:${pattern})$`
}

function isValidPublicPhone(value: string): boolean {
    const digits = value.replace(/\D/g, "")
    return digits.length === 10 || (digits.length === 11 && digits.startsWith("1"))
}

function getNumericValue(value: PublicFieldValue | undefined): number {
    if (typeof value === "number") return value
    if (typeof value === "string") return Number(value.trim())
    return Number.NaN
}

export function getPublicFieldValidationError(
    field: FormField,
    value: PublicFieldValue | undefined,
): string | null {
    if (field.required && isEmptyPublicFieldValue(value)) {
        return `${field.label} is required.`
    }
    if (isEmptyPublicFieldValue(value)) {
        return null
    }

    if (field.type === "email") {
        if (typeof value !== "string" || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())) {
            return `${field.label} must be a valid email address.`
        }
    }

    if (field.type === "phone") {
        if (typeof value !== "string" || !isValidPublicPhone(value)) {
            return `${field.label} must be a valid phone number.`
        }
    }

    const validation = field.validation
    if (validation) {
        if (
            field.type === "text" ||
            field.type === "textarea" ||
            field.type === "email" ||
            field.type === "phone" ||
            field.type === "address"
        ) {
            if (typeof value !== "string") return `Please review: ${field.label}`
            if (validation.min_length !== null && validation.min_length !== undefined) {
                if (value.length < validation.min_length) {
                    return `Please enter at least ${validation.min_length} characters for ${field.label}`
                }
            }
            if (validation.max_length !== null && validation.max_length !== undefined) {
                if (value.length > validation.max_length) {
                    return `Please limit ${field.label} to ${validation.max_length} characters`
                }
            }
            if (validation.pattern) {
                try {
                    const regex = new RegExp(getAnchoredPattern(validation.pattern))
                    if (!regex.test(value)) {
                        return `Please enter a valid ${field.label}`
                    }
                } catch {
                    return `Validation rule invalid for ${field.label}`
                }
            }
        }

        if (field.type === "number") {
            const numericValue = getNumericValue(value)
            if (!Number.isFinite(numericValue)) {
                return `Please enter a valid number for ${field.label}`
            }
            if (validation.min_value !== null && validation.min_value !== undefined) {
                if (numericValue < validation.min_value) {
                    return `Please enter ${field.label} of at least ${validation.min_value}`
                }
            }
            if (validation.max_value !== null && validation.max_value !== undefined) {
                if (numericValue > validation.max_value) {
                    return `Please enter ${field.label} of at most ${validation.max_value}`
                }
            }
        }
    } else if (field.type === "number") {
        const numericValue = getNumericValue(value)
        if (!Number.isFinite(numericValue)) {
            return `Please enter a valid number for ${field.label}`
        }
    }

    return null
}
