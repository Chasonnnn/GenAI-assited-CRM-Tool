"use client"

import { Separator } from "@/components/ui/separator"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { US_STATES } from "@/lib/constants/us-states"
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

const PRONOUN_OPTIONS = ["He/Him", "She/Her", "They/Them", "Other"]

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

interface IntendedParentFormFieldsProps {
    values: IntendedParentFormValues
    onChange: <K extends keyof IntendedParentFormValues>(
        field: K,
        value: IntendedParentFormValues[K],
    ) => void
    idPrefix: string
    showAddressSection?: boolean
    showClinicSection?: boolean
    showInternalNotes?: boolean
}

function PronounsField({
    id,
    label,
    value,
    onChange,
}: {
    id: string
    label: string
    value: string
    onChange: (value: string) => void
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor={id}>{label}</Label>
            <select
                id={id}
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
            >
                <option value="">Select pronouns</option>
                {PRONOUN_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                        {option}
                    </option>
                ))}
            </select>
        </div>
    )
}

function StateField({
    id,
    label,
    value,
    onChange,
}: {
    id: string
    label: string
    value: string
    onChange: (value: string) => void
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor={id}>{label}</Label>
            <select
                id={id}
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
            >
                <option value="">Select a state</option>
                {US_STATES.map((state) => (
                    <option key={state.value} value={state.value}>
                        {state.label} ({state.value})
                    </option>
                ))}
            </select>
        </div>
    )
}

export function IntendedParentFormFields({
    values,
    onChange,
    idPrefix,
    showAddressSection = true,
    showClinicSection = true,
    showInternalNotes = true,
}: IntendedParentFormFieldsProps) {
    return (
        <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                    <Label htmlFor={`${idPrefix}full_name`}>Full Name *</Label>
                    <Input
                        id={`${idPrefix}full_name`}
                        value={values.full_name}
                        onChange={(event) => onChange("full_name", event.target.value)}
                        placeholder="John and Jane Doe"
                    />
                </div>
                <PronounsField
                    id={`${idPrefix}pronouns`}
                    label="Pronouns"
                    value={values.pronouns}
                    onChange={(value) => onChange("pronouns", value)}
                />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                    <Label htmlFor={`${idPrefix}email`}>Email *</Label>
                    <Input
                        id={`${idPrefix}email`}
                        type="email"
                        value={values.email}
                        onChange={(event) => onChange("email", event.target.value)}
                        placeholder="john@example.com"
                    />
                </div>
                <div className="space-y-2">
                    <Label htmlFor={`${idPrefix}phone`}>Phone</Label>
                    <Input
                        id={`${idPrefix}phone`}
                        value={values.phone}
                        onChange={(event) => onChange("phone", event.target.value)}
                        placeholder="+1 (555) 123-4567"
                    />
                </div>
            </div>

            <Separator />
            <p className="text-sm font-medium">Partner</p>
            <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                    <Label htmlFor={`${idPrefix}partner_name`}>Partner Name</Label>
                    <Input
                        id={`${idPrefix}partner_name`}
                        value={values.partner_name}
                        onChange={(event) => onChange("partner_name", event.target.value)}
                        placeholder="Partner name"
                    />
                </div>
                <PronounsField
                    id={`${idPrefix}partner_pronouns`}
                    label="Partner Pronouns"
                    value={values.partner_pronouns}
                    onChange={(value) => onChange("partner_pronouns", value)}
                />
            </div>
            <div className="space-y-2">
                <Label htmlFor={`${idPrefix}partner_email`}>Partner Email</Label>
                <Input
                    id={`${idPrefix}partner_email`}
                    type="email"
                    value={values.partner_email}
                    onChange={(event) => onChange("partner_email", event.target.value)}
                    placeholder="partner@example.com"
                />
            </div>

            {showAddressSection && (
                <>
                    <Separator />
                    <p className="text-sm font-medium">Address</p>
                    <div className="space-y-2">
                        <Label htmlFor={`${idPrefix}address_line1`}>Address Line 1</Label>
                        <Input
                            id={`${idPrefix}address_line1`}
                            value={values.address_line1}
                            onChange={(event) => onChange("address_line1", event.target.value)}
                            placeholder="Street address"
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor={`${idPrefix}address_line2`}>Address Line 2</Label>
                        <Input
                            id={`${idPrefix}address_line2`}
                            value={values.address_line2}
                            onChange={(event) => onChange("address_line2", event.target.value)}
                            placeholder="Suite, unit, etc."
                        />
                    </div>
                    <div className="grid gap-4 md:grid-cols-3">
                        <div className="space-y-2">
                            <Label htmlFor={`${idPrefix}city`}>City</Label>
                            <Input
                                id={`${idPrefix}city`}
                                value={values.city}
                                onChange={(event) => onChange("city", event.target.value)}
                            />
                        </div>
                        <StateField
                            id={`${idPrefix}state`}
                            label="State"
                            value={values.state}
                            onChange={(value) => onChange("state", value)}
                        />
                        <div className="space-y-2">
                            <Label htmlFor={`${idPrefix}postal`}>ZIP</Label>
                            <Input
                                id={`${idPrefix}postal`}
                                value={values.postal}
                                onChange={(event) => onChange("postal", event.target.value)}
                                placeholder="00000"
                            />
                        </div>
                    </div>
                </>
            )}

            {showClinicSection && (
                <>
                    <Separator />
                    <p className="text-sm font-medium">IVF Clinic</p>
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                            <Label htmlFor={`${idPrefix}ip_clinic_name`}>IVF Clinic Name</Label>
                            <Input
                                id={`${idPrefix}ip_clinic_name`}
                                value={values.ip_clinic_name}
                                onChange={(event) => onChange("ip_clinic_name", event.target.value)}
                                placeholder="Clinic name"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor={`${idPrefix}ip_clinic_email`}>IVF Clinic Email</Label>
                            <Input
                                id={`${idPrefix}ip_clinic_email`}
                                type="email"
                                value={values.ip_clinic_email}
                                onChange={(event) => onChange("ip_clinic_email", event.target.value)}
                                placeholder="clinic@example.com"
                            />
                        </div>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                            <Label htmlFor={`${idPrefix}ip_clinic_phone`}>IVF Clinic Phone</Label>
                            <Input
                                id={`${idPrefix}ip_clinic_phone`}
                                value={values.ip_clinic_phone}
                                onChange={(event) => onChange("ip_clinic_phone", event.target.value)}
                                placeholder="+1 (555) 123-4567"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor={`${idPrefix}ip_clinic_fax`}>IVF Clinic Fax</Label>
                            <Input
                                id={`${idPrefix}ip_clinic_fax`}
                                value={values.ip_clinic_fax}
                                onChange={(event) => onChange("ip_clinic_fax", event.target.value)}
                                placeholder="+1 (555) 123-4568"
                            />
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor={`${idPrefix}ip_clinic_address_line1`}>IVF Clinic Street Address</Label>
                        <Input
                            id={`${idPrefix}ip_clinic_address_line1`}
                            value={values.ip_clinic_address_line1}
                            onChange={(event) => onChange("ip_clinic_address_line1", event.target.value)}
                            placeholder="Street address"
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor={`${idPrefix}ip_clinic_address_line2`}>IVF Clinic Suite or Unit</Label>
                        <Input
                            id={`${idPrefix}ip_clinic_address_line2`}
                            value={values.ip_clinic_address_line2}
                            onChange={(event) => onChange("ip_clinic_address_line2", event.target.value)}
                            placeholder="Suite, unit, etc."
                        />
                    </div>
                    <div className="grid gap-4 md:grid-cols-3">
                        <div className="space-y-2">
                            <Label htmlFor={`${idPrefix}ip_clinic_city`}>IVF Clinic Locality</Label>
                            <Input
                                id={`${idPrefix}ip_clinic_city`}
                                value={values.ip_clinic_city}
                                onChange={(event) => onChange("ip_clinic_city", event.target.value)}
                            />
                        </div>
                        <StateField
                            id={`${idPrefix}ip_clinic_state`}
                            label="IVF Clinic State"
                            value={values.ip_clinic_state}
                            onChange={(value) => onChange("ip_clinic_state", value)}
                        />
                        <div className="space-y-2">
                            <Label htmlFor={`${idPrefix}ip_clinic_postal`}>IVF Clinic Postal Code</Label>
                            <Input
                                id={`${idPrefix}ip_clinic_postal`}
                                value={values.ip_clinic_postal}
                                onChange={(event) => onChange("ip_clinic_postal", event.target.value)}
                                placeholder="00000"
                            />
                        </div>
                    </div>
                </>
            )}

            {showInternalNotes && (
                <>
                    <Separator />
                    <div className="space-y-2">
                        <Label htmlFor={`${idPrefix}notes_internal`}>Internal Notes</Label>
                        <Textarea
                            id={`${idPrefix}notes_internal`}
                            value={values.notes_internal}
                            onChange={(event) => onChange("notes_internal", event.target.value)}
                            placeholder="Notes visible only to staff..."
                            rows={3}
                        />
                    </div>
                </>
            )}
        </div>
    )
}
