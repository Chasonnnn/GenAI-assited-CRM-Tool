import type { SurrogateSource } from "@/lib/types/surrogate"

/** One label map for surrogate sources: filter items, triggers, chips, badges and exports. */
export const SURROGATE_SOURCE_LABELS: Record<SurrogateSource, string> = {
    manual: "Manual",
    meta: "Meta",
    tiktok: "TikTok",
    google: "Google",
    website: "Website",
    referral: "Referral",
    agency: "Agency",
    import: "Import",
    other: "Other",
}

export function isSurrogateSource(value: string | null | undefined): value is SurrogateSource {
    return typeof value === "string" && Object.hasOwn(SURROGATE_SOURCE_LABELS, value)
}

export function getSurrogateSourceLabel(value: string | null | undefined): string {
    return isSurrogateSource(value) ? SURROGATE_SOURCE_LABELS[value] : "Unknown source"
}
