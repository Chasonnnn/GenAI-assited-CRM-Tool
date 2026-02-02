"use client"

import * as React from "react"
import { useParams, useSearchParams } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Checkbox } from "@/components/ui/checkbox"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import {
    CheckIcon,
    ChevronLeftIcon,
    ChevronRightIcon,
    CalendarIcon,
    UploadIcon,
    XIcon,
    LockIcon,
    Loader2Icon,
    CheckCircle2Icon,
    FileTextIcon,
    PencilIcon,
    AlertTriangleIcon,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"
import { getPublicForm, submitPublicForm, type FormPublicRead, type FormSchema } from "@/lib/api/forms"

type Step = {
    id: number
    label: string
    shortLabel: string
}

type TableRow = Record<string, string | number | null>
type AnswerValue = string | number | boolean | string[] | TableRow[] | null
type Answers = Record<string, AnswerValue>
type UnknownRecord = Record<string, unknown>
type FileUploads = Record<string, File[]>

const PER_FILE_FIELD_MAX = 5

const isFormPublicRead = (value: unknown): value is FormPublicRead => {
    if (!value || typeof value !== "object") return false
    const record = value as UnknownRecord
    if (typeof record.form_id !== "string") return false
    if (typeof record.name !== "string") return false
    if (typeof record.max_file_size_bytes !== "number") return false
    if (typeof record.max_file_count !== "number") return false
    if (!record.form_schema || typeof record.form_schema !== "object") return false
    const schema = record.form_schema as UnknownRecord
    return Array.isArray(schema.pages)
}

// Format date for display
function formatDate(value: string | null): string {
    if (!value) return ""
    return formatLocalDate(parseDateInput(value))
}

function shortenStepLabel(label: string): string {
    const words = label.replace(/&/g, " ").split(/\s+/).filter(Boolean)
    if (words.length <= 2) return label
    return `${words[0]} ${words[1]}`
}

// Progress Stepper Component
function ProgressStepper({
    currentStep,
    steps,
}: {
    currentStep: number
    steps: Step[]
}) {
    const totalSteps = steps.length
    const currentLabel = steps[currentStep - 1]?.label ?? ""
    const progress =
        totalSteps <= 1 ? 0 : ((currentStep - 1) / (totalSteps - 1)) * 100
    const maxVisible = 5
    let start = Math.max(0, currentStep - 1 - Math.floor(maxVisible / 2))
    let end = start + maxVisible - 1
    if (end > totalSteps - 1) {
        end = totalSteps - 1
        start = Math.max(0, end - maxVisible + 1)
    }
    const visibleSteps = steps.slice(start, end + 1)

    return (
        <>
            {/* Desktop Stepper */}
            <div className="hidden md:flex flex-col items-center gap-4 rounded-2xl border border-stone-200/70 bg-stone-50/80 px-6 py-5">
                <div className="text-[11px] uppercase tracking-[0.3em] text-stone-400">
                    Step {currentStep} of {totalSteps}
                </div>
                <div className="text-base font-medium text-stone-900">{currentLabel}</div>
                <div className="w-full max-w-xl">
                    <div className="h-1.5 w-full rounded-full bg-stone-200">
                        <div
                            className="h-full rounded-full bg-primary transition-all"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                </div>
                <div className="flex items-center gap-3 text-xs text-stone-400">
                    {start > 0 && <span className="px-1">…</span>}
                    {visibleSteps.map((step) => (
                        <span
                            key={step.id}
                            className={cn(
                                "transition-colors",
                                step.id === currentStep
                                    ? "text-primary font-semibold"
                                    : "text-stone-400"
                            )}
                        >
                            {step.shortLabel}
                        </span>
                    ))}
                    {end < totalSteps - 1 && <span className="px-1">…</span>}
                </div>
            </div>

            {/* Mobile Stepper */}
            <div className="md:hidden rounded-xl border border-stone-200 bg-white px-4 py-3 text-center">
                <div className="text-xs uppercase tracking-[0.25em] text-stone-400">
                    Step {currentStep} of {totalSteps}
                </div>
                <div className="mt-1 text-sm font-semibold text-stone-900">
                    {steps[currentStep - 1]?.shortLabel}
                </div>
                <div className="mt-3 h-1 w-full rounded-full bg-stone-200">
                    <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>
        </>
    )
}

// Large Option Card for Radio/Checkbox selections
function OptionCard({
    selected,
    onClick,
    label,
    description,
}: {
    selected: boolean
    onClick: () => void
    label: string
    description?: string
}) {
    return (
        <button
            type="button"
            onClick={onClick}
            className={cn(
                "w-full rounded-2xl border border-stone-200 bg-white p-4 text-left transition-all",
                "hover:border-primary/60 hover:bg-primary/5",
                "focus:outline-none focus:ring-2 focus:ring-primary/20 focus:ring-offset-2",
                selected
                    ? "border-primary bg-primary/10"
                    : "border-stone-200"
            )}
        >
            <div className="flex items-center gap-3">
                <div
                    className={cn(
                        "flex size-6 items-center justify-center rounded-full border-2 transition-all",
                        selected
                            ? "border-primary bg-primary"
                            : "border-stone-300 bg-white"
                    )}
                >
                    {selected && <CheckIcon className="size-4 text-white" />}
                </div>
                <div>
                    <div className="font-medium text-stone-900">{label}</div>
                    {description && (
                        <div className="text-sm text-stone-500">{description}</div>
                    )}
                </div>
            </div>
        </button>
    )
}

// File Upload Zone
function FileUploadZone({
    files,
    onFilesChange,
    maxFiles = 10,
    maxFileSizeBytes,
    allowedMimeTypes,
}: {
    files: File[]
    onFilesChange: (files: File[]) => void
    maxFiles?: number
    maxFileSizeBytes?: number | null
    allowedMimeTypes?: string[] | null
}) {
    const [isDragging, setIsDragging] = React.useState(false)
    const inputRef = React.useRef<HTMLInputElement>(null)

    const maxSizeBytes = maxFileSizeBytes || 10 * 1024 * 1024
    const acceptedTypes = allowedMimeTypes && allowedMimeTypes.length > 0 ? allowedMimeTypes : null

    const isAllowedType = (file: File) => {
        if (!acceptedTypes) return true
        return acceptedTypes.some((type) => {
            if (type.endsWith("/*")) {
                return file.type.startsWith(type.replace("/*", "/"))
            }
            return file.type === type
        })
    }

    const applyFileLimits = (incomingFiles: File[]) => {
        const filteredFiles = incomingFiles.filter((file) => {
            if (!isAllowedType(file)) {
                toast.error(`File type not allowed: ${file.name}`)
                return false
            }
            if (file.size > maxSizeBytes) {
                const maxMb = Math.floor(maxSizeBytes / (1024 * 1024))
                toast.error(`File too large (${file.name}). Max ${maxMb} MB.`)
                return false
            }
            return true
        })

        const combined = [...files, ...filteredFiles]
        if (combined.length > maxFiles) {
            toast.error(`Maximum ${maxFiles} files allowed.`)
        }
        onFilesChange(combined.slice(0, maxFiles))
    }

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)
        const droppedFiles = Array.from(e.dataTransfer.files)
        applyFileLimits(droppedFiles)
    }

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFiles = Array.from(e.target.files || [])
        applyFileLimits(selectedFiles)
    }

    const removeFile = (index: number) => {
        const newFiles = files.filter((_, i) => i !== index)
        onFilesChange(newFiles)
    }

    return (
        <div className="space-y-3">
            <div
                onClick={() => inputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={(e) => {
                    e.preventDefault()
                    setIsDragging(true)
                }}
                onDragLeave={() => setIsDragging(false)}
                className={cn(
                    "flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed p-6 cursor-pointer transition-all",
                    "hover:border-primary/60 hover:bg-primary/5",
                    isDragging
                        ? "border-primary bg-primary/10"
                        : "border-stone-300 bg-white"
                )}
            >
                <UploadIcon className="size-10 text-stone-400" />
                <div className="text-center">
                    <p className="text-sm font-medium text-stone-700">
                        Drag and drop files here
                    </p>
                    <p className="text-sm text-stone-500">
                        or{" "}
                        <span className="text-primary underline underline-offset-2">
                            click to browse
                        </span>
                    </p>
                </div>
                <p className="text-xs text-stone-400">
                    Up to {maxFiles} files for this field, {(maxSizeBytes / (1024 * 1024)).toFixed(0)}MB each
                </p>
                <input
                    ref={inputRef}
                    type="file"
                    multiple
                    accept={acceptedTypes ? acceptedTypes.join(",") : undefined}
                    onChange={handleFileSelect}
                    className="hidden"
                />
            </div>

            {/* File List */}
            {files.length > 0 && (
                <div className="space-y-2">
                    {files.map((file, index) => (
                        <div
                            key={`${file.name}-${index}`}
                            className="flex items-center justify-between rounded-xl border border-stone-200 bg-stone-50 p-3"
                        >
                            <div className="flex items-center gap-3">
                                <FileTextIcon className="size-5 text-stone-400" />
                                <div>
                                    <p className="text-sm font-medium text-stone-700">
                                        {file.name}
                                    </p>
                                    <p className="text-xs text-stone-500">
                                        {(file.size / 1024).toFixed(1)} KB
                                    </p>
                                </div>
                            </div>
                            <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                className="size-8"
                                onClick={() => removeFile(index)}
                            >
                                <XIcon className="size-4" />
                            </Button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

// Privacy Notice
function PrivacyNotice({ text }: { text?: string | null }) {
    const notice =
        text && text.trim().length > 0
            ? text
            : "Your information is encrypted and secure"
    const trimmed = notice.trim()
    const isUrl = /^https?:\/\//i.test(trimmed) || /^mailto:/i.test(trimmed)
    return (
        <div className="flex items-center gap-2 text-xs text-stone-500 mt-6">
            <LockIcon className="size-4" />
            {isUrl ? (
                <a
                    href={trimmed}
                    target="_blank"
                    rel="noreferrer"
                    className="underline decoration-dotted underline-offset-2 hover:text-primary"
                >
                    View privacy policy
                </a>
            ) : (
                <span className="whitespace-pre-line">{notice}</span>
            )}
        </div>
    )
}

// Main Form Component
export default function PublicApplicationForm() {
    const params = useParams()
    const searchParams = useSearchParams()
    const tokenParam = params.token
    const token = (Array.isArray(tokenParam) ? tokenParam[0] : tokenParam) ?? ""
    const previewKey = searchParams.get("formId") || "draft"
    const isPreview = token === "preview"

    const [currentStep, setCurrentStep] = React.useState(1)
    const [formConfig, setFormConfig] = React.useState<FormPublicRead | null>(null)
    const [answers, setAnswers] = React.useState<Answers>({})
    const [fileUploads, setFileUploads] = React.useState<FileUploads>({})
    const [isSubmitting, setIsSubmitting] = React.useState(false)
    const [isSubmitted, setIsSubmitted] = React.useState(false)
    const [isLoading, setIsLoading] = React.useState(true)
    const [formError, setFormError] = React.useState<string | null>(null)
    const [datePickerOpen, setDatePickerOpen] = React.useState<Record<string, boolean>>({})
    const [agreed, setAgreed] = React.useState(false)
    const [logoError, setLogoError] = React.useState(false)

    // Validate token on mount
    React.useEffect(() => {
        const loadForm = async () => {
            if (!token) {
                setFormError("This form link is invalid or has expired.")
                setIsLoading(false)
                return
            }

            if (isPreview) {
                try {
                    const stored = window.localStorage.getItem(`form-preview:${previewKey}`)
                    if (!stored) {
                        throw new Error("Missing preview payload")
                    }
                    const parsed = JSON.parse(stored)
                    if (!isFormPublicRead(parsed)) {
                        throw new Error("Invalid preview payload")
                    }
                    setFormConfig(parsed)
                    setLogoError(false)
                    setIsLoading(false)
                } catch {
                    setFormError("Preview data is unavailable. Return to the builder and click Preview again.")
                    setIsLoading(false)
                }
                return
            }

            try {
                const form = await getPublicForm(token)
                setFormConfig(form)
                setLogoError(false)
                setIsLoading(false)
            } catch {
                setFormError("This form link is invalid or has expired.")
                setIsLoading(false)
            }
        }
        loadForm()
    }, [token, isPreview, previewKey])

    const pages = formConfig?.form_schema.pages || []
    const publicTitle =
        formConfig?.form_schema.public_title?.trim() ||
        formConfig?.name ||
        "Surrogate Application"
    const logoUrl = formConfig?.form_schema.logo_url?.trim() || ""
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || ""
    const resolvedLogoUrl =
        logoUrl && logoUrl.startsWith("/") && apiBaseUrl
            ? `${apiBaseUrl}${logoUrl}`
            : logoUrl
    const privacyNotice = formConfig?.form_schema.privacy_notice
    const showLogo = Boolean(resolvedLogoUrl) && !logoError
    const steps: Step[] = [
        ...pages.map((page, index) => {
            const label = page.title || `Step ${index + 1}`
            return {
                id: index + 1,
                label,
                shortLabel: shortenStepLabel(label),
            }
        }),
        { id: pages.length + 1, label: "Review & Submit", shortLabel: "Review" },
    ]

    const totalFiles = Object.values(fileUploads).reduce((sum, group) => sum + group.length, 0)
    const maxTotalFiles = formConfig?.max_file_count ?? 10

    const updateFileUploads = (fieldKey: string, nextFiles: File[]) => {
        setFileUploads((prev) => {
            const otherCount = Object.entries(prev).reduce(
                (sum, [key, files]) => (key === fieldKey ? sum : sum + files.length),
                0,
            )
            const allowedByTotal = Math.max(0, maxTotalFiles - otherCount)
            const allowed = Math.min(PER_FILE_FIELD_MAX, allowedByTotal)
            const trimmed = nextFiles.slice(0, allowed)
            if (trimmed.length < nextFiles.length) {
                if (allowedByTotal < PER_FILE_FIELD_MAX) {
                    toast.error(`Maximum ${maxTotalFiles} files allowed.`)
                } else {
                    toast.error(`Maximum ${PER_FILE_FIELD_MAX} files allowed per upload field.`)
                }
            }
            return { ...prev, [fieldKey]: trimmed }
        })
    }

    const getMaxFilesForField = (fieldKey: string) => {
        const currentFiles = fileUploads[fieldKey] || []
        const otherCount = totalFiles - currentFiles.length
        const allowedByTotal = Math.max(0, maxTotalFiles - otherCount)
        return Math.min(PER_FILE_FIELD_MAX, allowedByTotal)
    }

    const updateField = (field: string, value: AnswerValue) => {
        setAnswers((prev) => ({ ...prev, [field]: value }))
    }

    const isEmptyValue = (value: AnswerValue) => {
        if (value === null || value === undefined) return true
        if (typeof value === "string") return value.trim() === ""
        if (Array.isArray(value)) return value.length === 0
        return false
    }

    const evaluateCondition = (
        condition: FormSchema["pages"][number]["fields"][number]["show_if"],
        value: AnswerValue,
    ) => {
        if (!condition) return true
        const expected = condition.value
        switch (condition.operator) {
            case "is_empty":
                return isEmptyValue(value)
            case "is_not_empty":
                return !isEmptyValue(value)
            case "equals":
                if (expected !== undefined && expected !== null && typeof expected === "string") {
                    return value !== null && value !== undefined
                        ? String(value) === expected
                        : false
                }
                return value === expected
            case "not_equals":
                if (expected !== undefined && expected !== null && typeof expected === "string") {
                    return value !== null && value !== undefined
                        ? String(value) !== expected
                        : true
                }
                return value !== expected
            case "contains":
                if (Array.isArray(value)) {
                    const list = value.filter((item): item is string => typeof item === "string")
                    return expected ? list.includes(String(expected)) : false
                }
                if (typeof value === "string" && typeof expected === "string") {
                    return value.includes(expected)
                }
                return false
            case "not_contains":
                if (Array.isArray(value)) {
                    const list = value.filter((item): item is string => typeof item === "string")
                    return expected ? !list.includes(String(expected)) : true
                }
                if (typeof value === "string" && typeof expected === "string") {
                    return !value.includes(expected)
                }
                return true
            default:
                return true
        }
    }

    const isFieldVisible = (
        field: FormSchema["pages"][number]["fields"][number],
        values: Answers,
    ) => {
        if (!field.show_if) return true
        const controllingValue = values[field.show_if.field_key] ?? null
        return evaluateCondition(field.show_if, controllingValue)
    }

    const fileFields = pages.flatMap((page) =>
        page.fields.filter((field) => field.type === "file" && isFieldVisible(field, answers)),
    )

    const getFieldValidationError = (
        field: FormSchema["pages"][number]["fields"][number],
        value: AnswerValue,
    ): string | null => {
        if (field.type === "file") return null
        if (field.required && isEmptyValue(value)) {
            return `Please complete: ${field.label}`
        }
        if (isEmptyValue(value)) return null

        if (field.type === "repeatable_table") {
            if (!Array.isArray(value)) {
                return `Please add at least one row for ${field.label}`
            }
            const minRows = field.min_rows ?? null
            const maxRows = field.max_rows ?? null
            if (minRows !== null && value.length < minRows) {
                return `Please add at least ${minRows} rows for ${field.label}`
            }
            if (maxRows !== null && value.length > maxRows) {
                return `Please limit ${field.label} to ${maxRows} rows`
            }
            const columns = field.columns || []
            for (const row of value) {
                if (!row || typeof row !== "object") {
                    return `Please complete ${field.label}`
                }
                for (const column of columns) {
                    if (!column.required) continue
                    const rowValue = (row as Record<string, unknown>)[column.key]
                    if (rowValue === null || rowValue === undefined || rowValue === "") {
                        return `Please complete: ${column.label}`
                    }
                }
            }
            return null
        }

        const validation = field.validation
        if (!validation) return null

        if (
            field.type === "text" ||
            field.type === "textarea" ||
            field.type === "email" ||
            field.type === "phone" ||
            field.type === "address"
        ) {
            if (typeof value !== "string") return `Please review: ${field.label}`
            if (validation.min_length !== null && validation.min_length !== undefined) {
                if (value.length < validation.min_length) {
                    return `Please enter at least ${validation.min_length} characters for ${field.label}`
                }
            }
            if (validation.max_length !== null && validation.max_length !== undefined) {
                if (value.length > validation.max_length) {
                    return `Please limit ${field.label} to ${validation.max_length} characters`
                }
            }
            if (validation.pattern) {
                try {
                    const rawPattern = validation.pattern
                    const anchored =
                        rawPattern.startsWith("^") && rawPattern.endsWith("$")
                            ? rawPattern
                            : `^(?:${rawPattern})$`
                    const regex = new RegExp(anchored)
                    if (!regex.test(value)) {
                        return `Please enter a valid ${field.label}`
                    }
                } catch {
                    return `Validation rule invalid for ${field.label}`
                }
            }
        }

        if (field.type === "number") {
            const numericValue =
                typeof value === "number" ? value : Number(typeof value === "string" ? value : NaN)
            if (Number.isNaN(numericValue)) {
                return `Please enter a valid number for ${field.label}`
            }
            if (validation.min_value !== null && validation.min_value !== undefined) {
                if (numericValue < validation.min_value) {
                    return `Please enter ${field.label} of at least ${validation.min_value}`
                }
            }
            if (validation.max_value !== null && validation.max_value !== undefined) {
                if (numericValue > validation.max_value) {
                    return `Please enter ${field.label} of at most ${validation.max_value}`
                }
            }
        }

        return null
    }

    React.useEffect(() => {
        if (currentStep > steps.length) {
            setCurrentStep(steps.length)
        }
    }, [currentStep, steps.length])

    const validateStep = (step: number): boolean => {
        if (!formConfig) return false
        if (step > pages.length) return true

        const page = pages[step - 1]
        if (!page) return false
        for (const field of page.fields) {
            if (!isFieldVisible(field, answers)) continue
            const error = getFieldValidationError(field, answers[field.key] ?? null)
            if (error) {
                toast.error(error)
                return false
            }
        }

        return true
    }

    const handleNext = () => {
        if (!validateStep(currentStep)) return
        if (currentStep < steps.length) {
            setCurrentStep(currentStep + 1)
            window.scrollTo({ top: 0, behavior: "smooth" })
        }
    }

    const handleBack = () => {
        if (currentStep > 1) {
            setCurrentStep(currentStep - 1)
            window.scrollTo({ top: 0, behavior: "smooth" })
        }
    }

    const handleSubmit = async () => {
        if (isPreview) {
            toast.info("Preview mode only. Submissions are disabled.")
            return
        }
        if (!agreed) {
            toast.error("Please confirm the agreement before submitting.")
            return
        }

        for (let index = 0; index < pages.length; index += 1) {
            const page = pages[index]
            if (!page) continue
            for (const field of page.fields) {
                if (!isFieldVisible(field, answers)) continue
                const error = getFieldValidationError(field, answers[field.key] ?? null)
                if (error) {
                    toast.error(error)
                    setCurrentStep(index + 1)
                    window.scrollTo({ top: 0, behavior: "smooth" })
                    return
                }
            }
        }

        const missingFileField = fileFields.find(
            (field) => field.required && (fileUploads[field.key]?.length ?? 0) === 0,
        )
        if (missingFileField) {
            toast.error(`Please upload: ${missingFileField.label}`)
            return
        }

        setIsSubmitting(true)
        try {
            const fileEntries = Object.entries(fileUploads).flatMap(([fieldKey, items]) =>
                items.map((file) => ({ fieldKey, file })),
            )
            const files = fileEntries.map((entry) => entry.file)
            const fileFieldKeys = fileEntries.length
                ? fileEntries.map((entry) => entry.fieldKey)
                : undefined
            await submitPublicForm(token, answers, files, fileFieldKeys)
            setIsSubmitted(true)
        } catch {
            toast.error("Failed to submit application. Please try again.")
        } finally {
            setIsSubmitting(false)
        }
    }

    const goToEditStep = (step: number) => {
        setCurrentStep(step)
        window.scrollTo({ top: 0, behavior: "smooth" })
    }

    const isReviewStep = currentStep === steps.length
    const currentPage = pages[currentStep - 1]

    const renderReviewValue = (
        field: FormSchema["pages"][number]["fields"][number],
        value: AnswerValue,
    ) => {
        if (value === null || value === undefined || value === "") {
            return <span className="text-stone-400">—</span>
        }
        if (field.type === "date" && typeof value === "string") {
            return <span className="font-medium">{formatDate(value)}</span>
        }
        if (field.type === "repeatable_table" && Array.isArray(value)) {
            return (
                <span className="font-medium">
                    {value.length} row{value.length === 1 ? "" : "s"}
                </span>
            )
        }
        if (typeof value === "boolean") {
            return value ? <Badge className="bg-primary">Yes</Badge> : <Badge variant="secondary">No</Badge>
        }
        if (Array.isArray(value)) {
            return <span className="font-medium">{value.join(", ") || "—"}</span>
        }
        return <span className="font-medium">{String(value)}</span>
    }

    const renderFieldInput = (field: FormSchema["pages"][number]["fields"][number]) => {
        const value = answers[field.key]
        const requiredMark = field.required ? <span className="text-red-500">*</span> : null

        if (field.type === "textarea") {
            return (
                <div key={field.key} className="space-y-2 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                    <Label htmlFor={field.key} className="text-sm font-medium">
                        {field.label} {requiredMark}
                    </Label>
                    <Textarea
                        id={field.key}
                        value={typeof value === "string" ? value : ""}
                        onChange={(e) => updateField(field.key, e.target.value)}
                        placeholder={field.label}
                        className="min-h-24 rounded-xl border-stone-200 bg-white"
                    />
                    {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
                </div>
            )
        }

        if (field.type === "date") {
            const isOpen = datePickerOpen[field.key] || false
            const dateValue = typeof value === "string" ? parseDateInput(value) : undefined
            return (
                <div key={field.key} className="space-y-2 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                    <Label className="text-sm font-medium">
                        {field.label} {requiredMark}
                    </Label>
                    <Popover
                        open={isOpen}
                        onOpenChange={(open) =>
                            setDatePickerOpen((prev) => ({ ...prev, [field.key]: open }))
                        }
                    >
                        <PopoverTrigger
                            render={
                                <Button
                                    variant="outline"
                                    className={cn(
                                        "w-full h-11 justify-start rounded-xl border-stone-200 bg-white text-left font-normal",
                                        !value && "text-stone-500",
                                    )}
                                >
                                    <CalendarIcon className="mr-2 size-4" />
                                    {typeof value === "string" ? formatDate(value) : "Select a date"}
                                </Button>
                            }
                        />
                        <PopoverContent className="w-auto p-0" align="start">
                            <Calendar
                                mode="single"
                                selected={dateValue}
                                onSelect={(date) => {
                                    updateField(field.key, date ? formatLocalDate(date) : null)
                                    setDatePickerOpen((prev) => ({ ...prev, [field.key]: false }))
                                }}
                                initialFocus
                            />
                        </PopoverContent>
                    </Popover>
                    {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
                </div>
            )
        }

        if (field.type === "select" || field.type === "radio") {
            const options = field.options || []
            return (
                <div key={field.key} className="space-y-3 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                    <Label className="text-sm font-medium">
                        {field.label} {requiredMark}
                    </Label>
                    {options.length === 0 ? (
                        <p className="text-sm text-stone-500">No options configured.</p>
                    ) : (
                        <div className="grid gap-3 sm:grid-cols-2">
                            {options.map((option) => (
                                <OptionCard
                                    key={option.value}
                                    selected={value === option.value}
                                    onClick={() => updateField(field.key, option.value)}
                                    label={option.label}
                                />
                            ))}
                        </div>
                    )}
                    {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
                </div>
            )
        }

        if (field.type === "multiselect" || field.type === "checkbox") {
            const options = field.options || []
            const selectedValues = Array.isArray(value)
                ? value.filter((item): item is string => typeof item === "string")
                : []
            return (
                <div key={field.key} className="space-y-3 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                    <Label className="text-sm font-medium">
                        {field.label} {requiredMark}
                    </Label>
                    {options.length === 0 ? (
                        <p className="text-sm text-stone-500">No options configured.</p>
                    ) : (
                        <div className="grid gap-3 sm:grid-cols-2">
                            {options.map((option) => (
                                <OptionCard
                                    key={option.value}
                                    selected={selectedValues.includes(option.value)}
                                    onClick={() => {
                                        const next = selectedValues.includes(option.value)
                                            ? selectedValues.filter((item) => item !== option.value)
                                            : [...selectedValues, option.value]
                                        updateField(field.key, next)
                                    }}
                                    label={option.label}
                                />
                            ))}
                        </div>
                    )}
                    {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
                </div>
            )
        }

        if (field.type === "repeatable_table") {
            const columns = field.columns || []
            const rows = Array.isArray(value)
                ? value.filter((item): item is TableRow => typeof item === "object" && item !== null)
                : []
            const minRows = field.min_rows ?? 0
            const maxRows = field.max_rows ?? null

            const addRow = () => {
                if (maxRows !== null && rows.length >= maxRows) return
                const newRow: TableRow = {}
                columns.forEach((column) => {
                    newRow[column.key] = ""
                })
                updateField(field.key, [...rows, newRow])
            }

            const removeRow = (index: number) => {
                const nextRows = rows.filter((_, rowIndex) => rowIndex !== index)
                updateField(field.key, nextRows)
            }

            const updateRow = (rowIndex: number, columnKey: string, nextValue: string) => {
                const nextRows = [...rows]
                const row = { ...(nextRows[rowIndex] || {}) }
                row[columnKey] = nextValue
                nextRows[rowIndex] = row
                updateField(field.key, nextRows)
            }

            return (
                <div key={field.key} className="space-y-3 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                    <div className="flex items-center justify-between">
                        <Label className="text-sm font-medium">
                            {field.label} {requiredMark}
                        </Label>
                        <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={addRow}
                            disabled={maxRows !== null && rows.length >= maxRows}
                        >
                            Add Row
                        </Button>
                    </div>
                    {columns.length === 0 ? (
                        <p className="text-sm text-stone-500">No columns configured.</p>
                    ) : (
                        <div className="space-y-3">
                            {rows.length === 0 && minRows === 0 ? (
                                <p className="text-sm text-stone-500">
                                    No rows yet. Add a row to get started.
                                </p>
                            ) : (
                                rows.map((row, rowIndex) => (
                                    <div
                                        key={`${field.key}-row-${rowIndex}`}
                                        className="rounded-xl border border-stone-200 bg-white p-3"
                                    >
                                        <div className="grid gap-3 md:grid-cols-2">
                                            {columns.map((column) => (
                                                <div key={column.key} className="space-y-2">
                                                    <Label className="text-xs font-medium">
                                                        {column.label}
                                                        {column.required && (
                                                            <span className="text-red-500"> *</span>
                                                        )}
                                                    </Label>
                                                    {column.type === "select" ? (
                                                        <select
                                                            className="h-10 w-full rounded-lg border border-stone-200 bg-white px-3 text-sm"
                                                            value={String(row[column.key] ?? "")}
                                                            onChange={(e) =>
                                                                updateRow(rowIndex, column.key, e.target.value)
                                                            }
                                                        >
                                                            <option value="">Select...</option>
                                                            {(column.options || []).map((option) => (
                                                                <option key={option.value} value={option.value}>
                                                                    {option.label}
                                                                </option>
                                                            ))}
                                                        </select>
                                                    ) : (
                                                        <Input
                                                            type={column.type === "number" ? "number" : column.type === "date" ? "date" : "text"}
                                                            value={String(row[column.key] ?? "")}
                                                            onChange={(e) =>
                                                                updateRow(rowIndex, column.key, e.target.value)
                                                            }
                                                            className="h-10 rounded-lg border-stone-200 bg-white"
                                                        />
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                        <div className="mt-3 flex justify-end">
                                            <Button
                                                type="button"
                                                size="sm"
                                                variant="ghost"
                                                onClick={() => removeRow(rowIndex)}
                                                disabled={rows.length <= minRows}
                                            >
                                                Remove
                                            </Button>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    )}
                    {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
                </div>
            )
        }

        const inputType =
            field.type === "email"
                ? "email"
                : field.type === "phone"
                    ? "tel"
                    : field.type === "number"
                        ? "number"
                        : "text"

        return (
            <div key={field.key} className="space-y-2 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <Label htmlFor={field.key} className="text-sm font-medium">
                    {field.label} {requiredMark}
                </Label>
                <Input
                    id={field.key}
                    type={inputType}
                    value={typeof value === "string" ? value : value ? String(value) : ""}
                    onChange={(e) => updateField(field.key, e.target.value)}
                    placeholder={field.label}
                    className="h-11 rounded-xl border-stone-200 bg-white"
                />
                {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
            </div>
        )
    }

    // Loading state
    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <Loader2Icon className="size-10 animate-spin text-primary mx-auto mb-4" />
                    <p className="text-stone-600">Loading application form...</p>
                </div>
            </div>
        )
    }

    // Error state
    if (formError) {
        return (
            <div className="min-h-screen flex items-center justify-center p-4">
                <Card className="max-w-md w-full rounded-3xl border border-stone-200 bg-white shadow-sm">
                    <CardContent className="pt-8 pb-8 text-center">
                        <AlertTriangleIcon className="size-16 text-amber-500 mx-auto mb-4" />
                        <h1 className="text-xl font-semibold text-stone-900 mb-2">
                            Form Not Available
                        </h1>
                        <p className="text-stone-600">{formError}</p>
                    </CardContent>
                </Card>
            </div>
        )
    }

    // Success state
    if (isSubmitted) {
        return (
            <div className="min-h-screen flex items-center justify-center p-4">
                <Card className="max-w-md w-full rounded-3xl border border-stone-200 bg-white shadow-sm">
                    <CardContent className="pt-12 pb-12 text-center">
                        <div className="flex size-20 items-center justify-center rounded-full bg-primary/20 mx-auto mb-6">
                            <CheckCircle2Icon className="size-10 text-primary" />
                        </div>
                        <h1 className="text-2xl font-semibold text-stone-900 mb-3">
                            Application Submitted!
                        </h1>
                        <p className="text-stone-600 leading-relaxed">
                            Thank you for your interest in our program. We'll review your
                            application and contact you within 3-5 business days.
                        </p>
                    </CardContent>
                </Card>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-gradient-to-b from-stone-50 via-stone-50 to-stone-100/70 pb-28">
            <div className="h-0.5 w-full bg-primary/80" />
            {/* Header */}
            <header className="py-8 md:py-10">
                <div className="max-w-3xl mx-auto px-4">
                    <div className="rounded-3xl border border-stone-200/70 bg-white/95 p-8 shadow-[0_2px_12px_rgba(15,23,42,0.06)] md:p-10">
                        <div className="flex flex-col items-center gap-4 text-center">
                            {showLogo ? (
                                <div className="flex size-16 items-center justify-center">
                                    <img
                                        src={resolvedLogoUrl}
                                        alt={`${publicTitle} logo`}
                                        className="size-16 rounded-2xl object-contain shadow-sm"
                                        onError={() => setLogoError(true)}
                                    />
                                </div>
                            ) : (
                                <div className="flex size-16 items-center justify-center rounded-2xl bg-primary/10">
                                    <span className="text-primary text-2xl font-semibold">
                                        {publicTitle.charAt(0).toUpperCase()}
                                    </span>
                                </div>
                            )}
                            <div className="space-y-3">
                                <h1 className="text-3xl font-semibold tracking-tight text-stone-900 md:text-4xl">
                                    {publicTitle}
                                </h1>
                                <p className="mx-auto max-w-2xl text-base text-stone-500 md:text-lg">
                                    {formConfig?.description ||
                                        "Thank you for your interest in our program"}
                                </p>
                                {isPreview && (
                                    <div className="pt-2 text-[11px] uppercase tracking-[0.3em] text-stone-400">
                                        Preview Mode
                                    </div>
                                )}
                            </div>
                        </div>
                        <div className="mt-8">
                            <ProgressStepper currentStep={currentStep} steps={steps} />
                        </div>
                    </div>
                </div>
            </header>

            {/* Form Content */}
            <div className="max-w-3xl mx-auto px-4">
                {!formConfig ? (
                    <Card className="rounded-3xl border border-stone-200 bg-white shadow-sm">
                        <CardContent className="pt-8 pb-8 text-center">
                            <p className="text-stone-600">Form configuration is unavailable.</p>
                        </CardContent>
                    </Card>
                ) : isReviewStep ? (
                    <Card className="rounded-3xl border border-stone-200 bg-white shadow-sm">
                        <CardHeader className="pb-4 border-b border-stone-100">
                            <CardTitle className="text-xl">Review Your Application</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6 pt-4">
                            <p className="text-stone-600 text-sm">
                                Please review your information before submitting.
                            </p>

                            {pages.length === 0 ? (
                                <div className="rounded-xl border border-stone-200 p-4 text-sm text-stone-500">
                                    No form pages available for review.
                                </div>
                            ) : (
                                pages.map((page, index) => (
                                    <div key={`${page.title}-${index}`} className="rounded-xl border border-stone-200 p-4">
                                        <div className="flex items-center justify-between mb-3">
                                            <h3 className="font-semibold text-stone-900">
                                                {page.title || `Page ${index + 1}`}
                                            </h3>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => goToEditStep(index + 1)}
                                                className="text-primary hover:text-primary/80"
                                            >
                                                <PencilIcon className="size-3 mr-1" />
                                                Edit
                                            </Button>
                                        </div>
                                        <div className="grid gap-2 text-sm">
                                            {page.fields
                                                .filter(
                                                    (field) =>
                                                        field.type !== "file" &&
                                                        isFieldVisible(field, answers),
                                                )
                                                .map((field) => (
                                                <div key={field.key} className="flex justify-between">
                                                    <span className="text-stone-500">{field.label}</span>
                                                    {renderReviewValue(field, answers[field.key] ?? null)}
                                                </div>
                                            ))}
                                            {page.fields
                                                .filter(
                                                    (field) =>
                                                        field.type === "file" &&
                                                        isFieldVisible(field, answers),
                                                )
                                                .map((field) => {
                                                    const count = fileUploads[field.key]?.length ?? 0
                                                    return (
                                                        <div key={field.key} className="flex justify-between">
                                                            <span className="text-stone-500">{field.label}</span>
                                                            <span className="font-medium">
                                                                {count ? `${count} file(s)` : "—"}
                                                            </span>
                                                        </div>
                                                    )
                                                })}
                                        </div>
                                    </div>
                                ))
                            )}

                            <div className="flex items-start gap-3 p-4 rounded-xl bg-stone-50">
                                <Checkbox
                                    id="agree"
                                    checked={agreed}
                                    onCheckedChange={(checked) => setAgreed(checked === true)}
                                    className="mt-1"
                                />
                                <label
                                    htmlFor="agree"
                                    className="text-sm text-stone-600 leading-relaxed"
                                >
                                    I confirm that the information provided is accurate and
                                    complete. I understand that providing false information may
                                    result in disqualification from the program.
                                </label>
                            </div>

                            <PrivacyNotice text={privacyNotice ?? null} />
                        </CardContent>
                    </Card>
                ) : currentPage ? (
                    <Card className="rounded-3xl border border-stone-200 bg-white shadow-sm">
                        <CardHeader className="pb-4 border-b border-stone-100">
                            <CardTitle className="text-xl">
                                {currentPage.title || `Step ${currentStep}`}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6 pt-4">
                            {currentPage.fields.filter(
                                (field) =>
                                    field.type !== "file" && isFieldVisible(field, answers),
                            ).length === 0 ? (
                                <div className="rounded-xl border border-stone-200 p-4 text-sm text-stone-500">
                                    No fields on this page.
                                </div>
                            ) : (
                                currentPage.fields
                                    .filter(
                                        (field) =>
                                            field.type !== "file" && isFieldVisible(field, answers),
                                    )
                                    .map((field) => renderFieldInput(field))
                            )}

                            {currentPage.fields
                                .filter(
                                    (field) =>
                                        field.type === "file" && isFieldVisible(field, answers),
                                )
                                .map((field) => (
                                    <div key={field.key} className="space-y-2 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                                        <Label className="text-sm font-medium">
                                            {field.label} {field.required && <span className="text-red-500">*</span>}
                                        </Label>
                                        <FileUploadZone
                                            files={fileUploads[field.key] || []}
                                            onFilesChange={(nextFiles) => updateFileUploads(field.key, nextFiles)}
                                            maxFiles={getMaxFilesForField(field.key)}
                                            maxFileSizeBytes={formConfig.max_file_size_bytes}
                                            allowedMimeTypes={formConfig.allowed_mime_types ?? null}
                                        />
                                        {field.help_text && (
                                            <p className="text-xs text-stone-500">{field.help_text}</p>
                                        )}
                                    </div>
                                ))}

                            <PrivacyNotice text={privacyNotice ?? null} />
                        </CardContent>
                    </Card>
                ) : (
                    <Card className="rounded-3xl border border-stone-200 bg-white shadow-sm">
                        <CardContent className="pt-8 pb-8 text-center">
                            <p className="text-stone-600">This page is unavailable.</p>
                        </CardContent>
                    </Card>
                )}
            </div>
            {/* Navigation Buttons */}
            <div className="sticky bottom-0 z-20 mt-10">
                <div className="bg-gradient-to-b from-transparent via-stone-50/90 to-stone-50 pb-6 pt-4">
                    <div className="max-w-3xl mx-auto px-4">
                        <div className="flex items-center justify-center gap-3 rounded-2xl border border-stone-200/80 bg-white/95 px-4 py-3 shadow-[0_6px_18px_rgba(15,23,42,0.06)] backdrop-blur">
                            <Button
                                variant="ghost"
                                onClick={handleBack}
                                disabled={currentStep === 1}
                                className="h-11 px-5 text-stone-600"
                            >
                                <ChevronLeftIcon className="size-4 mr-2" />
                                Back
                            </Button>

                            {currentStep < steps.length ? (
                                <Button
                                    onClick={handleNext}
                                    className="h-11 px-7 bg-primary hover:bg-primary/90"
                                >
                                    Continue
                                    <ChevronRightIcon className="size-4 ml-2" />
                                </Button>
                            ) : (
                                <Button
                                    onClick={handleSubmit}
                                    disabled={isSubmitting || !agreed}
                                    className="h-11 px-7 bg-primary hover:bg-primary/90"
                                >
                                    {isSubmitting ? (
                                        <>
                                            <Loader2Icon className="size-4 mr-2 animate-spin" />
                                            Submitting...
                                        </>
                                    ) : (
                                        "Submit Application"
                                    )}
                                </Button>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Footer */}
            <footer className="max-w-3xl mx-auto px-4 mt-12 text-center">
                <a
                    href="/privacy"
                    className="text-sm text-stone-500 hover:text-primary underline underline-offset-2"
                >
                    Privacy Policy
                </a>
            </footer>
        </div>
    )
}
