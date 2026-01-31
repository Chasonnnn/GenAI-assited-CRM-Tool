"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { ChangeEvent } from "react"
import { useParams, useRouter } from "next/navigation"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
    ArrowLeftIcon,
    EyeIcon,
    GripVerticalIcon,
    MailIcon,
    PhoneIcon,
    CalendarIcon,
    HashIcon,
    ListIcon,
    CheckSquareIcon,
    FileIcon,
    HomeIcon,
    TypeIcon,
    PlusIcon,
    XIcon,
    Loader2Icon,
    Trash2Icon,
    CopyIcon,
    SmartphoneIcon,
} from "lucide-react"
import { toast } from "sonner"
import {
    useCreateForm,
    useForm,
    useFormMappings,
    usePublishForm,
    useSetFormMappings,
    useUpdateForm,
    useUploadFormLogo,
} from "@/lib/hooks/use-forms"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import { NotFoundState } from "@/components/not-found-state"
import type {
    FieldType,
    FormSchema,
    FormFieldOption,
    FormRead,
    FormCreatePayload,
    FormFieldValidation,
} from "@/lib/api/forms"
import { useAuth } from "@/lib/auth-context"
import { useOrgSignature } from "@/lib/hooks/use-signature"

// Field type definitions
type FieldTypeOption = {
    id: FieldType
    label: string
    icon: typeof TypeIcon
}

const fieldTypes: { basic: FieldTypeOption[]; advanced: FieldTypeOption[] } = {
    basic: [
        { id: "text", label: "Name", icon: TypeIcon },
        { id: "textarea", label: "Long Text", icon: TypeIcon },
        { id: "email", label: "Email", icon: MailIcon },
        { id: "phone", label: "Phone", icon: PhoneIcon },
        { id: "date", label: "Date", icon: CalendarIcon },
        { id: "number", label: "Number", icon: HashIcon },
    ],
    advanced: [
        { id: "select", label: "Select", icon: ListIcon },
        { id: "multiselect", label: "Multi-Select", icon: CheckSquareIcon },
        { id: "radio", label: "Radio", icon: CheckSquareIcon },
        { id: "checkbox", label: "Checkbox", icon: CheckSquareIcon },
        { id: "file", label: "File Upload", icon: FileIcon },
        { id: "address", label: "Address", icon: HomeIcon },
        { id: "repeatable_table", label: "Repeating Table", icon: ListIcon },
    ],
}

// Surrogate field mappings matching backend SURROGATE_FIELD_TYPES
const surrogateFieldMappings = [
    { value: "full_name", label: "Full Name" },
    { value: "email", label: "Email" },
    { value: "phone", label: "Phone" },
    { value: "state", label: "State" },
    { value: "date_of_birth", label: "Date of Birth" },
    { value: "race", label: "Race" },
    { value: "height_ft", label: "Height (ft)" },
    { value: "weight_lb", label: "Weight (lb)" },
    { value: "is_age_eligible", label: "Age Eligible" },
    { value: "is_citizen_or_pr", label: "US Citizen/PR" },
    { value: "has_child", label: "Has Child" },
    { value: "is_non_smoker", label: "Non-Smoker" },
    { value: "has_surrogate_experience", label: "Surrogate Experience" },
    { value: "num_deliveries", label: "Number of Deliveries" },
    { value: "num_csections", label: "Number of C-Sections" },
    { value: "is_priority", label: "Priority" },
]

type FormField = {
    id: string
    type: FieldType
    label: string
    helperText: string
    required: boolean
    surrogateFieldMapping: string
    options?: string[]
    validation?: FormFieldValidation | null
    showIf?: {
        fieldKey: string
        operator: "equals" | "not_equals" | "contains" | "not_contains" | "is_empty" | "is_not_empty"
        value?: string
    } | null
    columns?: {
        id: string
        label: string
        type: "text" | "number" | "date" | "select"
        required: boolean
        options?: string[]
        validation?: FormFieldValidation | null
    }[]
    minRows?: number | null
    maxRows?: number | null
}

type ShowIfOperator = NonNullable<FormField["showIf"]>["operator"]

type FormPage = {
    id: number
    name: string
    fields: FormField[]
}

function toFieldOptions(options?: string[]): FormFieldOption[] | null {
    if (!options || options.length === 0) return null
    return options.map((option) => ({
        label: option,
        value: option,
    }))
}

type SchemaMetadata = {
    publicTitle: string
    logoUrl: string
    privacyNotice: string
}

function buildFormSchema(pages: FormPage[], metadata: SchemaMetadata): FormSchema {
    const publicTitle = metadata.publicTitle.trim()
    const logoUrl = metadata.logoUrl.trim()
    const privacyNotice = metadata.privacyNotice.trim()

    return {
        pages: pages.map((page) => ({
            title: page.name || null,
            fields: page.fields.map((field) => ({
                key: field.id,
                label: field.label,
                type: field.type,
                required: field.required,
                options: toFieldOptions(field.options),
                validation: field.validation ?? null,
                help_text: field.helperText || null,
                show_if: field.showIf
                    ? {
                        field_key: field.showIf.fieldKey,
                        operator: field.showIf.operator,
                        value: field.showIf.value ?? null,
                    }
                    : null,
                columns: field.columns
                    ? field.columns.map((column) => ({
                        key: column.id,
                        label: column.label,
                        type: column.type,
                        required: column.required,
                        options: toFieldOptions(column.options),
                        validation: column.validation ?? null,
                    }))
                    : null,
                min_rows: field.minRows ?? null,
                max_rows: field.maxRows ?? null,
            })),
        })),
        public_title: publicTitle || null,
        logo_url: logoUrl || null,
        privacy_notice: privacyNotice || null,
    }
}

function schemaToPages(schema: FormSchema, mappings: Map<string, string>): FormPage[] {
    const pages = schema.pages.map((page, index) => ({
        id: index + 1,
        name: page.title || `Page ${index + 1}`,
        fields: page.fields.map((field) => {
            const options = field.options?.map((option) => option.label || option.value)
            const columns = field.columns?.map((column) => {
                const columnOptions = column.options?.map((option) => option.label || option.value)
                return {
                    id: column.key,
                    label: column.label,
                    type: column.type,
                    required: column.required ?? false,
                    ...(columnOptions ? { options: columnOptions } : {}),
                    validation: column.validation ?? null,
                }
            })
            const showIf =
                field.show_if
                    ? {
                        fieldKey: field.show_if.field_key,
                        operator: field.show_if.operator,
                        ...(field.show_if.value !== null && field.show_if.value !== undefined
                            ? { value: String(field.show_if.value) }
                            : {}),
                    }
                    : null
            return {
                id: field.key,
                type: field.type,
                label: field.label,
                helperText: field.help_text || "",
                required: field.required ?? false,
                surrogateFieldMapping: mappings.get(field.key) || "",
                validation: field.validation ?? null,
                showIf,
                ...(columns && columns.length > 0 ? { columns } : {}),
                minRows: field.min_rows ?? null,
                maxRows: field.max_rows ?? null,
                ...(options ? { options } : {}),
            }
        }),
    }))

    if (pages.length === 0) {
        return [{ id: 1, name: "Page 1", fields: [] }]
    }

    return pages
}

function schemaToMetadata(schema?: FormSchema | null): SchemaMetadata {
    return {
        publicTitle: schema?.public_title ?? "",
        logoUrl: schema?.logo_url ?? "",
        privacyNotice: schema?.privacy_notice ?? "",
    }
}

function buildMappings(pages: FormPage[]): { field_key: string; surrogate_field: string }[] {
    return pages.flatMap((page) =>
        page.fields
            .filter((field) => field.surrogateFieldMapping)
            .map((field) => ({
                field_key: field.id,
                surrogate_field: field.surrogateFieldMapping,
            })),
    )
}

const YES_NO_OPTIONS = ["Yes", "No"]
const YES_NO_UNSURE_OPTIONS = ["Yes", "No", "Not sure"]
const BLOOD_TYPE_OPTIONS = ["A", "B", "AB", "O"]
const RH_FACTOR_OPTIONS = ["Positive", "Negative", "Unknown"]
const PREGNANCY_CONDITION_OPTIONS = [
    "Gestational diabetes",
    "Preeclampsia",
    "Preterm labor",
    "Placenta previa",
    "Other complications",
]
const DISEASE_OPTIONS = ["HIV", "Hepatitis B", "Hepatitis C", "Herpes", "Syphilis", "Other"]
const IP_TYPE_OPTIONS = ["Heterosexual couple", "Same-sex couple", "Single parent", "Not sure"]
const COMPLIANCE_NOTICE =
    "By submitting this form, you consent to the collection and use of your information, including health-related details, for eligibility review and care coordination. Access is limited to authorized staff and retained per policy."
const COMPLIANCE_NOTICE_ES =
    "Al enviar este formulario, usted autoriza la recopilacion y uso de su informacion, incluidos datos de salud, para evaluar elegibilidad y coordinar la atencion. El acceso se limita al personal autorizado y se conserva segun la politica."

const TRANSLATION_MAP: Record<string, string> = {
    "Surrogacy Application": "Solicitud de gestacion subrogada",
    "Applicant Intake": "Ingreso de solicitantes",
    "Intended Parent Intake": "Ingreso de padres intencionados",
    "Contact Info": "Informacion de contacto",
    "Eligibility": "Elegibilidad",
    "Background": "Antecedentes",
    "Documents": "Documentos",
    "Full Name": "Nombre completo",
    "Email": "Correo electronico",
    "Phone": "Telefono",
    "State": "Estado",
    "Address": "Direccion",
    "Date of Birth": "Fecha de nacimiento",
    "US Citizen/PR": "Ciudadania EEUU o residencia",
    "Has Child": "Tiene hijo",
    "Non-Smoker": "No fumador",
    "Surrogate Experience": "Experiencia como gestante",
    "Number of Deliveries": "Numero de partos",
    "Number of C-Sections": "Numero de cesareas",
    "Height (ft)": "Altura (pies)",
    "Weight (lb)": "Peso (libras)",
    "Supporting Documents": "Documentos de respaldo",
    "Consent to Privacy Notice": "Consentimiento de aviso de privacidad",
}

const READING_LEVEL_HINTS = [
    "Keep each question under 12 words.",
    "Use simple yes/no options for eligibility checks.",
    "Explain acronyms like C-section the first time.",
]

type FormDraft = {
    formName: string
    description: string
    publicTitle: string
    privacyNotice: string
    pages: FormPage[]
    requiredSections: string[]
    optionalSections: string[]
    suggestedFieldTypes: string[]
    conditionalLogic: string[]
    readingLevelHints: string[]
    translationDraft: string
    maxFileSizeMb?: number
    maxFileCount?: number
    allowedMimeTypesText?: string
}

const buildFieldId = () => {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return crypto.randomUUID()
    }
    return `field-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const buildColumnId = () => {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return crypto.randomUUID()
    }
    return `col-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const buildDraftField = ({
    id,
    label,
    type,
    required = false,
    helperText = "",
    surrogateFieldMapping = "",
    options,
    validation,
    showIf,
    columns,
    minRows,
    maxRows,
}: {
    id?: string
    label: string
    type: FieldType
    required?: boolean
    helperText?: string
    surrogateFieldMapping?: string
    options?: string[]
    validation?: FormFieldValidation | null
    showIf?: FormField["showIf"] | null
    columns?: FormField["columns"]
    minRows?: number | null
    maxRows?: number | null
}): FormField => ({
    id: id ?? buildFieldId(),
    type,
    label,
    helperText,
    required,
    surrogateFieldMapping,
    ...(options ? { options } : {}),
    ...(validation ? { validation } : {}),
    ...(showIf ? { showIf } : {}),
    ...(columns ? { columns } : {}),
    ...(minRows !== undefined ? { minRows } : {}),
    ...(maxRows !== undefined ? { maxRows } : {}),
})

const translateLabel = (label: string) => TRANSLATION_MAP[label] || label

const buildTranslationDraft = (publicTitle: string, pages: FormPage[]) => {
    const sectionLines = pages.map((page) => `${page.name} -> ${translateLabel(page.name)}`)
    const fieldLabels = pages.flatMap((page) => page.fields.map((field) => field.label))
    const uniqueFields = Array.from(new Set(fieldLabels))
    const fieldLines = uniqueFields.slice(0, 12).map((label) => `${label} -> ${translateLabel(label)}`)
    const overflow = uniqueFields.length > 12 ? `; +${uniqueFields.length - 12} more` : ""

    return [
        `Title: ${translateLabel(publicTitle)}`,
        `Sections: ${sectionLines.join("; ")}`,
        `Fields: ${fieldLines.join("; ")}${overflow}`,
        `Privacy notice (ES): ${COMPLIANCE_NOTICE_ES}`,
    ].join("\n")
}

const generateFormDraft = (prompt: string): FormDraft => {
    const trimmed = prompt.trim()
    const lower = trimmed.toLowerCase()

    const isSurrogacy = lower.includes("surrogate") || lower.includes("surrogacy")
    const isIntendedParent = /\bintended parent\b/.test(lower) || /\bip\b/.test(lower)
    const needsDocuments =
        lower.includes("document") ||
        lower.includes("upload") ||
        lower.includes("file") ||
        lower.includes("insurance") ||
        lower.includes("id")
    const needsBackground =
        lower.includes("history") ||
        lower.includes("experience") ||
        lower.includes("pregnan") ||
        lower.includes("delivery") ||
        lower.includes("c-section")
    const needsMedical =
        lower.includes("medical") ||
        lower.includes("health") ||
        lower.includes("clinic") ||
        lower.includes("doctor") ||
        lower.includes("hipaa") ||
        lower.includes("phi")
    const includeAddress =
        lower.includes("address") ||
        lower.includes("street") ||
        lower.includes("city") ||
        lower.includes("zip") ||
        lower.includes("location")

    const publicTitle = isSurrogacy
        ? "Surrogacy Application"
        : isIntendedParent
            ? "Intended Parent Intake"
            : "Applicant Intake"
    const formName = `${publicTitle} Form`
    const description =
        trimmed || "Collect applicant details to support intake and eligibility review."

    const contactFields: FormField[] = [
        buildDraftField({
            label: "Full Name",
            type: "text",
            required: true,
            surrogateFieldMapping: "full_name",
            helperText: "Use your legal name.",
        }),
        buildDraftField({
            label: "Email",
            type: "email",
            required: true,
            surrogateFieldMapping: "email",
            helperText: "We will send updates here.",
        }),
        buildDraftField({
            label: "Phone",
            type: "phone",
            required: true,
            surrogateFieldMapping: "phone",
            helperText: "Best number for calls or texts.",
        }),
        buildDraftField({
            label: "State",
            type: "text",
            required: true,
            surrogateFieldMapping: "state",
            helperText: "Use two-letter state code.",
        }),
    ]

    if (includeAddress) {
        contactFields.push(
            buildDraftField({
                label: "Address",
                type: "address",
                required: false,
                helperText: "Street, city, and zip.",
            }),
        )
    }

    const eligibilityFields: FormField[] = [
        buildDraftField({
            label: "Date of Birth",
            type: "date",
            required: true,
            surrogateFieldMapping: "date_of_birth",
            helperText: "Used to confirm eligibility.",
        }),
        buildDraftField({
            label: "US Citizen/PR",
            type: "radio",
            required: true,
            surrogateFieldMapping: "is_citizen_or_pr",
            helperText: "Select yes or no.",
            options: YES_NO_OPTIONS,
        }),
        buildDraftField({
            label: "Has Child",
            type: "radio",
            required: true,
            surrogateFieldMapping: "has_child",
            helperText: "Select yes or no.",
            options: YES_NO_OPTIONS,
        }),
        buildDraftField({
            label: "Non-Smoker",
            type: "radio",
            required: true,
            surrogateFieldMapping: "is_non_smoker",
            helperText: "Select yes or no.",
            options: YES_NO_OPTIONS,
        }),
        buildDraftField({
            label: "Consent to Privacy Notice",
            type: "checkbox",
            required: true,
            helperText: "Required to submit this form.",
            options: ["I agree to the privacy notice"],
        }),
    ]

    const backgroundFields: FormField[] = []

    if (needsBackground || needsMedical) {
        backgroundFields.push(
            buildDraftField({
                label: "Surrogate Experience",
                type: "radio",
                required: false,
                surrogateFieldMapping: "has_surrogate_experience",
                helperText: "Select yes or no.",
                options: YES_NO_OPTIONS,
            }),
        )
    }

    if (needsMedical || lower.includes("height") || lower.includes("weight")) {
        backgroundFields.push(
            buildDraftField({
                label: "Height (ft)",
                type: "number",
                required: false,
                surrogateFieldMapping: "height_ft",
                helperText: "Numbers only.",
            }),
            buildDraftField({
                label: "Weight (lb)",
                type: "number",
                required: false,
                surrogateFieldMapping: "weight_lb",
                helperText: "Numbers only.",
            }),
        )
    }

    if (needsBackground || lower.includes("delivery") || lower.includes("c-section")) {
        backgroundFields.push(
            buildDraftField({
                label: "Number of Deliveries",
                type: "number",
                required: false,
                surrogateFieldMapping: "num_deliveries",
                helperText: "Enter 0 if none.",
            }),
            buildDraftField({
                label: "Number of C-Sections",
                type: "number",
                required: false,
                surrogateFieldMapping: "num_csections",
                helperText: "Enter 0 if none.",
            }),
        )
    }

    if (needsMedical || lower.includes("race")) {
        backgroundFields.push(
            buildDraftField({
                label: "Race",
                type: "text",
                required: false,
                surrogateFieldMapping: "race",
                helperText: "Optional.",
            }),
        )
    }

    const pages: FormPage[] = [
        { id: 1, name: "Contact Info", fields: contactFields },
        { id: 2, name: "Eligibility", fields: eligibilityFields },
    ]

    if (backgroundFields.length > 0) {
        pages.push({ id: pages.length + 1, name: "Background", fields: backgroundFields })
    }

    if (needsDocuments) {
        pages.push({
            id: pages.length + 1,
            name: "Documents",
            fields: [
                buildDraftField({
                    label: "Supporting Documents",
                    type: "file",
                    required: false,
                    helperText: "Upload files if you have them now.",
                }),
            ],
        })
    }

    const requiredSections = ["Contact Info", "Eligibility"]
    const optionalSections = pages
        .map((page) => page.name)
        .filter((name) => !requiredSections.includes(name))

    const typeLabels = new Map(
        [...fieldTypes.basic, ...fieldTypes.advanced].map((type) => [type.id, type.label]),
    )
    const suggestedFieldTypes = Array.from(
        new Set(pages.flatMap((page) => page.fields.map((field) => typeLabels.get(field.type) || field.type))),
    )

    const conditionalLogic: string[] = []
    if (backgroundFields.some((field) => field.label === "Surrogate Experience")) {
        conditionalLogic.push(
            "If Surrogate Experience is No, skip delivery history questions.",
        )
    }
    if (eligibilityFields.some((field) => field.label === "US Citizen/PR")) {
        conditionalLogic.push(
            "If US Citizen/PR is No, request visa or work authorization details.",
        )
    }
    if (eligibilityFields.some((field) => field.label === "Non-Smoker")) {
        conditionalLogic.push(
            "If Non-Smoker is No, ask about tobacco or nicotine use.",
        )
    }
    if (needsDocuments) {
        conditionalLogic.push(
            "Show document uploads only after eligibility is confirmed.",
        )
    }

    const translationDraft = buildTranslationDraft(publicTitle, pages)

    return {
        formName,
        description,
        publicTitle,
        privacyNotice: COMPLIANCE_NOTICE,
        pages,
        requiredSections,
        optionalSections,
        suggestedFieldTypes,
        conditionalLogic,
        readingLevelHints: READING_LEVEL_HINTS,
        translationDraft,
        maxFileSizeMb: 10,
        maxFileCount: 10,
        allowedMimeTypesText: "",
    }
}

const buildTemplateDraft = ({
    formName,
    description,
    publicTitle,
    privacyNotice,
    pages,
    requiredSections,
    conditionalLogic,
    maxFileSizeMb,
    maxFileCount,
    allowedMimeTypesText,
}: {
    formName: string
    description: string
    publicTitle: string
    privacyNotice: string
    pages: FormPage[]
    requiredSections: string[]
    conditionalLogic: string[]
    maxFileSizeMb?: number
    maxFileCount?: number
    allowedMimeTypesText?: string
}): FormDraft => {
    const optionalSections = pages
        .map((page) => page.name)
        .filter((name) => !requiredSections.includes(name))

    const typeLabels = new Map(
        [...fieldTypes.basic, ...fieldTypes.advanced].map((type) => [type.id, type.label]),
    )
    const suggestedFieldTypes = Array.from(
        new Set(
            pages.flatMap((page) => page.fields.map((field) => typeLabels.get(field.type) || field.type)),
        ),
    )

    const draft: FormDraft = {
        formName,
        description,
        publicTitle,
        privacyNotice,
        pages,
        requiredSections,
        optionalSections,
        suggestedFieldTypes,
        conditionalLogic,
        readingLevelHints: READING_LEVEL_HINTS,
        translationDraft: buildTranslationDraft(publicTitle, pages),
    }
    if (maxFileSizeMb !== undefined) {
        draft.maxFileSizeMb = maxFileSizeMb
    }
    if (maxFileCount !== undefined) {
        draft.maxFileCount = maxFileCount
    }
    if (allowedMimeTypesText !== undefined) {
        draft.allowedMimeTypesText = allowedMimeTypesText
    }
    return draft
}

const buildJotformTemplate = (): FormDraft => {
    const field = (
        id: string,
        label: string,
        type: FieldType,
        options: {
            required?: boolean
            helperText?: string
            surrogateFieldMapping?: string
            optionList?: string[]
            showIf?: FormField["showIf"] | null
            columns?: FormField["columns"]
            minRows?: number | null
            maxRows?: number | null
        } = {},
    ) =>
        buildDraftField({
            id,
            label,
            type,
            required: options.required ?? false,
            helperText: options.helperText ?? "",
            surrogateFieldMapping: options.surrogateFieldMapping ?? "",
            ...(options.optionList ? { options: options.optionList } : {}),
            showIf: options.showIf ?? null,
            ...(options.columns ? { columns: options.columns } : {}),
            ...(options.minRows !== undefined ? { minRows: options.minRows } : {}),
            ...(options.maxRows !== undefined ? { maxRows: options.maxRows } : {}),
        })

    const pages: FormPage[] = [
        {
            id: 1,
            name: "Surrogate Information",
            fields: [
                field("full_name", "Full Name", "text", {
                    required: true,
                    surrogateFieldMapping: "full_name",
                    helperText: "First and last name.",
                }),
                field("date_of_birth", "Date of Birth", "date", {
                    required: true,
                    surrogateFieldMapping: "date_of_birth",
                }),
                field("height_ft", "Height (ft)", "number", {
                    helperText: "Feet (e.g., 5.5).",
                    surrogateFieldMapping: "height_ft",
                }),
                field("weight_lb", "Weight (lb)", "number", {
                    helperText: "Pounds.",
                    surrogateFieldMapping: "weight_lb",
                }),
                field("email", "Email", "email", {
                    required: true,
                    surrogateFieldMapping: "email",
                }),
                field("cell_phone", "Cell Phone", "phone", {
                    required: true,
                    surrogateFieldMapping: "phone",
                }),
                field("address_line_1", "Street Address", "text", {
                    required: true,
                }),
                field("address_line_2", "Street Address Line 2", "text"),
                field("city", "City", "text", { required: true }),
                field("state", "State / Province", "text", {
                    required: true,
                    surrogateFieldMapping: "state",
                }),
                field("postal_code", "Postal / Zip Code", "text", { required: true }),
                field("country", "Country", "text"),
            ],
        },
        {
            id: 2,
            name: "Eligibility & Background",
            fields: [
                field("covid_vaccine_received", "Have you received Covid vaccine in the past?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("covid_vaccine_when", "If yes, when?", "date", {
                    helperText: "Date of your most recent vaccine.",
                    showIf: { fieldKey: "covid_vaccine_received", operator: "equals", value: "Yes" },
                }),
                field("covid_vaccine_willing", "If no, are you willing to receive Covid vaccine?", "radio", {
                    optionList: YES_NO_OPTIONS,
                    showIf: { fieldKey: "covid_vaccine_received", operator: "equals", value: "No" },
                }),
                field("tattoos_past_year", "Have you received any tattoos in the past year?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("tattoo_last_date", "If yes, date of your last tattoo", "date", {
                    showIf: { fieldKey: "tattoos_past_year", operator: "equals", value: "Yes" },
                }),
                field("religion_yes_no", "Do you have a religion?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("religion_detail", "If yes, please specify your religion", "text", {
                    showIf: { fieldKey: "religion_yes_no", operator: "equals", value: "Yes" },
                }),
                field("us_citizen", "Are you a US citizen or permanent resident?", "radio", {
                    required: true,
                    optionList: YES_NO_OPTIONS,
                    surrogateFieldMapping: "is_citizen_or_pr",
                }),
                field("race", "What is your race?", "text", { surrogateFieldMapping: "race" }),
                field("sexual_orientation", "Sexual Orientation", "text"),
                field("marital_status", "Marital status", "text", {
                    helperText: "Single, married, partnered, divorced, etc.",
                }),
                field("marriage_date", "If married, date of marriage", "date"),
                field("biological_children_count", "How many biological children do you have?", "number", {
                    helperText: "Enter 0 if none.",
                }),
                field("languages_spoken", "What languages do you speak?", "text"),
                field("schedule_flexible", "Is your daily schedule flexible?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("drivers_license", "Do you have a valid driver's license?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("transportation", "Do you have reliable transportation?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("car_insurance", "Do you have car insurance?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("health_insurance_carrier", "Name of health insurance carrier?", "text"),
                field("arrested", "Have you ever been arrested?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("arrested_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "arrested", operator: "equals", value: "Yes" },
                }),
                field("legal_cases_pending", "Are you currently involved in any legal cases that are pending?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("legal_cases_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "legal_cases_pending", operator: "equals", value: "Yes" },
                }),
                field(
                    "government_assistance",
                    "Do you receive any government assistance (WIC, Medicaid, Food Stamps, Disability)?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("government_assistance_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "government_assistance", operator: "equals", value: "Yes" },
                }),
            ],
        },
        {
            id: 3,
            name: "Education & Employment",
            fields: [
                field("education_level", "Highest level of education completed?", "text"),
                field("further_education_plans", "Do you plan on furthering your education?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("further_education_details", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "further_education_plans", operator: "equals", value: "Yes" },
                }),
                field("currently_employed", "Are you currently employed?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("employer_title", "If yes, present employer and title", "text", {
                    showIf: { fieldKey: "currently_employed", operator: "equals", value: "Yes" },
                }),
                field("employment_duration", "How long have you been employed there?", "text", {
                    showIf: { fieldKey: "currently_employed", operator: "equals", value: "Yes" },
                }),
            ],
        },
        {
            id: 4,
            name: "Pregnancy Information",
            fields: [
                buildDraftField({
                    id: "pregnancy_list",
                    label: "List of pregnancies",
                    type: "repeatable_table",
                    helperText:
                        "Include: own/surrogacy, # babies, delivery date, vaginal/C-section, gender, weight, weeks at birth, complications.",
                    columns: [
                        { id: "preg_type", label: "Type", type: "select", required: true, options: ["Own", "Surrogacy"] },
                        { id: "babies", label: "# Babies", type: "number", required: true },
                        { id: "delivery_date", label: "Delivery Date", type: "date", required: false },
                        { id: "delivery_type", label: "Delivery Type", type: "select", required: false, options: ["Vaginal", "C-Section"] },
                        { id: "gender", label: "Gender", type: "text", required: false },
                        { id: "weight", label: "Birth Weight", type: "text", required: false },
                        { id: "weeks", label: "Weeks at Birth", type: "number", required: false },
                        { id: "complications", label: "Complications", type: "text", required: false },
                    ],
                }),
                field("had_abortion", "Have you ever had an abortion?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("abortion_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "had_abortion", operator: "equals", value: "Yes" },
                }),
                field("had_miscarriage", "Have you ever had a miscarriage?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("miscarriage_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "had_miscarriage", operator: "equals", value: "Yes" },
                }),
                field(
                    "pregnancy_conditions",
                    "Have you ever experienced the following conditions?",
                    "checkbox",
                    { optionList: PREGNANCY_CONDITION_OPTIONS },
                ),
                field("pregnancy_conditions_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "pregnancy_conditions", operator: "is_not_empty", value: "" },
                }),
                field("breastfeeding", "Are you currently breastfeeding?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("breastfeeding_stop", "If yes, when do you plan to stop?", "text", {
                    showIf: { fieldKey: "breastfeeding", operator: "equals", value: "Yes" },
                }),
                field("sexually_active", "Are you sexually active?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("birth_control", "Are you using birth control?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("birth_control_type", "If yes, what kind?", "text", {
                    showIf: { fieldKey: "birth_control", operator: "equals", value: "Yes" },
                }),
                field("regular_cycles", "Do you have regular monthly menstrual cycles?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("irregular_cycles_detail", "If no, please specify", "text", {
                    showIf: { fieldKey: "regular_cycles", operator: "equals", value: "No" },
                }),
                field("last_obgyn_visit", "When did you last see your Ob/Gyn?", "date"),
                field("last_pap_smear", "Date of last Pap Smear and result?", "text"),
                field("reproductive_illnesses", "List any reproductive illness you have experienced", "textarea"),
            ],
        },
        {
            id: 5,
            name: "Family Support",
            fields: [
                field("spouse_significant_other", "Do you have a spouse/significant other?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field(
                    "spouse_occupation",
                    "If yes, what is your spouse/significant other's occupation?",
                    "text",
                    { showIf: { fieldKey: "spouse_significant_other", operator: "equals", value: "Yes" } },
                ),
                field("family_support", "Does your family support your decision to become a surrogate?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("bed_rest_help", "Who would help you if placed on bed rest?", "textarea"),
                field("anticipate_difficulties", "Do you anticipate any difficulties in becoming a surrogate?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("difficulties_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "anticipate_difficulties", operator: "equals", value: "Yes" },
                }),
                field("living_conditions", "Describe your current living conditions", "textarea"),
                buildDraftField({
                    id: "household_members",
                    label: "List everyone living in household with you, including age and relationship",
                    type: "repeatable_table",
                    columns: [
                        { id: "member_name", label: "Name", type: "text", required: true },
                        { id: "member_age", label: "Age", type: "number", required: true },
                        { id: "relationship", label: "Relationship", type: "text", required: true },
                    ],
                }),
                field("pets_at_home", "Do you have pets at home?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("pets_details", "If yes, what kind?", "text", {
                    showIf: { fieldKey: "pets_at_home", operator: "equals", value: "Yes" },
                }),
            ],
        },
        {
            id: 6,
            name: "Medical Info",
            fields: [
                field("blood_type", "Blood type", "select", { optionList: BLOOD_TYPE_OPTIONS }),
                field("rh_factor", "Rh factor", "select", { optionList: RH_FACTOR_OPTIONS }),
                field("current_weight", "Weight (lb)", "number"),
                field("current_height", "Height (ft)", "number"),
                field("drink_alcohol", "Do you drink alcohol?", "radio", { optionList: YES_NO_OPTIONS }),
                field("drink_alcohol_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "drink_alcohol", operator: "equals", value: "Yes" },
                }),
                field("household_smoke", "Does anyone in your household smoke?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("household_smoke_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "household_smoke", operator: "equals", value: "Yes" },
                }),
                field("used_illicit_drugs", "Have you ever used illicit drugs?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("used_illicit_drugs_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "used_illicit_drugs", operator: "equals", value: "Yes" },
                }),
                field(
                    "used_tobacco_last_6_months",
                    "Have you used tobacco, marijuana or illicit drugs within the past 6 months?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("used_tobacco_last_6_months_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "used_tobacco_last_6_months", operator: "equals", value: "Yes" },
                }),
                field("taking_medication", "Are you taking any medication?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("taking_medication_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "taking_medication", operator: "equals", value: "Yes" },
                }),
                field("treated_conditions", "Are you being treated for any medical conditions?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("treated_conditions_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "treated_conditions", operator: "equals", value: "Yes" },
                }),
                field(
                    "significant_illness_history",
                    "Have you or your immediate family had a history of significant illness or medical condition?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("significant_illness_history_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "significant_illness_history", operator: "equals", value: "Yes" },
                }),
                field(
                    "hospitalized_operations",
                    "Have you ever been hospitalized or had any operations (excluding birth)?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("hospitalized_operations_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "hospitalized_operations", operator: "equals", value: "Yes" },
                }),
                field("nearest_hospital", "How close are you to nearest hospital? Please list name and city.", "text"),
                field("psychiatric_conditions", "Have you ever been diagnosed or treated for any psychiatric conditions?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("psychiatric_conditions_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "psychiatric_conditions", operator: "equals", value: "Yes" },
                }),
                field("depression_anxiety_meds", "Have you ever taken any medication for depression/anxiety?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("depression_anxiety_meds_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "depression_anxiety_meds", operator: "equals", value: "Yes" },
                }),
                field(
                    "partner_psychiatric_hospital",
                    "Has your partner/spouse ever been hospitalized for psychiatric illness?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("partner_psychiatric_hospital_explain", "If yes, please explain", "textarea", {
                    showIf: { fieldKey: "partner_psychiatric_hospital", operator: "equals", value: "Yes" },
                }),
                field("immunized_hep_b", "Have you ever been immunized for Hepatitis B? (past only)", "radio", {
                    optionList: YES_NO_UNSURE_OPTIONS,
                }),
                field("immunized_hep_b_explain", "If yes or unsure, please explain", "textarea", {
                    showIf: { fieldKey: "immunized_hep_b", operator: "not_equals", value: "No" },
                }),
                field(
                    "diseases_self",
                    "Have you ever been diagnosed with any of the following diseases?",
                    "checkbox",
                    { optionList: DISEASE_OPTIONS },
                ),
                field(
                    "diseases_partner",
                    "Has your partner/spouse ever been diagnosed with any of the following diseases?",
                    "checkbox",
                    { optionList: DISEASE_OPTIONS },
                ),
            ],
        },
        {
            id: 7,
            name: "Characteristics",
            fields: [
                field("why_surrogate", "Why do you want to be a surrogate? Message to intended parents?", "textarea"),
                field("personality", "Describe your personality and character", "textarea"),
                field("hobbies", "What are your hobbies, interests, and talents?", "textarea"),
                field("daily_diet", "What is your daily diet?", "textarea"),
            ],
        },
        {
            id: 8,
            name: "Decisions",
            fields: [
                field("willing_ip_types", "Will you work with intended parents who are:", "checkbox", {
                    optionList: IP_TYPE_OPTIONS,
                }),
                field("willing_international", "Would you be willing to work with intended parents from other countries?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("willing_travel_canada", "Would you be willing to travel to Canada?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("willing_ip_hep_b", "Would you be willing to carry for intended parents who carry Hepatitis B?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field(
                    "willing_ip_hep_b_recovered",
                    "Would you be willing to carry for intended parents who do not carry Hepatitis B but have recovered?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("willing_ip_hiv", "Would you be willing to carry for intended parents who have HIV?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("willing_donor", "Would you be willing to carry a child with donor eggs or sperm?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("willing_different_religion", "Would you be willing to carry for intended parents of a different religion?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("relationship_with_ips", "What kind of relationship do you want with intended parents during conception and pregnancy?", "textarea"),
                field("max_embryos_transfer", "Maximum number of embryos you are willing to transfer per cycle", "number"),
                field("willing_twins", "Would you be willing to carry twins if embryo split or two transferred?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("terminate_abnormality", "Would you be willing to terminate a pregnancy due to a birth abnormality or deformity?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("terminate_life_risk", "Would you be willing to terminate a pregnancy if your life or baby's life was in danger?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("reduce_multiple_pregnancy", "Are you okay with reducing multiple pregnancy if it is medically necessary?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("terminate_gender", "Would you be willing to terminate a pregnancy due to gender?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field(
                    "invasive_procedures",
                    "Would you be willing to do any invasive procedures (D&C, Amniocentesis, Chronic Villus Sampling)?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("pump_breast_milk", "Would you be willing to pump breast milk after delivery?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("ip_attend_ob", "Would you be comfortable with intended parents attending OB appointments?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("delivery_room", "Who are you willing to have in the delivery room?", "textarea"),
                field("agree_ivf_medications", "You will be required to take IVF medications. Do you agree?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field(
                    "agree_abstain",
                    "Will you abstain from sexual activity while undergoing treatment and throughout pregnancy?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
            ],
        },
        {
            id: 9,
            name: "Uploads & Signature",
            fields: [
                field("upload_photos", "Upload at least 4 pics of you and your family", "file", {
                    required: true,
                    helperText: "Upload 4+ clear photos.",
                }),
                field("supporting_documents", "Supporting documents (optional)", "file", {
                    helperText: "Upload any additional documents.",
                }),
                field("medical_records", "Medical records (optional)", "file", {
                    helperText: "Upload recent medical records if available.",
                }),
                field("signature_name", "Signature (type full legal name)", "text", {
                    required: true,
                }),
            ],
        },
    ]

    return buildTemplateDraft({
        formName: "Surrogate Application Form (Official)",
        description: "Template based on the Jotform surrogate intake sample.",
        publicTitle: "Surrogate Intake Form",
        privacyNotice: COMPLIANCE_NOTICE,
        pages,
        requiredSections: ["Surrogate Information", "Eligibility & Background"],
        conditionalLogic: [
            "If COVID vaccine is Yes, show date; if No, ask willingness.",
            "If tattoos is Yes, request last tattoo date.",
            "If any legal/assistance questions are Yes, collect explanation.",
            "If pregnancy conditions are selected, request details.",
        ],
        maxFileSizeMb: 15,
        maxFileCount: 12,
        allowedMimeTypesText: "image/*,application/pdf",
    })
}

// Page component
export default function FormBuilderPage() {
    const params = useParams<{ id: string }>()
    const idParam = params?.id
    const id = Array.isArray(idParam) ? idParam[0] : idParam ?? "new"
    const router = useRouter()
    const { user } = useAuth()
    const isNewForm = id === "new"
    const formId = isNewForm ? null : id

    const { data: formData, isLoading: isFormLoading } = useForm(formId)
    const { data: mappingData, isLoading: isMappingsLoading } = useFormMappings(formId)
    const { data: orgSignature } = useOrgSignature()
    const createFormMutation = useCreateForm()
    const updateFormMutation = useUpdateForm()
    const publishFormMutation = usePublishForm()
    const setMappingsMutation = useSetFormMappings()
    const uploadLogoMutation = useUploadFormLogo()

    const logoInputRef = useRef<HTMLInputElement>(null)
    const lastSavedFingerprintRef = useRef<string>("")
    const hydratedFormRef = useRef<string | null>(null)
    const orgLogoInitRef = useRef(false)

    const [hasHydrated, setHasHydrated] = useState(false)

    // Form state
    const [formName, setFormName] = useState(isNewForm ? "" : "Surrogate Application Form")
    const [formDescription, setFormDescription] = useState("")
    const [publicTitle, setPublicTitle] = useState("")
    const [logoUrl, setLogoUrl] = useState("")
    const [privacyNotice, setPrivacyNotice] = useState("")
    const [maxFileSizeMb, setMaxFileSizeMb] = useState(10)
    const [maxFileCount, setMaxFileCount] = useState(10)
    const [allowedMimeTypesText, setAllowedMimeTypesText] = useState("")
    const [isPublished, setIsPublished] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [isPublishing, setIsPublishing] = useState(false)
    const [useOrgLogo, setUseOrgLogo] = useState(false)
    const [customLogoUrl, setCustomLogoUrl] = useState("")
    const [isMobilePreview, setIsMobilePreview] = useState(false)
    const [autoSaveStatus, setAutoSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle")
    const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null)
    const [draftPrompt, setDraftPrompt] = useState("")
    const [formDraft, setFormDraft] = useState<FormDraft | null>(null)
    const [isDrafting, setIsDrafting] = useState(false)

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || ""
    const orgId = user?.org_id || ""
    const orgLogoPath = orgId ? `/forms/public/${orgId}/signature-logo` : ""
    const orgLogoAvailable = Boolean(orgSignature?.signature_logo_url)
    const resolvedLogoUrl =
        logoUrl && logoUrl.startsWith("/") && apiBaseUrl ? `${apiBaseUrl}${logoUrl}` : logoUrl

    // Page/field state
    const [pages, setPages] = useState<FormPage[]>([{ id: 1, name: "Page 1", fields: [] }])
    const [activePage, setActivePage] = useState(1)
    const [selectedField, setSelectedField] = useState<string | null>(null)
    const [draggedField, setDraggedField] = useState<{
        type: FieldType
        label: string
    } | null>(null)
    const [draggedFieldId, setDraggedFieldId] = useState<string | null>(null)
    const [dropIndicatorId, setDropIndicatorId] = useState<string | "end" | null>(null)

    // Dialog state
    const [showPublishDialog, setShowPublishDialog] = useState(false)
    const [showDeletePageDialog, setShowDeletePageDialog] = useState(false)
    const [pageToDelete, setPageToDelete] = useState<number | null>(null)

    const jotformTemplate = useMemo(() => buildJotformTemplate(), [])
    const jotformTemplateSummary = useMemo(() => {
        const questionCount = jotformTemplate.pages.reduce((sum, page) => sum + page.fields.length, 0)
        return {
            sections: jotformTemplate.pages.length,
            questions: questionCount,
        }
    }, [jotformTemplate])

    useEffect(() => {
        setHasHydrated(false)
        setFormDraft(null)
        setDraftPrompt("")
        setAutoSaveStatus("idle")
        setLastSavedAt(null)
        hydratedFormRef.current = null
        orgLogoInitRef.current = false
        setUseOrgLogo(false)
        setCustomLogoUrl("")
        setIsMobilePreview(false)
        setMaxFileSizeMb(10)
        setMaxFileCount(10)
        setAllowedMimeTypesText("")
    }, [formId])

    useEffect(() => {
        if (isNewForm) {
            setHasHydrated(true)
        }
    }, [isNewForm])

    useEffect(() => {
        if (isNewForm || !formData || isMappingsLoading || hasHydrated) return

        const mappingMap = new Map(
            (mappingData || []).map((mapping) => [mapping.field_key, mapping.surrogate_field]),
        )
        const schema = formData.form_schema || formData.published_schema

        setFormName(formData.name)
        setFormDescription(formData.description || "")
        const metadata = schemaToMetadata(schema || undefined)
        setPublicTitle(metadata.publicTitle)
        setLogoUrl(metadata.logoUrl)
        setPrivacyNotice(metadata.privacyNotice)
        setMaxFileSizeMb(Math.max(1, Math.round((formData.max_file_size_bytes ?? 10485760) / (1024 * 1024))))
        setMaxFileCount(formData.max_file_count ?? 10)
        setAllowedMimeTypesText((formData.allowed_mime_types || []).join(", "))
        setIsPublished(formData.status === "published")
        setPages(schema ? schemaToPages(schema, mappingMap) : [{ id: 1, name: "Page 1", fields: [] }])
        setActivePage(1)
        setSelectedField(null)
        setHasHydrated(true)
    }, [formData, mappingData, isMappingsLoading, hasHydrated, isNewForm])

    useEffect(() => {
        if (!hasHydrated || orgLogoInitRef.current) return
        if (!orgLogoPath) return
        const isOrgLogo = logoUrl === orgLogoPath
        setUseOrgLogo(isOrgLogo)
        if (!isOrgLogo) {
            setCustomLogoUrl(logoUrl)
        }
        orgLogoInitRef.current = true
    }, [hasHydrated, logoUrl, orgLogoPath])

    const fallbackPage: FormPage = { id: 1, name: "Page 1", fields: [] }
    const currentPage = pages.find((p) => p.id === activePage) ?? pages[0] ?? fallbackPage

    const draftPayload = useMemo<FormCreatePayload>(() => {
        const allowedMimeTypes = allowedMimeTypesText
            .split(",")
            .map((entry) => entry.trim())
            .filter(Boolean)
        return {
            name: formName.trim(),
            description: formDescription.trim() || null,
            form_schema: buildFormSchema(pages, {
                publicTitle,
                logoUrl,
                privacyNotice,
            }),
            max_file_size_bytes: Math.max(1, Math.round(maxFileSizeMb * 1024 * 1024)),
            max_file_count: Math.max(0, Math.round(maxFileCount)),
            allowed_mime_types: allowedMimeTypes.length > 0 ? allowedMimeTypes : null,
        }
    }, [
        formName,
        formDescription,
        pages,
        publicTitle,
        logoUrl,
        privacyNotice,
        maxFileSizeMb,
        maxFileCount,
        allowedMimeTypesText,
    ])
    const draftFingerprint = useMemo(() => JSON.stringify(draftPayload), [draftPayload])
    const debouncedPayload = useDebouncedValue(draftPayload, 1200)
    const debouncedFingerprint = useMemo(
        () => JSON.stringify(debouncedPayload),
        [debouncedPayload],
    )
    const isDirty = draftFingerprint !== lastSavedFingerprintRef.current

    useEffect(() => {
        if (!hasHydrated) return
        const identity = isNewForm ? "new" : formId || "unknown"
        if (hydratedFormRef.current === identity) return
        hydratedFormRef.current = identity
        lastSavedFingerprintRef.current = draftFingerprint
        if (!isNewForm && formData?.updated_at) {
            setAutoSaveStatus("saved")
            setLastSavedAt(new Date(formData.updated_at))
        } else {
            setAutoSaveStatus("idle")
        }
    }, [hasHydrated, isNewForm, formId, draftFingerprint, formData?.updated_at])

    // Drag and drop handlers
    const handleDragStart = (type: FieldType, label: string) => {
        setDraggedField({ type, label })
        setDraggedFieldId(null)
    }

    const handleFieldDragStart = (fieldId: string) => {
        setDraggedFieldId(fieldId)
        setDraggedField(null)
    }

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault()
    }

    const handleCanvasDragOver = (e: React.DragEvent) => {
        e.preventDefault()
        if (!draggedField && !draggedFieldId) return
        if (currentPage.fields.length > 0) {
            setDropIndicatorId("end")
        }
    }

    const handleFieldDragOver = (e: React.DragEvent, fieldId: string) => {
        e.preventDefault()
        e.stopPropagation()
        if (!draggedField && !draggedFieldId) return
        setDropIndicatorId(fieldId)
    }

    const generateFieldId = () => {
        if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
            return crypto.randomUUID()
        }
        return `field-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    }

    const buildNewField = (): FormField | null => {
        if (!draggedField) return null

        const fieldId = generateFieldId()

        const baseField: FormField = {
            id: fieldId,
            type: draggedField.type,
            label: draggedField.label,
            helperText: "",
            required: false,
            surrogateFieldMapping: "",
        }
        if (["select", "multiselect", "radio"].includes(draggedField.type)) {
            return { ...baseField, options: ["Option 1", "Option 2", "Option 3"] }
        }
        if (draggedField.type === "repeatable_table") {
            return {
                ...baseField,
                label: "Repeating Table",
                columns: [
                    {
                        id: buildColumnId(),
                        label: "Column 1",
                        type: "text",
                        required: false,
                    },
                    {
                        id: buildColumnId(),
                        label: "Column 2",
                        type: "text",
                        required: false,
                    },
                ],
                minRows: 0,
                maxRows: null,
            }
        }
        return baseField
    }

    const moveFieldToIndex = (fields: FormField[], fieldId: string, targetIndex: number) => {
        const fromIndex = fields.findIndex((field) => field.id === fieldId)
        if (fromIndex === -1) return fields
        if (fromIndex === targetIndex) return fields

        const nextFields = [...fields]
        const [moved] = nextFields.splice(fromIndex, 1)
        if (!moved) return fields
        const adjustedIndex = fromIndex < targetIndex ? targetIndex - 1 : targetIndex
        const clampedIndex = Math.max(0, Math.min(adjustedIndex, nextFields.length))
        nextFields.splice(clampedIndex, 0, moved)
        return nextFields
    }

    const insertFieldAtIndex = (fields: FormField[], field: FormField, targetIndex: number) => {
        const nextFields = [...fields]
        const clampedIndex = Math.max(0, Math.min(targetIndex, nextFields.length))
        nextFields.splice(clampedIndex, 0, field)
        return nextFields
    }

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault()
        const newField = buildNewField()
        const nextSelectedField = newField?.id || draggedFieldId

        setPages((prev) =>
            prev.map((page) => {
                if (page.id !== activePage) return page
                if (draggedFieldId) {
                    return { ...page, fields: moveFieldToIndex(page.fields, draggedFieldId, page.fields.length) }
                }
                if (newField) {
                    return { ...page, fields: [...page.fields, newField] }
                }
                return page
            }),
        )
        setDraggedField(null)
        setDraggedFieldId(null)
        setDropIndicatorId(null)
        if (nextSelectedField) {
            setSelectedField(nextSelectedField)
        }
    }

    const handleDropOnField = (e: React.DragEvent, targetFieldId: string) => {
        e.preventDefault()
        e.stopPropagation()
        const newField = buildNewField()
        const nextSelectedField = newField?.id || draggedFieldId

        setPages((prev) =>
            prev.map((page) => {
                if (page.id !== activePage) return page
                const targetIndex = page.fields.findIndex((field) => field.id === targetFieldId)
                if (targetIndex === -1) return page
                if (draggedFieldId) {
                    if (draggedFieldId === targetFieldId) return page
                    return { ...page, fields: moveFieldToIndex(page.fields, draggedFieldId, targetIndex) }
                }
                if (newField) {
                    return { ...page, fields: insertFieldAtIndex(page.fields, newField, targetIndex) }
                }
                return page
            }),
        )
        setDraggedField(null)
        setDraggedFieldId(null)
        setDropIndicatorId(null)
        if (nextSelectedField) {
            setSelectedField(nextSelectedField)
        }
    }

    const handleDragEnd = () => {
        setDraggedField(null)
        setDraggedFieldId(null)
        setDropIndicatorId(null)
    }

    // Field handlers
    const handleDeleteField = (fieldId: string) => {
        setPages((prev) =>
            prev.map((page) =>
                page.id === activePage ? { ...page, fields: page.fields.filter((f) => f.id !== fieldId) } : page,
            ),
        )
        if (selectedField === fieldId) {
            setSelectedField(null)
        }
    }

    const handleDuplicateField = (fieldId: string) => {
        const nextId = generateFieldId()
        setPages((prev) =>
            prev.map((page) => {
                if (page.id !== activePage) return page
                const index = page.fields.findIndex((field) => field.id === fieldId)
                if (index === -1) return page
                const source = page.fields[index]
                if (!source) return page
                const duplicated: FormField = {
                    ...source,
                    id: nextId,
                    label: `${source.label} (Copy)`,
                    surrogateFieldMapping: "",
                }
                const nextFields = [...page.fields]
                nextFields.splice(index + 1, 0, duplicated)
                return { ...page, fields: nextFields }
            }),
        )
        setSelectedField(nextId)
    }

    const handleUpdateField = (fieldId: string, updates: Partial<FormField>) => {
        setPages((prev) =>
            prev.map((page) =>
                page.id === activePage
                    ? {
                        ...page,
                        fields: page.fields.map((f) => (f.id === fieldId ? { ...f, ...updates } : f)),
                    }
                    : page,
            ),
        )
    }

    const normalizeValidation = (
        current: FormFieldValidation | null | undefined,
        updates: Partial<FormFieldValidation>,
    ) => {
        const next: FormFieldValidation = {
            min_length: current?.min_length ?? null,
            max_length: current?.max_length ?? null,
            min_value: current?.min_value ?? null,
            max_value: current?.max_value ?? null,
            pattern: current?.pattern ?? null,
            ...updates,
        }
        if (next.pattern !== null && typeof next.pattern === "string" && next.pattern.trim() === "") {
            next.pattern = null
        }
        const hasValue = Object.values(next).some((value) => value !== null && value !== undefined)
        return hasValue ? next : null
    }

    const parseOptionalNumber = (value: string) => {
        if (!value.trim()) return null
        const parsed = Number(value)
        return Number.isNaN(parsed) ? null : parsed
    }

    const parseOptionalInt = (value: string) => {
        if (!value.trim()) return null
        const parsed = Number.parseInt(value, 10)
        return Number.isNaN(parsed) ? null : parsed
    }

    const handleValidationChange = (fieldId: string, updates: Partial<FormFieldValidation>) => {
        const nextValidation = normalizeValidation(selectedFieldData?.validation, updates)
        handleUpdateField(fieldId, { validation: nextValidation })
    }

    const handleAddColumn = (fieldId: string) => {
        const existing = selectedFieldData?.columns ?? []
        const nextColumns = [
            ...existing,
            {
                id: buildColumnId(),
                label: `Column ${existing.length + 1}`,
                type: "text" as const,
                required: false,
            },
        ]
        handleUpdateField(fieldId, { columns: nextColumns })
    }

    const handleUpdateColumn = (
        fieldId: string,
        columnId: string,
        updates: Partial<NonNullable<FormField["columns"]>[number]>,
    ) => {
        const existing = selectedFieldData?.columns ?? []
        const nextColumns = existing.map((column) =>
            column.id === columnId ? { ...column, ...updates } : column,
        )
        handleUpdateField(fieldId, { columns: nextColumns })
    }

    const handleRemoveColumn = (fieldId: string, columnId: string) => {
        const existing = selectedFieldData?.columns ?? []
        const nextColumns = existing.filter((column) => column.id !== columnId)
        handleUpdateField(fieldId, { columns: nextColumns })
    }

    const handleShowIfChange = (
        fieldId: string,
        updates: Partial<NonNullable<FormField["showIf"]>>,
    ) => {
        const current = selectedFieldData?.showIf ?? {
            fieldKey: "",
            operator: "equals" as const,
            value: "",
        }
        const next = { ...current, ...updates }
        if (!next.fieldKey) {
            handleUpdateField(fieldId, { showIf: null })
            return
        }
        if (["is_empty", "is_not_empty"].includes(next.operator)) {
            handleUpdateField(fieldId, { showIf: { ...next, value: "" } })
            return
        }
        handleUpdateField(fieldId, { showIf: next })
    }

    const handleMappingChange = (fieldId: string, value: string | null) => {
        const nextValue = value && value !== "none" ? value : ""
        if (nextValue) {
            const hasConflict = pages.some((page) =>
                page.fields.some(
                    (field) =>
                        field.id !== fieldId && field.surrogateFieldMapping === nextValue,
                ),
            )
            if (hasConflict) {
                toast.error("This surrogate field is already mapped to another form field.")
                return
            }
        }
        handleUpdateField(fieldId, { surrogateFieldMapping: nextValue })
    }

    // Page handlers
    const handleAddPage = () => {
        const nextPageId = Math.max(0, ...pages.map((page) => page.id)) + 1
        const newPage: FormPage = {
            id: nextPageId,
            name: `Page ${nextPageId}`,
            fields: [],
        }
        setPages([...pages, newPage])
        setActivePage(newPage.id)
    }

    const handleDuplicatePage = (pageId: number) => {
        const nextPageId = Math.max(0, ...pages.map((page) => page.id)) + 1
        const sourcePage = pages.find((page) => page.id === pageId)
        if (!sourcePage) return

        const duplicatedFields = sourcePage.fields.map((field) => ({
            ...field,
            id: generateFieldId(),
            surrogateFieldMapping: "",
        }))

        const nextPage: FormPage = {
            id: nextPageId,
            name: `${sourcePage.name} (Copy)`,
            fields: duplicatedFields,
        }

        setPages((prev) => [...prev, nextPage])
        setActivePage(nextPageId)
        setSelectedField(duplicatedFields[0]?.id ?? null)
    }

    const requestDeletePage = (pageId: number) => {
        setPageToDelete(pageId)
        setShowDeletePageDialog(true)
    }

    const confirmDeletePage = () => {
        if (pageToDelete === null) {
            setShowDeletePageDialog(false)
            return
        }

        setPages((prev) => {
            const nextPages = prev.filter((page) => page.id !== pageToDelete)
            if (nextPages.length === 0) {
                const fallbackPage: FormPage = { id: 1, name: "Page 1", fields: [] }
                setActivePage(fallbackPage.id)
                setSelectedField(null)
                return [fallbackPage]
            }
            if (pageToDelete === activePage) {
                setActivePage(nextPages[0]?.id ?? 1)
                setSelectedField(null)
            }
            return nextPages
        })

        setShowDeletePageDialog(false)
        setPageToDelete(null)
    }

    const markSaved = useCallback((fingerprint: string, savedForm?: FormRead) => {
        lastSavedFingerprintRef.current = fingerprint
        setAutoSaveStatus("saved")
        if (savedForm?.updated_at) {
            setLastSavedAt(new Date(savedForm.updated_at))
        } else {
            setLastSavedAt(new Date())
        }
    }, [])

    const persistForm = useCallback(
        async (payloadOverride?: FormCreatePayload): Promise<FormRead> => {
            const payload = payloadOverride ?? draftPayload

            let savedForm: FormRead
            if (isNewForm) {
                savedForm = await createFormMutation.mutateAsync(payload)
                router.replace(`/automation/forms/${savedForm.id}`)
            } else {
                savedForm = await updateFormMutation.mutateAsync({
                    formId: id,
                    payload,
                })
            }

            const mappings = buildMappings(pages)
            await setMappingsMutation.mutateAsync({
                formId: savedForm.id,
                mappings,
            })

            setIsPublished(savedForm.status === "published")
            return savedForm
        },
        [
            createFormMutation,
            draftPayload,
            id,
            isNewForm,
            pages,
            router,
            setMappingsMutation,
            updateFormMutation,
        ],
    )

    const handleSave = async () => {
        if (!formName.trim()) {
            toast.error("Form name is required")
            return
        }
        setIsSaving(true)
        try {
            const savedForm = await persistForm(draftPayload)
            markSaved(draftFingerprint, savedForm)
            toast.success("Form saved")
        } catch {
            setAutoSaveStatus("error")
            toast.error("Failed to save form")
        } finally {
            setIsSaving(false)
        }
    }

    const handleLogoUrlChange = (value: string) => {
        setLogoUrl(value)
        if (!useOrgLogo) {
            setCustomLogoUrl(value)
        }
    }

    const handleUseOrgLogoChange = (checked: boolean) => {
        if (checked) {
            if (!orgLogoAvailable || !orgLogoPath) {
                toast.error("Add an organization logo in Settings to use this option.")
                return
            }
            if (logoUrl && logoUrl !== orgLogoPath) {
                setCustomLogoUrl(logoUrl)
            }
            setUseOrgLogo(true)
            setLogoUrl(orgLogoPath)
            return
        }

        setUseOrgLogo(false)
        setLogoUrl(customLogoUrl)
    }

    useEffect(() => {
        if (!hasHydrated) return
        if (!formName.trim()) return
        if (debouncedFingerprint === lastSavedFingerprintRef.current) return
        if (isSaving || isPublishing) return
        if (
            createFormMutation.isPending ||
            updateFormMutation.isPending ||
            setMappingsMutation.isPending
        ) {
            return
        }

        let cancelled = false
        setAutoSaveStatus("saving")

        persistForm(debouncedPayload)
            .then((savedForm) => {
                if (cancelled) return
                markSaved(debouncedFingerprint, savedForm)
            })
            .catch(() => {
                if (cancelled) return
                setAutoSaveStatus("error")
            })

        return () => {
            cancelled = true
        }
    }, [
        hasHydrated,
        formName,
        debouncedFingerprint,
        debouncedPayload,
        isSaving,
        isPublishing,
        createFormMutation.isPending,
        updateFormMutation.isPending,
        setMappingsMutation.isPending,
        persistForm,
        markSaved,
    ])

    const handleLogoUploadClick = () => {
        logoInputRef.current?.click()
    }

    const handleLogoFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        event.target.value = ""
        if (!file) return

        try {
            const uploaded = await uploadLogoMutation.mutateAsync(file)
            setLogoUrl(uploaded.logo_url)
            setCustomLogoUrl(uploaded.logo_url)
            setUseOrgLogo(false)
            toast.success("Logo uploaded")
        } catch {
            toast.error("Failed to upload logo")
        }
    }

    const handleGenerateDraft = () => {
        const prompt = draftPrompt.trim()
        if (prompt.length < 10) {
            toast.error("Provide a short prompt (at least 10 characters)")
            return
        }
        setIsDrafting(true)
        const draft = generateFormDraft(prompt)
        setFormDraft(draft)
        setIsDrafting(false)
        toast.success("Draft generated. Review and apply when ready.")
    }

    const applyDraft = (draft: FormDraft) => {
        const hasExistingFields = pages.some((page) => page.fields.length > 0)
        if (hasExistingFields) {
            const confirmed = window.confirm("Replace current fields with this draft?")
            if (!confirmed) return
        }
        setFormName(draft.formName)
        setFormDescription(draft.description)
        setPublicTitle(draft.publicTitle)
        setPrivacyNotice(draft.privacyNotice)
        if (draft.maxFileSizeMb !== undefined) {
            setMaxFileSizeMb(draft.maxFileSizeMb)
        }
        if (draft.maxFileCount !== undefined) {
            setMaxFileCount(draft.maxFileCount)
        }
        if (draft.allowedMimeTypesText !== undefined) {
            setAllowedMimeTypesText(draft.allowedMimeTypesText)
        }
        const nextPages = draft.pages.length > 0 ? draft.pages : [{ id: 1, name: "Page 1", fields: [] }]
        setPages(nextPages)
        setActivePage(nextPages[0]?.id ?? 1)
        setSelectedField(null)
        toast.success("Draft applied to the form.")
    }

    const handleApplyDraft = () => {
        if (!formDraft) return
        applyDraft(formDraft)
    }

    const handleUseJotformTemplate = () => {
        const template = buildJotformTemplate()
        setFormDraft(template)
        applyDraft(template)
    }

    // Publish handler
    const handlePublish = () => {
        if (!formName.trim()) {
            toast.error("Form name is required")
            return
        }
        if (pages.every((p) => p.fields.length === 0)) {
            toast.error("Add at least one field before publishing")
            return
        }
        setShowPublishDialog(true)
    }

    const handlePreview = () => {
        if (pages.every((page) => page.fields.length === 0)) {
            toast.error("Add at least one field before previewing")
            return
        }

        const previewKey = formId || "draft"
        const previewPayload = {
            form_id: previewKey,
            name: formName.trim() || "Untitled Form",
            description: formDescription.trim() || null,
            form_schema: buildFormSchema(pages, {
                publicTitle,
                logoUrl,
                privacyNotice,
            }),
            max_file_size_bytes: Math.max(1, Math.round(maxFileSizeMb * 1024 * 1024)),
            max_file_count: Math.max(0, Math.round(maxFileCount)),
            allowed_mime_types: (() => {
                const parsed = allowedMimeTypesText
                    .split(",")
                    .map((entry) => entry.trim())
                    .filter(Boolean)
                return parsed.length > 0 ? parsed : null
            })(),
            generated_at: new Date().toISOString(),
        }

        try {
            window.localStorage.setItem(
                `form-preview:${previewKey}`,
                JSON.stringify(previewPayload),
            )
            window.open(`/apply/preview?formId=${encodeURIComponent(previewKey)}`, "_blank")
        } catch {
            toast.error("Failed to open preview")
        }
    }

    const confirmPublish = async () => {
        setIsPublishing(true)
        try {
            const savedForm = await persistForm(draftPayload)
            markSaved(draftFingerprint, savedForm)
            await publishFormMutation.mutateAsync(savedForm.id)
            setIsPublished(true)
            setShowPublishDialog(false)
            toast.success("Form published")
        } catch {
            setAutoSaveStatus("error")
            toast.error("Failed to publish form")
        } finally {
            setIsPublishing(false)
        }
    }

    // Get selected field data
    const selectedFieldData = selectedField ? currentPage.fields.find((f) => f.id === selectedField) : null
    const conditionFieldOptions = useMemo(() => {
        const allFields = pages.flatMap((page) =>
            page.fields.map((field) => ({
                id: field.id,
                label: field.label || field.id,
                type: field.type,
                options: field.options,
            })),
        )
        return allFields.filter(
            (field) =>
                field.id !== selectedField &&
                field.type !== "file" &&
                field.type !== "repeatable_table",
        )
    }, [pages, selectedField])

    // Get field icon by type
    const getFieldIcon = (type: string) => {
        return [...fieldTypes.basic, ...fieldTypes.advanced].find((f) => f.id === type)?.icon || TypeIcon
    }

    const isDragging = Boolean(draggedField || draggedFieldId)
    const canvasWidthClass = isMobilePreview ? "max-w-sm" : "max-w-3xl"
    const canvasFrameClass = isMobilePreview
        ? "rounded-[32px] border border-stone-200 bg-white shadow-sm p-6"
        : ""
    const canvasScaleClass = isMobilePreview ? "origin-top scale-[0.96]" : ""
    const canvasTypographyClass = isMobilePreview
        ? "text-[0.95rem] [&_input]:text-sm [&_textarea]:text-sm [&_label]:text-xs [&_p]:text-xs"
        : ""
    const autoSaveLabel = useMemo(() => {
        if (!hasHydrated) return null
        if (isSaving || autoSaveStatus === "saving") return "Saving..."
        if (autoSaveStatus === "error") return "Autosave failed"
        if (isDirty) return "Unsaved changes"
        if (autoSaveStatus === "saved") {
            if (lastSavedAt) {
                return `Saved ${lastSavedAt.toLocaleTimeString("en-US", {
                    hour: "numeric",
                    minute: "2-digit",
                })}`
            }
            return "Saved"
        }
        return "Autosave on"
    }, [autoSaveStatus, hasHydrated, isDirty, isSaving, lastSavedAt])

    if (!isNewForm && (isFormLoading || isMappingsLoading)) {
        return (
            <div className="flex h-screen items-center justify-center bg-stone-100 dark:bg-stone-950">
                <div className="flex items-center gap-2 text-stone-600 dark:text-stone-400">
                    <Loader2Icon className="size-5 animate-spin" />
                    <span>Loading form...</span>
                </div>
            </div>
        )
    }

    if (!isNewForm && !formData) {
        return (
            <NotFoundState
                title="Form not found"
                backUrl="/automation?tab=forms"
            />
        )
    }

    return (
        <div className="flex h-screen flex-col bg-stone-100 dark:bg-stone-950">
            {/* Top Bar */}
            <div className="flex h-16 items-center justify-between border-b border-stone-200 bg-white px-6 dark:border-stone-800 dark:bg-stone-900">
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="icon" onClick={() => router.push("/automation?tab=forms")}>
                        <ArrowLeftIcon className="size-5" />
                    </Button>
                    <Input
                        value={formName}
                        onChange={(e) => setFormName(e.target.value)}
                        placeholder="Form name..."
                        className="h-9 w-64 border-none bg-transparent px-0 text-lg font-semibold focus-visible:ring-0"
                    />
                    <Badge variant={isPublished ? "default" : "secondary"} className={isPublished ? "bg-teal-500" : ""}>
                        {isPublished ? "Published" : "Draft"}
                    </Badge>
                </div>

                <div className="flex items-center gap-3">
                    <Button variant="outline" size="sm" onClick={handlePreview}>
                        <EyeIcon className="mr-2 size-4" />
                        Preview
                    </Button>
                    <Button
                        variant={isMobilePreview ? "secondary" : "outline"}
                        size="sm"
                        onClick={() => setIsMobilePreview((prev) => !prev)}
                    >
                        <SmartphoneIcon className="mr-2 size-4" />
                        Mobile
                    </Button>
                    {autoSaveLabel && (
                        <span
                            className={`text-xs ${
                                autoSaveStatus === "error" ? "text-red-600" : "text-stone-500"
                            }`}
                        >
                            {autoSaveLabel}
                        </span>
                    )}
                    <Button variant="secondary" size="sm" onClick={handleSave} disabled={isSaving}>
                        {isSaving && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Save
                    </Button>
                    <Button
                        size="sm"
                        className="bg-teal-600 hover:bg-teal-700"
                        onClick={handlePublish}
                        disabled={isPublished || isPublishing}
                    >
                        {isPublishing && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Publish
                    </Button>
                </div>
            </div>

            {/* Page Tabs */}
            <div className="flex items-center gap-2 border-b border-stone-200 bg-white px-6 py-2 dark:border-stone-800 dark:bg-stone-900">
                {pages.map((page) => (
                    <button
                        key={page.id}
                        onClick={() => setActivePage(page.id)}
                        className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${activePage === page.id
                                ? "bg-teal-500/10 text-teal-600 dark:bg-teal-500/20 dark:text-teal-400"
                                : "text-stone-600 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800"
                            }`}
                    >
                        {page.name}
                    </button>
                ))}
                <Button variant="ghost" size="sm" onClick={handleAddPage}>
                    <PlusIcon className="mr-1 size-4" />
                    Add Page
                </Button>
                <Button variant="ghost" size="sm" onClick={() => handleDuplicatePage(activePage)}>
                    <CopyIcon className="mr-1 size-4" />
                    Duplicate Page
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-600 hover:text-red-700"
                    onClick={() => requestDeletePage(activePage)}
                    disabled={pages.length === 1}
                >
                    <Trash2Icon className="mr-1 size-4" />
                    Delete Page
                </Button>
            </div>

            <div className="flex flex-1 overflow-hidden">
                {/* Left Sidebar - Field Buttons */}
                <div className="w-[200px] overflow-y-auto border-r border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
                    <div className="space-y-6">
                        {/* Basic Fields */}
                        <div>
                            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
                                Basic
                            </h3>
                            <div className="space-y-2">
                                {fieldTypes.basic.map((field) => {
                                    const IconComponent = field.icon
                                    return (
                                        <button
                                            key={field.id}
                                            draggable
                                            onDragStart={() => handleDragStart(field.id, field.label)}
                                            onDragEnd={handleDragEnd}
                                            className="flex w-full cursor-grab items-center gap-3 rounded-lg border border-stone-200 bg-white p-3 text-left text-sm font-medium transition-all hover:border-teal-500 hover:bg-teal-50 active:cursor-grabbing dark:border-stone-700 dark:bg-stone-800 dark:hover:border-teal-500 dark:hover:bg-teal-950"
                                        >
                                            <IconComponent className="size-5 text-stone-600 dark:text-stone-400" />
                                            <span className="flex-1">{field.label}</span>
                                            <GripVerticalIcon className="size-4 text-stone-400" />
                                        </button>
                                    )
                                })}
                            </div>
                        </div>

                        {/* Advanced Fields */}
                        <div>
                            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
                                Advanced
                            </h3>
                            <div className="space-y-2">
                                {fieldTypes.advanced.map((field) => {
                                    const IconComponent = field.icon
                                    return (
                                        <button
                                            key={field.id}
                                            draggable
                                            onDragStart={() => handleDragStart(field.id, field.label)}
                                            onDragEnd={handleDragEnd}
                                            className="flex w-full cursor-grab items-center gap-3 rounded-lg border border-stone-200 bg-white p-3 text-left text-sm font-medium transition-all hover:border-teal-500 hover:bg-teal-50 active:cursor-grabbing dark:border-stone-700 dark:bg-stone-800 dark:hover:border-teal-500 dark:hover:bg-teal-950"
                                        >
                                            <IconComponent className="size-5 text-stone-600 dark:text-stone-400" />
                                            <span className="flex-1">{field.label}</span>
                                            <GripVerticalIcon className="size-4 text-stone-400" />
                                        </button>
                                    )
                                })}
                            </div>
                        </div>

                        {/* Add Page Button */}
                        <Button variant="outline" size="sm" className="w-full bg-transparent" onClick={handleAddPage}>
                            <PlusIcon className="mr-2 size-4" />
                            Add Page
                        </Button>
                    </div>
                </div>

                {/* Center Canvas */}
                <div className="flex-1 overflow-y-auto p-8">
                    <div
                        onDragOver={handleCanvasDragOver}
                        onDrop={handleDrop}
                        className={`mx-auto min-h-[500px] ${canvasWidthClass} space-y-4 ${
                            currentPage.fields.length === 0 ? "flex items-center justify-center" : ""
                        } ${canvasFrameClass} ${canvasScaleClass} ${canvasTypographyClass}`}
                    >
                        {currentPage.fields.length === 0 ? (
                            <div
                                onDragOver={handleDragOver}
                                onDrop={handleDrop}
                                className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-stone-300 p-12 text-center dark:border-stone-700"
                            >
                                <div className="mb-4 flex size-20 items-center justify-center rounded-full bg-teal-100 dark:bg-teal-950">
                                    <TypeIcon className="size-10 text-teal-600 dark:text-teal-400" />
                                </div>
                                <h3 className="mb-2 text-lg font-semibold">Drag fields here to build your form</h3>
                                <p className="text-sm text-stone-500 dark:text-stone-400">
                                    Start by dragging fields from the left sidebar
                                </p>
                            </div>
                        ) : (
                            <>
                                {currentPage.fields.map((field) => {
                                    const IconComponent = getFieldIcon(field.type)
                                    return (
                                        <div key={field.id} className="space-y-2">
                                            {isDragging && dropIndicatorId === field.id && (
                                                <div className="h-0.5 rounded-full bg-teal-500" />
                                            )}
                                            <Card
                                                draggable
                                                onDragStart={() => handleFieldDragStart(field.id)}
                                                onDragOver={(e) => handleFieldDragOver(e, field.id)}
                                                onDrop={(e) => handleDropOnField(e, field.id)}
                                                onDragEnd={handleDragEnd}
                                                className={`cursor-pointer transition-all hover:shadow-md ${selectedField === field.id ? "ring-2 ring-teal-500" : ""
                                                    }`}
                                                onClick={() => setSelectedField(field.id)}
                                            >
                                                <CardContent className="flex items-start gap-4 p-6">
                                                    <GripVerticalIcon className="mt-1 size-5 cursor-grab text-stone-400" />
                                                    <IconComponent className="mt-1 size-5 text-teal-600 dark:text-teal-400" />
                                                    <div className="flex-1">
                                                        <div className="flex items-start justify-between">
                                                            <div className="flex-1">
                                                                <Input
                                                                    draggable={false}
                                                                    value={field.label}
                                                                    onChange={(e) => handleUpdateField(field.id, { label: e.target.value })}
                                                                    className="mb-1 h-auto border-none bg-transparent p-0 text-base font-medium focus-visible:ring-0"
                                                                    onClick={(e) => e.stopPropagation()}
                                                                />
                                                                {field.helperText && (
                                                                    <p className="text-sm text-stone-500 dark:text-stone-400">{field.helperText}</p>
                                                                )}
                                                            </div>
                                                            {field.required && <span className="ml-2 text-red-500">*</span>}
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            className="shrink-0"
                                                            onClick={(e) => {
                                                                e.stopPropagation()
                                                                handleDuplicateField(field.id)
                                                            }}
                                                        >
                                                            <CopyIcon className="size-4" />
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            className="shrink-0"
                                                            onClick={(e) => {
                                                                e.stopPropagation()
                                                                handleDeleteField(field.id)
                                                            }}
                                                        >
                                                            <XIcon className="size-4" />
                                                        </Button>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        </div>
                                    )
                                })}
                                {isDragging && dropIndicatorId === "end" && (
                                    <div className="h-0.5 rounded-full bg-teal-500" />
                                )}
                            </>
                        )}
                    </div>
                </div>

                {/* Right Sidebar - Settings */}
                <div className="w-[280px] overflow-y-auto border-l border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
                    {selectedFieldData ? (
                        <div className="space-y-6">
                            <div>
                                <h3 className="mb-4 text-sm font-semibold">Field Settings</h3>

                                {/* Label */}
                                <div className="space-y-2">
                                    <Label htmlFor="field-label">Label</Label>
                                    <Input
                                        id="field-label"
                                        value={selectedFieldData.label}
                                        onChange={(e) => handleUpdateField(selectedFieldData.id, { label: e.target.value })}
                                    />
                                </div>

                                {/* Helper Text */}
                                <div className="mt-4 space-y-2">
                                    <Label htmlFor="field-helper">Helper Text</Label>
                                    <Input
                                        id="field-helper"
                                        value={selectedFieldData.helperText}
                                        onChange={(e) => handleUpdateField(selectedFieldData.id, { helperText: e.target.value })}
                                        placeholder="Optional hint for users"
                                    />
                                </div>

                                {/* Required Toggle */}
                                <div className="mt-4 flex items-center justify-between">
                                    <Label htmlFor="field-required">Required</Label>
                                    <Switch
                                        id="field-required"
                                        checked={selectedFieldData.required}
                                        onCheckedChange={(checked) => handleUpdateField(selectedFieldData.id, { required: checked })}
                                    />
                                </div>

                                {/* Conditional Logic */}
                                <div className="mt-4 space-y-2">
                                    <div className="flex items-center justify-between">
                                        <Label>Conditional Logic</Label>
                                        {selectedFieldData.showIf && (
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => handleUpdateField(selectedFieldData.id, { showIf: null })}
                                            >
                                                Clear
                                            </Button>
                                        )}
                                    </div>
                                    {conditionFieldOptions.length === 0 ? (
                                        <p className="text-xs text-stone-500">
                                            Add another field to enable conditional logic.
                                        </p>
                                    ) : (
                                        <>
                                            <Select
                                                value={selectedFieldData.showIf?.fieldKey || "none"}
                                                onValueChange={(value) => {
                                                    const safeValue = value ?? "none"
                                                    handleShowIfChange(selectedFieldData.id, {
                                                        fieldKey: safeValue === "none" ? "" : safeValue,
                                                    })
                                                }}
                                            >
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Select field" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="none">No condition</SelectItem>
                                                    {conditionFieldOptions.map((option) => (
                                                        <SelectItem key={option.id} value={option.id}>
                                                            {option.label}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                            {selectedFieldData.showIf && (
                                                <>
                                                    <Select
                                                        value={selectedFieldData.showIf.operator}
                                                        onValueChange={(value) =>
                                                            handleShowIfChange(selectedFieldData.id, {
                                                                operator: value as ShowIfOperator,
                                                            })
                                                        }
                                                    >
                                                        <SelectTrigger>
                                                            <SelectValue placeholder="Condition" />
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {(() => {
                                                                const controlling = conditionFieldOptions.find(
                                                                    (field) =>
                                                                        field.id === selectedFieldData.showIf?.fieldKey,
                                                                )
                                                                const isMulti =
                                                                    controlling?.type === "checkbox" ||
                                                                    controlling?.type === "multiselect"
                                                                const ops = isMulti
                                                                    ? [
                                                                        { value: "contains", label: "contains" },
                                                                        { value: "not_contains", label: "not contains" },
                                                                        { value: "is_empty", label: "is empty" },
                                                                        { value: "is_not_empty", label: "is not empty" },
                                                                    ]
                                                                    : [
                                                                        { value: "equals", label: "equals" },
                                                                        { value: "not_equals", label: "not equals" },
                                                                        { value: "is_empty", label: "is empty" },
                                                                        { value: "is_not_empty", label: "is not empty" },
                                                                    ]
                                                                return ops.map((op) => (
                                                                    <SelectItem key={op.value} value={op.value}>
                                                                        {op.label}
                                                                    </SelectItem>
                                                                ))
                                                            })()}
                                                        </SelectContent>
                                                    </Select>
                                                    {!["is_empty", "is_not_empty"].includes(
                                                        selectedFieldData.showIf.operator,
                                                    ) && (
                                                        <>
                                                            {(() => {
                                                                const controlling = conditionFieldOptions.find(
                                                                    (field) =>
                                                                        field.id === selectedFieldData.showIf?.fieldKey,
                                                                )
                                                                const optionList = controlling?.options || []
                                                                if (
                                                                    optionList.length > 0 &&
                                                                    (controlling?.type === "select" ||
                                                                        controlling?.type === "radio" ||
                                                                        controlling?.type === "checkbox" ||
                                                                        controlling?.type === "multiselect")
                                                                ) {
                                                                    return (
                                                                        <Select
                                                                            value={selectedFieldData.showIf?.value || ""}
                                                                            onValueChange={(value) =>
                                                                                handleShowIfChange(selectedFieldData.id, {
                                                                                    value: value ?? "",
                                                                                })
                                                                            }
                                                                        >
                                                                            <SelectTrigger>
                                                                                <SelectValue placeholder="Value" />
                                                                            </SelectTrigger>
                                                                            <SelectContent>
                                                                                {optionList.map((option) => (
                                                                                    <SelectItem
                                                                                        key={option}
                                                                                        value={option}
                                                                                    >
                                                                                        {option}
                                                                                    </SelectItem>
                                                                                ))}
                                                                            </SelectContent>
                                                                        </Select>
                                                                    )
                                                                }
                                                                return (
                                                                    <Input
                                                                        value={selectedFieldData.showIf?.value || ""}
                                                                        onChange={(e) =>
                                                                            handleShowIfChange(selectedFieldData.id, {
                                                                                value: e.target.value,
                                                                            })
                                                                        }
                                                                        placeholder="Value to match"
                                                                    />
                                                                )
                                                            })()}
                                                        </>
                                                    )}
                                                </>
                                            )}
                                        </>
                                    )}
                                </div>

                                {/* Validation Rules */}
                                {["text", "textarea", "email", "phone", "address"].includes(
                                    selectedFieldData.type,
                                ) && (
                                    <div className="mt-4 space-y-2">
                                        <Label>Validation</Label>
                                        <div className="grid grid-cols-2 gap-2">
                                            <Input
                                                inputMode="numeric"
                                                placeholder="Min length"
                                                value={selectedFieldData.validation?.min_length ?? ""}
                                                onChange={(e) =>
                                                    handleValidationChange(selectedFieldData.id, {
                                                        min_length: parseOptionalNumber(e.target.value),
                                                    })
                                                }
                                            />
                                            <Input
                                                inputMode="numeric"
                                                placeholder="Max length"
                                                value={selectedFieldData.validation?.max_length ?? ""}
                                                onChange={(e) =>
                                                    handleValidationChange(selectedFieldData.id, {
                                                        max_length: parseOptionalNumber(e.target.value),
                                                    })
                                                }
                                            />
                                        </div>
                                        <Input
                                            placeholder="Regex pattern (optional)"
                                            value={selectedFieldData.validation?.pattern ?? ""}
                                            onChange={(e) =>
                                                handleValidationChange(selectedFieldData.id, {
                                                    pattern: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                )}

                                {selectedFieldData.type === "number" && (
                                    <div className="mt-4 space-y-2">
                                        <Label>Validation</Label>
                                        <div className="grid grid-cols-2 gap-2">
                                            <Input
                                                inputMode="numeric"
                                                placeholder="Min value"
                                                value={selectedFieldData.validation?.min_value ?? ""}
                                                onChange={(e) =>
                                                    handleValidationChange(selectedFieldData.id, {
                                                        min_value: parseOptionalNumber(e.target.value),
                                                    })
                                                }
                                            />
                                            <Input
                                                inputMode="numeric"
                                                placeholder="Max value"
                                                value={selectedFieldData.validation?.max_value ?? ""}
                                                onChange={(e) =>
                                                    handleValidationChange(selectedFieldData.id, {
                                                        max_value: parseOptionalNumber(e.target.value),
                                                    })
                                                }
                                            />
                                        </div>
                                    </div>
                                )}

                                {selectedFieldData.type === "repeatable_table" && (
                                    <div className="mt-4 space-y-3">
                                        <Label>Table Columns</Label>
                                        <div className="grid grid-cols-2 gap-2">
                                            <Input
                                                inputMode="numeric"
                                                placeholder="Min rows"
                                                value={selectedFieldData.minRows ?? ""}
                                                onChange={(e) =>
                                                    handleUpdateField(selectedFieldData.id, {
                                                        minRows: parseOptionalInt(e.target.value),
                                                    })
                                                }
                                            />
                                            <Input
                                                inputMode="numeric"
                                                placeholder="Max rows"
                                                value={selectedFieldData.maxRows ?? ""}
                                                onChange={(e) =>
                                                    handleUpdateField(selectedFieldData.id, {
                                                        maxRows: parseOptionalInt(e.target.value),
                                                    })
                                                }
                                            />
                                        </div>
                                        <div className="space-y-3">
                                            {(selectedFieldData.columns || []).map((column) => (
                                                <div
                                                    key={column.id}
                                                    className="rounded-lg border border-stone-200 p-3"
                                                >
                                                    <div className="flex items-center gap-2">
                                                        <Input
                                                            value={column.label}
                                                            onChange={(e) =>
                                                                handleUpdateColumn(selectedFieldData.id, column.id, {
                                                                    label: e.target.value,
                                                                })
                                                            }
                                                            placeholder="Column label"
                                                        />
                                                        <Select
                                                            value={column.type}
                                                            onValueChange={(value) => {
                                                                const nextType = (value ?? "text") as
                                                                    | "text"
                                                                    | "number"
                                                                    | "date"
                                                                    | "select"
                                                                handleUpdateColumn(selectedFieldData.id, column.id, {
                                                                    type: nextType,
                                                                    options:
                                                                        nextType === "select"
                                                                            ? column.options || ["Option 1", "Option 2"]
                                                                            : [],
                                                                })
                                                            }}
                                                        >
                                                            <SelectTrigger className="w-[120px]">
                                                                <SelectValue />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                <SelectItem value="text">Text</SelectItem>
                                                                <SelectItem value="number">Number</SelectItem>
                                                                <SelectItem value="date">Date</SelectItem>
                                                                <SelectItem value="select">Select</SelectItem>
                                                            </SelectContent>
                                                        </Select>
                                                        <Switch
                                                            checked={column.required}
                                                            onCheckedChange={(checked) =>
                                                                handleUpdateColumn(selectedFieldData.id, column.id, {
                                                                    required: checked,
                                                                })
                                                            }
                                                        />
                                                        <Button
                                                            type="button"
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() =>
                                                                handleRemoveColumn(selectedFieldData.id, column.id)
                                                            }
                                                        >
                                                            <XIcon className="size-4" />
                                                        </Button>
                                                    </div>
                                                    {column.type === "select" && (
                                                        <Input
                                                            className="mt-2"
                                                            value={(column.options || []).join(", ")}
                                                            onChange={(e) =>
                                                                handleUpdateColumn(selectedFieldData.id, column.id, {
                                                                    options: e.target.value
                                                                        .split(",")
                                                                        .map((entry) => entry.trim())
                                                                        .filter(Boolean),
                                                                })
                                                            }
                                                            placeholder="Options (comma separated)"
                                                        />
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            className="w-full bg-transparent"
                                            onClick={() => handleAddColumn(selectedFieldData.id)}
                                        >
                                            <PlusIcon className="mr-2 size-4" />
                                            Add Column
                                        </Button>
                                    </div>
                                )}

                                {/* Options for Select/Radio/Multi-select */}
                                {selectedFieldData.options && (
                                    <div className="mt-4 space-y-2">
                                        <Label>Options</Label>
                                        {selectedFieldData.options.map((option, index) => (
                                            <div key={index} className="flex gap-2">
                                                <Input
                                                    value={option}
                                                    onChange={(e) => {
                                                        const newOptions = [...selectedFieldData.options!]
                                                        newOptions[index] = e.target.value
                                                        handleUpdateField(selectedFieldData.id, { options: newOptions })
                                                    }}
                                                />
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => {
                                                        const newOptions = selectedFieldData.options!.filter((_, i) => i !== index)
                                                        handleUpdateField(selectedFieldData.id, { options: newOptions })
                                                    }}
                                                >
                                                    <XIcon className="size-4" />
                                                </Button>
                                            </div>
                                        ))}
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full bg-transparent"
                                            onClick={() => {
                                                const newOptions = [
                                                    ...selectedFieldData.options!,
                                                    `Option ${selectedFieldData.options!.length + 1}`,
                                                ]
                                                handleUpdateField(selectedFieldData.id, { options: newOptions })
                                            }}
                                        >
                                            <PlusIcon className="mr-2 size-4" />
                                            Add Option
                                        </Button>
                                    </div>
                                )}
                            </div>

                            {/* Field Mapping */}
                            <div className="border-t border-stone-200 pt-6 dark:border-stone-800">
                                <h3 className="mb-3 text-sm font-semibold">Field Mapping</h3>
                                <p className="mb-3 text-xs text-stone-500 dark:text-stone-400">
                                    Map this field to a Surrogate field to auto-populate data
                                </p>
                                <Select
                                    value={selectedFieldData.surrogateFieldMapping || "none"}
                                    onValueChange={(value) =>
                                        handleMappingChange(selectedFieldData.id, value)
                                    }
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select field" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="none">None</SelectItem>
                                        {surrogateFieldMappings.map((mapping) => (
                                            <SelectItem key={mapping.value} value={mapping.value}>
                                                {mapping.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-6">
                            <div className="rounded-lg border border-stone-200 bg-stone-50 p-4 dark:border-stone-800 dark:bg-stone-900">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-sm font-semibold">Template Library</h3>
                                    <Badge variant="outline">Starter</Badge>
                                </div>
                                <p className="mt-2 text-xs text-stone-500 dark:text-stone-400">
                                    Start from a proven intake template modeled after the Jotform surrogate application.
                                </p>
                                <div className="mt-3 rounded-md border border-stone-200 bg-white p-3 text-sm dark:border-stone-800 dark:bg-stone-950">
                                    <div className="flex items-center justify-between">
                                        <p className="font-semibold">Jotform Surrogate Intake</p>
                                        <Badge variant="secondary" className="text-[11px]">
                                            {jotformTemplateSummary.sections} sections
                                        </Badge>
                                    </div>
                                    <p className="mt-1 text-xs text-stone-500">
                                        {jotformTemplateSummary.questions} questions • Includes uploads and signature
                                    </p>
                                    <Button
                                        size="sm"
                                        className="mt-3 w-full"
                                        onClick={handleUseJotformTemplate}
                                    >
                                        Use Jotform Surrogate Intake Template
                                    </Button>
                                    <p className="mt-2 text-[11px] text-stone-500">
                                        Applying a template will replace current fields.
                                    </p>
                                </div>
                            </div>

                            <div className="rounded-lg border border-stone-200 bg-stone-50 p-4 dark:border-stone-800 dark:bg-stone-900">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-sm font-semibold">Generate from Prompt</h3>
                                    <Badge variant="outline">Draft</Badge>
                                </div>
                                <p className="mt-2 text-xs text-stone-500 dark:text-stone-400">
                                    Describe the form you want and apply the draft to create sections, fields, and compliance text.
                                </p>
                                <div className="mt-3 space-y-2">
                                    <Textarea
                                        value={draftPrompt}
                                        onChange={(e) => setDraftPrompt(e.target.value)}
                                        placeholder="Example: Surrogacy intake form with eligibility questions, medical background, and document upload."
                                        rows={4}
                                    />
                                    <div className="flex items-center gap-2">
                                        <Button
                                            size="sm"
                                            onClick={handleGenerateDraft}
                                            disabled={isDrafting}
                                        >
                                            {isDrafting && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                                            Generate Draft
                                        </Button>
                                        {formDraft && (
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={handleApplyDraft}
                                            >
                                                Apply Draft
                                            </Button>
                                        )}
                                    </div>
                                </div>

                                {formDraft && (
                                    <div className="mt-4 space-y-4 text-xs text-stone-600 dark:text-stone-400">
                                        <div>
                                            <p className="text-[11px] font-semibold uppercase text-stone-500 dark:text-stone-400">
                                                Sections
                                            </p>
                                            <p>Required: {formDraft.requiredSections.join(", ")}</p>
                                            {formDraft.optionalSections.length > 0 && (
                                                <p>Optional: {formDraft.optionalSections.join(", ")}</p>
                                            )}
                                        </div>

                                        <div>
                                            <p className="text-[11px] font-semibold uppercase text-stone-500 dark:text-stone-400">
                                                Field Types
                                            </p>
                                            <div className="mt-2 flex flex-wrap gap-2">
                                                {formDraft.suggestedFieldTypes.map((type) => (
                                                    <Badge key={type} variant="secondary" className="text-[11px]">
                                                        {type}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>

                                        <div>
                                            <p className="text-[11px] font-semibold uppercase text-stone-500 dark:text-stone-400">
                                                Conditional Logic
                                            </p>
                                            <div className="mt-2 space-y-1">
                                                {formDraft.conditionalLogic.length > 0 ? (
                                                    formDraft.conditionalLogic.map((item) => (
                                                        <p key={item}>• {item}</p>
                                                    ))
                                                ) : (
                                                    <p>No conditional logic suggestions yet.</p>
                                                )}
                                            </div>
                                        </div>

                                        <div>
                                            <p className="text-[11px] font-semibold uppercase text-stone-500 dark:text-stone-400">
                                                Reading-Level Hints
                                            </p>
                                            <div className="mt-2 space-y-1">
                                                {formDraft.readingLevelHints.map((hint) => (
                                                    <p key={hint}>• {hint}</p>
                                                ))}
                                            </div>
                                        </div>

                                        <div>
                                            <p className="text-[11px] font-semibold uppercase text-stone-500 dark:text-stone-400">
                                                Compliance Text
                                            </p>
                                            <Textarea value={formDraft.privacyNotice} readOnly rows={3} />
                                        </div>

                                        <div>
                                            <p className="text-[11px] font-semibold uppercase text-stone-500 dark:text-stone-400">
                                                Auto-Translation Draft
                                            </p>
                                            <Textarea value={formDraft.translationDraft} readOnly rows={4} />
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div>
                                <h3 className="mb-4 text-sm font-semibold">Form Settings</h3>

                                {/* Form Name */}
                                <div className="space-y-2">
                                    <Label htmlFor="form-name">Form Name</Label>
                                    <Input id="form-name" value={formName} onChange={(e) => setFormName(e.target.value)} />
                                </div>

                                {/* Form Description */}
                                <div className="mt-4 space-y-2">
                                    <Label htmlFor="form-description">Description</Label>
                                    <Textarea
                                        id="form-description"
                                        value={formDescription}
                                        onChange={(e) => setFormDescription(e.target.value)}
                                        rows={3}
                                        placeholder="Describe the purpose of this form"
                                    />
                                </div>

                                {/* Public Title */}
                                <div className="mt-4 space-y-2">
                                    <Label htmlFor="public-title">Public Title</Label>
                                    <Input
                                        id="public-title"
                                        value={publicTitle}
                                        onChange={(e) => setPublicTitle(e.target.value)}
                                        placeholder="Business or program title shown to applicants"
                                    />
                                </div>

                                {/* Logo URL */}
                                <div className="mt-4 space-y-2">
                                    <div className="flex items-center justify-between">
                                        <Label htmlFor="logo-url">Logo URL</Label>
                                        <div className="flex items-center gap-2 text-xs text-stone-500">
                                            <Switch
                                                checked={useOrgLogo}
                                                onCheckedChange={handleUseOrgLogoChange}
                                                disabled={!orgLogoAvailable}
                                            />
                                            <span>Use org logo</span>
                                        </div>
                                    </div>
                                    <Input
                                        id="logo-url"
                                        value={logoUrl}
                                        onChange={(e) => handleLogoUrlChange(e.target.value)}
                                        placeholder="https://example.com/logo.png"
                                        disabled={useOrgLogo}
                                    />
                                    {!orgLogoAvailable && (
                                        <p className="text-xs text-stone-500">
                                            Add an organization logo in Settings to enable this option.
                                        </p>
                                    )}
                                    <div className="flex items-center gap-2">
                                        <input
                                            ref={logoInputRef}
                                            type="file"
                                            accept="image/png,image/jpeg"
                                            className="hidden"
                                            onChange={handleLogoFileChange}
                                        />
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            onClick={handleLogoUploadClick}
                                            disabled={uploadLogoMutation.isPending || useOrgLogo}
                                        >
                                            {uploadLogoMutation.isPending && (
                                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                                            )}
                                            Upload Logo
                                        </Button>
                                        {logoUrl && !useOrgLogo && (
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => handleLogoUrlChange("")}
                                                >
                                                Remove
                                            </Button>
                                        )}
                                    </div>
                                    {logoUrl && (
                                        <div className="rounded-lg border border-stone-200 bg-stone-50 p-3">
                                            <img
                                                src={resolvedLogoUrl}
                                                alt="Form logo preview"
                                                className="h-14 w-auto rounded-md object-contain"
                                            />
                                        </div>
                                    )}
                                </div>

                                {/* Privacy Notice */}
                                <div className="mt-4 space-y-2">
                                    <Label htmlFor="privacy-notice">Privacy Notice</Label>
                                    <Textarea
                                        id="privacy-notice"
                                        value={privacyNotice}
                                        onChange={(e) => setPrivacyNotice(e.target.value)}
                                        rows={4}
                                        placeholder="Describe how applicant data is protected or paste a privacy policy URL"
                                    />
                                </div>

                                <div className="mt-6 space-y-3">
                                    <div className="flex items-center justify-between">
                                        <h4 className="text-sm font-semibold">Upload Rules</h4>
                                        <Badge variant="outline">Files</Badge>
                                    </div>
                                    <div className="grid grid-cols-2 gap-2">
                                        <div className="space-y-2">
                                            <Label htmlFor="max-file-size">Max file size (MB)</Label>
                                            <Input
                                                id="max-file-size"
                                                inputMode="numeric"
                                                value={maxFileSizeMb}
                                                onChange={(e) =>
                                                    setMaxFileSizeMb(
                                                        Number.parseFloat(e.target.value || "0") || 1,
                                                    )
                                                }
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="max-file-count">Max files total</Label>
                                            <Input
                                                id="max-file-count"
                                                inputMode="numeric"
                                                value={maxFileCount}
                                                onChange={(e) =>
                                                    setMaxFileCount(
                                                        Number.parseInt(e.target.value || "0", 10) || 0,
                                                    )
                                                }
                                            />
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="allowed-mime-types">
                                            Allowed MIME types (comma separated)
                                        </Label>
                                        <Input
                                            id="allowed-mime-types"
                                            value={allowedMimeTypesText}
                                            onChange={(e) => setAllowedMimeTypesText(e.target.value)}
                                            placeholder="image/*,application/pdf"
                                        />
                                        <p className="text-xs text-stone-500">
                                            Leave blank to allow any file types. Per-field uploads are still capped at 5 files.
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <div className="rounded-lg border border-stone-200 bg-stone-50 p-4 dark:border-stone-800 dark:bg-stone-900">
                                <p className="text-xs text-stone-600 dark:text-stone-400">
                                    Select a field from the canvas to edit its settings
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Publish Confirmation Dialog */}
            <AlertDialog open={showPublishDialog} onOpenChange={setShowPublishDialog}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Publish Form</AlertDialogTitle>
                        <AlertDialogDescription>
                            Publishing will make this form available for submissions. You can still edit the draft version, but the
                            published version will be locked until you re-publish.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={isPublishing}>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={confirmPublish}
                            className="bg-teal-600 hover:bg-teal-700"
                            disabled={isPublishing}
                        >
                            {isPublishing && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                            Publish
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog
                open={showDeletePageDialog}
                onOpenChange={(open) => {
                    setShowDeletePageDialog(open)
                    if (!open) {
                        setPageToDelete(null)
                    }
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete Page</AlertDialogTitle>
                        <AlertDialogDescription>
                            This removes the page and all fields on it. This action cannot be undone.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={confirmDeletePage}
                            className="bg-red-600 hover:bg-red-700"
                        >
                            Delete Page
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}
