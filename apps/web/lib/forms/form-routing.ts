import type {
    FormRoutingExactMatch,
    FormRoutingNoMatch,
    FormRoutingRead,
    FormRoutingUpdate,
    FormSubmissionRoutingReviewStep,
    FormWorkflowTriggerType,
} from "@/lib/api/forms"
import { createSelectLabelGetter, toSelectOptions } from "@/lib/select-labels"

export const ROUTING_EXACT_MATCH_OPTIONS: ReadonlyArray<{ value: FormRoutingExactMatch; label: string }> = [
    { value: "auto", label: "Link automatically" },
    { value: "review", label: "Review first" },
]

export const ROUTING_NO_MATCH_OPTIONS: ReadonlyArray<{ value: FormRoutingNoMatch; label: string }> = [
    { value: "auto", label: "Automatically" },
    { value: "review", label: "After review" },
    { value: "off", label: "Off" },
]

// A null lead source lets the server pick its default; the select stores it as this sentinel.
export const ROUTING_LEAD_SOURCE_DEFAULT = "default"

const ROUTING_LEAD_SOURCE_LABELS: Record<string, string> = {
    [ROUTING_LEAD_SOURCE_DEFAULT]: "Default",
    website: "Website",
    form_embed: "Form embed",
}

export const ROUTING_LEAD_SOURCE_OPTIONS = toSelectOptions(ROUTING_LEAD_SOURCE_LABELS)

export const getRoutingLeadSourceLabel = createSelectLabelGetter(ROUTING_LEAD_SOURCE_LABELS, {
    emptyLabel: "Default",
    allValue: ROUTING_LEAD_SOURCE_DEFAULT,
    unknownLabel: "Unknown source",
})

const ROUTING_REVIEW_STEP_LABELS: Record<FormSubmissionRoutingReviewStep, string> = {
    match: "Match check",
    create_lead: "No match",
}

export const getRoutingReviewStepLabel = createSelectLabelGetter(ROUTING_REVIEW_STEP_LABELS, {
    emptyLabel: "Routing review",
    unknownLabel: "Routing review",
})

export const FORM_WORKFLOW_TRIGGER_TYPES: readonly FormWorkflowTriggerType[] = [
    "form_submitted",
    "form_submission_approved",
    "form_submission_rejected",
]

export function toRoutingUpdate(routing: FormRoutingRead): FormRoutingUpdate {
    return {
        exact_match: routing.exact_match,
        no_match: routing.no_match,
        lead_source: routing.lead_source,
        auto_create_donor: routing.auto_create_donor,
    }
}

/** The routing fields the user changed and has not saved yet. */
export type RoutingDraft = Partial<FormRoutingUpdate>

const ROUTING_FIELDS = ["exact_match", "no_match", "lead_source", "auto_create_donor"] as const

/** Keeps only the draft fields that still differ from the saved routing. */
export function pruneRoutingDraft(draft: RoutingDraft, saved: FormRoutingUpdate): RoutingDraft {
    const pending: Record<string, unknown> = {}
    for (const field of ROUTING_FIELDS) {
        if (field in draft && draft[field] !== saved[field]) pending[field] = draft[field]
    }
    return pending as RoutingDraft
}

/** True when both reads hold the same lead kind and routing settings. */
export function isSameSavedRouting(left: FormRoutingRead, right: FormRoutingRead): boolean {
    return left.lead_kind === right.lead_kind && ROUTING_FIELDS.every((field) => left[field] === right[field])
}

export function parseRoutingLeadSource(value: string | null): FormRoutingUpdate["lead_source"] {
    return value === "website" || value === "form_embed" ? value : null
}

export function newFormWorkflowHref(formId: string, triggerType: FormWorkflowTriggerType) {
    const params = new URLSearchParams({ scope: "org", trigger: triggerType, form_id: formId })
    return `/automation/workflows/new?${params.toString()}`
}
