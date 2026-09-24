/** Scheduling instants are UTC; calendar date keys are in the displayed timezone. */
export function formatSchedulingDate(iso: string, timezone: string): string {
    return new Intl.DateTimeFormat(undefined, {
        timeZone: timezone, weekday: "long", year: "numeric", month: "long", day: "numeric",
    }).format(new Date(iso))
}

export function formatSchedulingTime(iso: string, timezone: string): string {
    return new Intl.DateTimeFormat(undefined, {
        timeZone: timezone, hour: "numeric", minute: "2-digit",
    }).format(new Date(iso))
}

export function schedulingDateKey(iso: string | Date, timezone: string): string {
    const parts = new Intl.DateTimeFormat("en-US", {
        timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit",
    }).formatToParts(typeof iso === "string" ? new Date(iso) : iso)
    const value = (type: Intl.DateTimeFormatPartTypes) => parts.find(part => part.type === type)?.value
    return `${value("year")}-${value("month")}-${value("day")}`
}

export function schedulingTimezoneLabel(timezone: string): string {
    return timezone.replaceAll("_", " ")
}

export function localDateTimeToIso(value: string): string | null {
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return null
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return null
    const localValue = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60_000)
        .toISOString().slice(0, 16)
    // Reject normalized invalid dates and clock times skipped by daylight saving.
    return localValue === value ? parsed.toISOString() : null
}
