import type { FormFieldMappingItem, FormSubmissionRead, FormSubmissionStatus } from "@/lib/api/forms"

export function readAnswerValue(
    submission: FormSubmissionRead,
    keys: string[],
    mappings: FormFieldMappingItem[] = [],
) {
    const mappedKeys = mappings
        .filter((mapping) => keys.includes(mapping.surrogate_field))
        .map((mapping) => mapping.field_key)
    for (const key of [...new Set([...mappedKeys, ...keys])]) {
        const rawValue = submission.answers?.[key]
        if (typeof rawValue === "string" && rawValue.trim()) {
            return rawValue.trim()
        }
    }
    return "—"
}

export function formatSubmissionDateTime(isoString: string) {
    const value = new Date(isoString)
    if (Number.isNaN(value.getTime())) return "—"
    return value.toLocaleString()
}

export function submissionOutcomeLabel(submission: FormSubmissionRead) {
    if (submission.match_status === "linked") return "Matched"
    if (submission.match_status === "lead_created") return "Lead Created"
    if (submission.match_status === "routing_review") return "Routing Review"
    return "Pending Match"
}

export function submissionOutcomeBadgeClass(submission: FormSubmissionRead) {
    if (submission.match_status === "linked") {
        return "border-emerald-200 bg-emerald-50 text-emerald-700"
    }
    if (submission.match_status === "lead_created") {
        return "border-blue-200 bg-blue-50 text-blue-700"
    }
    return "border-amber-200 bg-amber-50 text-amber-700"
}

export function submissionStatusLabel(status: FormSubmissionStatus) {
    if (status === "approved") return "Approved"
    if (status === "rejected") return "Rejected"
    return "Pending Review"
}

export function submissionReviewLabel(submission: FormSubmissionRead) {
    return submissionStatusLabel(submission.status)
}

const MATCH_REASON_LABELS: Record<string, string> = {
    workflow_pending: "Waiting for routing",
    routing_review_dismissed: "Routing review dismissed",
    phone_dob_name_exact: "Name, date of birth and phone match",
    email_dob_name_exact: "Name, date of birth and email match",
    phone_dob_name_ambiguous: "Several records share name, date of birth and phone",
    email_dob_name_ambiguous: "Several records share name, date of birth and email",
    no_deterministic_match: "No matching record",
    existing_submission_for_surrogate: "Surrogate already has an application on this form",
    already_linked: "Already linked",
    manually_linked: "Linked by reviewer",
    manual_lead_creation: "Lead created by reviewer",
    manual_review_required: "Matching record outside your access",
    manual_retry_reset: "Reset for reprocessing",
    manual_retry_lead_creation: "Lead created on reprocess",
    manual_retry_requires_manual_link: "Previously promoted; link manually",
    existing_lead_retained: "Existing lead kept",
    existing_lead_relinked: "Existing lead relinked",
    routing_lead_creation: "Lead created by routing",
    // Rows from before form routing replaced the routing workflow actions keep this reason.
    workflow_lead_creation: "Lead created by workflow",
    workflow_website_lead_creation: "Website lead created by workflow",
    lead_promoted_to_surrogate: "Lead promoted to surrogate",
    lead_promoted_to_donor: "Lead promoted to donor",
    donor_email_name_type_exact: "Name, email and donor type match",
    donor_identity_conflict: "Email or phone belongs to a different donor",
    donor_no_deterministic_match: "No matching donor",
    existing_submission_for_donor: "Donor already has an application on this form",
    donor_photo_requires_review: "Profile photo needs review",
    donor_email_phone_match: "Email and phone match",
    donor_email_match: "Email matches",
    donor_phone_match: "Phone matches",
}

export function matchReasonLabel(reason: string | null | undefined) {
    if (!reason) return "—"
    return MATCH_REASON_LABELS[reason] ?? "Other reason"
}

export function submissionStatusBadgeClass(status: FormSubmissionStatus) {
    if (status === "approved") {
        return "border-emerald-200 bg-emerald-50 text-emerald-700"
    }
    if (status === "rejected") {
        return "border-red-200 bg-red-50 text-red-700"
    }
    return "border-stone-200 bg-stone-100 text-stone-700"
}

export function submissionReviewBadgeClass(submission: FormSubmissionRead) {
    return submissionStatusBadgeClass(submission.status)
}
