// Kept out of the "use client" editor module so Server Components can read them.

// Intake triggers store the applicant type under a trigger-specific key.
export const INTAKE_LEAD_KIND_CONFIG_KEYS: Partial<Record<string, string>> = {
    form_submitted: "lead_kind",
    form_submission_approved: "lead_kind",
    form_submission_rejected: "lead_kind",
    intake_lead_created: "lead_type",
}

// Triggers configured with a form; the form also sets the workflow's surrogate or donor context.
export const FORM_TRIGGER_TYPES = new Set(Object.keys(INTAKE_LEAD_KIND_CONFIG_KEYS))
