"use client"

import type React from "react"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
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
} from "lucide-react"
import { toast } from "sonner"
import {
    useCreateForm,
    useForm,
    useFormMappings,
    usePublishForm,
    useSetFormMappings,
    useUpdateForm,
} from "@/lib/hooks/use-forms"
import type { FormSchema, FormFieldOption, FormRead } from "@/lib/api/forms"

// Field type definitions
const fieldTypes = {
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

// Case field mappings matching backend CASE_FIELD_TYPES
const caseFieldMappings = [
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
    type: string
    label: string
    helperText: string
    required: boolean
    caseFieldMapping: string
    options?: string[]
}

type FormPage = {
    id: number
    name: string
    fields: FormField[]
}

function toFieldOptions(options?: string[]): FormFieldOption[] | undefined {
    if (!options || options.length === 0) return undefined
    return options.map((option) => ({
        label: option,
        value: option,
    }))
}

function buildFormSchema(pages: FormPage[]): FormSchema {
    return {
        pages: pages.map((page) => ({
            title: page.name || null,
            fields: page.fields.map((field) => ({
                key: field.id,
                label: field.label,
                type: field.type as FormSchema["pages"][number]["fields"][number]["type"],
                required: field.required,
                options: toFieldOptions(field.options),
                help_text: field.helperText || null,
            })),
        })),
    }
}

function schemaToPages(schema: FormSchema, mappings: Map<string, string>): FormPage[] {
    const pages = schema.pages.map((page, index) => ({
        id: index + 1,
        name: page.title || `Page ${index + 1}`,
        fields: page.fields.map((field) => ({
            id: field.key,
            type: field.type,
            label: field.label,
            helperText: field.help_text || "",
            required: field.required ?? false,
            caseFieldMapping: mappings.get(field.key) || "",
            options: field.options?.map((option) => option.label || option.value) || undefined,
        })),
    }))

    if (pages.length === 0) {
        return [{ id: 1, name: "Page 1", fields: [] }]
    }

    return pages
}

function buildMappings(pages: FormPage[]): { field_key: string; case_field: string }[] {
    return pages.flatMap((page) =>
        page.fields
            .filter((field) => field.caseFieldMapping)
            .map((field) => ({
                field_key: field.id,
                case_field: field.caseFieldMapping,
            })),
    )
}

// Page component
export default function FormBuilderPage({ params }: { params: { id: string } }) {
    const { id } = params
    const router = useRouter()
    const isNewForm = id === "new"
    const formId = isNewForm ? null : id

    const { data: formData, isLoading: isFormLoading } = useForm(formId)
    const { data: mappingData, isLoading: isMappingsLoading } = useFormMappings(formId)
    const createFormMutation = useCreateForm()
    const updateFormMutation = useUpdateForm()
    const publishFormMutation = usePublishForm()
    const setMappingsMutation = useSetFormMappings()

    const [hasHydrated, setHasHydrated] = useState(false)

    // Form state
    const [formName, setFormName] = useState(isNewForm ? "" : "Surrogate Application Form")
    const [formDescription, setFormDescription] = useState("")
    const [isPublished, setIsPublished] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [isPublishing, setIsPublishing] = useState(false)

    // Page/field state
    const [pages, setPages] = useState<FormPage[]>([{ id: 1, name: "Page 1", fields: [] }])
    const [activePage, setActivePage] = useState(1)
    const [selectedField, setSelectedField] = useState<string | null>(null)
    const [draggedField, setDraggedField] = useState<{ type: string; label: string } | null>(null)

    // Dialog state
    const [showPublishDialog, setShowPublishDialog] = useState(false)

    useEffect(() => {
        setHasHydrated(false)
    }, [formId])

    useEffect(() => {
        if (isNewForm || !formData || isMappingsLoading || hasHydrated) return

        const mappingMap = new Map(
            (mappingData || []).map((mapping) => [mapping.field_key, mapping.case_field]),
        )
        const schema = formData.form_schema || formData.published_schema

        setFormName(formData.name)
        setFormDescription(formData.description || "")
        setIsPublished(formData.status === "published")
        setPages(schema ? schemaToPages(schema, mappingMap) : [{ id: 1, name: "Page 1", fields: [] }])
        setActivePage(1)
        setSelectedField(null)
        setHasHydrated(true)
    }, [formData, mappingData, isMappingsLoading, hasHydrated, isNewForm])

    const currentPage = pages.find((p) => p.id === activePage) || pages[0]

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
            <div className="flex h-screen items-center justify-center bg-stone-100 dark:bg-stone-950">
                <div className="text-center text-stone-600 dark:text-stone-400">
                    <p className="text-sm">Form not found.</p>
                </div>
            </div>
        )
    }

    // Drag and drop handlers
    const handleDragStart = (type: string, label: string) => {
        setDraggedField({ type, label })
    }

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault()
    }

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault()
        if (!draggedField) return

        const fieldId =
            typeof crypto !== "undefined" && "randomUUID" in crypto
                ? crypto.randomUUID()
                : `field-${Date.now()}`

        const newField: FormField = {
            id: fieldId,
            type: draggedField.type,
            label: draggedField.label,
            helperText: "",
            required: false,
            caseFieldMapping: "",
            options: ["select", "multiselect", "radio"].includes(draggedField.type)
                ? ["Option 1", "Option 2", "Option 3"]
                : undefined,
        }

        setPages((prev) =>
            prev.map((page) => (page.id === activePage ? { ...page, fields: [...page.fields, newField] } : page)),
        )
        setDraggedField(null)
        setSelectedField(newField.id)
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

    const persistForm = async (): Promise<FormRead> => {
        const payload = {
            name: formName.trim(),
            description: formDescription.trim() || null,
            form_schema: buildFormSchema(pages),
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
                    <Button variant="outline" size="sm" disabled>
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
                        onDragOver={handleDragOver}
                        onDrop={handleDrop}
                        className={`mx-auto max-w-3xl space-y-4 ${currentPage.fields.length === 0 ? "flex min-h-[500px] items-center justify-center" : ""
                            }`}
                    >
                        {currentPage.fields.length === 0 ? (
                            <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-stone-300 p-12 text-center dark:border-stone-700">
                                <div className="mb-4 flex size-20 items-center justify-center rounded-full bg-teal-100 dark:bg-teal-950">
                                    <TypeIcon className="size-10 text-teal-600 dark:text-teal-400" />
                                </div>
                                <h3 className="mb-2 text-lg font-semibold">Drag fields here to build your form</h3>
                                <p className="text-sm text-stone-500 dark:text-stone-400">
                                    Start by dragging fields from the left sidebar
                                </p>
                            </div>
                        ) : (
                            currentPage.fields.map((field) => {
                                const IconComponent = getFieldIcon(field.type)
                                return (
                                    <Card
                                        key={field.id}
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
                                )
                            })
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
                                    Map this field to a Case field to auto-populate data
                                </p>
                                <Select
                                    value={selectedFieldData.caseFieldMapping || "none"}
                                    onValueChange={(value) =>
                                        handleUpdateField(selectedFieldData.id, {
                                            caseFieldMapping: value && value !== "none" ? value : "",
                                        })
                                    }
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select field" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="none">None</SelectItem>
                                        {caseFieldMappings.map((mapping) => (
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
        </div>
    )
}
