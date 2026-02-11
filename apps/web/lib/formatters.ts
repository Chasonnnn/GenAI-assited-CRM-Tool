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

const RACE_LABEL_OVERRIDES: Record<string, string> = {
  american_indian_or_alaska_native: "American Indian or Alaska Native",
  asian: "Asian",
  black_or_african_american: "Black or African American",
  hispanic_or_latino: "Hispanic or Latino",
  native_hawaiian_or_other_pacific_islander: "Native Hawaiian or Other Pacific Islander",
  white: "White",
  other_please_specify: "Other (please specify)",
  not_hispanic_or_latino: "Not Hispanic or Latino",
}

const LOWERCASE_WORDS = new Set(["or", "and", "of", "the", "a", "an", "in", "on", "to", "for"])

function toTitleCase(value: string): string {
  return value
    .split(" ")
    .map((word, index) => {
      if (!word) return ""
      if (index > 0 && LOWERCASE_WORDS.has(word)) return word
      return `${word.charAt(0).toUpperCase()}${word.slice(1)}`
    })
    .join(" ")
}

export function formatRace(value: string | null | undefined): string {
  if (!value) return ""
  const trimmed = value.trim()
  if (!trimmed) return ""
  const normalizedKey = trimmed.toLowerCase().replace(/[\s-]+/g, "_")
  const override = RACE_LABEL_OVERRIDES[normalizedKey]
  if (override) return override
  const normalized = trimmed.replace(/[_-]+/g, " ").toLowerCase()
  return toTitleCase(normalized)
}
