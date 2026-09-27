import { humanizeSelectKey } from "@/lib/select-labels"
import { SURROGATE_SOURCE_LABELS } from "@/lib/surrogate-source-labels"

/**
 * Donor source is free text, not an enum: the API create payload, intake promotion
 * ("shared_intake", review resolutions) and workflow actions each write their own key.
 * Known keys get product labels; other slugs are humanized and anything else reads "Other".
 */
export const DONOR_SOURCE_LABELS: Readonly<Record<string, string>> = {
    ...SURROGATE_SOURCE_LABELS,
    shared_intake: "Intake form",
    form_embed: "Website form",
    manual_review_resolution: "Intake review",
    manual_retry_resolution: "Intake review",
}

export function getDonorSourceLabel(value: string): string {
    const key = value.trim()
    const label = Object.hasOwn(DONOR_SOURCE_LABELS, key) ? DONOR_SOURCE_LABELS[key] : undefined
    return label ?? humanizeSelectKey(key) ?? "Other"
}
