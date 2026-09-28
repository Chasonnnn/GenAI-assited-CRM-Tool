import type { FormLeadKind, FormPurpose, FormSurrogateFieldOption } from "@/lib/api/forms"
import { DEFAULT_FORM_SURROGATE_FIELD_OPTIONS } from "@/lib/api/forms"
import { buildMappings, type BuilderFormPage } from "@/lib/forms/form-builder-document"
import {
    getBuilderFieldGroupsForLeadKind,
    type BuilderPaletteField,
} from "@/lib/forms/form-builder-library"
import { getDonorRequiredFieldStatuses, isDonorFormLeadKind } from "@/lib/forms/form-lead-kind"

export type PublishReadinessStatus = "ready" | "missing" | "not_required" | "wrong_type"

export type PublishReadinessItem = {
    key: string
    label: string
    status: PublishReadinessStatus
    /** Mapped field to fix when the status is not_required or wrong_type. */
    fieldId: string | null
    /** Preset field that satisfies a missing item in one click. */
    addField: BuilderPaletteField | null
}

const EMAIL_OR_PHONE_KEY = "email_or_phone"

function findPresetField(leadKind: FormLeadKind, mapping: string): BuilderPaletteField | null {
    for (const group of getBuilderFieldGroupsForLeadKind(leadKind).presetGroups) {
        const field = group.fields.find((candidate) => candidate.surrogateFieldMapping === mapping)
        if (field) return field
    }
    return null
}

function getOptionLabel(value: string, mappingOptions: FormSurrogateFieldOption[]): string {
    return (
        mappingOptions.find((option) => option.value === value)?.label ??
        DEFAULT_FORM_SURROGATE_FIELD_OPTIONS.find((option) => option.value === value)?.label ??
        value
    )
}

function getCriticalValues(mappingOptions: FormSurrogateFieldOption[]): string[] {
    const fromOptions = mappingOptions.filter((option) => option.is_critical).map((option) => option.value)
    if (fromOptions.length > 0) return fromOptions
    return DEFAULT_FORM_SURROGATE_FIELD_OPTIONS.filter((option) => option.is_critical).map(
        (option) => option.value,
    )
}

/**
 * Identity fields a form must collect before it can be published. Lead capture
 * forms need a name plus email or phone; other forms need every critical
 * mapping; donor forms also need their donor fields required and correctly typed.
 */
export function getPublishReadinessItems({
    pages,
    leadKind,
    purpose,
    mappingOptions,
}: {
    pages: BuilderFormPage[]
    leadKind: FormLeadKind
    purpose: FormPurpose
    mappingOptions: FormSurrogateFieldOption[]
}): PublishReadinessItem[] {
    const mappedFields = new Set(buildMappings(pages).map((mapping) => mapping.surrogate_field))
    const fieldKeys = new Set(pages.flatMap((page) => page.fields.map((field) => field.id)))
    const isCollected = (value: string) => mappedFields.has(value) || fieldKeys.has(value)
    const baseItem = (key: string, label: string, ready: boolean, addMapping = key): PublishReadinessItem => ({
        key,
        label,
        status: ready ? "ready" : "missing",
        fieldId: null,
        addField: ready ? null : findPresetField(leadKind, addMapping),
    })

    const baseItems =
        purpose === "lead_capture"
            ? [
                  baseItem("full_name", getOptionLabel("full_name", mappingOptions), isCollected("full_name")),
                  baseItem(
                      EMAIL_OR_PHONE_KEY,
                      "Email or Phone",
                      isCollected("email") || isCollected("phone"),
                      "email",
                  ),
              ]
            : getCriticalValues(mappingOptions).map((value) =>
                  baseItem(value, getOptionLabel(value, mappingOptions), isCollected(value)),
              )

    if (!isDonorFormLeadKind(leadKind)) return baseItems

    const donorItems: PublishReadinessItem[] = getDonorRequiredFieldStatuses(pages).map((item) => ({
        key: item.value,
        label: item.label,
        status: item.status,
        fieldId: item.fieldId,
        addField: item.status === "missing" ? findPresetField(leadKind, item.value) : null,
    }))
    const donorKeys = new Set(donorItems.map((item) => item.key))
    // A donor Email requirement covers the lead-capture "Email or Phone" rule.
    const extraItems = baseItems.filter(
        (item) => item.key !== EMAIL_OR_PHONE_KEY && !donorKeys.has(item.key),
    )
    return [...donorItems, ...extraItems]
}

export function getPublishReadinessReason(items: PublishReadinessItem[]): string | null {
    const labelsWith = (status: PublishReadinessStatus) =>
        items.filter((item) => item.status === status).map((item) => item.label).join(", ")
    const parts = [
        labelsWith("missing") && `add ${labelsWith("missing")}`,
        labelsWith("not_required") && `mark ${labelsWith("not_required")} required`,
        labelsWith("wrong_type") && `change the field type for ${labelsWith("wrong_type")}`,
    ].filter(Boolean)
    return parts.length > 0 ? `To publish, ${parts.join("; ")}.` : null
}
