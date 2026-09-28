import { createSelectLabelGetter } from "@/lib/select-labels"
import { SURROGATE_SOURCE_LABELS, isSurrogateSource } from "@/lib/surrogate-source-labels"
import type { SurrogateSource } from "@/lib/types/surrogate"

/** Donor source stores the surrogate source values ("meta", "website", ...). */
export type DonorSource = SurrogateSource

/** One label map for donor sources: filter items, triggers, chips, badges and cells. */
export const DONOR_SOURCE_LABELS: Readonly<Record<DonorSource, string>> = SURROGATE_SOURCE_LABELS

export const isDonorSource = (value: string | null | undefined): value is DonorSource =>
    isSurrogateSource(value)

export const getDonorSourceLabel = createSelectLabelGetter(DONOR_SOURCE_LABELS, {
    emptyLabel: "Unknown source",
    unknownLabel: "Unknown source",
})

export const getDonorSourceFilterLabel = createSelectLabelGetter(DONOR_SOURCE_LABELS, {
    emptyLabel: "All sources",
    allValue: "all",
    unknownLabel: "Unknown source",
})
