import type { MetaFormSummary, MetaLeadKind } from "@/lib/api/meta-forms"
import { createSelectLabelGetter, humanizeSelectKey, toSelectOptions } from "@/lib/select-labels"

export const META_LEAD_KIND_LABELS = {
    surrogate: "Surrogate",
    egg_donor: "Egg donor",
    sperm_donor: "Sperm donor",
} as const satisfies Record<MetaLeadKind, string>

export const META_LEAD_KIND_OPTIONS = toSelectOptions(META_LEAD_KIND_LABELS) as Array<{
    value: MetaLeadKind
    label: string
}>

export const getMetaLeadKindLabel = createSelectLabelGetter(META_LEAD_KIND_LABELS, {
    emptyLabel: "Surrogate",
    unknownLabel: "Unknown lead type",
})

export function isDonorLeadKind(value: MetaLeadKind | null | undefined): boolean {
    return value === "egg_donor" || value === "sperm_donor"
}

const META_LEAD_STATUS_LABELS: Readonly<Record<string, string>> = {
    received: "Received",
    fetching: "Fetching",
    fetch_failed: "Fetch failed",
    stored: "Stored",
    awaiting_mapping: "Awaiting mapping",
    converted: "Converted",
    convert_failed: "Conversion failed",
}

const REPROCESS_BLOCK_REASON_LABELS: Readonly<Record<string, string>> = {
    duplicate_email: "Duplicate email",
    test_lead: "Test lead",
    mapping_not_ready: "Mapping not ready",
}

export function getMetaLeadStatusLabel(status: string | null | undefined): string {
    if (!status) return "Unknown status"
    return META_LEAD_STATUS_LABELS[status] ?? humanizeSelectKey(status) ?? "Unknown status"
}

export function getReprocessBlockReasonLabel(reason: string | null | undefined): string {
    if (!reason) return "Blocked"
    return REPROCESS_BLOCK_REASON_LABELS[reason] ?? humanizeSelectKey(reason) ?? "Blocked"
}

/** Zapier-created forms store the literal page id "zapier" and no page name. */
export function isZapierMetaForm(form: Pick<MetaFormSummary, "page_id">): boolean {
    return form.page_id.trim().toLowerCase() === "zapier"
}
