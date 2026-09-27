import type { DateRangePreset } from "@/components/ui/date-range-picker"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"

// Shared by the list pages that filter on one date column with DateRangePicker and keep the
// selection in the URL as ?range=<preset>&from=YYYY-MM-DD&to=YYYY-MM-DD.

export type DateRangeSelection = { from: Date | undefined; to: Date | undefined }

export const EMPTY_DATE_RANGE: DateRangeSelection = { from: undefined, to: undefined }

const DATE_RANGE_PRESETS: readonly DateRangePreset[] = ["all", "today", "week", "month", "custom"]

const DATE_RANGE_PRESET_LABELS: Record<Exclude<DateRangePreset, "custom">, string> = {
    all: "All Time",
    today: "Today",
    week: "This Week",
    month: "This Month",
}

const filterDateFormatter = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
})

export function parseDateRangePreset(value: string | null): DateRangePreset {
    return DATE_RANGE_PRESETS.includes(value as DateRangePreset) ? (value as DateRangePreset) : "all"
}

export function parseDateRangeParam(value: string | null): Date | undefined {
    if (!value) return undefined
    const parsed = parseDateInput(value)
    return Number.isNaN(parsed.getTime()) ? undefined : parsed
}

/** Reads ?range, ?from and ?to. `from` and `to` only apply to the custom preset. */
export function readDateRangeParams(params: { get: (key: string) => string | null }): {
    preset: DateRangePreset
    customRange: DateRangeSelection
} {
    const preset = parseDateRangePreset(params.get("range"))
    return {
        preset,
        customRange:
            preset === "custom"
                ? { from: parseDateRangeParam(params.get("from")), to: parseDateRangeParam(params.get("to")) }
                : EMPTY_DATE_RANGE,
    }
}

/** Writes ?range, ?from and ?to; "all" removes all three. */
export function writeDateRangeParams(
    params: URLSearchParams,
    preset: DateRangePreset,
    customRange: DateRangeSelection,
): void {
    params.delete("from")
    params.delete("to")
    if (preset === "all") {
        params.delete("range")
        return
    }
    params.set("range", preset)
    if (preset !== "custom") return
    if (customRange.from) params.set("from", formatLocalDate(customRange.from))
    if (customRange.to) params.set("to", formatLocalDate(customRange.to))
}

/** Local calendar-day bounds (YYYY-MM-DD) for the API. Presets set only the start day. */
export function getDateRangeBounds(
    preset: DateRangePreset,
    customRange: DateRangeSelection,
    now: Date = new Date(),
): { from?: string; to?: string } {
    if (preset === "all") return {}
    if (preset === "custom") {
        return {
            ...(customRange.from ? { from: formatLocalDate(customRange.from) } : {}),
            ...(customRange.to ? { to: formatLocalDate(customRange.to) } : {}),
        }
    }
    if (preset === "today") return { from: formatLocalDate(new Date(now.getFullYear(), now.getMonth(), now.getDate())) }
    if (preset === "week") return { from: formatLocalDate(new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)) }
    return { from: formatLocalDate(new Date(now.getFullYear(), now.getMonth(), 1)) }
}

/** Label for the date filter chip, for example "Sep 1, 2026 - Sep 26, 2026" or "This Month". */
export function getDateRangeFilterLabel(preset: DateRangePreset, customRange: DateRangeSelection): string {
    if (preset !== "custom") return DATE_RANGE_PRESET_LABELS[preset]
    if (customRange.from && customRange.to) {
        return `${filterDateFormatter.format(customRange.from)} - ${filterDateFormatter.format(customRange.to)}`
    }
    if (customRange.from) return `From ${filterDateFormatter.format(customRange.from)}`
    if (customRange.to) return `Until ${filterDateFormatter.format(customRange.to)}`
    return "Custom Range"
}
