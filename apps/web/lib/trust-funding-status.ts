export const TRUST_FUNDING_STATUS_VALUES = [
    "pending_funding",
    "funded",
    "needs_replenishment",
    "closed",
] as const

export type TrustFundingStatus = (typeof TRUST_FUNDING_STATUS_VALUES)[number]

export type TrustFundingStatusOption = {
    value: TrustFundingStatus
    label: string
}

export const DEFAULT_TRUST_FUNDING_STATUS_OPTIONS: TrustFundingStatusOption[] = [
    { value: "pending_funding", label: "Pending Funding" },
    { value: "funded", label: "Funded" },
    { value: "needs_replenishment", label: "Needs Replenishment" },
    { value: "closed", label: "Closed" },
]

export function getTrustFundingStatusOptions(
    currentValue: string | null | undefined,
): TrustFundingStatusOption[] {
    if (!currentValue) {
        return DEFAULT_TRUST_FUNDING_STATUS_OPTIONS
    }

    const hasMatch = DEFAULT_TRUST_FUNDING_STATUS_OPTIONS.some((option) => option.value === currentValue)
    if (hasMatch) {
        return DEFAULT_TRUST_FUNDING_STATUS_OPTIONS
    }

    return [
        { value: currentValue as TrustFundingStatus, label: currentValue },
        ...DEFAULT_TRUST_FUNDING_STATUS_OPTIONS,
    ]
}

export function getTrustFundingStatusLabel(value: string | null | undefined): string {
    return (
        DEFAULT_TRUST_FUNDING_STATUS_OPTIONS.find((option) => option.value === value)?.label
        ?? (value || "Not provided")
    )
}
