import type { FieldType, FormLeadKind } from "@/lib/api/forms"
import {
    DEFAULT_FORM_DONOR_FIELD_OPTIONS,
    DEFAULT_FORM_SURROGATE_FIELD_OPTIONS,
} from "@/lib/api/forms"
import type { BuilderFormField, BuilderFormPage } from "@/lib/forms/form-builder-document"
import type { BuilderPaletteField } from "@/lib/forms/form-builder-library"

export const FORM_LEAD_KIND_LABELS: Record<FormLeadKind, string> = {
    surrogate: "Surrogate",
    egg_donor: "Egg Donor",
    sperm_donor: "Sperm Donor",
}

export const FORM_LEAD_KIND_OPTIONS: Array<{ value: FormLeadKind; label: string }> = [
    { value: "surrogate", label: FORM_LEAD_KIND_LABELS.surrogate },
    { value: "egg_donor", label: FORM_LEAD_KIND_LABELS.egg_donor },
    { value: "sperm_donor", label: FORM_LEAD_KIND_LABELS.sperm_donor },
]

const DONOR_FIELD_TYPES: Record<string, Set<FieldType>> = {
    donor_type: new Set(["radio", "select"]),
    full_name: new Set(["text", "textarea"]),
    email: new Set(["email", "text"]),
    phone: new Set(["phone", "text"]),
    state: new Set(["text", "select"]),
    education: new Set(["text", "textarea", "select"]),
    profile_photo: new Set(["file"]),
}

const DONOR_REQUIRED_MAPPING_VALUES = ["full_name", "email", "profile_photo"] as const
const DONOR_ALLOWED_MAPPING_VALUES = new Set(DEFAULT_FORM_DONOR_FIELD_OPTIONS.map((option) => option.value))
const SURROGATE_ALLOWED_MAPPING_VALUES = new Set(
    DEFAULT_FORM_SURROGATE_FIELD_OPTIONS.map((option) => option.value),
)
const DONOR_LABEL_BY_VALUE = new Map(
    DEFAULT_FORM_DONOR_FIELD_OPTIONS.map((option) => [option.value, option.label] as const),
)

export function isDonorFormLeadKind(leadKind: FormLeadKind): boolean {
    return leadKind === "egg_donor" || leadKind === "sperm_donor"
}

export function normalizePaletteFieldForLeadKind(
    field: BuilderPaletteField,
    leadKind: FormLeadKind,
): BuilderPaletteField {
    const allowedMappings = isDonorFormLeadKind(leadKind)
        ? DONOR_ALLOWED_MAPPING_VALUES
        : SURROGATE_ALLOWED_MAPPING_VALUES
    if (!field.surrogateFieldMapping || allowedMappings.has(field.surrogateFieldMapping)) {
        return field
    }
    const normalizedField = { ...field }
    delete normalizedField.surrogateFieldMapping
    return normalizedField
}

function normalizeFieldMapping(field: BuilderFormField, allowedMappings: Set<string>): BuilderFormField {
    if (!field.surrogateFieldMapping || allowedMappings.has(field.surrogateFieldMapping)) {
        return field
    }
    return { ...field, surrogateFieldMapping: "" }
}

export function normalizePagesForLeadKind(
    pages: BuilderFormPage[],
    leadKind: FormLeadKind,
): BuilderFormPage[] {
    const allowedMappings = isDonorFormLeadKind(leadKind)
        ? DONOR_ALLOWED_MAPPING_VALUES
        : SURROGATE_ALLOWED_MAPPING_VALUES
    return pages.map((page) => ({
        ...page,
        fields: page.fields.map((field) => normalizeFieldMapping(field, allowedMappings)),
    }))
}

export type DonorRequiredFieldStatus = {
    value: string
    label: string
    status: "ready" | "missing" | "not_required" | "wrong_type"
    fieldId: string | null
}

export function getDonorRequiredFieldStatuses(pages: BuilderFormPage[]): DonorRequiredFieldStatus[] {
    const mappedFieldByTarget = new Map<string, BuilderFormField>()
    for (const field of pages.flatMap((page) => page.fields)) {
        if (field.surrogateFieldMapping) {
            mappedFieldByTarget.set(field.surrogateFieldMapping, field)
        }
    }

    return DONOR_REQUIRED_MAPPING_VALUES.map((target): DonorRequiredFieldStatus => {
        const label = DONOR_LABEL_BY_VALUE.get(target) ?? target
        const field = mappedFieldByTarget.get(target)
        if (!field) return { value: target, label, status: "missing", fieldId: null }
        if (!DONOR_FIELD_TYPES[target]?.has(field.type)) {
            return { value: target, label, status: "wrong_type", fieldId: field.id }
        }
        return { value: target, label, status: field.required ? "ready" : "not_required", fieldId: field.id }
    })
}

export function getDonorPublishValidationMessage(
    pages: BuilderFormPage[],
    leadKind: FormLeadKind,
): string | null {
    if (!isDonorFormLeadKind(leadKind)) return null

    const statuses = getDonorRequiredFieldStatuses(pages)
    const labelsWith = (status: DonorRequiredFieldStatus["status"]) =>
        statuses.filter((item) => item.status === status).map((item) => item.label)
    const missing = labelsWith("missing")
    const optional = labelsWith("not_required")
    const incompatible = labelsWith("wrong_type")

    const parts: string[] = []
    if (missing.length > 0) parts.push(`map required fields: ${missing.join(", ")}`)
    if (optional.length > 0) parts.push(`mark required: ${optional.join(", ")}`)
    if (incompatible.length > 0) parts.push(`use compatible field types: ${incompatible.join(", ")}`)
    return parts.length > 0 ? `Donor intake is incomplete; ${parts.join("; ")}.` : null
}
