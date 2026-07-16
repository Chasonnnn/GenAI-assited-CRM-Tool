"use client"

import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { AlertTriangleIcon, CheckCircle2Icon, Loader2Icon, SendIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { PublicFormFieldRenderer, type PublicFormAnswerValue } from "@/components/forms/PublicFormFieldRenderer"
import {
    getPublicFieldValidationError,
    isEmptyPublicFieldValue,
} from "@/lib/forms/public-field-validation"
import { cn } from "@/lib/utils"
import type { JsonObject } from "@/lib/types/json"
import {
    createEmbedFormSession,
    getEmbedPublicForm,
    submitEmbedPublicForm,
    type FormField,
} from "@/lib/api/forms"

type Props = {
    slug: string
    initialParentOrigin?: string | null
}

type Answers = Record<string, PublicFormAnswerValue>
type ParentMessage =
    | { type: string; attribution?: Record<string, unknown> }
type EmbedSessionState = {
    key: string
    token: string
}
type EmbedFormState = {
    parentOrigin: string | null
    sessionState: EmbedSessionState | null
    answers: Answers
    datePickerOpen: Record<string, boolean>
    isSubmitting: boolean
    isSubmitted: boolean
    error: string | null
}
type EmbedFormAction =
    | { type: "sessionCreated"; sessionState: EmbedSessionState }
    | { type: "sessionFailed" }
    | { type: "answerChanged"; fieldKey: string; value: PublicFormAnswerValue }
    | { type: "datePickerOpenChanged"; update: React.SetStateAction<Record<string, boolean>> }
    | { type: "validationFailed"; error: string }
    | { type: "submissionStarted" }
    | { type: "submissionSucceeded" }
    | { type: "submissionFailed" }
type EnsureEmbedSessionArgs = {
    slug: string
    origin: string
    attribution: Record<string, unknown>
    sessionStateRef: { current: EmbedSessionState | null }
    sessionRequestKeyRef: { current: string | null }
    onSessionCreated: (sessionState: EmbedSessionState) => void
    onSessionFailed: () => void
}

const pageClassName = "public-form-light min-h-screen bg-transparent text-stone-900"
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

function createInitialEmbedFormState(initialParentOrigin: string | null | undefined): EmbedFormState {
    const parentOrigin = initialParentOrigin ?? getInitialParentOrigin()
    return {
        parentOrigin,
        sessionState: null,
        answers: {},
        datePickerOpen: {},
        isSubmitting: false,
        isSubmitted: false,
        error: parentOrigin ? null : "This form is not available for this website.",
    }
}

function getEmbedSessionKey(slug: string, origin: string): string {
    return `${slug}\u0000${origin}`
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

function evaluateCondition(field: FormField, answers: Answers): boolean {
    const condition = field.show_if
    if (!condition) return true
    const value = answers[condition.field_key]
    switch (condition.operator) {
        case "is_empty":
            return isEmptyPublicFieldValue(value)
        case "is_not_empty":
            return !isEmptyPublicFieldValue(value)
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
    return getPublicFieldValidationError(field, value)
}

function asJsonObject(answers: Answers): JsonObject {
    return answers as unknown as JsonObject
}

function embedFormReducer(state: EmbedFormState, action: EmbedFormAction): EmbedFormState {
    switch (action.type) {
        case "sessionCreated":
            return {
                ...state,
                sessionState: action.sessionState,
            }
        case "sessionFailed":
            return {
                ...state,
                error: "This form is not available for this website.",
            }
        case "answerChanged":
            return {
                ...state,
                answers: {
                    ...state.answers,
                    [action.fieldKey]: action.value,
                },
            }
        case "datePickerOpenChanged": {
            const datePickerOpen =
                typeof action.update === "function" ? action.update(state.datePickerOpen) : action.update
            return {
                ...state,
                datePickerOpen,
            }
        }
        case "validationFailed":
            return {
                ...state,
                error: action.error,
            }
        case "submissionStarted":
            return {
                ...state,
                isSubmitting: true,
                error: null,
            }
        case "submissionSucceeded":
            return {
                ...state,
                isSubmitting: false,
                isSubmitted: true,
            }
        case "submissionFailed":
            return {
                ...state,
                isSubmitting: false,
                error: "Unable to submit the form. Please try again.",
            }
    }
}

function postEmbedMessageToParent(parentOrigin: string | null, message: Record<string, unknown>): void {
    if (!parentOrigin || window.parent === window) return
    window.parent.postMessage(message, parentOrigin)
}

function ensureEmbedSession({
    slug,
    origin,
    attribution,
    sessionStateRef,
    sessionRequestKeyRef,
    onSessionCreated,
    onSessionFailed,
}: EnsureEmbedSessionArgs): void {
    const sessionKey = getEmbedSessionKey(slug, origin)
    if (sessionStateRef.current?.key === sessionKey || sessionRequestKeyRef.current === sessionKey) return
    sessionRequestKeyRef.current = sessionKey
    void (async () => {
        try {
            const session = await createEmbedFormSession(slug, origin, attribution)
            const nextSession = {
                key: sessionKey,
                token: session.session_token,
            }
            sessionStateRef.current = nextSession
            onSessionCreated(nextSession)
        } catch {
            onSessionFailed()
        }
        if (sessionRequestKeyRef.current === sessionKey) {
            sessionRequestKeyRef.current = null
        }
    })()
}

export default function EmbedFormPageClient({ slug, initialParentOrigin }: Props) {
    const parentOrigin = initialParentOrigin ?? getInitialParentOrigin()
    return (
        <EmbedFormSession
            key={`${slug}\u0000${parentOrigin ?? "missing-origin"}`}
            slug={slug}
            parentOrigin={parentOrigin}
        />
    )
}

function EmbedFormSession({ slug, parentOrigin }: { slug: string; parentOrigin: string | null }) {
    const containerRef = React.useRef<HTMLDivElement | null>(null)
    const sessionStateRef = React.useRef<EmbedSessionState | null>(null)
    const sessionRequestKeyRef = React.useRef<string | null>(null)
    const [state, dispatch] = React.useReducer(
        embedFormReducer,
        parentOrigin,
        createInitialEmbedFormState,
    )
    const {
        sessionState,
        answers,
        datePickerOpen,
        isSubmitting,
        isSubmitted,
        error: localError,
    } = state
    const formQuery = useQuery({
        queryKey: ["public", "embed-form", slug, parentOrigin],
        queryFn: () => {
            if (!parentOrigin) throw new Error("Missing parent origin")
            return getEmbedPublicForm(slug, parentOrigin)
        },
        enabled: Boolean(parentOrigin),
        retry: false,
    })
    const formConfig = parentOrigin ? formQuery.data ?? null : null
    const isLoading = parentOrigin ? formQuery.isLoading : false
    const error = localError ?? (formQuery.isError
        ? "This form is not available for this website."
        : null)
    const activeSessionKey = parentOrigin ? getEmbedSessionKey(slug, parentOrigin) : null
    const sessionToken = sessionState?.key === activeSessionKey ? sessionState.token : null
    const setDatePickerOpen: React.Dispatch<React.SetStateAction<Record<string, boolean>>> = (update) => {
        dispatch({ type: "datePickerOpenChanged", update })
    }

    React.useEffect(() => {
        if (!parentOrigin || !formConfig) return
        const onMessage = (event: MessageEvent<ParentMessage>) => {
            if (event.origin !== parentOrigin) return
            if (!event.data || event.data.type !== "sf:form:init") return
            ensureEmbedSession({
                slug,
                origin: event.origin,
                attribution: sanitizeAttribution(event.data.attribution),
                sessionStateRef,
                sessionRequestKeyRef,
                onSessionCreated: (nextSession) => dispatch({ type: "sessionCreated", sessionState: nextSession }),
                onSessionFailed: () => dispatch({ type: "sessionFailed" }),
            })
        }
        window.addEventListener("message", onMessage)
        postEmbedMessageToParent(parentOrigin, { type: "sf:form:ready" })

        const fallback = window.setTimeout(() => {
            ensureEmbedSession({
                slug,
                origin: parentOrigin,
                attribution: {},
                sessionStateRef,
                sessionRequestKeyRef,
                onSessionCreated: (nextSession) => dispatch({ type: "sessionCreated", sessionState: nextSession }),
                onSessionFailed: () => dispatch({ type: "sessionFailed" }),
            })
        }, 1000)

        return () => {
            window.removeEventListener("message", onMessage)
            window.clearTimeout(fallback)
        }
    }, [formConfig, parentOrigin, slug])

    React.useEffect(() => {
        if (!containerRef.current) return
        const element = containerRef.current
        const sendHeight = () => {
            postEmbedMessageToParent(parentOrigin, {
                type: "sf:form:resize",
                height: Math.ceil(element.getBoundingClientRect().height),
            })
        }
        const observer = new ResizeObserver(sendHeight)
        observer.observe(element)
        sendHeight()
        return () => observer.disconnect()
    }, [parentOrigin, formConfig, error, isLoading, isSubmitted])

    const pages = formConfig?.form_schema.pages || []
    const visibleFields: FormField[] = []
    for (const page of pages) {
        for (const field of page.fields) {
            if (evaluateCondition(field, answers)) visibleFields.push(field)
        }
    }

    const renderableFields: FormField[] = []
    for (const field of visibleFields) {
        if (field.type !== "file") renderableFields.push(field)
    }

    const updateField = (fieldKey: string, value: PublicFormAnswerValue) => {
        dispatch({ type: "answerChanged", fieldKey, value })
        postEmbedMessageToParent(parentOrigin, { type: "sf:form:started" })
    }

    const validate = (): string | null => {
        for (const field of visibleFields) {
            if (field.type === "file") {
                return "This embedded form cannot collect file uploads."
            }
            const fieldError = getFieldError(field, answers[field.key])
            if (fieldError) return fieldError
        }
        if (!sessionToken) {
            return "This form session is not ready yet."
        }
        return null
    }

    const handleSubmit = async () => {
        const validationError = validate()
        if (validationError) {
            dispatch({ type: "validationFailed", error: validationError })
            postEmbedMessageToParent(parentOrigin, { type: "sf:form:error", reason: "validation" })
            return
        }
        if (!formConfig || !sessionToken) return

        dispatch({ type: "submissionStarted" })
        try {
            const response = await submitEmbedPublicForm(slug, {
                embed_session_token: sessionToken,
                idempotency_key: buildIdempotencyKey(),
                published_version_id: formConfig.published_version_id,
                answers: asJsonObject(answers),
                attribution: {},
            })
            postEmbedMessageToParent(parentOrigin, {
                type: "sf:form:submitted",
                submissionRef: response.id,
            })
            dispatch({ type: "submissionSucceeded" })
        } catch {
            dispatch({ type: "submissionFailed" })
            postEmbedMessageToParent(parentOrigin, { type: "sf:form:error", reason: "submit" })
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
                <main className="mx-auto w-full max-w-[760px] px-4 py-4 sm:px-6 sm:py-6">
                    <section className="border border-stone-200/80 bg-white px-4 py-5 shadow-[0_18px_60px_rgba(31,38,58,0.08)] sm:px-6 sm:py-6">
                        <div className="mb-5 border-b border-stone-200/80 pb-4">
                            {formConfig.form_schema.public_eyebrow?.trim() ? (
                                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-stone-400">
                                    {formConfig.form_schema.public_eyebrow.trim()}
                                </p>
                            ) : null}
                            {formConfig.form_schema.public_title?.trim() ? (
                                <h1 className="text-[22px] font-semibold leading-tight text-stone-950">
                                    {formConfig.form_schema.public_title.trim()}
                                </h1>
                            ) : null}
                            {formConfig.form_schema.public_subtitle?.trim() ? (
                                <p className="mt-2 max-w-[54ch] text-[14px] leading-6 text-stone-600">
                                    {formConfig.form_schema.public_subtitle.trim()}
                                </p>
                            ) : null}
                        </div>

                    <div className="space-y-3.5">
                        {renderableFields.map((field) => (
                            <PublicFormFieldRenderer
                                key={field.key}
                                field={field}
                                value={answers[field.key]}
                                updateField={updateField}
                                datePickerOpen={datePickerOpen}
                                setDatePickerOpen={setDatePickerOpen}
                                density="compact"
                            />
                        ))}

                        {formConfig.form_schema.privacy_notice?.trim() ? (
                            <p className="rounded-md bg-stone-50 px-3 py-2 text-[12px] leading-5 text-stone-500">
                                {formConfig.form_schema.privacy_notice.trim()}
                            </p>
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
                            className="h-10 w-full rounded-md"
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
                    </section>
                </main>
            ) : null}
        </div>
    )
}
