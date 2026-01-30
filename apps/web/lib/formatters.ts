const relativeTimeFormatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" })

const RELATIVE_UNITS: Array<{ unit: Intl.RelativeTimeFormatUnit; ms: number }> = [
  { unit: "year", ms: 1000 * 60 * 60 * 24 * 365 },
  { unit: "month", ms: 1000 * 60 * 60 * 24 * 30 },
  { unit: "week", ms: 1000 * 60 * 60 * 24 * 7 },
  { unit: "day", ms: 1000 * 60 * 60 * 24 },
  { unit: "hour", ms: 1000 * 60 * 60 },
  { unit: "minute", ms: 1000 * 60 },
  { unit: "second", ms: 1000 },
]

const dateFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" })
const timeFormatter = new Intl.DateTimeFormat(undefined, { timeStyle: "short" })

function toDate(input: Date | string | null | undefined): Date | null {
  if (!input) return null
  const date = input instanceof Date ? input : new Date(input)
  if (Number.isNaN(date.getTime())) return null
  return date
}

export function formatRelativeTime(
  input: Date | string | null | undefined,
  fallback = ""
): string {
  const date = toDate(input)
  if (!date) return fallback

  const diff = date.getTime() - Date.now()
  const abs = Math.abs(diff)

  for (const { unit, ms } of RELATIVE_UNITS) {
    if (abs >= ms || unit === "second") {
      return relativeTimeFormatter.format(Math.round(diff / ms), unit)
    }
  }

  return fallback
}

export function formatDate(
  input: Date | string | null | undefined,
  options?: Intl.DateTimeFormatOptions,
  fallback = ""
): string {
  const date = toDate(input)
  if (!date) return fallback
  const formatter = options ? new Intl.DateTimeFormat(undefined, options) : dateFormatter
  return formatter.format(date)
}

export function formatDateTime(
  input: Date | string | null | undefined,
  fallback = ""
): string {
  const date = toDate(input)
  if (!date) return fallback
  return `${dateFormatter.format(date)} at ${timeFormatter.format(date)}`
}
