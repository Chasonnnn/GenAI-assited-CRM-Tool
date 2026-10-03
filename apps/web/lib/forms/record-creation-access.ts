import type { FormLeadKind } from "@/lib/api/forms"

type EffectiveAccess = { policy_version?: number; permissions: string[] } | undefined

function isDonorKind(kind: FormLeadKind) {
    return kind === "egg_donor" || kind === "sperm_donor"
}

export function canCreateIntakeRecord(access: EffectiveAccess, kind: FormLeadKind): boolean {
    const module = isDonorKind(kind) ? "donors" : "surrogates"
    const action = access?.policy_version === 2 ? "create" : "edit"
    return access?.permissions.includes(`${action}_${module}`) === true
}

/** Mirrors the submission review check: review_form_submissions under policy v2, manage_forms under v1. */
export function canReviewFormSubmissions(access: EffectiveAccess): boolean {
    const permission = (access?.policy_version ?? 1) >= 2 ? "review_form_submissions" : "manage_forms"
    return access?.permissions.includes(permission) === true
}

/**
 * Mirrors the routing review endpoints: the submission review permission, edit_donors on donor
 * submissions, and create_* under policy v2 to create the lead.
 */
export function canReviewRoutingSubmission(
    access: EffectiveAccess,
    kind: FormLeadKind,
    action: "review" | "create_lead",
): boolean {
    const permissions = access?.permissions ?? []
    if (!canReviewFormSubmissions(access)) return false
    if (isDonorKind(kind) && !permissions.includes("edit_donors")) return false
    if (action === "create_lead" && access?.policy_version === 2) {
        return permissions.includes(isDonorKind(kind) ? "create_donors" : "create_surrogates")
    }
    return true
}
