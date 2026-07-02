const SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
const LONG_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

export function formatUtcDateLabel(
    value: string | null | undefined,
    options: { month?: "short" | "long"; fallback?: string } = {},
) {
    if (!value) return options.fallback ?? "-"

    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
    if (!match) return value

    const year = match[1]
    const monthIndex = Number(match[2]) - 1
    const day = Number(match[3])
    const monthLabel = (options.month === "long" ? LONG_MONTHS : SHORT_MONTHS)[monthIndex]

    if (!monthLabel || !Number.isInteger(day) || day < 1 || day > 31) return value

    return `${monthLabel} ${day}, ${year}`
}
