// Shared client-side checks for staff forms. Each returns an error message, or undefined when valid.

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export const EMAIL_INVALID_MESSAGE = "Enter a valid email address."

export function isValidEmail(value: string): boolean {
    return EMAIL_PATTERN.test(value.trim())
}

export function validateRequired(value: string | null | undefined, message: string): string | undefined {
    return value && value.trim() ? undefined : message
}

export function validateEmail(
    value: string | null | undefined,
    { requiredMessage }: { requiredMessage?: string | undefined } = {},
): string | undefined {
    const trimmed = value?.trim() ?? ""
    if (!trimmed) return requiredMessage
    return isValidEmail(trimmed) ? undefined : EMAIL_INVALID_MESSAGE
}

export function validateIntegerRange(
    value: string | number | null | undefined,
    { min, max, message }: { min?: number | undefined; max?: number | undefined; message: string },
): string | undefined {
    const text = typeof value === "number" ? String(value) : (value ?? "").trim()
    if (!/^-?\d+$/.test(text)) return message
    const parsed = Number(text)
    if (min !== undefined && parsed < min) return message
    if (max !== undefined && parsed > max) return message
    return undefined
}
