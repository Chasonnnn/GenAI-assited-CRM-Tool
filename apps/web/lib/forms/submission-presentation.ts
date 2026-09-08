import type { FormSubmissionRead } from "@/lib/api/forms"

export function readAnswerValue(submission: FormSubmissionRead, keys: string[]) {
    for (const key of keys) {
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

export function submissionReviewLabel(submission: FormSubmissionRead) {
    if (submission.status === "approved") return "Approved"
    if (submission.status === "rejected") return "Rejected"
    return "Pending Review"
}

export function submissionReviewBadgeClass(submission: FormSubmissionRead) {
    if (submission.status === "approved") {
        return "border-emerald-200 bg-emerald-50 text-emerald-700"
    }
    if (submission.status === "rejected") {
        return "border-red-200 bg-red-50 text-red-700"
    }
    return "border-stone-200 bg-stone-100 text-stone-700"
}
