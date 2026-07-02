import type { IntendedParentCreate, IntendedParentUpdate } from "@/lib/types/intended-parent"

export interface IntendedParentFormValues {
    full_name: string
    email: string
    phone: string
    pronouns: string
    partner_name: string
    partner_email: string
    partner_pronouns: string
    address_line1: string
    address_line2: string
    city: string
    state: string
    postal: string
    ip_clinic_name: string
    ip_clinic_address_line1: string
    ip_clinic_address_line2: string
    ip_clinic_city: string
    ip_clinic_state: string
    ip_clinic_postal: string
    ip_clinic_phone: string
    ip_clinic_fax: string
    ip_clinic_email: string
    notes_internal: string
}

export const EMPTY_INTENDED_PARENT_FORM_VALUES: IntendedParentFormValues = {
    full_name: "",
    email: "",
    phone: "",
    pronouns: "",
    partner_name: "",
    partner_email: "",
    partner_pronouns: "",
    address_line1: "",
    address_line2: "",
    city: "",
    state: "",
    postal: "",
    ip_clinic_name: "",
    ip_clinic_address_line1: "",
    ip_clinic_address_line2: "",
    ip_clinic_city: "",
    ip_clinic_state: "",
    ip_clinic_postal: "",
    ip_clinic_phone: "",
    ip_clinic_fax: "",
    ip_clinic_email: "",
    notes_internal: "",
}

const OPTIONAL_FIELDS: Array<keyof IntendedParentFormValues> = [
    "phone",
    "pronouns",
    "partner_name",
    "partner_email",
    "partner_pronouns",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "postal",
    "ip_clinic_name",
    "ip_clinic_address_line1",
    "ip_clinic_address_line2",
    "ip_clinic_city",
    "ip_clinic_state",
    "ip_clinic_postal",
    "ip_clinic_phone",
    "ip_clinic_fax",
    "ip_clinic_email",
    "notes_internal",
]

const STATE_FIELDS = new Set<keyof IntendedParentFormValues>(["state", "ip_clinic_state"])

function normalizeOptionalField(
    field: keyof IntendedParentFormValues,
    value: string,
): string | null {
    const trimmed = value.trim()
    if (!trimmed) return null
    if (STATE_FIELDS.has(field)) return trimmed.toUpperCase()
    return trimmed
}

export function buildIntendedParentCreatePayload(
    values: IntendedParentFormValues,
): IntendedParentCreate {
    const payload: IntendedParentCreate = {
        full_name: values.full_name.trim(),
        email: values.email.trim(),
    }
    const payloadRecord = payload as unknown as Record<string, string | null>

    for (const field of OPTIONAL_FIELDS) {
        const nextValue = normalizeOptionalField(field, values[field])
        if (nextValue !== null) {
            payloadRecord[field] = nextValue
        }
    }

    return payload
}

export function buildIntendedParentUpdatePayload(
    values: IntendedParentFormValues,
): IntendedParentUpdate {
    const payload: IntendedParentUpdate = {
        full_name: values.full_name.trim(),
        email: values.email.trim(),
    }
    const payloadRecord = payload as unknown as Record<string, string | null>

    for (const field of OPTIONAL_FIELDS) {
        payloadRecord[field] = normalizeOptionalField(field, values[field])
    }

    return payload
}
