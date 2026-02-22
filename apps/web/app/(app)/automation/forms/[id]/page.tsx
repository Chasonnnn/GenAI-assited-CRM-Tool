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
    QrCodeIcon,
    RotateCcwIcon,
    LinkIcon,
    DownloadIcon,
} from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { toast } from "sonner"
import {
    useCreateForm,
    useCreateFormIntakeLink,
    useForm,
    useFormIntakeLinks,
    useFormSubmissions,
    useFormMappings,
    usePublishForm,
    useResolveSubmissionMatch,
    useRotateFormIntakeLink,
    useSetFormMappings,
    useSubmissionMatchCandidates,
    usePromoteIntakeLead,
    useUpdateFormDeliverySettings,
    useUpdateFormIntakeLink,
    useUpdateForm,
    useUploadFormLogo,
} from "@/lib/hooks/use-forms"
import { useFormMappingOptions } from "@/lib/hooks/use-form-mapping-options"
import { useEmailTemplates } from "@/lib/hooks/use-email-templates"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import { NotFoundState } from "@/components/not-found-state"
import { DEFAULT_FORM_SURROGATE_FIELD_OPTIONS } from "@/lib/api/forms"
import type {
    FieldType,
    FormSchema,
    FormFieldOption,
    FormRead,
    FormSubmissionRead,
    FormCreatePayload,
    FormFieldValidation,
    FormIntakeLinkRead,
    FormSurrogateFieldOption,
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

function getMissingCriticalMappings(
    pages: FormPage[],
    mappingOptions: FormSurrogateFieldOption[],
): FormSurrogateFieldOption[] {
    const criticalFieldTypeHints: Record<string, FieldType[]> = {
        full_name: ["text", "textarea"],
        email: ["email"],
        phone: ["phone"],
    }
    const hasCandidateField = (target: string) => {
        const hintedTypes = criticalFieldTypeHints[target]
        if (!hintedTypes || hintedTypes.length === 0) {
            return true
        }
        return pages.some((page) =>
            page.fields.some((field) => hintedTypes.includes(field.type)),
        )
    }

    const mappedFields = new Set(buildMappings(pages).map((mapping) => mapping.surrogate_field))
    const criticalMappings = mappingOptions.filter((option) => option.is_critical)
    const criticalValues =
        criticalMappings.length > 0
            ? criticalMappings.map((option) => option.value)
            : DEFAULT_FORM_SURROGATE_FIELD_OPTIONS.filter((option) => option.is_critical).map((option) => option.value)
    const optionByValue = new Map(mappingOptions.map((option) => [option.value, option]))
    const fallbackByValue = new Map(DEFAULT_FORM_SURROGATE_FIELD_OPTIONS.map((option) => [option.value, option]))

    return criticalValues
        .filter((value) => !mappedFields.has(value))
        .filter((value) => hasCandidateField(value))
        .map(
            (value) =>
                optionByValue.get(value) ??
                fallbackByValue.get(value) ??
                ({ value, label: value, is_critical: true } as FormSurrogateFieldOption),
        )
}

const buildColumnId = () => {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return crypto.randomUUID()
    }
    return `col-${Date.now()}-${Math.random().toString(16).slice(2)}`
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
    const { data: mappingOptionsData } = useFormMappingOptions()
    const { data: intakeLinks = [] } = useFormIntakeLinks(formId, true)
    const { data: emailTemplates = [] } = useEmailTemplates({ activeOnly: true })
    const { data: orgSignature } = useOrgSignature()
    const createFormMutation = useCreateForm()
    const updateFormMutation = useUpdateForm()
    const publishFormMutation = usePublishForm()
    const setMappingsMutation = useSetFormMappings()
    const uploadLogoMutation = useUploadFormLogo()
    const createIntakeLinkMutation = useCreateFormIntakeLink()
    const updateIntakeLinkMutation = useUpdateFormIntakeLink()
    const rotateIntakeLinkMutation = useRotateFormIntakeLink()
    const updateDeliverySettingsMutation = useUpdateFormDeliverySettings()
    const resolveSubmissionMatchMutation = useResolveSubmissionMatch()
    const promoteIntakeLeadMutation = usePromoteIntakeLead()
    const {
        data: ambiguousSubmissions = [],
        refetch: refetchAmbiguousSubmissions,
    } = useFormSubmissions(formId, {
        source_mode: "shared",
        match_status: "ambiguous_review",
        limit: 50,
    })
    const {
        data: leadQueueSubmissions = [],
        refetch: refetchLeadQueueSubmissions,
    } = useFormSubmissions(formId, {
        source_mode: "shared",
        status: "pending_review",
        match_status: "lead_created",
        limit: 50,
    })

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
    const [defaultTemplateId, setDefaultTemplateId] = useState("")
    const [newCampaignName, setNewCampaignName] = useState("")
    const [newEventName, setNewEventName] = useState("")
    const [newMaxSubmissions, setNewMaxSubmissions] = useState("")
    const [newExpiresAt, setNewExpiresAt] = useState("")
    const [selectedQrLinkId, setSelectedQrLinkId] = useState<string | null>(null)
    const [workspaceTab, setWorkspaceTab] = useState<"builder" | "submissions">("builder")
    const [selectedQueueSubmissionId, setSelectedQueueSubmissionId] = useState<string | null>(null)
    const [resolveReviewNotes, setResolveReviewNotes] = useState("")
    const [isPublished, setIsPublished] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [isPublishing, setIsPublishing] = useState(false)
    const [useOrgLogo, setUseOrgLogo] = useState(false)
    const [customLogoUrl, setCustomLogoUrl] = useState("")
    const [isMobilePreview, setIsMobilePreview] = useState(false)
    const [autoSaveStatus, setAutoSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle")
    const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null)

    const { data: selectedMatchCandidates = [], isLoading: isMatchCandidatesLoading } =
        useSubmissionMatchCandidates(selectedQueueSubmissionId)

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || ""
    const orgId = user?.org_id || ""
    const orgLogoPath = orgId ? `/forms/public/${orgId}/signature-logo` : ""
    const orgLogoAvailable = Boolean(orgSignature?.signature_logo_url)
    const resolvedLogoUrl =
        logoUrl && logoUrl.startsWith("/") && apiBaseUrl ? `${apiBaseUrl}${logoUrl}` : logoUrl
    const surrogateFieldMappings = useMemo(
        () =>
            mappingOptionsData && mappingOptionsData.length > 0
                ? mappingOptionsData
                : DEFAULT_FORM_SURROGATE_FIELD_OPTIONS,
        [mappingOptionsData],
    )

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

    const [rightSidebarTab, setRightSidebarTab] = useState<"field" | "form">("form")
    const selectField = useCallback((fieldId: string | null) => {
        setSelectedField(fieldId)
        setRightSidebarTab(fieldId ? "field" : "form")
    }, [])

    useEffect(() => {
        setHasHydrated(false)
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
        setDefaultTemplateId("")
        setNewCampaignName("")
        setNewEventName("")
        setNewMaxSubmissions("")
        setNewExpiresAt("")
        setSelectedQrLinkId(null)
        setWorkspaceTab("builder")
        setSelectedQueueSubmissionId(null)
        setResolveReviewNotes("")
    }, [formId])

    useEffect(() => {
        if (isNewForm) {
            setHasHydrated(true)
        }
    }, [isNewForm])

    useEffect(() => {
        if (workspaceTab !== "submissions") {
            setSelectedQueueSubmissionId(null)
        }
    }, [workspaceTab])

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
        setDefaultTemplateId(formData.default_application_email_template_id || "")
        setIsPublished(formData.status === "published")
        setPages(schema ? schemaToPages(schema, mappingMap) : [{ id: 1, name: "Page 1", fields: [] }])
        setActivePage(1)
        selectField(null)
        setHasHydrated(true)
    }, [formData, mappingData, isMappingsLoading, hasHydrated, isNewForm, selectField])

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
            default_application_email_template_id: defaultTemplateId || null,
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
        defaultTemplateId,
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
            selectField(nextSelectedField)
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
            selectField(nextSelectedField)
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
            selectField(null)
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
        selectField(nextId)
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
        selectField(duplicatedFields[0]?.id ?? null)
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
                selectField(null)
                return [fallbackPage]
            }
            if (pageToDelete === activePage) {
                setActivePage(nextPages[0]?.id ?? 1)
                selectField(null)
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

    const handleDefaultTemplateSelection = async (nextTemplateId: string | null) => {
        const normalizedTemplateId = nextTemplateId ?? ""
        setDefaultTemplateId(normalizedTemplateId)
        if (!formId) return
        try {
            await updateDeliverySettingsMutation.mutateAsync({
                formId,
                payload: {
                    default_application_email_template_id: normalizedTemplateId || null,
                },
            })
        } catch {
            toast.error("Failed to update delivery template")
        }
    }

    const hasMissingCriticalMappings = () => {
        const missingCriticalMappings = getMissingCriticalMappings(pages, surrogateFieldMappings)
        if (missingCriticalMappings.length === 0) {
            return false
        }

        const missingLabels = missingCriticalMappings.map((mapping) => mapping.label).join(", ")
        toast.error(`Map required surrogate fields before publishing: ${missingLabels}.`)
        return true
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
        if (hasMissingCriticalMappings()) {
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
        if (hasMissingCriticalMappings()) {
            return
        }

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

    const sortedIntakeLinks = useMemo(
        () =>
            [...intakeLinks].sort((a, b) => {
                const left = new Date(a.created_at).getTime()
                const right = new Date(b.created_at).getTime()
                return right - left
            }),
        [intakeLinks],
    )

    useEffect(() => {
        if (sortedIntakeLinks.length === 0) {
            setSelectedQrLinkId(null)
            return
        }
        if (selectedQrLinkId && sortedIntakeLinks.some((link) => link.id === selectedQrLinkId)) {
            return
        }
        setSelectedQrLinkId(sortedIntakeLinks[0]?.id || null)
    }, [selectedQrLinkId, sortedIntakeLinks])

    const selectedQrLink = useMemo(
        () => sortedIntakeLinks.find((link) => link.id === selectedQrLinkId) || null,
        [selectedQrLinkId, sortedIntakeLinks],
    )

    const handleCreateSharedLink = async () => {
        if (!formId) {
            toast.error("Save this form first before creating shared links.")
            return
        }
        if (!isPublished) {
            toast.error("Publish the form before creating shared links.")
            return
        }

        const parsedMax = newMaxSubmissions.trim()
            ? Number.parseInt(newMaxSubmissions.trim(), 10)
            : null
        if (parsedMax !== null && (Number.isNaN(parsedMax) || parsedMax <= 0)) {
            toast.error("Max submissions must be a positive number.")
            return
        }

        try {
            const created = await createIntakeLinkMutation.mutateAsync({
                formId,
                payload: {
                    campaign_name: newCampaignName.trim() || null,
                    event_name: newEventName.trim() || null,
                    max_submissions: parsedMax,
                    expires_at: newExpiresAt ? new Date(newExpiresAt).toISOString() : null,
                },
            })
            setSelectedQrLinkId(created.id)
            setNewCampaignName("")
            setNewEventName("")
            setNewMaxSubmissions("")
            setNewExpiresAt("")
            toast.success("Shared intake link created")
        } catch {
            toast.error("Failed to create shared intake link")
        }
    }

    const handleRotateSharedLink = async (linkId: string) => {
        if (!formId) return
        try {
            await rotateIntakeLinkMutation.mutateAsync({ formId, linkId })
            toast.success("Shared intake link rotated")
        } catch {
            toast.error("Failed to rotate link")
        }
    }

    const handleToggleSharedLinkActive = async (link: FormIntakeLinkRead) => {
        if (!formId) return
        try {
            await updateIntakeLinkMutation.mutateAsync({
                formId,
                linkId: link.id,
                payload: { is_active: !link.is_active },
            })
            toast.success(link.is_active ? "Link disabled" : "Link enabled")
        } catch {
            toast.error("Failed to update link")
        }
    }

    const handleCopySharedLink = async (link: FormIntakeLinkRead) => {
        const url = link.intake_url?.trim()
        if (!url) {
            toast.error("No intake URL available")
            return
        }
        try {
            await navigator.clipboard.writeText(url)
            toast.success("Shared link copied")
        } catch {
            toast.error("Failed to copy link")
        }
    }

    const getQrSvgMarkup = () => {
        const svg = document.querySelector("#shared-intake-qr svg")
        if (!(svg instanceof SVGSVGElement)) {
            toast.error("QR code not ready yet")
            return null
        }

        let markup = new XMLSerializer().serializeToString(svg)
        if (!markup.includes("xmlns=\"http://www.w3.org/2000/svg\"")) {
            markup = markup.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"')
        }
        return markup
    }

    const buildQrFilename = (extension: "svg" | "png") => {
        const baseRaw = selectedQrLink?.campaign_name || selectedQrLink?.event_name || selectedQrLink?.slug || "intake-link"
        const base = baseRaw
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "")
        return `${base || "intake-link"}-qr.${extension}`
    }

    const downloadBlob = (blob: Blob, filename: string) => {
        const downloadUrl = URL.createObjectURL(blob)
        const anchor = document.createElement("a")
        anchor.href = downloadUrl
        anchor.download = filename
        document.body.appendChild(anchor)
        anchor.click()
        anchor.remove()
        URL.revokeObjectURL(downloadUrl)
    }

    const handleDownloadQrSvg = () => {
        const markup = getQrSvgMarkup()
        if (!markup) return

        const blob = new Blob([markup], { type: "image/svg+xml;charset=utf-8" })
        downloadBlob(blob, buildQrFilename("svg"))
    }

    const handleDownloadQrPng = async () => {
        const markup = getQrSvgMarkup()
        if (!markup) return

        const svgBlob = new Blob([markup], { type: "image/svg+xml;charset=utf-8" })
        const svgUrl = URL.createObjectURL(svgBlob)
        try {
            const image = new Image()
            image.crossOrigin = "anonymous"

            await new Promise<void>((resolve, reject) => {
                image.onload = () => resolve()
                image.onerror = () => reject(new Error("Failed to render QR image"))
                image.src = svgUrl
            })

            const canvas = document.createElement("canvas")
            canvas.width = image.width || 120
            canvas.height = image.height || 120
            const context = canvas.getContext("2d")
            if (!context) {
                toast.error("Could not prepare PNG download")
                return
            }
            context.drawImage(image, 0, 0)

            const blob = await new Promise<Blob | null>((resolve) =>
                canvas.toBlob((result) => resolve(result), "image/png"),
            )
            if (!blob) {
                toast.error("Could not generate PNG")
                return
            }
            downloadBlob(blob, buildQrFilename("png"))
        } catch {
            toast.error("Failed to download PNG")
        } finally {
            URL.revokeObjectURL(svgUrl)
        }
    }

    const readAnswerValue = (submission: FormSubmissionRead, keys: string[]) => {
        for (const key of keys) {
            const rawValue = submission.answers?.[key]
            if (typeof rawValue === "string" && rawValue.trim()) {
                return rawValue.trim()
            }
        }
        return "—"
    }

    const refreshSubmissionQueues = async () => {
        await Promise.all([refetchAmbiguousSubmissions(), refetchLeadQueueSubmissions()])
    }

    const handleResolveSubmissionToSurrogate = async (submissionId: string, surrogateId: string) => {
        try {
            await resolveSubmissionMatchMutation.mutateAsync({
                submissionId,
                payload: {
                    surrogate_id: surrogateId,
                    create_intake_lead: false,
                    review_notes: resolveReviewNotes.trim() || null,
                },
            })
            toast.success("Submission linked to surrogate")
            setSelectedQueueSubmissionId(null)
            setResolveReviewNotes("")
            await refreshSubmissionQueues()
        } catch {
            toast.error("Failed to link submission")
        }
    }

    const handleResolveSubmissionToLead = async (submissionId: string) => {
        try {
            await resolveSubmissionMatchMutation.mutateAsync({
                submissionId,
                payload: {
                    create_intake_lead: true,
                    review_notes: resolveReviewNotes.trim() || null,
                },
            })
            toast.success("Submission moved to intake lead")
            setSelectedQueueSubmissionId(null)
            setResolveReviewNotes("")
            await refreshSubmissionQueues()
        } catch {
            toast.error("Failed to move submission to intake lead")
        }
    }

    const handlePromoteLeadFromSubmission = async (submission: FormSubmissionRead) => {
        if (!submission.intake_lead_id) {
            toast.error("No intake lead linked to this submission")
            return
        }
        try {
            await promoteIntakeLeadMutation.mutateAsync({
                leadId: submission.intake_lead_id,
                payload: {},
            })
            toast.success("Intake lead promoted to surrogate")
            await refreshSubmissionQueues()
        } catch {
            toast.error("Failed to promote intake lead")
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

            <div className="flex items-center gap-2 border-b border-stone-200 bg-white px-6 py-2 dark:border-stone-800 dark:bg-stone-900">
                <button
                    type="button"
                    onClick={() => setWorkspaceTab("builder")}
                    className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                        workspaceTab === "builder"
                            ? "bg-teal-500/10 text-teal-600 dark:bg-teal-500/20 dark:text-teal-400"
                            : "text-stone-600 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800"
                    }`}
                >
                    Builder
                </button>
                <button
                    type="button"
                    onClick={() => setWorkspaceTab("submissions")}
                    className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                        workspaceTab === "submissions"
                            ? "bg-teal-500/10 text-teal-600 dark:bg-teal-500/20 dark:text-teal-400"
                            : "text-stone-600 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800"
                    }`}
                >
                    Submissions
                    {ambiguousSubmissions.length + leadQueueSubmissions.length > 0 && (
                        <span className="ml-2 rounded-full bg-amber-500 px-2 py-0.5 text-[10px] font-semibold text-white">
                            {ambiguousSubmissions.length + leadQueueSubmissions.length}
                        </span>
                    )}
                </button>
            </div>

            {/* Page Tabs */}
            <div
                className={
                    workspaceTab === "builder"
                        ? "flex items-center gap-2 border-b border-stone-200 bg-white px-6 py-2 dark:border-stone-800 dark:bg-stone-900"
                        : "hidden"
                }
            >
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

            <div className={workspaceTab === "builder" ? "flex flex-1 overflow-hidden" : "hidden"}>
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
                                                onClick={() => selectField(field.id)}
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
                    <div className="mb-4 grid grid-cols-2 gap-2 rounded-lg border border-stone-200 bg-stone-50 p-1 text-xs font-medium dark:border-stone-800 dark:bg-stone-950">
                        <button
                            type="button"
                            disabled={!selectedFieldData}
                            onClick={() => setRightSidebarTab("field")}
                            className={`rounded-md px-2 py-1 transition ${
                                rightSidebarTab === "field"
                                    ? "bg-white text-stone-900 shadow-sm dark:bg-stone-900 dark:text-stone-100"
                                    : "text-stone-500 hover:text-stone-800 dark:text-stone-400 dark:hover:text-stone-200"
                            } ${!selectedFieldData ? "cursor-not-allowed opacity-50" : ""}`}
                        >
                            Field Settings
                        </button>
                        <button
                            type="button"
                            onClick={() => setRightSidebarTab("form")}
                            className={`rounded-md px-2 py-1 transition ${
                                rightSidebarTab === "form"
                                    ? "bg-white text-stone-900 shadow-sm dark:bg-stone-900 dark:text-stone-100"
                                    : "text-stone-500 hover:text-stone-800 dark:text-stone-400 dark:hover:text-stone-200"
                            }`}
                        >
                            Form Settings
                        </button>
                    </div>

                    {rightSidebarTab === "field" ? (
                        selectedFieldData ? (
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
                            <div className="rounded-lg border border-stone-200 bg-stone-50 p-4 dark:border-stone-800 dark:bg-stone-900">
                                <p className="text-xs text-stone-600 dark:text-stone-400">
                                    Select a field from the canvas to edit its settings
                                </p>
                            </div>
                        )
                    ) : (
                        <div className="space-y-6">
                            <div>
                                <h3 className="mb-4 text-sm font-semibold">Form Settings</h3>

                                {/* Form Name */}
                                <div className="space-y-2">
                                    <Label htmlFor="form-name">Form Name</Label>
                                    <Input
                                        id="form-name"
                                        value={formName}
                                        onChange={(e) => setFormName(e.target.value)}
                                    />
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

                                <div className="mt-6 space-y-4 rounded-lg border border-stone-200 p-4 dark:border-stone-800">
                                    <div className="flex items-center justify-between">
                                        <h4 className="text-sm font-semibold">Distribution</h4>
                                        <Badge variant="outline">Dedicated + Shared</Badge>
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="default-template">Default application email template</Label>
                                        <Select
                                            value={defaultTemplateId || "none"}
                                            onValueChange={(value) =>
                                                handleDefaultTemplateSelection(value === "none" ? "" : value)
                                            }
                                        >
                                            <SelectTrigger id="default-template">
                                                <SelectValue placeholder="Select template" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="none">No default template</SelectItem>
                                                {emailTemplates.map((template) => (
                                                    <SelectItem key={template.id} value={template.id}>
                                                        {template.name}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                        <p className="text-xs text-stone-500">
                                            Dedicated surrogate sends use this template by default. Users can override at send time.
                                        </p>
                                    </div>

                                    <div className="space-y-2">
                                        <Label>Create shared intake link</Label>
                                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                            <Input
                                                value={newCampaignName}
                                                onChange={(e) => setNewCampaignName(e.target.value)}
                                                placeholder="Campaign name"
                                            />
                                            <Input
                                                value={newEventName}
                                                onChange={(e) => setNewEventName(e.target.value)}
                                                placeholder="Event name"
                                            />
                                            <Input
                                                value={newMaxSubmissions}
                                                onChange={(e) => setNewMaxSubmissions(e.target.value)}
                                                placeholder="Max submissions (optional)"
                                                inputMode="numeric"
                                            />
                                            <Input
                                                value={newExpiresAt}
                                                onChange={(e) => setNewExpiresAt(e.target.value)}
                                                type="datetime-local"
                                                placeholder="Expires at (optional)"
                                            />
                                        </div>
                                        <Button
                                            type="button"
                                            variant="outline"
                                            className="w-full bg-transparent"
                                            onClick={handleCreateSharedLink}
                                            disabled={
                                                createIntakeLinkMutation.isPending || !formId || !isPublished
                                            }
                                        >
                                            {createIntakeLinkMutation.isPending && (
                                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                                            )}
                                            <LinkIcon className="mr-2 size-4" />
                                            Create Shared Link
                                        </Button>
                                        {!isPublished && (
                                            <p className="text-xs text-amber-600">
                                                Publish the form before creating shared links.
                                            </p>
                                        )}
                                    </div>

                                    <div className="space-y-3">
                                        <div className="flex items-center justify-between">
                                            <Label>Shared links</Label>
                                            <span className="text-xs text-stone-500">
                                                {sortedIntakeLinks.length} total
                                            </span>
                                        </div>
                                        {sortedIntakeLinks.length === 0 ? (
                                            <p className="text-xs text-stone-500">
                                                No shared links yet. Create one for event intake and QR distribution.
                                            </p>
                                        ) : (
                                            <div className="space-y-2">
                                                {sortedIntakeLinks.map((link) => (
                                                    <div
                                                        key={link.id}
                                                        className="rounded-md border border-stone-200 p-3 dark:border-stone-800"
                                                    >
                                                        <div className="flex flex-wrap items-center justify-between gap-2">
                                                            <button
                                                                type="button"
                                                                className="text-left"
                                                                onClick={() => setSelectedQrLinkId(link.id)}
                                                            >
                                                                <div className="text-sm font-medium">
                                                                    {link.event_name || link.campaign_name || "Shared link"}
                                                                </div>
                                                                <div className="text-xs text-stone-500">
                                                                    {link.intake_url || `/intake/${link.slug}`}
                                                                </div>
                                                            </button>
                                                            <div className="flex items-center gap-2">
                                                                <Badge
                                                                    variant={link.is_active ? "default" : "secondary"}
                                                                    className={link.is_active ? "bg-teal-500" : ""}
                                                                >
                                                                    {link.is_active ? "Active" : "Inactive"}
                                                                </Badge>
                                                                <Button
                                                                    type="button"
                                                                    size="icon"
                                                                    variant="ghost"
                                                                    onClick={() => handleCopySharedLink(link)}
                                                                    title="Copy link"
                                                                >
                                                                    <CopyIcon className="size-4" />
                                                                </Button>
                                                                <Button
                                                                    type="button"
                                                                    size="icon"
                                                                    variant="ghost"
                                                                    onClick={() => handleToggleSharedLinkActive(link)}
                                                                    title={link.is_active ? "Disable link" : "Enable link"}
                                                                    disabled={updateIntakeLinkMutation.isPending}
                                                                >
                                                                    <SmartphoneIcon className="size-4" />
                                                                </Button>
                                                                <Button
                                                                    type="button"
                                                                    size="icon"
                                                                    variant="ghost"
                                                                    onClick={() => handleRotateSharedLink(link.id)}
                                                                    title="Rotate slug"
                                                                    disabled={rotateIntakeLinkMutation.isPending}
                                                                >
                                                                    <RotateCcwIcon className="size-4" />
                                                                </Button>
                                                            </div>
                                                        </div>
                                                        <div className="mt-2 text-xs text-stone-500">
                                                            Submissions: {link.submissions_count}
                                                            {link.max_submissions ? ` / ${link.max_submissions}` : ""}
                                                            {link.expires_at
                                                                ? ` · Expires ${new Date(link.expires_at).toLocaleString()}`
                                                                : ""}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>

                                    {selectedQrLink?.intake_url && (
                                        <div className="space-y-2 rounded-md border border-stone-200 p-3 dark:border-stone-800">
                                            <div className="flex items-center gap-2 text-sm font-medium">
                                                <QrCodeIcon className="size-4" />
                                                Event QR
                                            </div>
                                            <div className="flex items-center gap-4">
                                                <div id="shared-intake-qr" className="rounded-md border border-stone-200 bg-white p-2">
                                                    <QRCodeSVG value={selectedQrLink.intake_url} size={120} includeMargin />
                                                </div>
                                                <div className="space-y-2 text-xs text-stone-500">
                                                    <div className="break-all">{selectedQrLink.intake_url}</div>
                                                    <div className="flex flex-wrap gap-2">
                                                        <Button
                                                            type="button"
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => handleCopySharedLink(selectedQrLink)}
                                                        >
                                                            <CopyIcon className="mr-2 size-3" />
                                                            Copy URL
                                                        </Button>
                                                        <Button
                                                            type="button"
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={handleDownloadQrSvg}
                                                        >
                                                            <DownloadIcon className="mr-2 size-3" />
                                                            Download SVG
                                                        </Button>
                                                        <Button
                                                            type="button"
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={handleDownloadQrPng}
                                                        >
                                                            <DownloadIcon className="mr-2 size-3" />
                                                            Download PNG
                                                        </Button>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}

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
                        </div>
                    )}
                </div>
            </div>

            <div className={workspaceTab === "submissions" ? "flex-1 overflow-y-auto p-6" : "hidden"}>
                <div className="mx-auto max-w-6xl space-y-6">
                    <div className="grid gap-3 sm:grid-cols-3">
                        <Card>
                            <CardContent className="space-y-1 p-4">
                                <p className="text-xs uppercase tracking-wide text-stone-500">Ambiguous</p>
                                <p className="text-2xl font-semibold">{ambiguousSubmissions.length}</p>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardContent className="space-y-1 p-4">
                                <p className="text-xs uppercase tracking-wide text-stone-500">Lead Queue</p>
                                <p className="text-2xl font-semibold">{leadQueueSubmissions.length}</p>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardContent className="space-y-1 p-4">
                                <p className="text-xs uppercase tracking-wide text-stone-500">Pending Shared Total</p>
                                <p className="text-2xl font-semibold">
                                    {ambiguousSubmissions.length + leadQueueSubmissions.length}
                                </p>
                            </CardContent>
                        </Card>
                    </div>

                    {!formId ? (
                        <Card>
                            <CardContent className="p-6 text-sm text-stone-600">
                                Create and publish the form before reviewing submissions.
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="grid gap-6 xl:grid-cols-2">
                            <Card>
                                <CardContent className="space-y-4 p-5">
                                    <div className="flex items-center justify-between">
                                        <h3 className="text-sm font-semibold">Ambiguous Match Queue</h3>
                                        <Badge variant="outline">{ambiguousSubmissions.length}</Badge>
                                    </div>
                                    {ambiguousSubmissions.length === 0 ? (
                                        <p className="text-sm text-stone-500">No ambiguous submissions.</p>
                                    ) : (
                                        <div className="space-y-3">
                                            {ambiguousSubmissions.map((submission) => {
                                                const fullName = readAnswerValue(submission, ["full_name", "name"])
                                                const dateOfBirth = readAnswerValue(submission, ["date_of_birth", "dob"])
                                                const phone = readAnswerValue(submission, [
                                                    "phone",
                                                    "phone_number",
                                                    "mobile_phone",
                                                ])
                                                const email = readAnswerValue(submission, ["email", "email_address"])
                                                const isSelected = selectedQueueSubmissionId === submission.id

                                                return (
                                                    <div
                                                        key={submission.id}
                                                        className="space-y-2 rounded-lg border border-stone-200 p-3 text-sm"
                                                    >
                                                        <div className="grid gap-1 sm:grid-cols-2">
                                                            <div><span className="font-medium">Name:</span> {fullName}</div>
                                                            <div><span className="font-medium">DOB:</span> {dateOfBirth}</div>
                                                            <div><span className="font-medium">Phone:</span> {phone}</div>
                                                            <div><span className="font-medium">Email:</span> {email}</div>
                                                        </div>
                                                        <div className="flex flex-wrap gap-2">
                                                            <Button
                                                                type="button"
                                                                size="sm"
                                                                variant={isSelected ? "default" : "outline"}
                                                                onClick={() =>
                                                                    setSelectedQueueSubmissionId(
                                                                        isSelected ? null : submission.id,
                                                                    )
                                                                }
                                                            >
                                                                {isSelected ? "Hide Candidates" : "Review Candidates"}
                                                            </Button>
                                                            <Button
                                                                type="button"
                                                                size="sm"
                                                                variant="outline"
                                                                disabled={resolveSubmissionMatchMutation.isPending}
                                                                onClick={() => handleResolveSubmissionToLead(submission.id)}
                                                            >
                                                                Keep As Lead
                                                            </Button>
                                                        </div>
                                                    </div>
                                                )
                                            })}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>

                            <Card>
                                <CardContent className="space-y-4 p-5">
                                    <div className="flex items-center justify-between">
                                        <h3 className="text-sm font-semibold">Lead Promotion Queue</h3>
                                        <Badge variant="outline">{leadQueueSubmissions.length}</Badge>
                                    </div>
                                    {leadQueueSubmissions.length === 0 ? (
                                        <p className="text-sm text-stone-500">No pending lead submissions.</p>
                                    ) : (
                                        <div className="space-y-3">
                                            {leadQueueSubmissions.map((submission) => {
                                                const fullName = readAnswerValue(submission, ["full_name", "name"])
                                                const dateOfBirth = readAnswerValue(submission, ["date_of_birth", "dob"])
                                                const phone = readAnswerValue(submission, [
                                                    "phone",
                                                    "phone_number",
                                                    "mobile_phone",
                                                ])
                                                const email = readAnswerValue(submission, ["email", "email_address"])

                                                return (
                                                    <div
                                                        key={submission.id}
                                                        className="space-y-2 rounded-lg border border-stone-200 p-3 text-sm"
                                                    >
                                                        <div className="grid gap-1 sm:grid-cols-2">
                                                            <div><span className="font-medium">Name:</span> {fullName}</div>
                                                            <div><span className="font-medium">DOB:</span> {dateOfBirth}</div>
                                                            <div><span className="font-medium">Phone:</span> {phone}</div>
                                                            <div><span className="font-medium">Email:</span> {email}</div>
                                                        </div>
                                                        <div className="flex flex-wrap gap-2">
                                                            <Button
                                                                type="button"
                                                                size="sm"
                                                                variant="outline"
                                                                disabled={
                                                                    promoteIntakeLeadMutation.isPending ||
                                                                    !submission.intake_lead_id
                                                                }
                                                                onClick={() => handlePromoteLeadFromSubmission(submission)}
                                                            >
                                                                Promote Lead
                                                            </Button>
                                                        </div>
                                                    </div>
                                                )
                                            })}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </div>
                    )}

                    {selectedQueueSubmissionId && (
                        <Card>
                            <CardContent className="space-y-4 p-5">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-sm font-semibold">Match Candidates</h3>
                                    <Badge variant="outline">{selectedMatchCandidates.length}</Badge>
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="queue-review-notes-submissions">Reviewer notes</Label>
                                    <Textarea
                                        id="queue-review-notes-submissions"
                                        rows={2}
                                        value={resolveReviewNotes}
                                        onChange={(event) => setResolveReviewNotes(event.target.value)}
                                        placeholder="Why this match was resolved..."
                                    />
                                </div>

                                {isMatchCandidatesLoading ? (
                                    <p className="text-sm text-stone-500">Loading candidates...</p>
                                ) : selectedMatchCandidates.length === 0 ? (
                                    <p className="text-sm text-stone-500">No candidates found.</p>
                                ) : (
                                    <div className="space-y-2">
                                        {selectedMatchCandidates.map((candidate) => (
                                            <div
                                                key={candidate.id}
                                                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-stone-200 p-3 text-sm"
                                            >
                                                <div className="space-y-1">
                                                    <p className="font-mono text-xs text-stone-600">
                                                        surrogate_id: {candidate.surrogate_id}
                                                    </p>
                                                    <p className="text-xs text-stone-500">{candidate.reason}</p>
                                                </div>
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    onClick={() =>
                                                        handleResolveSubmissionToSurrogate(
                                                            selectedQueueSubmissionId,
                                                            candidate.surrogate_id,
                                                        )
                                                    }
                                                    disabled={resolveSubmissionMatchMutation.isPending}
                                                >
                                                    Link Candidate
                                                </Button>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
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
