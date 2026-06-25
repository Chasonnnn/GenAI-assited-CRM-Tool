"use client"

import * as React from "react"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import {
    ChevronLeftIcon,
    ChevronRightIcon,
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
import { ApiError } from "@/lib/api"
import type { JsonObject } from "@/lib/types/json"
import { PublicFormFieldRenderer } from "@/components/forms/PublicFormFieldRenderer"
import { PublicFormHeader } from "@/components/forms/PublicFormHeader"
import { getPublicFieldValidationError } from "@/lib/forms/public-field-validation"
import {
    getSharedPublicForm,
    getSharedPublicFormDraft,
    lookupSharedPublicFormDraft,
    restoreSharedPublicFormDraft,
    saveSharedPublicFormDraft,
    submitSharedPublicForm,
    type FormIntakePublicRead,
    type FormSubmissionSharedResponse,
    type FormSchema,
} from "@/lib/api/forms"

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
type FormPage = FormSchema["pages"][number]
type FormField = FormPage["fields"][number]

const PER_FILE_FIELD_MAX = 5

function getUploadFileKey(file: File): string {
    return `${file.name}:${file.size}:${file.lastModified}`
}

function getPageKey(page: FormSchema["pages"][number]): string {
    const title = page.title?.trim() || "untitled"
    const fieldKeys = page.fields.map((field) => field.key).join("|")
    return `${title}:${fieldKeys}`
}

function getVisibleFieldGroups(
    fields: FormField[],
    answers: Answers,
    isFieldVisible: (field: FormField, values: Answers) => boolean,
) {
    const standardFields: FormField[] = []
    const fileFields: FormField[] = []

    for (const field of fields) {
        if (!isFieldVisible(field, answers)) continue
        if (field.type === "file") {
            fileFields.push(field)
        } else {
            standardFields.push(field)
        }
    }

    return { standardFields, fileFields }
}

const isIntakePublicRead = (value: unknown): value is FormIntakePublicRead => {
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

function formatSavedTime(value: string | null): string {
    if (!value) return ""
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ""
    return date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })
}

function ReviewValue({
    field,
    value,
}: {
    field: FormField
    value: AnswerValue
}) {
    if (value === null || value === undefined || value === "") {
        return <span className="text-stone-400">No answer</span>
    }
    if (field.type === "date" && typeof value === "string") {
        return <span className="font-medium">{formatDate(value)}</span>
    }
    if ((field.type === "repeatable_table" || field.type === "table") && Array.isArray(value)) {
        return (
            <span className="font-medium">
                {value.length} row{value.length === 1 ? "" : "s"}
            </span>
        )
    }
    if (typeof value === "boolean") {
        return value ? (
            <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                Yes
            </span>
        ) : (
            <span className="inline-flex items-center rounded-full bg-stone-100 px-2 py-0.5 text-xs font-medium text-stone-600">
                No
            </span>
        )
    }
    if (Array.isArray(value)) {
        return <span className="font-medium">{value.join(", ") || "—"}</span>
    }
    return <span className="font-medium">{String(value)}</span>
}

const publicFormPageClassName =
    "public-form-light min-h-screen bg-gradient-to-b from-stone-50 via-stone-50 to-stone-100/70 text-stone-900"
const publicFormCardClassName =
    "gap-0 rounded-lg border border-stone-200/80 bg-white py-0 shadow-[0_18px_45px_rgba(15,23,42,0.06)]"
const publicFormCardHeaderClassName = "border-b border-stone-100 px-5 py-4 md:px-6"
const publicFormCardContentClassName = "space-y-5 px-5 py-5 md:px-6 md:py-6"

function formatSavedDateTime(value: string | null): string {
    if (!value) return ""
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ""
    return date.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    })
}

function sanitizeIdentityValue(value: AnswerValue): string {
    if (value === null || value === undefined) return ""
    if (typeof value === "string") return value.trim()
    if (typeof value === "number" || typeof value === "boolean") return String(value).trim()
    return ""
}

function normalizeIdentityName(value: string): string {
    return value.trim().toLowerCase().replace(/\s+/g, " ")
}

function normalizeIdentityPhone(value: string): string {
    return value.replace(/\D/g, "")
}

function buildIdentityFingerprint(args: {
    fullName: string
    dateOfBirth: string
    email?: string
    phone?: string
}): string {
    return [
        normalizeIdentityName(args.fullName),
        args.dateOfBirth.trim(),
        (args.email || "").trim().toLowerCase(),
        normalizeIdentityPhone(args.phone || ""),
    ].join("|")
}

function resolveIdentityFieldKeys(schema: FormSchema): {
    fullNameKey: string | null
    dateOfBirthKey: string | null
    emailKey: string | null
    phoneKey: string | null
} {
    const firstPage = schema.pages[0]
    if (!firstPage) {
        return {
            fullNameKey: null,
            dateOfBirthKey: null,
            emailKey: null,
            phoneKey: null,
        }
    }

    let fullNameKey: string | null = null
    let dateOfBirthKey: string | null = null
    let emailKey: string | null = null
    let phoneKey: string | null = null

    for (const field of firstPage.fields) {
        const key = field.key.toLowerCase()
        const label = (field.label || "").toLowerCase()

        if (!fullNameKey && (key === "full_name" || key.includes("full_name") || label.includes("full name"))) {
            fullNameKey = field.key
        }
        if (!dateOfBirthKey && (key === "date_of_birth" || key.includes("dob") || label.includes("date of birth") || label === "dob")) {
            dateOfBirthKey = field.key
        }
        if (!emailKey && (key === "email" || key.includes("email") || label.includes("email"))) {
            emailKey = field.key
        }
        if (!phoneKey && (key === "phone" || key.includes("phone") || key.includes("mobile") || label.includes("phone") || label.includes("mobile"))) {
            phoneKey = field.key
        }
    }

    return { fullNameKey, dateOfBirthKey, emailKey, phoneKey }
}

function filterDraftAnswersForSchema(schema: FormSchema, rawAnswers: unknown): Answers {
    if (!rawAnswers || typeof rawAnswers !== "object" || Array.isArray(rawAnswers)) {
        return {}
    }
    const allowedKeys = new Set<string>()
    for (const page of schema.pages) {
        for (const field of page.fields) {
            if (field.type !== "file") {
                allowedKeys.add(field.key)
            }
        }
    }
    const restored: Answers = {}
    for (const [key, value] of Object.entries(rawAnswers as Record<string, unknown>)) {
        if (!allowedKeys.has(key)) continue
        restored[key] = value as AnswerValue
    }
    return restored
}

function shortenStepLabel(label: string): string {
    const words = label.replace(/&/g, " ").split(/\s+/).filter(Boolean)
    const firstWord = words[0] ?? label
    const secondWord = words[1] ?? ""
    if (words.length <= 1) return label
    if (words.length === 2 && label.length <= 16) return label.replace(/\s*&\s*/g, " ")
    if (words.length === 2) return firstWord
    return secondWord ? `${firstWord} ${secondWord}` : firstWord
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
    const progressValue =
        totalSteps <= 0 ? 0 : Math.round((currentStep / totalSteps) * 100)
    const maxVisible = 5
    let start = Math.max(0, currentStep - 1 - Math.floor(maxVisible / 2))
    let end = start + maxVisible - 1
    if (end > totalSteps - 1) {
        end = totalSteps - 1
        start = Math.max(0, end - maxVisible + 1)
    }
    const visibleSteps = steps.slice(start, end + 1)

    return (
        <div className="space-y-3">
            <div className="text-center">
                <div className="text-[11px] font-medium uppercase tracking-[0.22em] text-stone-500">
                    Step {currentStep} of {totalSteps}
                </div>
                <div className="mt-1 text-sm font-semibold text-stone-950">{currentLabel}</div>
            </div>
            <div
                role="progressbar"
                aria-label="Application progress"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={progressValue}
                className="h-1.5 w-full overflow-hidden rounded-full bg-stone-200"
            >
                <div
                    className="h-full rounded-full bg-gradient-to-r from-sky-500 via-blue-500 to-violet-600 transition-[width] duration-300 ease-out"
                    style={{ width: `${progressValue}%` }}
                />
            </div>
            <div className="flex items-center justify-between gap-2 text-xs text-stone-500">
                {start > 0 && <span className="shrink-0 px-1">…</span>}
                {visibleSteps.map((step) => (
                    <div key={step.id} className="flex min-w-0 flex-1 flex-col items-center gap-1">
                        <span
                            className={cn(
                                "size-1.5 rounded-full transition-colors",
                                step.id <= currentStep ? "bg-blue-500" : "bg-stone-300",
                            )}
                        />
                        <span
                            className={cn(
                                "max-w-full truncate transition-colors",
                                step.id === currentStep
                                    ? "font-semibold text-stone-950"
                                    : "text-stone-500",
                            )}
                        >
                            {step.shortLabel}
                        </span>
                    </div>
                ))}
                {end < totalSteps - 1 && <span className="shrink-0 px-1">…</span>}
            </div>
        </div>
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
    const inputId = React.useId()

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

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            inputRef.current?.click()
        }
    }

    return (
        <div className="space-y-3">
            <div
                onClick={() => inputRef.current?.click()}
                onKeyDown={handleKeyDown}
                role="button"
                tabIndex={0}
                aria-label="Upload files"
                onDrop={handleDrop}
                onDragOver={(e) => {
                    e.preventDefault()
                    setIsDragging(true)
                }}
                onDragLeave={() => setIsDragging(false)}
                className={cn(
                    "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-6 transition-all",
                    "hover:border-blue-300 hover:bg-sky-50",
                    "focus:outline-none focus:ring-2 focus:ring-primary/20 focus:ring-offset-2",
                    isDragging
                        ? "border-blue-400 bg-sky-50"
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
                    id={inputId}
                    name="public_form_file_upload"
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
                            key={getUploadFileKey(file)}
                            className="flex items-center justify-between rounded-lg border border-stone-200 bg-stone-50 p-3"
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
                                aria-label={`Remove ${file.name}`}
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

type PublicApplicationFormProps = {
    slug: string
}

type SharedResumePrompt = {
    sourceDraftId: string
    updatedAt: string | null
    fingerprint: string
}

// Main Form Component
export default function PublicApplicationForm({ slug }: PublicApplicationFormProps) {
    const token = slug
    const isPreview = false

    const [currentStep, setCurrentStep] = React.useState(1)
    const [formConfig, setFormConfig] = React.useState<FormIntakePublicRead | null>(null)
    const [answers, setAnswers] = React.useState<Answers>({})
    const [fileUploads, setFileUploads] = React.useState<FileUploads>({})
    const [isSubmitting, setIsSubmitting] = React.useState(false)
    const [isSubmitted, setIsSubmitted] = React.useState(false)
    const [submissionOutcome, setSubmissionOutcome] = React.useState<FormSubmissionSharedResponse["outcome"] | null>(null)
    const [isLoading, setIsLoading] = React.useState(true)
    const [formError, setFormError] = React.useState<string | null>(null)
    const [datePickerOpen, setDatePickerOpen] = React.useState<Record<string, boolean>>({})
    const [agreed, setAgreed] = React.useState(false)
    const [logoError, setLogoError] = React.useState(false)
    const [draftRestored, setDraftRestored] = React.useState(false)
    const [draftSaveState, setDraftSaveState] = React.useState<"idle" | "saving" | "saved" | "error">("idle")
    const [draftUpdatedAt, setDraftUpdatedAt] = React.useState<string | null>(null)
    const [draftSessionId, setDraftSessionId] = React.useState<string | null>(null)
    const [draftSessionExists, setDraftSessionExists] = React.useState(false)
    const [resumePrompt, setResumePrompt] = React.useState<SharedResumePrompt | null>(null)
    const [isRestoringResume, setIsRestoringResume] = React.useState(false)
    const autosaveTimerRef = React.useRef<number | null>(null)
    const resumeLookupTimerRef = React.useRef<number | null>(null)
    const skipNextAutosaveRef = React.useRef(true)
    const createdDraftSessionRef = React.useRef<string | null>(null)
    const suppressedIdentityFingerprintsRef = React.useRef<Set<string>>(new Set())
    const lookupCacheRef = React.useRef<Map<string, "no_match" | "match_found">>(new Map())
    const lookupSeqRef = React.useRef(0)

    React.useEffect(() => {
        if (!slug) return
        const storageKey = `intake-draft-session:${slug}`
        const existing = window.localStorage.getItem(storageKey)
        if (existing) {
            createdDraftSessionRef.current = existing
            setDraftSessionExists(true)
            setDraftSessionId(existing)
            return
        }
        const nextSessionId =
            typeof window.crypto?.randomUUID === "function"
                ? window.crypto.randomUUID()
                : `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`
        createdDraftSessionRef.current = nextSessionId
        setDraftSessionExists(false)
        setDraftSessionId(nextSessionId)
    }, [slug])

    // Validate shared link on mount
    React.useEffect(() => {
        const loadForm = async () => {
            if (!token) {
                setFormError("This form link is invalid or has expired.")
                setIsLoading(false)
                return
            }
            if (!draftSessionId) {
                return
            }

            try {
                const form = await getSharedPublicForm(token)
                if (!isIntakePublicRead(form)) {
                    throw new Error("Invalid form payload")
                }
                setFormConfig(form)
                setLogoError(false)
                if (draftSessionExists) {
                    try {
                        const draft = await getSharedPublicFormDraft(token, draftSessionId)
                        const restored = filterDraftAnswersForSchema(form.form_schema, draft?.answers)
                        if (Object.keys(restored).length > 0) {
                            skipNextAutosaveRef.current = true
                            setAnswers(restored)
                            setDraftRestored(true)
                        }
                        if (draft?.updated_at) {
                            setDraftUpdatedAt(draft.updated_at)
                            setDraftSaveState("saved")
                        }
                    } catch (error) {
                        if (error instanceof ApiError && error.status === 404) {
                            window.localStorage.removeItem(`intake-draft-session:${token}`)
                            setDraftSessionExists(false)
                        } else {
                            setDraftSaveState("error")
                        }
                    }
                }
                setIsLoading(false)
            } catch {
                setFormError("This form link is invalid or has expired.")
                setIsLoading(false)
            }
        }
        void loadForm()
    }, [draftSessionExists, draftSessionId, token, isPreview])

    React.useEffect(() => {
        if (!token || !formConfig || !draftSessionId || isPreview || isSubmitted || isRestoringResume) return

        const identityKeys = resolveIdentityFieldKeys(formConfig.form_schema)
        if (!identityKeys.fullNameKey || !identityKeys.dateOfBirthKey) {
            return
        }

        const fullName = sanitizeIdentityValue(answers[identityKeys.fullNameKey] ?? null)
        const dateOfBirth = sanitizeIdentityValue(answers[identityKeys.dateOfBirthKey] ?? null)
        const email = identityKeys.emailKey
            ? sanitizeIdentityValue(answers[identityKeys.emailKey] ?? null)
            : ""
        const phone = identityKeys.phoneKey
            ? sanitizeIdentityValue(answers[identityKeys.phoneKey] ?? null)
            : ""
        const hasEnoughIdentity = Boolean(fullName && dateOfBirth && (email || phone))

        if (!hasEnoughIdentity) {
            setResumePrompt(null)
            return
        }

        const fingerprint = buildIdentityFingerprint({ fullName, dateOfBirth, email, phone })
        if (suppressedIdentityFingerprintsRef.current.has(fingerprint)) {
            return
        }

        const cached = lookupCacheRef.current.get(fingerprint)
        if (cached === "no_match") {
            setResumePrompt(null)
            return
        }
        if (cached === "match_found" && resumePrompt?.fingerprint === fingerprint) {
            return
        }

        if (resumeLookupTimerRef.current) {
            window.clearTimeout(resumeLookupTimerRef.current)
        }

        const lookupAnswers: Record<string, AnswerValue> = {}
        lookupAnswers[identityKeys.fullNameKey] = fullName
        lookupAnswers[identityKeys.dateOfBirthKey] = dateOfBirth
        if (identityKeys.emailKey && email) {
            lookupAnswers[identityKeys.emailKey] = email
        }
        if (identityKeys.phoneKey && phone) {
            lookupAnswers[identityKeys.phoneKey] = phone
        }

        resumeLookupTimerRef.current = window.setTimeout(() => {
            const requestId = lookupSeqRef.current + 1
            lookupSeqRef.current = requestId

            void (async () => {
                try {
                    const result = await lookupSharedPublicFormDraft(
                        token,
                        lookupAnswers as JsonObject,
                        draftSessionId,
                    )
                    if (lookupSeqRef.current !== requestId) return
                    if (
                        result.status === "match_found" &&
                        result.source_draft_id &&
                        !suppressedIdentityFingerprintsRef.current.has(fingerprint)
                    ) {
                        lookupCacheRef.current.set(fingerprint, "match_found")
                        setResumePrompt({
                            sourceDraftId: result.source_draft_id,
                            updatedAt: result.updated_at ?? null,
                            fingerprint,
                        })
                        return
                    }

                    lookupCacheRef.current.set(fingerprint, "no_match")
                    setResumePrompt((current) =>
                        current?.fingerprint === fingerprint ? null : current,
                    )
                } catch {
                    // No-op: keep typing flow uninterrupted.
                }
            })()
        }, 700)

        return () => {
            if (resumeLookupTimerRef.current) {
                window.clearTimeout(resumeLookupTimerRef.current)
                resumeLookupTimerRef.current = null
            }
        }
    }, [
        answers,
        draftSessionId,
        formConfig,
        isPreview,
        isRestoringResume,
        isSubmitted,
        resumePrompt?.fingerprint,
        token,
    ])

    const isDraftValueEmpty = (value: AnswerValue): boolean => {
        if (value === null || value === undefined) return true
        if (typeof value === "string") return value.trim() === ""
        if (typeof value === "number" || typeof value === "boolean") return false
        if (Array.isArray(value)) return value.length === 0
        if (typeof value === "object") return Object.keys(value as Record<string, unknown>).length === 0
        return false
    }

    const hasAnyDraftAnswer = React.useCallback(
        (data: Answers) => Object.values(data).some((value) => !isDraftValueEmpty(value)),
        [],
    )

    const persistDraftSession = React.useCallback((sessionId: string) => {
        if (!token) return
        window.localStorage.setItem(`intake-draft-session:${token}`, sessionId)
        createdDraftSessionRef.current = sessionId
        setDraftSessionExists(true)
    }, [token])

    const saveDraftNow = React.useCallback(async () => {
        if (!token || !formConfig || !draftSessionId) return
        if (!hasAnyDraftAnswer(answers)) return

        setDraftSaveState("saving")
        try {
            const res = await saveSharedPublicFormDraft(token, draftSessionId, answers)
            persistDraftSession(draftSessionId)
            setDraftUpdatedAt(res.updated_at)
            setDraftSaveState("saved")
        } catch (error) {
            if (error instanceof ApiError && (error.status === 404 || error.status === 409)) {
                setDraftSaveState("idle")
                return
            }
            setDraftSaveState("error")
        }
    }, [answers, draftSessionId, formConfig, hasAnyDraftAnswer, persistDraftSession, token])

    const handleContinuePreviousApplication = React.useCallback(async () => {
        if (!resumePrompt || !draftSessionId || !formConfig) return
        setIsRestoringResume(true)
        try {
            const restored = await restoreSharedPublicFormDraft(
                token,
                draftSessionId,
                resumePrompt.sourceDraftId,
            )
            const nextAnswers = filterDraftAnswersForSchema(formConfig.form_schema, restored.answers)
            skipNextAutosaveRef.current = true
            setAnswers(nextAnswers)
            persistDraftSession(draftSessionId)
            setDraftUpdatedAt(restored.updated_at)
            setDraftSaveState("saved")
            setDraftRestored(true)
            suppressedIdentityFingerprintsRef.current.add(resumePrompt.fingerprint)
            setResumePrompt(null)
            toast.success("Restored your previous application")
        } catch {
            toast.error("Unable to restore previous application")
        } finally {
            setIsRestoringResume(false)
        }
    }, [draftSessionId, formConfig, persistDraftSession, resumePrompt, token])

    const handleStartNewApplication = React.useCallback(() => {
        if (!resumePrompt) return
        suppressedIdentityFingerprintsRef.current.add(resumePrompt.fingerprint)
        setResumePrompt(null)
    }, [resumePrompt])

    // Autosave drafts (answers only, not file uploads)
    React.useEffect(() => {
        if (!token || !formConfig || !draftSessionId) return
        if (isSubmitted) return
        if (!hasAnyDraftAnswer(answers)) return

        if (skipNextAutosaveRef.current) {
            skipNextAutosaveRef.current = false
            return
        }

        if (autosaveTimerRef.current) {
            window.clearTimeout(autosaveTimerRef.current)
        }
        autosaveTimerRef.current = window.setTimeout(() => {
            void saveDraftNow()
        }, 1500)

        return () => {
            if (autosaveTimerRef.current) {
                window.clearTimeout(autosaveTimerRef.current)
                autosaveTimerRef.current = null
            }
        }
    }, [answers, draftSessionId, formConfig, hasAnyDraftAnswer, isSubmitted, saveDraftNow, token])

    const pages = formConfig?.form_schema.pages || []
    const hasAnyFileFields = pages.some((page) => page.fields.some((field) => field.type === "file"))
    const publicTitle = formConfig?.form_schema.public_title?.trim() ?? ""
    const publicEyebrow = formConfig?.form_schema.public_eyebrow?.trim() ?? ""
    const publicSubtitle = formConfig?.form_schema.public_subtitle?.trim() ?? ""
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

    const visibleReviewPages = pages.map((page) => ({
        page,
        fieldGroups: getVisibleFieldGroups(page.fields, answers, isFieldVisible),
    }))
    const fileFields: FormField[] = []
    for (const reviewPage of visibleReviewPages) {
        fileFields.push(...reviewPage.fieldGroups.fileFields)
    }

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

        if (field.type === "table") {
            if (!Array.isArray(value)) {
                return `Please complete: ${field.label}`
            }
            const configuredRows = field.rows || []
            const columns = field.columns || []
            const submittedRows = new Map<string, TableRow>()

            value.forEach((row) => {
                if (!row || typeof row !== "object") {
                    return
                }
                const rowKey = (row as TableRow).row_key
                if (typeof rowKey === "string" && rowKey) {
                    submittedRows.set(rowKey, row as TableRow)
                }
            })

            for (const row of configuredRows) {
                const submittedRow = submittedRows.get(row.key)
                if (!submittedRow) {
                    return `Please complete: ${row.label}`
                }
                for (const column of columns) {
                    if (!column.required) continue
                    const rowValue = submittedRow[column.key]
                    if (rowValue === null || rowValue === undefined || rowValue === "") {
                        return `Please complete: ${row.label} / ${column.label}`
                    }
                }
            }
            return null
        }

        return getPublicFieldValidationError(field, value)
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
        if (!isPreview) void saveDraftNow()
        if (currentStep < steps.length) {
            setCurrentStep((previousStep) => Math.min(previousStep + 1, steps.length))
            window.scrollTo({ top: 0, behavior: "smooth" })
        }
    }

    const handleBack = () => {
        if (currentStep > 1) {
            if (!isPreview) void saveDraftNow()
            setCurrentStep((previousStep) => Math.max(previousStep - 1, 1))
            window.scrollTo({ top: 0, behavior: "smooth" })
        }
    }

    const handleSubmit = async () => {
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
                    setCurrentStep(() => index + 1)
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
            const response = await submitSharedPublicForm(token, answers, files, fileFieldKeys)
            if (draftSessionId) {
                window.localStorage.removeItem(`intake-draft-session:${token}`)
            }
            setSubmissionOutcome(response.outcome)
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
    const currentVisibleFields = currentPage
        ? getVisibleFieldGroups(currentPage.fields, answers, isFieldVisible)
        : { standardFields: [], fileFields: [] }

    const renderFieldInput = (field: FormSchema["pages"][number]["fields"][number]) => {
        const value = answers[field.key]

        if (field.type === "repeatable_table") {
            const requiredMark = field.required ? <span className="text-red-500">*</span> : null
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
                                            {columns.map((column) => {
                                                const fieldInputId = `${field.key}-${rowIndex}-${column.key}`
                                                const fieldInputName = `${field.key}[${rowIndex}][${column.key}]`
                                                return (
                                                    <div key={column.key} className="space-y-2">
                                                        <Label htmlFor={fieldInputId} className="text-xs font-medium">
                                                            {column.label}
                                                            {column.required && (
                                                                <span className="text-red-500"> *</span>
                                                            )}
                                                        </Label>
                                                        {column.type === "select" ? (
                                                            <select
                                                                id={fieldInputId}
                                                                name={fieldInputName}
                                                                className="h-10 w-full rounded-lg border border-stone-200 bg-white px-3 text-sm"
                                                                value={String(row[column.key] ?? "")}
                                                                onChange={(e) =>
                                                                    updateRow(rowIndex, column.key, e.target.value)
                                                                }
                                                            >
                                                                <option value="">Select…</option>
                                                                {(column.options || []).map((option) => (
                                                                    <option key={option.value} value={option.value}>
                                                                        {option.label}
                                                                    </option>
                                                                ))}
                                                            </select>
                                                        ) : (
                                                            <Input
                                                                id={fieldInputId}
                                                                name={fieldInputName}
                                                                type={column.type === "number" ? "number" : column.type === "date" ? "date" : "text"}
                                                                value={String(row[column.key] ?? "")}
                                                                onChange={(e) =>
                                                                    updateRow(rowIndex, column.key, e.target.value)
                                                                }
                                                                className="h-10 rounded-lg border-stone-200 bg-white shadow-none"
                                                            />
                                                        )}
                                                    </div>
                                                )
                                            })}
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

        return (
            <PublicFormFieldRenderer
                key={field.key}
                field={field}
                value={value}
                updateField={updateField}
                datePickerOpen={datePickerOpen}
                setDatePickerOpen={setDatePickerOpen}
            />
        )
    }

    // Loading state
    if (isLoading) {
        return (
            <div className={cn(publicFormPageClassName, "flex items-center justify-center p-4")}>
                <div className="text-center">
                    <Loader2Icon className="size-10 animate-spin text-primary mx-auto mb-4" />
                    <p className="text-stone-600">Loading application form…</p>
                </div>
            </div>
        )
    }

    // Error state
    if (formError) {
        return (
            <div className={cn(publicFormPageClassName, "flex items-center justify-center p-4")}>
                <Card className={cn(publicFormCardClassName, "w-full max-w-md")}>
                    <CardContent className="px-6 py-8 text-center">
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
        const outcomeMessage =
            submissionOutcome === "linked"
                ? "Your application is in review. A coordinator will follow up shortly."
                : submissionOutcome === "ambiguous_review"
                    ? "Your application is received and queued for verification. Our intake team will contact you soon."
                    : "Your application has been received and added to intake review. A coordinator will reach out soon."

        return (
            <div className={cn(publicFormPageClassName, "flex items-center justify-center p-4")}>
                <Card className={cn(publicFormCardClassName, "w-full max-w-md")}>
                    <CardContent className="px-6 py-10 text-center">
                        <div className="mx-auto mb-6 flex size-16 items-center justify-center rounded-full bg-emerald-50">
                            <CheckCircle2Icon className="size-10 text-emerald-600" />
                        </div>
                        <h1 className="text-2xl font-semibold text-stone-900 mb-3">
                            Application Submitted!
                        </h1>
                        <p className="text-stone-600 leading-relaxed">
                            {outcomeMessage}
                        </p>
                    </CardContent>
                </Card>
            </div>
        )
    }

    return (
        <div className={cn(publicFormPageClassName, "pb-12")}>
            <PublicFormHeader
                eyebrow={publicEyebrow}
                publicTitle={publicTitle}
                description={publicSubtitle}
                resolvedLogoUrl={resolvedLogoUrl}
                showLogo={showLogo}
                onLogoError={() => setLogoError(true)}
                metadata={
                    isPreview
                        ? "Preview Mode"
                        : draftSaveState === "saving"
                            ? "Saving…"
                            : draftSaveState === "error"
                                ? "Autosave unavailable"
                                : draftUpdatedAt
                                    ? `Saved ${formatSavedTime(draftUpdatedAt)}`
                                    : "Autosave on"
                }
            >
                {!isPreview && draftRestored && (
                    <div className="flex items-center justify-center gap-2 text-xs text-stone-500">
                        <PencilIcon className="size-3" />
                        Restored saved progress
                    </div>
                )}
                {!isPreview && resumePrompt && (
                    <div className="mx-auto w-full max-w-2xl rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-left text-sm text-amber-900">
                        <div className="flex items-start justify-between gap-3">
                            <div className="space-y-1">
                                <div className="font-medium">Continue previous application?</div>
                                <div className="text-xs text-amber-900/80">
                                    We found saved progress from{" "}
                                    {formatSavedDateTime(resumePrompt.updatedAt) || "a recent session"}.
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    onClick={handleStartNewApplication}
                                    disabled={isRestoringResume}
                                >
                                    Start new
                                </Button>
                                <Button
                                    type="button"
                                    size="sm"
                                    onClick={() => void handleContinuePreviousApplication()}
                                    disabled={isRestoringResume}
                                >
                                    {isRestoringResume ? (
                                        <>
                                            <Loader2Icon className="mr-2 size-3.5 animate-spin" />
                                            Restoring…
                                        </>
                                    ) : (
                                        "Continue previous application"
                                    )}
                                </Button>
                            </div>
                        </div>
                    </div>
                )}
                <div className="space-y-4">
                    <ProgressStepper currentStep={currentStep} steps={steps} />
                    {!isPreview && hasAnyFileFields && (
                        <div
                            data-slot="public-upload-note"
                            className="flex items-start gap-3 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-left text-sm text-sky-950"
                        >
                            <UploadIcon className="mt-0.5 size-4 text-sky-600" />
                            <div>
                                <div className="font-medium">Uploads aren&apos;t saved yet</div>
                                <div className="text-xs text-sky-900/75">
                                    File uploads are only sent when you submit the application.
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </PublicFormHeader>

            {/* Form Content */}
            <div className="max-w-3xl mx-auto px-4">
                {!formConfig ? (
                    <Card className={publicFormCardClassName}>
                        <CardContent className="px-6 py-8 text-center">
                            <p className="text-stone-600">Form configuration is unavailable.</p>
                        </CardContent>
                    </Card>
                ) : isReviewStep ? (
                    <Card className={publicFormCardClassName}>
                        <CardHeader className={publicFormCardHeaderClassName}>
                            <CardTitle className="text-lg text-stone-950">Review Your Application</CardTitle>
                        </CardHeader>
                        <CardContent className={publicFormCardContentClassName}>
                            <p className="text-stone-600 text-sm">
                                Please review your information before submitting.
                            </p>

                            {pages.length === 0 ? (
                                <div className="rounded-lg border border-stone-200 p-4 text-sm text-stone-500">
                                    No form pages available for review.
                                </div>
                            ) : (
                                visibleReviewPages.map(({ page, fieldGroups }, index) => (
                                    <div key={getPageKey(page)} className="rounded-lg border border-stone-200 p-4">
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
                                            {fieldGroups.standardFields.map((field) => (
                                                <div key={field.key} className="flex justify-between">
                                                    <span className="text-stone-500">{field.label}</span>
                                                    <ReviewValue field={field} value={answers[field.key] ?? null} />
                                                </div>
                                            ))}
                                            {fieldGroups.fileFields.map((field) => {
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

                            <div className="flex items-start gap-3 rounded-lg bg-stone-50 p-4">
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
                    <Card className={publicFormCardClassName}>
                        <CardHeader className={publicFormCardHeaderClassName}>
                            <CardTitle className="text-lg text-stone-950">
                                {currentPage.title || `Step ${currentStep}`}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className={publicFormCardContentClassName}>
                            {currentVisibleFields.standardFields.length === 0 ? (
                                <div className="rounded-lg border border-stone-200 p-4 text-sm text-stone-500">
                                    No fields on this page.
                                </div>
                            ) : (
                                currentVisibleFields.standardFields.map((field) => renderFieldInput(field))
                            )}

                            {currentVisibleFields.fileFields.map((field) => (
                                <div key={field.key} className="space-y-2 rounded-lg border border-stone-200/80 bg-stone-50/60 p-4">
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
                    <Card className={publicFormCardClassName}>
                        <CardContent className="px-6 py-8 text-center">
                            <p className="text-stone-600">This page is unavailable.</p>
                        </CardContent>
                    </Card>
                )}
            </div>
            {/* Navigation Buttons */}
            <div className="mt-8">
                <div>
                    <div className="max-w-3xl mx-auto px-4">
                        <div className="flex items-center justify-end gap-3 rounded-lg border border-stone-200/80 bg-white/95 px-4 py-3 shadow-[0_10px_28px_rgba(15,23,42,0.08)] backdrop-blur md:shadow-sm">
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
                                            Submitting…
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
                <Link
                    href="/privacy"
                    className="text-sm text-stone-500 hover:text-primary underline underline-offset-2"
                >
                    Privacy Policy
                </Link>
                <span className="mx-2 text-stone-300" aria-hidden="true">
                    |
                </span>
                <Link
                    href="/terms"
                    className="text-sm text-stone-500 hover:text-primary underline underline-offset-2"
                >
                    Terms
                </Link>
            </footer>
        </div>
    )
}
