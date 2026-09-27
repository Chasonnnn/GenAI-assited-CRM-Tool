"use client"

import { Separator } from "@/components/ui/separator"
import { ValidatedField } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { US_STATES } from "@/lib/constants/us-states"
import type { IntendedParentFormValues } from "./intended-parent-form-values"

const PRONOUN_OPTIONS = ["He/Him", "She/Her", "They/Them", "Other"]

function FormSelect({
    id,
    label,
    value,
    onChange,
    placeholder,
    options,
}: {
    id: string
    label: string
    value: string
    onChange: (value: string) => void
    placeholder: string
    options: ReadonlyArray<{ label: string; value: string }>
}) {
    const labelId = `${id}-label`

    return (
        <div className="space-y-2">
            <Label id={labelId} htmlFor={id}>{label}</Label>
            <Select value={value || null} onValueChange={(nextValue) => onChange(nextValue ?? "")}>
                <SelectTrigger id={id} aria-labelledby={labelId}>
                    <SelectValue placeholder={placeholder}>
                        {(selectedValue: string | null) =>
                            options.find((option) => option.value === selectedValue)?.label ?? placeholder
                        }
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="">{placeholder}</SelectItem>
                    {options.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                            {option.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    )
}

export type ValidatedIntendedParentField = "full_name" | "email" | "partner_email"

/** Subset of useFormValidation for the fields this component validates. */
export type IntendedParentFieldValidation = {
    errorFor: (field: ValidatedIntendedParentField) => string | undefined
    touch: (field: ValidatedIntendedParentField) => void
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
    validation?: IntendedParentFieldValidation
}

// City gets the most room; State needs space for "New York (NY)"; ZIP is short.
const CITY_STATE_ZIP_GRID = "grid gap-4 md:grid-cols-[1fr_1.4fr_0.8fr]"

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
        <FormSelect
            id={id}
            label={label}
            value={value}
            onChange={onChange}
            placeholder="Select pronouns"
            options={PRONOUN_OPTIONS.map((option) => ({ label: option, value: option }))}
        />
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
        <FormSelect
            id={id}
            label={label}
            value={value}
            onChange={onChange}
            placeholder="Select a state"
            options={US_STATES.map((state) => ({
                label: `${state.label} (${state.value})`,
                value: state.value,
            }))}
        />
    )
}

export function IntendedParentFormFields({
    values,
    onChange,
    idPrefix,
    showAddressSection = true,
    showClinicSection = true,
    showInternalNotes = true,
    validation,
}: IntendedParentFormFieldsProps) {
    return (
        <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
                <ValidatedField
                    id={`${idPrefix}full_name`}
                    label="Full Name *"
                    error={validation?.errorFor("full_name")}
                    className="gap-2"
                >
                    {(control) => (
                        <Input
                            {...control}
                            required
                            value={values.full_name}
                            onChange={(event) => onChange("full_name", event.target.value)}
                            onBlur={() => validation?.touch("full_name")}
                            placeholder="John and Jane Doe"
                        />
                    )}
                </ValidatedField>
                <PronounsField
                    id={`${idPrefix}pronouns`}
                    label="Pronouns"
                    value={values.pronouns}
                    onChange={(value) => onChange("pronouns", value)}
                />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
                <ValidatedField
                    id={`${idPrefix}email`}
                    label="Email *"
                    error={validation?.errorFor("email")}
                    className="gap-2"
                >
                    {(control) => (
                        <Input
                            {...control}
                            type="email"
                            required
                            value={values.email}
                            onChange={(event) => onChange("email", event.target.value)}
                            onBlur={() => validation?.touch("email")}
                            placeholder="john@example.com"
                        />
                    )}
                </ValidatedField>
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
            <ValidatedField
                id={`${idPrefix}partner_email`}
                label="Partner Email"
                error={validation?.errorFor("partner_email")}
                className="gap-2"
            >
                {(control) => (
                    <Input
                        {...control}
                        type="email"
                        value={values.partner_email}
                        onChange={(event) => onChange("partner_email", event.target.value)}
                        onBlur={() => validation?.touch("partner_email")}
                        placeholder="partner@example.com"
                    />
                )}
            </ValidatedField>

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
                    <div className={CITY_STATE_ZIP_GRID}>
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
                    <div className={CITY_STATE_ZIP_GRID}>
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
