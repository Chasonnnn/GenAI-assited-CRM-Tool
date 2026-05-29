"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { EyeIcon, EyeOffIcon, SendIcon, Loader2Icon } from "lucide-react"
import DOMPurify from "dompurify"
import { TrustedSanitizedHtmlFragment } from "@/components/safe-html-content"
import { normalizeTemplateHtml } from "@/lib/email-template-html"
import { useEmailTemplates, useEmailTemplate } from "@/lib/hooks/use-email-templates"
import { useSignaturePreview } from "@/lib/hooks/use-signature"
import { useSendSurrogateEmail, useSurrogateTemplateVariables } from "@/lib/hooks/use-surrogates"
import type { EmailTemplate, EmailTemplateListItem } from "@/lib/api/email-templates"
import {
    EmailAttachmentsPanel,
    type EmailAttachmentSelectionState,
    type EmailAttachmentsPanelHandle,
} from "@/components/email/EmailAttachmentsPanel"
import { cn } from "@/lib/utils"

type TemplatePreviewValue = string | number | boolean | null | undefined

interface EmailComposeDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    surrogateData: {
        id: string
        email: string
        full_name: string
        surrogate_number: string
        status: string
        state?: string
        phone?: string
        [key: string]: TemplatePreviewValue
    }
    onSuccess?: () => void
}

const PREVIEW_FONT_STACK =
    '-apple-system, BlinkMacSystemFont, "Segoe UI", "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", Arial, sans-serif'
const PREVIEW_FORM_LINK = "https://app.surrogacyforce.com/intake/EXAMPLE_SLUG"
const PREVIEW_APPOINTMENT_LINK = "https://app.surrogacyforce.com/book/EXAMPLE_APPOINTMENT_SLUG"

const LEGACY_UNSUBSCRIBE_TOKEN_RE = /\{\{\s*unsubscribe_url\s*\}\}/gi
const LEGACY_UNSUBSCRIBE_ANCHOR_RE =
    /<a\b[^>]*\bhref\s*=\s*(["'])\s*\{\{\s*unsubscribe_url\s*\}\}\s*\1[^>]*>[\s\S]*?<\/a>/gi
const TEMPLATE_TOKEN_RE = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g
const TEMPLATE_HIGHLIGHT_RE = /(\{\{[^}]+\}\})/g

const AVAILABLE_VARIABLES = [
    "{{first_name}}",
    "{{full_name}}",
    "{{email}}",
    "{{phone}}",
    "{{surrogate_number}}",
    "{{status_label}}",
    "{{state}}",
    "{{owner_name}}",
    "{{form_link}}",
    "{{appointment_link}}",
    "{{org_name}}",
    "{{org_logo_url}}",
    "{{unsubscribe_url}}",
]

interface ComposeFormState {
    selectedTemplate: string
    subject: string
    body: string
    isPreview: boolean
    attachmentSelection: EmailAttachmentSelectionState
    isBodyDropActive: boolean
}

type ComposeFormAction =
    | { type: "selectTemplate"; templateId: string }
    | { type: "hydrateTemplate"; subject: string; body: string }
    | { type: "setSubject"; subject: string }
    | { type: "setBody"; body: string }
    | { type: "togglePreview"; body?: string }
    | { type: "setAttachmentSelection"; selection: EmailAttachmentSelectionState }
    | { type: "setBodyDropActive"; isActive: boolean }
    | { type: "reset" }

function createEmptyAttachmentSelection(): EmailAttachmentSelectionState {
    return {
        selectedAttachmentIds: [],
        hasBlockingAttachments: false,
        totalBytes: 0,
        errorMessage: null,
    }
}

function createInitialComposeFormState(): ComposeFormState {
    return {
        selectedTemplate: "",
        subject: "",
        body: "",
        isPreview: true,
        attachmentSelection: createEmptyAttachmentSelection(),
        isBodyDropActive: false,
    }
}

function composeFormReducer(state: ComposeFormState, action: ComposeFormAction): ComposeFormState {
    switch (action.type) {
        case "selectTemplate":
            return state.selectedTemplate === action.templateId
                ? state
                : { ...state, selectedTemplate: action.templateId }
        case "hydrateTemplate":
            return state.subject === action.subject && state.body === action.body
                ? state
                : { ...state, subject: action.subject, body: action.body }
        case "setSubject":
            return state.subject === action.subject ? state : { ...state, subject: action.subject }
        case "setBody":
            return state.body === action.body ? state : { ...state, body: action.body }
        case "togglePreview":
            return {
                ...state,
                body: action.body ?? state.body,
                isPreview: !state.isPreview,
            }
        case "setAttachmentSelection":
            return { ...state, attachmentSelection: action.selection }
        case "setBodyDropActive":
            return state.isBodyDropActive === action.isActive
                ? state
                : { ...state, isBodyDropActive: action.isActive }
        case "reset":
            return createInitialComposeFormState()
        default:
            return state
    }
}

function dataTransferHasFiles(dataTransfer: DataTransfer | null): boolean {
    if (!dataTransfer) return false
    return Array.from(dataTransfer.types ?? []).includes("Files")
}

function escapeHtml(raw: string): string {
    return raw
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;")
}

function HighlightedTemplateText({ text }: { text: string }) {
    let offset = 0

    return (
        <>
            {text.split(TEMPLATE_HIGHLIGHT_RE).map((part) => {
                if (!part) return null
                const key = `${offset}:${part}`
                offset += part.length
                const isVariable = /^\{\{[^}]+\}\}$/.test(part)

                return isVariable ? (
                    <span key={key} className="bg-teal-500/20 text-teal-400 px-1 py-0.5 rounded font-medium">
                        {part}
                    </span>
                ) : (
                    <span key={key}>{part}</span>
                )
            })}
        </>
    )
}

function sanitizePreviewHtml(html: string) {
    return DOMPurify.sanitize(html, {
        USE_PROFILES: { html: true },
        ADD_TAGS: [
            "table",
            "thead",
            "tbody",
            "tfoot",
            "tr",
            "td",
            "th",
            "colgroup",
            "col",
            "img",
            "hr",
            "div",
            "span",
            "center",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        ],
        ADD_ATTR: [
            "style",
            "class",
            "align",
            "valign",
            "width",
            "height",
            "cellpadding",
            "cellspacing",
            "border",
            "bgcolor",
            "colspan",
            "rowspan",
            "role",
            "target",
            "rel",
            "href",
            "src",
            "alt",
            "title",
        ],
    })
}

function buildPreviewVariableValues(
    surrogateData: EmailComposeDialogProps["surrogateData"],
    resolvedTemplateVariables: Record<string, string>
) {
    const fallbackValues: Record<string, string> = {}
    for (const [key, value] of Object.entries(surrogateData)) {
        if (value === undefined || value === null) continue
        fallbackValues[key] = String(value)
    }

    const fullName = fallbackValues.full_name || ""
    fallbackValues.first_name = fullName ? (fullName.trim().split(/\s+/)[0] ?? "") : ""
    fallbackValues.status_label = fallbackValues.status_label || fallbackValues.status || ""
    fallbackValues.form_link = fallbackValues.form_link || PREVIEW_FORM_LINK
    fallbackValues.appointment_link = fallbackValues.appointment_link || PREVIEW_APPOINTMENT_LINK

    return {
        ...fallbackValues,
        ...resolvedTemplateVariables,
    }
}

function replaceTemplateVariables(text: string, previewVariableValues: Record<string, string>) {
    return text.replace(TEMPLATE_TOKEN_RE, (match: string, variableName: string) => {
        const value = previewVariableValues[variableName]
        if (value === undefined || value === null) {
            return match
        }
        return String(value)
    })
}

function findUnresolvedTemplateVariables(
    texts: string[],
    previewVariableValues: Record<string, string>
) {
    const unresolved = new Set<string>()

    for (const text of texts) {
        text.replace(TEMPLATE_TOKEN_RE, (match: string, variableName: string) => {
            if (!Object.prototype.hasOwnProperty.call(previewVariableValues, variableName)) {
                unresolved.add(variableName)
            }
            return match
        })
    }

    return Array.from(unresolved).sort()
}

function buildPreviewMessageHtml(body: string, previewVariableValues: Record<string, string>) {
    if (!body) return ""

    let html = replaceTemplateVariables(body, previewVariableValues)
    html = html.replace(LEGACY_UNSUBSCRIBE_TOKEN_RE, "")
    html = html.replace(LEGACY_UNSUBSCRIBE_ANCHOR_RE, "")

    const hasHtmlTags = /<[a-z][\s\S]*>/i.test(html)
    if (!hasHtmlTags) {
        html = html
            .split(/\r?\n/)
            .map((line) =>
                line.trim()
                    ? `<p style="margin: 0 0 1em 0;">${escapeHtml(line)}</p>`
                    : `<p style="margin: 0 0 1em 0;">&nbsp;</p>`
            )
            .join("")
    } else {
        html = normalizeTemplateHtml(html)
    }

    if (!/<html\b|<body\b/i.test(html)) {
        html = `<div style="font-family: ${PREVIEW_FONT_STACK}; font-size: 16px; line-height: 24px; color: #111827;">${html}</div>`
    }

    return sanitizePreviewHtml(html)
}

function buildPreviewFooterHtml(signatureHtml: string) {
    const includeDivider = !signatureHtml
    const unsubscribeFooterHtml = `
        <div style="margin-top: 14px; font-size: 12px; color: #6b7280; ${includeDivider ? "padding-top: 16px; border-top: 1px solid #e5e7eb;" : ""}">
            <p style="margin: 0;">
                If you no longer wish to receive these emails, you can
                <a href="https://app.example.com/email/unsubscribe/preview" target="_blank" rel="noopener noreferrer" style="color: #6b7280; text-decoration: underline;">Unsubscribe</a>.
            </p>
        </div>
    `.trim()

    return sanitizePreviewHtml(`${signatureHtml}${unsubscribeFooterHtml}`)
}

function resolveTemplateLabel(
    templateId: string | null,
    templates: EmailTemplateListItem[],
    fullTemplate: EmailTemplate | null | undefined
) {
    if (!templateId) return ""

    const listTemplate = templates.find((template) => template.id === templateId)
    const selectedFullTemplate = fullTemplate?.id === templateId ? fullTemplate : null

    return (
        selectedFullTemplate?.name?.trim() ||
        listTemplate?.name?.trim() ||
        listTemplate?.subject?.trim() ||
        selectedFullTemplate?.subject?.trim() ||
        templateId
    )
}

export function EmailComposeDialog({
    open,
    onOpenChange,
    surrogateData,
    onSuccess,
}: EmailComposeDialogProps) {
    const [composeState, dispatch] = React.useReducer(
        composeFormReducer,
        undefined,
        createInitialComposeFormState
    )
    const {
        selectedTemplate,
        subject,
        body,
        isPreview,
        attachmentSelection,
        isBodyDropActive,
    } = composeState
    const idempotencyKeyRef = React.useRef<string | null>(null)
    const hydratedTemplateIdRef = React.useRef<string | null>(null)
    const previewEditorRef = React.useRef<HTMLDivElement | null>(null)
    const attachmentsPanelRef = React.useRef<EmailAttachmentsPanelHandle | null>(null)
    const dragDepthRef = React.useRef(0)

    const { data: templates = [], isLoading: templatesLoading } = useEmailTemplates({
        activeOnly: true,
        usageContext: "manual",
    })
    const { data: fullTemplate } = useEmailTemplate(selectedTemplate || null)
    const { data: personalSignaturePreview } = useSignaturePreview()
    const sendEmailMutation = useSendSurrogateEmail()
    const { data: resolvedTemplateVariables = {} } = useSurrogateTemplateVariables(surrogateData.id, {
        enabled: open && Boolean(surrogateData.id),
    })

    React.useEffect(() => {
        if (!fullTemplate?.id) return
        if (hydratedTemplateIdRef.current === fullTemplate.id) return

        hydratedTemplateIdRef.current = fullTemplate.id
        dispatch({
            type: "hydrateTemplate",
            subject: fullTemplate.subject,
            body: fullTemplate.body,
        })
    }, [fullTemplate])

    React.useEffect(() => {
        if (open) return

        dragDepthRef.current = 0
        idempotencyKeyRef.current = null
        hydratedTemplateIdRef.current = null
        dispatch({ type: "reset" })
    }, [open])

    const previewVariableValues = React.useMemo(
        () => buildPreviewVariableValues(surrogateData, resolvedTemplateVariables),
        [resolvedTemplateVariables, surrogateData]
    )
    const unresolvedTemplateVariables = React.useMemo(
        () => findUnresolvedTemplateVariables([subject, body], previewVariableValues),
        [body, previewVariableValues, subject]
    )

    const readSanitizedPreviewEditorHtml = React.useCallback(() => {
        const editor = previewEditorRef.current
        if (!editor || !isPreview) return null

        const editedHtml = editor.innerHTML.trim()
        const normalizedHtml = editedHtml ? normalizeTemplateHtml(editedHtml) : ""
        return normalizedHtml ? sanitizePreviewHtml(normalizedHtml) : ""
    }, [isPreview])

    const syncPreviewEditorToBody = React.useCallback(() => {
        const sanitizedEditedHtml = readSanitizedPreviewEditorHtml()
        if (sanitizedEditedHtml === null) return body

        if (sanitizedEditedHtml !== body) {
            dispatch({ type: "setBody", body: sanitizedEditedHtml })
        }

        return sanitizedEditedHtml
    }, [body, readSanitizedPreviewEditorHtml])

    const handleSend = async () => {
        try {
            const bodyForSend = isPreview ? syncPreviewEditorToBody() : body
            if (findUnresolvedTemplateVariables([subject, bodyForSend], previewVariableValues).length > 0) {
                return
            }
            if (!idempotencyKeyRef.current) {
                idempotencyKeyRef.current =
                    typeof crypto !== "undefined" && "randomUUID" in crypto
                        ? crypto.randomUUID()
                        : `${Date.now()}-${Math.random().toString(16).slice(2)}`
            }
            await sendEmailMutation.mutateAsync({
                surrogateId: surrogateData.id,
                data: {
                    template_id: selectedTemplate,
                    subject,
                    body: bodyForSend,
                    idempotency_key: idempotencyKeyRef.current,
                    attachment_ids: attachmentSelection.selectedAttachmentIds,
                },
            })
            onSuccess?.()
            onOpenChange(false)
        } catch (error) {
            console.error("Failed to send email:", error)
        }
    }

    const handleSelectTemplate = React.useCallback((templateId: string) => {
        dispatch({ type: "selectTemplate", templateId })
    }, [])

    const handleSubjectChange = React.useCallback((nextSubject: string) => {
        dispatch({ type: "setSubject", subject: nextSubject })
    }, [])

    const handleBodyChange = React.useCallback((nextBody: string) => {
        dispatch({ type: "setBody", body: nextBody })
    }, [])

    const handleAttachmentSelectionChange = React.useCallback((selection: EmailAttachmentSelectionState) => {
        dispatch({ type: "setAttachmentSelection", selection })
    }, [])

    const handleCancel = React.useCallback(() => {
        onOpenChange(false)
    }, [onOpenChange])

    const handlePreviewToggle = React.useCallback(() => {
        const bodyFromPreview = readSanitizedPreviewEditorHtml()
        dispatch(
            bodyFromPreview === null
                ? { type: "togglePreview" }
                : { type: "togglePreview", body: bodyFromPreview }
        )
    }, [readSanitizedPreviewEditorHtml])

    const previewSubject = React.useMemo(
        () => replaceTemplateVariables(subject, previewVariableValues),
        [previewVariableValues, subject]
    )

    const previewMessageHtml = React.useMemo(
        () => buildPreviewMessageHtml(body, previewVariableValues),
        [body, previewVariableValues]
    )

    const previewFooterHtml = React.useMemo(
        () => buildPreviewFooterHtml(personalSignaturePreview?.html || ""),
        [personalSignaturePreview?.html]
    )

    const handleBodyDragEnter = React.useCallback((event: React.DragEvent<HTMLElement>) => {
        if (!dataTransferHasFiles(event.dataTransfer)) return
        event.preventDefault()
        dragDepthRef.current += 1
        dispatch({ type: "setBodyDropActive", isActive: true })
    }, [])

    const handleBodyDragOver = React.useCallback((event: React.DragEvent<HTMLElement>) => {
        if (!dataTransferHasFiles(event.dataTransfer)) return
        event.preventDefault()
        event.dataTransfer.dropEffect = "copy"
        if (!isBodyDropActive) {
            dispatch({ type: "setBodyDropActive", isActive: true })
        }
    }, [isBodyDropActive])

    const handleBodyDragLeave = React.useCallback((event: React.DragEvent<HTMLElement>) => {
        if (!dataTransferHasFiles(event.dataTransfer)) return
        event.preventDefault()
        dragDepthRef.current = Math.max(0, dragDepthRef.current - 1)
        if (dragDepthRef.current === 0) {
            dispatch({ type: "setBodyDropActive", isActive: false })
        }
    }, [])

    const handleBodyDrop = React.useCallback(async (event: React.DragEvent<HTMLElement>) => {
        if (!dataTransferHasFiles(event.dataTransfer)) return
        event.preventDefault()
        dragDepthRef.current = 0
        dispatch({ type: "setBodyDropActive", isActive: false })

        const files = Array.from(event.dataTransfer.files ?? [])
        if (files.length === 0) return

        await attachmentsPanelRef.current?.uploadFiles(files)
    }, [])

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Send Email</DialogTitle>
                    <DialogDescription>Compose and send an email to {surrogateData.full_name}</DialogDescription>
                </DialogHeader>

                <div className="grid gap-6 py-4">
                    <TemplateSelector
                        selectedTemplate={selectedTemplate}
                        templates={templates}
                        templatesLoading={templatesLoading}
                        fullTemplate={fullTemplate}
                        onSelectTemplate={handleSelectTemplate}
                    />
                    <RecipientEmailField email={surrogateData.email} />
                    <SubjectField
                        subject={subject}
                        isPreview={isPreview}
                        onSubjectChange={handleSubjectChange}
                    />
                    <MessageComposer
                        recipientEmail={surrogateData.email}
                        body={body}
                        isPreview={isPreview}
                        isBodyDropActive={isBodyDropActive}
                        attachmentSelection={attachmentSelection}
                        previewSubject={previewSubject}
                        previewMessageHtml={previewMessageHtml}
                        previewFooterHtml={previewFooterHtml}
                        previewEditorRef={previewEditorRef}
                        onPreviewToggle={handlePreviewToggle}
                        onBodyChange={handleBodyChange}
                        onPreviewBlur={syncPreviewEditorToBody}
                        onBodyDragEnter={handleBodyDragEnter}
                        onBodyDragOver={handleBodyDragOver}
                        onBodyDragLeave={handleBodyDragLeave}
                        onBodyDrop={handleBodyDrop}
                    />
                    <MutationFeedback
                        isError={sendEmailMutation.isError}
                        isSuccess={sendEmailMutation.isSuccess}
                        error={sendEmailMutation.error}
                    />

                    <EmailAttachmentsPanel
                        ref={attachmentsPanelRef}
                        surrogateId={surrogateData.id}
                        onSelectionChange={handleAttachmentSelectionChange}
                        hideUI
                    />
                </div>

                <ComposeDialogActions
                    selectedTemplate={selectedTemplate}
                    subject={subject}
                    body={body}
                    attachmentSelection={attachmentSelection}
                    unresolvedTemplateVariables={unresolvedTemplateVariables}
                    isPending={sendEmailMutation.isPending}
                    onCancel={handleCancel}
                    onSend={handleSend}
                />
            </DialogContent>
        </Dialog>
    )
}

interface TemplateSelectorProps {
    selectedTemplate: string
    templates: EmailTemplateListItem[]
    templatesLoading: boolean
    fullTemplate: EmailTemplate | null | undefined
    onSelectTemplate: (templateId: string) => void
}

function TemplateSelector({
    selectedTemplate,
    templates,
    templatesLoading,
    fullTemplate,
    onSelectTemplate,
}: TemplateSelectorProps) {
    const getTemplateLabel = React.useCallback(
        (templateId: string | null) => resolveTemplateLabel(templateId, templates, fullTemplate),
        [fullTemplate, templates]
    )

    return (
        <div className="grid gap-2">
            <Label id="email-template-label">Email Template</Label>
            <Select
                value={selectedTemplate}
                onValueChange={(value) => onSelectTemplate(value || "")}
                disabled={templatesLoading}
            >
                <SelectTrigger
                    id="template"
                    className="w-full"
                    aria-label="Email Template"
                    aria-labelledby="email-template-label"
                >
                    <SelectValue
                        placeholder={templatesLoading ? "Loading templates..." : "Select a template..."}
                    >
                        {(value: string | null) => getTemplateLabel(value)}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {templates.map((template) => {
                        const resolvedLabel = getTemplateLabel(template.id)

                        return (
                            <SelectItem key={template.id} value={template.id}>
                                {resolvedLabel}
                            </SelectItem>
                        )
                    })}
                </SelectContent>
            </Select>
        </div>
    )
}

function RecipientEmailField({ email }: { email: string }) {
    return (
        <div className="grid gap-2">
            <Label htmlFor="recipient">To</Label>
            <Input
                id="recipient"
                name="recipient"
                value={email}
                readOnly
                autoComplete="email"
                spellCheck={false}
                className="bg-muted/50 cursor-not-allowed"
            />
        </div>
    )
}

interface SubjectFieldProps {
    subject: string
    isPreview: boolean
    onSubjectChange: (subject: string) => void
}

function SubjectField({ subject, isPreview, onSubjectChange }: SubjectFieldProps) {
    return (
        <div className="grid gap-2">
            <Label htmlFor="subject">Subject</Label>
            <Input
                id="subject"
                name="subject"
                value={subject}
                onChange={(event) => onSubjectChange(event.target.value)}
                placeholder="Enter email subject..."
                autoComplete="off"
            />
            {!isPreview && subject && (
                <div className="text-xs text-muted-foreground">
                    <HighlightedTemplateText text={subject} />
                </div>
            )}
        </div>
    )
}

interface MessageComposerProps {
    recipientEmail: string
    body: string
    isPreview: boolean
    isBodyDropActive: boolean
    attachmentSelection: EmailAttachmentSelectionState
    previewSubject: string
    previewMessageHtml: string
    previewFooterHtml: string
    previewEditorRef: React.RefObject<HTMLDivElement | null>
    onPreviewToggle: () => void
    onBodyChange: (body: string) => void
    onPreviewBlur: () => void
    onBodyDragEnter: React.DragEventHandler<HTMLElement>
    onBodyDragOver: React.DragEventHandler<HTMLElement>
    onBodyDragLeave: React.DragEventHandler<HTMLElement>
    onBodyDrop: React.DragEventHandler<HTMLElement>
}

function MessageComposer({
    recipientEmail,
    body,
    isPreview,
    isBodyDropActive,
    attachmentSelection,
    previewSubject,
    previewMessageHtml,
    previewFooterHtml,
    previewEditorRef,
    onPreviewToggle,
    onBodyChange,
    onPreviewBlur,
    onBodyDragEnter,
    onBodyDragOver,
    onBodyDragLeave,
    onBodyDrop,
}: MessageComposerProps) {
    return (
        <div
            className={cn(
                "grid gap-2 rounded-lg transition-colors",
                isBodyDropActive && "ring-1 ring-primary/40 bg-primary/5 px-2 py-2"
            )}
            onDragEnter={onBodyDragEnter}
            onDragOver={onBodyDragOver}
            onDragLeave={onBodyDragLeave}
            onDrop={onBodyDrop}
        >
            <MessageHeader isPreview={isPreview} onPreviewToggle={onPreviewToggle} />
            <AttachmentDropStatus
                attachmentSelection={attachmentSelection}
                isBodyDropActive={isBodyDropActive}
            />

            {isPreview ? (
                <MessagePreview
                    recipientEmail={recipientEmail}
                    previewSubject={previewSubject}
                    previewMessageHtml={previewMessageHtml}
                    previewFooterHtml={previewFooterHtml}
                    previewEditorRef={previewEditorRef}
                    onPreviewBlur={onPreviewBlur}
                />
            ) : (
                <Textarea
                    id="body"
                    aria-labelledby="message-label"
                    value={body}
                    onChange={(event) => onBodyChange(event.target.value)}
                    placeholder="Enter email message..."
                    className="min-h-48 font-mono text-sm"
                />
            )}

            {body && !isPreview && <TemplateVariableHints />}
        </div>
    )
}

function MessageHeader({
    isPreview,
    onPreviewToggle,
}: {
    isPreview: boolean
    onPreviewToggle: () => void
}) {
    return (
        <div className="flex items-center justify-between">
            <Label id="message-label" htmlFor={isPreview ? undefined : "body"}>
                Message
            </Label>
            <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onPreviewToggle}
                className="h-7 gap-2"
            >
                {isPreview ? (
                    <>
                        <EyeOffIcon className="size-4" />
                        Edit HTML
                    </>
                ) : (
                    <>
                        <EyeIcon className="size-4" />
                        Show Preview
                    </>
                )}
            </Button>
        </div>
    )
}

function AttachmentDropStatus({
    attachmentSelection,
    isBodyDropActive,
}: {
    attachmentSelection: EmailAttachmentSelectionState
    isBodyDropActive: boolean
}) {
    const attachmentCount = attachmentSelection.selectedAttachmentIds.length

    return (
        <>
            <p className="text-xs text-muted-foreground">
                Drag and drop files into the message area to attach.
            </p>
            {attachmentCount > 0 && (
                <p className="text-xs text-muted-foreground">
                    {attachmentCount} attachment{attachmentCount === 1 ? "" : "s"} ready to send
                </p>
            )}
            {attachmentSelection.errorMessage && (
                <p className="text-xs text-destructive">{attachmentSelection.errorMessage}</p>
            )}
            {isBodyDropActive && (
                <p className="text-xs font-medium text-primary">
                    Drop files to attach to this email.
                </p>
            )}
        </>
    )
}

interface MessagePreviewProps {
    recipientEmail: string
    previewSubject: string
    previewMessageHtml: string
    previewFooterHtml: string
    previewEditorRef: React.RefObject<HTMLDivElement | null>
    onPreviewBlur: () => void
}

function MessagePreview({
    recipientEmail,
    previewSubject,
    previewMessageHtml,
    previewFooterHtml,
    previewEditorRef,
    onPreviewBlur,
}: MessagePreviewProps) {
    return (
        <div className="rounded-xl border border-input overflow-hidden">
            <div className="bg-muted/30 border-b px-4 py-3 space-y-2">
                <div className="flex items-center gap-2 text-sm">
                    <span className="font-medium text-muted-foreground w-16">To:</span>
                    <span className="text-foreground">{recipientEmail}</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                    <span className="font-medium text-muted-foreground w-16">Subject:</span>
                    <span className="font-medium text-foreground">{previewSubject}</span>
                </div>
            </div>
            <div className="bg-white p-4 space-y-4">
                <div
                    ref={previewEditorRef}
                    role="textbox"
                    aria-label="Message preview editor"
                    aria-labelledby="message-label"
                    aria-multiline="true"
                    contentEditable
                    suppressContentEditableWarning
                    onBlur={onPreviewBlur}
                    className="prose prose-sm prose-stone max-w-none min-h-40 rounded-md border border-transparent px-1 text-stone-900 outline-none transition-colors [&_p]:whitespace-pre-wrap focus:border-ring"
                >
                    <TrustedSanitizedHtmlFragment html={previewMessageHtml} />
                </div>
                <div className="border-t border-stone-200 pt-4">
                    <div className="prose prose-sm prose-stone max-w-none text-stone-900 [&_p]:whitespace-pre-wrap">
                        <TrustedSanitizedHtmlFragment html={previewFooterHtml} />
                    </div>
                </div>
            </div>
            <div className="border-t bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
                You can edit the message directly in preview mode.
            </div>
        </div>
    )
}

function TemplateVariableHints() {
    return (
        <div className="bg-muted/30 rounded-lg px-3 py-2 text-xs">
            <div className="font-medium mb-2 text-muted-foreground">Available Variables:</div>
            <div className="flex flex-wrap gap-2">
                {AVAILABLE_VARIABLES.map((variable) => (
                    <code
                        key={variable}
                        className="bg-teal-500/20 text-teal-400 px-2 py-1 rounded text-xs"
                    >
                        {variable}
                    </code>
                ))}
            </div>
        </div>
    )
}

function MutationFeedback({
    isError,
    isSuccess,
    error,
}: {
    isError: boolean
    isSuccess: boolean
    error: unknown
}) {
    return (
        <>
            {isError && (
                <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg text-sm">
                    {error instanceof Error ? error.message : "Failed to send email. Please try again."}
                </div>
            )}
            {isSuccess && (
                <div className="bg-green-500/10 text-green-600 dark:text-green-400 px-4 py-3 rounded-lg text-sm">
                    Email sent successfully!
                </div>
            )}
        </>
    )
}

interface ComposeDialogActionsProps {
    selectedTemplate: string
    subject: string
    body: string
    attachmentSelection: EmailAttachmentSelectionState
    unresolvedTemplateVariables: string[]
    isPending: boolean
    onCancel: () => void
    onSend: () => void
}

function ComposeDialogActions({
    selectedTemplate,
    subject,
    body,
    attachmentSelection,
    unresolvedTemplateVariables,
    isPending,
    onCancel,
    onSend,
}: ComposeDialogActionsProps) {
    const sendDisabled =
        !selectedTemplate ||
        !subject ||
        !body ||
        attachmentSelection.hasBlockingAttachments ||
        unresolvedTemplateVariables.length > 0 ||
        isPending

    return (
        <div className="space-y-3">
            {unresolvedTemplateVariables.length > 0 && (
                <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                    This template includes unsupported template fields: {unresolvedTemplateVariables.join(", ")}.
                    Choose a different template or remove those fields before sending.
                </p>
            )}
            <DialogFooter>
                <Button
                    type="button"
                    variant="outline"
                    onClick={onCancel}
                    disabled={isPending}
                >
                    Cancel
                </Button>
                <Button
                    type="button"
                    onClick={onSend}
                    disabled={sendDisabled}
                    className="gap-2"
                >
                    {isPending ? (
                        <>
                            <Loader2Icon className="size-4 animate-spin" />
                            Sending&hellip;
                        </>
                    ) : (
                        <>
                            <SendIcon className="size-4" />
                            Send Email
                        </>
                    )}
                </Button>
            </DialogFooter>
        </div>
    )
}
