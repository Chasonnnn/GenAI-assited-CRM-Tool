import type { FormFieldOption } from "@/lib/api/forms"

export function getFormOptionLabel(
    options: FormFieldOption[] | null | undefined,
    value: unknown,
): string | null {
    if (typeof value !== "string" || !options || options.length === 0) return null
    return options.find((option) => option.value === value)?.label ?? null
}

export function getFormOptionLabels(
    options: FormFieldOption[] | null | undefined,
    values: unknown[],
): string[] {
    return values.map((value) => getFormOptionLabel(options, value) ?? String(value))
}
