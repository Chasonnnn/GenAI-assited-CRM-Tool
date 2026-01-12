"use client"

import * as React from "react"
import { useParams, useSearchParams } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
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

type AnswerValue = string | number | boolean | string[] | null
type Answers = Record<string, AnswerValue>
type UnknownRecord = Record<string, unknown>

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

// Progress Stepper Component
function ProgressStepper({
    currentStep,
    steps,
}: {
    currentStep: number
    steps: Step[]
}) {
    return (
        <>
            {/* Desktop Stepper */}
            <div className="hidden md:flex items-center justify-center gap-2 mb-8">
                {steps.map((step, index) => {
                    const isCompleted = currentStep > step.id
                    const isCurrent = currentStep === step.id
                    const isLast = index === steps.length - 1

                    return (
                        <React.Fragment key={step.id}>
                            <div className="flex items-center gap-2">
                                <div
                                    className={cn(
                                        "flex size-10 items-center justify-center rounded-full text-sm font-semibold transition-all",
                                        isCompleted && "bg-primary text-white",
                                        isCurrent && "bg-primary text-white ring-4 ring-primary/20",
                                        !isCompleted && !isCurrent && "bg-stone-200 text-stone-500"
                                    )}
                                >
                                    {isCompleted ? <CheckIcon className="size-5" /> : step.id}
                                </div>
                                <span
                                    className={cn(
                                        "text-sm font-medium",
                                        isCurrent && "text-primary",
                                        !isCurrent && "text-stone-500"
                                    )}
                                >
                                    {step.label}
                                </span>
                            </div>
                            {!isLast && (
                                <div
                                    className={cn(
                                        "h-0.5 w-12 transition-all",
                                        isCompleted ? "bg-primary" : "bg-stone-200"
                                    )}
                                />
                            )}
                        </React.Fragment>
                    )
                })}
            </div>

            {/* Mobile Stepper */}
            <div className="md:hidden flex items-center justify-between mb-6 px-1">
                <span className="text-sm font-medium text-stone-600">
                    Step {currentStep} of {steps.length}
                </span>
                <span className="text-sm font-semibold text-primary">
                    {steps[currentStep - 1]?.label}
                </span>
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
                "w-full p-4 rounded-xl border-2 text-left transition-all",
                "hover:border-primary hover:bg-primary/10/50",
                "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
                selected
                    ? "border-primary bg-primary/10"
                    : "border-stone-200 bg-white"
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
                    "flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-8 cursor-pointer transition-all",
                    "hover:border-primary hover:bg-primary/10/50",
                    isDragging
                        ? "border-primary bg-primary/10"
                        : "border-stone-300 bg-stone-50"
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
                    Up to {maxFiles} files, {(maxSizeBytes / (1024 * 1024)).toFixed(0)}MB each
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
                            className="flex items-center justify-between rounded-lg border border-stone-200 bg-white p-3"
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
    const [files, setFiles] = React.useState<File[]>([])
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
    const privacyNotice = formConfig?.form_schema.privacy_notice
    const showLogo = Boolean(logoUrl) && !logoError
    const steps: Step[] = [
        ...pages.map((page, index) => ({
            id: index + 1,
            label: page.title || `Step ${index + 1}`,
            shortLabel: page.title || `Step ${index + 1}`,
        })),
        { id: pages.length + 1, label: "Review & Submit", shortLabel: "Review" },
    ]

    const updateField = (field: string, value: AnswerValue) => {
        setAnswers((prev) => ({ ...prev, [field]: value }))
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
        const missingFields = page.fields.filter((field) => {
            if (!field.required || field.type === "file") return false
            const value = answers[field.key]
            if (value === null || value === undefined) return true
            if (typeof value === "string" && value.trim() === "") return true
            if (Array.isArray(value) && value.length === 0) return true
            return false
        })

        if (missingFields.length > 0) {
            toast.error(`Please complete: ${missingFields[0]?.label}`)
            return false
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
        setIsSubmitting(true)
        try {
            await submitPublicForm(token, answers, files)
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
                <div key={field.key} className="space-y-2">
                    <Label htmlFor={field.key} className="text-sm font-medium">
                        {field.label} {requiredMark}
                    </Label>
                    <Textarea
                        id={field.key}
                        value={typeof value === "string" ? value : ""}
                        onChange={(e) => updateField(field.key, e.target.value)}
                        placeholder={field.label}
                        className="min-h-24 rounded-lg"
                    />
                    {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
                </div>
            )
        }

        if (field.type === "date") {
            const isOpen = datePickerOpen[field.key] || false
            const dateValue = typeof value === "string" ? parseDateInput(value) : undefined
            return (
                <div key={field.key} className="space-y-2">
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
                                        "w-full h-12 justify-start text-left font-normal rounded-lg",
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
                <div key={field.key} className="space-y-3">
                    <Label className="text-sm font-medium">
                        {field.label} {requiredMark}
                    </Label>
                    {options.length === 0 ? (
                        <p className="text-sm text-stone-500">No options configured.</p>
                    ) : (
                        <div className="grid grid-cols-2 gap-3">
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
            const selectedValues = Array.isArray(value) ? value : []
            return (
                <div key={field.key} className="space-y-3">
                    <Label className="text-sm font-medium">
                        {field.label} {requiredMark}
                    </Label>
                    {options.length === 0 ? (
                        <p className="text-sm text-stone-500">No options configured.</p>
                    ) : (
                        <div className="grid grid-cols-2 gap-3">
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

        const inputType =
            field.type === "email"
                ? "email"
                : field.type === "phone"
                    ? "tel"
                    : field.type === "number"
                        ? "number"
                        : "text"

        return (
            <div key={field.key} className="space-y-2">
                <Label htmlFor={field.key} className="text-sm font-medium">
                    {field.label} {requiredMark}
                </Label>
                <Input
                    id={field.key}
                    type={inputType}
                    value={typeof value === "string" ? value : value ? String(value) : ""}
                    onChange={(e) => updateField(field.key, e.target.value)}
                    placeholder={field.label}
                    className="h-12 rounded-lg"
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
                <Card className="max-w-md w-full rounded-2xl shadow-lg">
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
                <Card className="max-w-md w-full rounded-2xl shadow-lg">
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
        <div className="min-h-screen pb-12">
            {/* Header */}
            <header className="py-8 md:py-12">
                <div className="max-w-2xl mx-auto px-4 text-center">
                    {/* Logo placeholder */}
                    {showLogo ? (
                        <div className="mx-auto mb-6 flex size-20 items-center justify-center">
                            <img
                                src={logoUrl}
                                alt={`${publicTitle} logo`}
                                className="size-20 rounded-2xl object-contain shadow-sm"
                                onError={() => setLogoError(true)}
                            />
                        </div>
                    ) : (
                        <div className="w-16 h-16 bg-primary rounded-2xl mx-auto mb-6 flex items-center justify-center">
                            <span className="text-white text-2xl font-bold">
                                {publicTitle.charAt(0).toUpperCase()}
                            </span>
                        </div>
                    )}
                    <h1 className="text-2xl md:text-3xl font-semibold text-stone-900 mb-2">
                        {publicTitle}
                    </h1>
                    <p className="text-stone-500">
                        {formConfig?.description || "Thank you for your interest in our program"}
                    </p>
                    {isPreview && (
                        <div className="mt-4 flex justify-center">
                            <Badge variant="secondary">Preview Mode</Badge>
                        </div>
                    )}
                </div>
            </header>

            {/* Progress Stepper */}
            <div className="max-w-2xl mx-auto px-4">
                <ProgressStepper currentStep={currentStep} steps={steps} />
            </div>

            {/* Form Content */}
            <div className="max-w-2xl mx-auto px-4">
                {!formConfig ? (
                    <Card className="rounded-2xl shadow-lg border-0">
                        <CardContent className="pt-8 pb-8 text-center">
                            <p className="text-stone-600">Form configuration is unavailable.</p>
                        </CardContent>
                    </Card>
                ) : isReviewStep ? (
                    <Card className="rounded-2xl shadow-lg border-0">
                        <CardHeader className="pb-2">
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
                                            {page.fields.filter((field) => field.type !== "file").map((field) => (
                                                <div key={field.key} className="flex justify-between">
                                                    <span className="text-stone-500">{field.label}</span>
                                                    {renderReviewValue(field, answers[field.key] ?? null)}
                                                </div>
                                            ))}
                                            {page.fields.some((field) => field.type === "file") && (
                                                <div className="flex justify-between">
                                                    <span className="text-stone-500">Uploaded Files</span>
                                                    <span className="font-medium">
                                                        {files.length ? `${files.length} file(s)` : "—"}
                                                    </span>
                                                </div>
                                            )}
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
                    <Card className="rounded-2xl shadow-lg border-0">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-xl">
                                {currentPage.title || `Step ${currentStep}`}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6 pt-4">
                            {currentPage.fields.filter((field) => field.type !== "file").length === 0 ? (
                                <div className="rounded-xl border border-stone-200 p-4 text-sm text-stone-500">
                                    No fields on this page.
                                </div>
                            ) : (
                                currentPage.fields
                                    .filter((field) => field.type !== "file")
                                    .map((field) => renderFieldInput(field))
                            )}

                            {currentPage.fields.some((field) => field.type === "file") && (
                                <div className="space-y-2">
                                    <Label className="text-sm font-medium">Upload Documents</Label>
                                    <FileUploadZone
                                        files={files}
                                        onFilesChange={setFiles}
                                        maxFiles={formConfig.max_file_count}
                                        maxFileSizeBytes={formConfig.max_file_size_bytes}
                                        allowedMimeTypes={formConfig.allowed_mime_types ?? null}
                                    />
                                </div>
                            )}

                            <PrivacyNotice text={privacyNotice ?? null} />
                        </CardContent>
                    </Card>
                ) : (
                    <Card className="rounded-2xl shadow-lg border-0">
                        <CardContent className="pt-8 pb-8 text-center">
                            <p className="text-stone-600">This page is unavailable.</p>
                        </CardContent>
                    </Card>
                )}
            </div>
            {/* Navigation Buttons */}
            <div className="flex items-center justify-between mt-6">
                <Button
                    variant="ghost"
                    onClick={handleBack}
                    disabled={currentStep === 1}
                    className="h-12 px-6"
                >
                    <ChevronLeftIcon className="size-4 mr-2" />
                    Back
                </Button>

                {currentStep < steps.length ? (
                    <Button
                        onClick={handleNext}
                        className="h-12 px-8 bg-primary hover:bg-primary/90"
                    >
                        Continue
                        <ChevronRightIcon className="size-4 ml-2" />
                    </Button>
                ) : (
                    <Button
                        onClick={handleSubmit}
                        disabled={isSubmitting || !agreed}
                        className="h-12 px-8 bg-primary hover:bg-primary/90"
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

            {/* Footer */}
            <footer className="max-w-2xl mx-auto px-4 mt-12 text-center">
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
