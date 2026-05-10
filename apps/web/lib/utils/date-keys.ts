function pad2(value: number): string {
    return value.toString().padStart(2, "0")
}

const dateKeyFormatters = new Map<string, Intl.DateTimeFormat>()

function getDateKeyFormatter(timezone: string): Intl.DateTimeFormat {
    const cached = dateKeyFormatters.get(timezone)
    if (cached) return cached

    const formatter = Intl.DateTimeFormat("en-CA", {
        timeZone: timezone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
    })
    dateKeyFormatters.set(timezone, formatter)
    return formatter
}

export function formatPlainDateKey(date: Date): string {
    return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`
}

export function formatDateKeyInTimeZone(date: Date, timezone: string): string {
    return getDateKeyFormatter(timezone).format(date)
}

export function getTodayDateKeyInTimeZone(timezone: string, now: Date = new Date()): string {
    return formatDateKeyInTimeZone(now, timezone)
}

export function isPastDateKey(dateKey: string, timezone: string, now: Date = new Date()): boolean {
    return dateKey < getTodayDateKeyInTimeZone(timezone, now)
}
