export const MARITAL_STATUS_VALUES = [
    "Single",
    "Married",
    "Partnered",
    "Committed Relationship",
    "Divorced",
    "Separated",
    "Widowed",
] as const

export type MaritalStatus = (typeof MARITAL_STATUS_VALUES)[number]

export type MaritalStatusOption = {
    value: string
    label: string
}

export const DEFAULT_MARITAL_STATUS_OPTIONS: MaritalStatusOption[] = MARITAL_STATUS_VALUES.map((value) => ({
    value,
    label: value,
}))

export function getMaritalStatusOptions(currentValue: string | null | undefined): MaritalStatusOption[] {
    if (!currentValue) {
        return DEFAULT_MARITAL_STATUS_OPTIONS
    }

    const hasMatch = DEFAULT_MARITAL_STATUS_OPTIONS.some((option) => option.value === currentValue)
    if (hasMatch) {
        return DEFAULT_MARITAL_STATUS_OPTIONS
    }

    return [{ value: currentValue, label: currentValue }, ...DEFAULT_MARITAL_STATUS_OPTIONS]
}
