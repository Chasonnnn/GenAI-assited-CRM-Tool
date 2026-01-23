"use client"

import { useEffect, useRef, useState } from "react"
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
import { NotFoundState } from "@/components/not-found-state"
import type { FieldType, FormSchema, FormFieldOption, FormRead } from "@/lib/api/forms"

// Field type definitions
type FieldTypeOption = {
    id: FieldType
    label: string
    icon: typeof TypeIcon
}

const fieldTypes: { basic: FieldTypeOption[]; advanced: FieldTypeOption[] } = {
    basic: [
        { id: "text", label: "Name", icon: TypeIcon },
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
}

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
            help_text: field.helperText || null,
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
            return {
                id: field.key,
                type: field.type,
                label: field.label,
                helperText: field.help_text || "",
                required: field.required ?? false,
                surrogateFieldMapping: mappings.get(field.key) || "",
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
}

const buildFieldId = () => {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return crypto.randomUUID()
    }
    return `field-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const buildDraftField = ({
    label,
    type,
    required = false,
    helperText = "",
    surrogateFieldMapping = "",
    options,
}: {
    label: string
    type: FieldType
    required?: boolean
    helperText?: string
    surrogateFieldMapping?: string
    options?: string[]
}): FormField => ({
    id: buildFieldId(),
    type,
    label,
    helperText,
    required,
    surrogateFieldMapping,
    ...(options ? { options } : {}),
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
    }
}

// Page component
export default function FormBuilderPage() {
    const params = useParams<{ id: string }>()
    const idParam = params?.id
    const id = Array.isArray(idParam) ? idParam[0] : idParam ?? "new"
    const router = useRouter()
    const isNewForm = id === "new"
    const formId = isNewForm ? null : id

    const { data: formData, isLoading: isFormLoading } = useForm(formId)
    const { data: mappingData, isLoading: isMappingsLoading } = useFormMappings(formId)
    const createFormMutation = useCreateForm()
    const updateFormMutation = useUpdateForm()
    const publishFormMutation = usePublishForm()
    const setMappingsMutation = useSetFormMappings()
    const uploadLogoMutation = useUploadFormLogo()

    const logoInputRef = useRef<HTMLInputElement>(null)

    const [hasHydrated, setHasHydrated] = useState(false)

    // Form state
    const [formName, setFormName] = useState(isNewForm ? "" : "Surrogate Application Form")
    const [formDescription, setFormDescription] = useState("")
    const [publicTitle, setPublicTitle] = useState("")
    const [logoUrl, setLogoUrl] = useState("")
    const [privacyNotice, setPrivacyNotice] = useState("")
    const [isPublished, setIsPublished] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [isPublishing, setIsPublishing] = useState(false)
    const [draftPrompt, setDraftPrompt] = useState("")
    const [formDraft, setFormDraft] = useState<FormDraft | null>(null)
    const [isDrafting, setIsDrafting] = useState(false)

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

    useEffect(() => {
        setHasHydrated(false)
        setFormDraft(null)
        setDraftPrompt("")
    }, [formId])

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
        setIsPublished(formData.status === "published")
        setPages(schema ? schemaToPages(schema, mappingMap) : [{ id: 1, name: "Page 1", fields: [] }])
        setActivePage(1)
        setSelectedField(null)
        setHasHydrated(true)
    }, [formData, mappingData, isMappingsLoading, hasHydrated, isNewForm])

    const fallbackPage: FormPage = { id: 1, name: "Page 1", fields: [] }
    const currentPage = pages.find((p) => p.id === activePage) ?? pages[0] ?? fallbackPage

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

    const buildNewField = (): FormField | null => {
        if (!draggedField) return null

        const fieldId =
            typeof crypto !== "undefined" && "randomUUID" in crypto
                ? crypto.randomUUID()
                : `field-${Date.now()}`

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

    // Page handlers
    const handleAddPage = () => {
        const newPage: FormPage = {
            id: pages.length + 1,
            name: `Page ${pages.length + 1}`,
            fields: [],
        }
        setPages([...pages, newPage])
        setActivePage(newPage.id)
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

    const persistForm = async (): Promise<FormRead> => {
        const payload = {
            name: formName.trim(),
            description: formDescription.trim() || null,
            form_schema: buildFormSchema(pages, {
                publicTitle,
                logoUrl,
                privacyNotice,
            }),
        }

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
    }

    const handleSave = async () => {
        if (!formName.trim()) {
            toast.error("Form name is required")
            return
        }
        setIsSaving(true)
        try {
            await persistForm()
            toast.success("Form saved")
        } catch {
            toast.error("Failed to save form")
        } finally {
            setIsSaving(false)
        }
    }

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

    const handleApplyDraft = () => {
        if (!formDraft) return
        const hasExistingFields = pages.some((page) => page.fields.length > 0)
        if (hasExistingFields) {
            const confirmed = window.confirm("Replace current fields with this draft?")
            if (!confirmed) return
        }
        setFormName(formDraft.formName)
        setFormDescription(formDraft.description)
        setPublicTitle(formDraft.publicTitle)
        setPrivacyNotice(formDraft.privacyNotice)
        const nextPages = formDraft.pages.length > 0 ? formDraft.pages : [{ id: 1, name: "Page 1", fields: [] }]
        setPages(nextPages)
        setActivePage(nextPages[0]?.id ?? 1)
        setSelectedField(null)
        toast.success("Draft applied to the form.")
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
            max_file_size_bytes: formData?.max_file_size_bytes ?? 10 * 1024 * 1024,
            max_file_count: formData?.max_file_count ?? 10,
            allowed_mime_types: formData?.allowed_mime_types ?? null,
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
            const savedForm = await persistForm()
            await publishFormMutation.mutateAsync(savedForm.id)
            setIsPublished(true)
            setShowPublishDialog(false)
            toast.success("Form published")
        } catch {
            toast.error("Failed to publish form")
        } finally {
            setIsPublishing(false)
        }
    }

    // Get selected field data
    const selectedFieldData = selectedField ? currentPage.fields.find((f) => f.id === selectedField) : null

    // Get field icon by type
    const getFieldIcon = (type: string) => {
        return [...fieldTypes.basic, ...fieldTypes.advanced].find((f) => f.id === type)?.icon || TypeIcon
    }

    const isDragging = Boolean(draggedField || draggedFieldId)

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
                        className={`mx-auto min-h-[500px] max-w-3xl space-y-4 ${currentPage.fields.length === 0 ? "flex items-center justify-center" : ""
                            }`}
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
                                        handleUpdateField(selectedFieldData.id, {
                                            surrogateFieldMapping: value && value !== "none" ? value : "",
                                        })
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
                                    <Label htmlFor="logo-url">Logo URL</Label>
                                    <Input
                                        id="logo-url"
                                        value={logoUrl}
                                        onChange={(e) => setLogoUrl(e.target.value)}
                                        placeholder="https://example.com/logo.png"
                                    />
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
                                            disabled={uploadLogoMutation.isPending}
                                        >
                                            {uploadLogoMutation.isPending && (
                                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                                            )}
                                            Upload Logo
                                        </Button>
                                        {logoUrl && (
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => setLogoUrl("")}
                                            >
                                                Remove
                                            </Button>
                                        )}
                                    </div>
                                    {logoUrl && (
                                        <div className="rounded-lg border border-stone-200 bg-stone-50 p-3">
                                            <img
                                                src={logoUrl}
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
