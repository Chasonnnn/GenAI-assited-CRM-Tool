"use client"

import * as React from "react"
import { AlertTriangleIcon, CheckCircle2Icon, Loader2Icon, SendIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { PublicFormFieldRenderer, type PublicFormAnswerValue } from "@/components/forms/PublicFormFieldRenderer"
import { cn } from "@/lib/utils"
import type { JsonObject } from "@/lib/types/json"
import {
    createEmbedFormSession,
    getEmbedPublicForm,
    submitEmbedPublicForm,
    type FormEmbedPublicRead,
    type FormField,
} from "@/lib/api/forms"

type Props = {
    slug: string
    initialParentOrigin?: string | null
}

type Answers = Record<string, PublicFormAnswerValue>
type ParentMessage =
    | { type: string; attribution?: Record<string, unknown> }

const pageClassName = "public-form-light min-h-screen bg-white text-stone-900"
const ALLOWED_ATTRIBUTION_KEYS = new Set([
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ad_id",
    "adset_id",
    "campaign_id",
    "fbclid",
    "fbc",
    "fbp",
    "referrer",
    "landing_url",
])

function getInitialParentOrigin(): string | null {
    if (typeof window === "undefined") return null
    const queryOrigin = new URLSearchParams(window.location.search).get("parent_origin")
    if (queryOrigin) return queryOrigin
    if (document.referrer) {
        try {
            return new URL(document.referrer).origin
        } catch {
            return null
        }
    }
    return null
}

function buildIdempotencyKey(): string {
    if (typeof window !== "undefined" && typeof window.crypto?.randomUUID === "function") {
        return window.crypto.randomUUID()
    }
    return `${Date.now()}-${Math.random().toString(36).slice(2, 14)}`
}

function sanitizeAttribution(payload: Record<string, unknown> | undefined): Record<string, unknown> {
    const sanitized: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(payload || {})) {
        if (!ALLOWED_ATTRIBUTION_KEYS.has(key)) continue
        if (value === null || value === undefined) continue
        sanitized[key] = String(value).slice(0, 1000)
    }
    return sanitized
}

function isEmptyValue(value: PublicFormAnswerValue | undefined): boolean {
    if (value === null || value === undefined) return true
    if (typeof value === "string") return value.trim() === ""
    if (Array.isArray(value)) return value.length === 0
    return false
}

function evaluateCondition(field: FormField, answers: Answers): boolean {
    const condition = field.show_if
    if (!condition) return true
    const value = answers[condition.field_key]
    switch (condition.operator) {
        case "is_empty":
            return isEmptyValue(value)
        case "is_not_empty":
            return !isEmptyValue(value)
        case "equals":
            return String(value ?? "") === String(condition.value ?? "")
        case "not_equals":
            return String(value ?? "") !== String(condition.value ?? "")
        case "contains":
            return Array.isArray(value)
                ? value.some((item) => String(item) === String(condition.value ?? ""))
                : String(value ?? "").includes(String(condition.value ?? ""))
        case "not_contains":
            return Array.isArray(value)
                ? !value.some((item) => String(item) === String(condition.value ?? ""))
                : !String(value ?? "").includes(String(condition.value ?? ""))
        default:
            return true
    }
}

function getFieldError(field: FormField, value: PublicFormAnswerValue | undefined): string | null {
    if (field.required && isEmptyValue(value)) {
        return `${field.label} is required.`
    }
    if (field.type === "email" && typeof value === "string" && value.trim()) {
        const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())
        if (!valid) return `${field.label} must be a valid email address.`
    }
    return null
}

function asJsonObject(answers: Answers): JsonObject {
    return answers as unknown as JsonObject
}

export default function EmbedFormPageClient({ slug, initialParentOrigin }: Props) {
    const containerRef = React.useRef<HTMLDivElement | null>(null)
    const [parentOrigin, setParentOrigin] = React.useState<string | null>(
        () => initialParentOrigin ?? getInitialParentOrigin(),
    )
    const [formConfig, setFormConfig] = React.useState<FormEmbedPublicRead | null>(null)
    const [sessionToken, setSessionToken] = React.useState<string | null>(null)
    const [answers, setAnswers] = React.useState<Answers>({})
    const [accepted, setAccepted] = React.useState(false)
    const [datePickerOpen, setDatePickerOpen] = React.useState<Record<string, boolean>>({})
    const [isLoading, setIsLoading] = React.useState(true)
    const [isSubmitting, setIsSubmitting] = React.useState(false)
    const [isSubmitted, setIsSubmitted] = React.useState(false)
    const [error, setError] = React.useState<string | null>(null)

    const postToParent = React.useCallback(
        (message: Record<string, unknown>) => {
            if (!parentOrigin || window.parent === window) return
            window.parent.postMessage(message, parentOrigin)
        },
        [parentOrigin],
    )

    React.useEffect(() => {
        const initialOrigin = initialParentOrigin ?? getInitialParentOrigin()
        setParentOrigin(initialOrigin)
        if (!initialOrigin) {
            setError("This form is not available for this website.")
            setIsLoading(false)
        }
    }, [initialParentOrigin])

    React.useEffect(() => {
        if (!parentOrigin) return
        const loadForm = async () => {
            try {
                const form = await getEmbedPublicForm(slug, parentOrigin)
                setFormConfig(form)
                setError(null)
            } catch {
                setError("This form is not available for this website.")
            } finally {
                setIsLoading(false)
            }
        }
        void loadForm()
    }, [parentOrigin, slug])

    React.useEffect(() => {
        if (!parentOrigin || !formConfig) return
        const onMessage = (event: MessageEvent<ParentMessage>) => {
            if (event.origin !== parentOrigin) return
            if (!event.data || event.data.type !== "sf:form:init") return
            void (async () => {
                try {
                    const session = await createEmbedFormSession(
                        slug,
                        event.origin,
                        sanitizeAttribution(event.data.attribution),
                    )
                    setSessionToken(session.session_token)
                } catch {
                    setError("This form is not available for this website.")
                }
            })()
        }
        window.addEventListener("message", onMessage)
        postToParent({ type: "sf:form:ready" })

        const fallback = window.setTimeout(() => {
            if (sessionToken) return
            void (async () => {
                try {
                    const session = await createEmbedFormSession(slug, parentOrigin, {})
                    setSessionToken(session.session_token)
                } catch {
                    setError("This form is not available for this website.")
                }
            })()
        }, 1000)

        return () => {
            window.removeEventListener("message", onMessage)
            window.clearTimeout(fallback)
        }
    }, [formConfig, parentOrigin, postToParent, sessionToken, slug])

    React.useEffect(() => {
        if (!containerRef.current) return
        const element = containerRef.current
        const sendHeight = () => {
            postToParent({
                type: "sf:form:resize",
                height: Math.ceil(element.getBoundingClientRect().height),
            })
        }
        const observer = new ResizeObserver(sendHeight)
        observer.observe(element)
        sendHeight()
        return () => observer.disconnect()
    }, [postToParent, formConfig, error, isLoading, isSubmitted])

    const visibleFields = React.useMemo(() => {
        const pages = formConfig?.form_schema.pages || []
        return pages.flatMap((page) => page.fields).filter((field) => evaluateCondition(field, answers))
    }, [answers, formConfig])

    const updateField = (fieldKey: string, value: PublicFormAnswerValue) => {
        setAnswers((current) => ({ ...current, [fieldKey]: value }))
        postToParent({ type: "sf:form:started" })
    }

    const validate = (): string | null => {
        for (const field of visibleFields) {
            if (field.type === "file") {
                return "This embedded form cannot collect file uploads."
            }
            const fieldError = getFieldError(field, answers[field.key])
            if (fieldError) return fieldError
        }
        if (formConfig?.consent.text && !accepted) {
            return "Consent is required before submitting."
        }
        if (!sessionToken) {
            return "This form session is not ready yet."
        }
        return null
    }

    const handleSubmit = async () => {
        const validationError = validate()
        if (validationError) {
            setError(validationError)
            postToParent({ type: "sf:form:error", reason: "validation" })
            return
        }
        if (!formConfig || !sessionToken) return

        setIsSubmitting(true)
        setError(null)
        try {
            const response = await submitEmbedPublicForm(slug, {
                embed_session_token: sessionToken,
                idempotency_key: buildIdempotencyKey(),
                published_version_id: formConfig.published_version_id,
                answers: asJsonObject(answers),
                consent: { accepted },
                attribution: {},
            })
            setIsSubmitted(true)
            postToParent({
                type: "sf:form:submitted",
                submissionRef: response.id,
            })
        } catch {
            setError("Unable to submit the form. Please try again.")
            postToParent({ type: "sf:form:error", reason: "submit" })
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <div ref={containerRef} className={cn(pageClassName, "p-0")}>
            {isLoading ? (
                <div className="flex min-h-[320px] items-center justify-center p-6">
                    <Loader2Icon className="size-8 animate-spin text-primary" />
                </div>
            ) : error && !formConfig ? (
                <div className="flex min-h-[320px] items-center justify-center p-6">
                    <Card className="w-full max-w-md rounded-lg border-stone-200">
                        <CardContent className="space-y-3 p-6 text-center">
                            <AlertTriangleIcon className="mx-auto size-10 text-amber-500" />
                            <p className="text-sm text-stone-600">{error}</p>
                        </CardContent>
                    </Card>
                </div>
            ) : isSubmitted ? (
                <div className="flex min-h-[320px] items-center justify-center p-6">
                    <Card className="w-full max-w-md rounded-lg border-stone-200">
                        <CardContent className="space-y-4 p-6 text-center">
                            <CheckCircle2Icon className="mx-auto size-12 text-primary" />
                            <div>
                                <h1 className="text-lg font-semibold text-stone-950">Request received</h1>
                                <p className="mt-2 text-sm leading-6 text-stone-600">
                                    The intake team will follow up with you shortly.
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            ) : formConfig ? (
                <main className="mx-auto w-full max-w-2xl p-4 sm:p-6">
                    <div className="mb-5 space-y-1">
                        <h1 className="text-xl font-semibold text-stone-950">
                            {formConfig.form_schema.public_title || formConfig.name}
                        </h1>
                        {formConfig.description ? (
                            <p className="text-sm leading-6 text-stone-600">{formConfig.description}</p>
                        ) : null}
                    </div>

                    <div className="space-y-5">
                        {visibleFields
                            .filter((field) => field.type !== "file")
                            .map((field) => (
                                <PublicFormFieldRenderer
                                    key={field.key}
                                    field={field}
                                    value={answers[field.key]}
                                    updateField={updateField}
                                    datePickerOpen={datePickerOpen}
                                    setDatePickerOpen={setDatePickerOpen}
                                />
                            ))}

                        {formConfig.consent.text ? (
                            <div className="flex items-start gap-3 rounded-lg border border-stone-200 bg-stone-50 p-4">
                                <Checkbox
                                    id="sf-embed-consent"
                                    checked={accepted}
                                    onCheckedChange={(checked) => setAccepted(checked === true)}
                                    className="mt-0.5"
                                />
                                <Label
                                    htmlFor="sf-embed-consent"
                                    className="text-sm leading-6 text-stone-700"
                                >
                                    {formConfig.consent.text}
                                    {formConfig.consent.privacy_policy_url ? (
                                        <>
                                            {" "}
                                            <a
                                                href={formConfig.consent.privacy_policy_url}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="font-medium text-primary underline underline-offset-2"
                                            >
                                                Privacy policy
                                            </a>
                                        </>
                                    ) : null}
                                </Label>
                            </div>
                        ) : null}

                        {error ? (
                            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                {error}
                            </div>
                        ) : null}

                        <Button
                            type="button"
                            onClick={() => void handleSubmit()}
                            disabled={isSubmitting || !sessionToken}
                            className="h-11 w-full"
                        >
                            {isSubmitting ? (
                                <>
                                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                                    Submitting
                                </>
                            ) : (
                                <>
                                    <SendIcon className="mr-2 size-4" />
                                    Submit
                                </>
                            )}
                        </Button>
                    </div>
                </main>
            ) : null}
        </div>
    )
}
