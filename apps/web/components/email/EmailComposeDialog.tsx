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
import { normalizeTemplateHtml } from "@/lib/email-template-html"
import { useEmailTemplates, useEmailTemplate } from "@/lib/hooks/use-email-templates"
import { useSignaturePreview } from "@/lib/hooks/use-signature"
import { useSendSurrogateEmail, useSurrogateTemplateVariables } from "@/lib/hooks/use-surrogates"
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
const PREVIEW_FORM_LINK = "https://app.surrogacyforce.com/apply/EXAMPLE_TOKEN"
const PREVIEW_APPOINTMENT_LINK = "https://app.surrogacyforce.com/book/EXAMPLE_APPOINTMENT_SLUG"

const LEGACY_UNSUBSCRIBE_TOKEN_RE = /\{\{\s*unsubscribe_url\s*\}\}/gi
const LEGACY_UNSUBSCRIBE_ANCHOR_RE =
    /<a\b[^>]*\bhref\s*=\s*(["'])\s*\{\{\s*unsubscribe_url\s*\}\}\s*\1[^>]*>[\s\S]*?<\/a>/gi
const TEMPLATE_TOKEN_RE = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g

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

export function EmailComposeDialog({
    open,
    onOpenChange,
    surrogateData,
    onSuccess,
}: EmailComposeDialogProps) {
    const [selectedTemplate, setSelectedTemplate] = React.useState<string>("")
    const [subject, setSubject] = React.useState("")
    const [body, setBody] = React.useState("")
    const [isPreview, setIsPreview] = React.useState(true)
    const [attachmentSelection, setAttachmentSelection] = React.useState<EmailAttachmentSelectionState>({
        selectedAttachmentIds: [],
        hasBlockingAttachments: false,
        totalBytes: 0,
        errorMessage: null,
    })
    const idempotencyKeyRef = React.useRef<string | null>(null)
    const hydratedTemplateIdRef = React.useRef<string | null>(null)
    const previewEditorRef = React.useRef<HTMLDivElement | null>(null)
    const attachmentsPanelRef = React.useRef<EmailAttachmentsPanelHandle | null>(null)
    const dragDepthRef = React.useRef(0)
    const [isBodyDropActive, setIsBodyDropActive] = React.useState(false)

    // Fetch email templates list
    const { data: templates = [], isLoading: templatesLoading } = useEmailTemplates({ activeOnly: true })
    // Fetch full template when one is selected
    const { data: fullTemplate } = useEmailTemplate(selectedTemplate || null)
    const { data: personalSignaturePreview } = useSignaturePreview()
    const sendEmailMutation = useSendSurrogateEmail()
    const { data: resolvedTemplateVariables = {} } = useSurrogateTemplateVariables(surrogateData.id, {
        enabled: open && Boolean(surrogateData.id),
    })

    const resolveTemplateLabel = React.useCallback(
        (templateId: string | null) => {
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
        },
        [fullTemplate, templates]
    )

    // Update subject and body when full template loads
    React.useEffect(() => {
        if (!fullTemplate?.id) return
        if (hydratedTemplateIdRef.current === fullTemplate.id) return

        setSubject(fullTemplate.subject)
        setBody(fullTemplate.body)
        hydratedTemplateIdRef.current = fullTemplate.id
    }, [fullTemplate])

    // Reset form when dialog closes
    React.useEffect(() => {
        if (!open) {
            setSelectedTemplate("")
            setSubject("")
            setBody("")
            setIsPreview(true)
            dragDepthRef.current = 0
            setIsBodyDropActive(false)
            setAttachmentSelection({
                selectedAttachmentIds: [],
                hasBlockingAttachments: false,
                totalBytes: 0,
                errorMessage: null,
            })
            idempotencyKeyRef.current = null
            hydratedTemplateIdRef.current = null
        }
    }, [open])

    const previewVariableValues = React.useMemo(() => {
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
    }, [resolvedTemplateVariables, surrogateData])

    const replaceTemplateVariables = React.useCallback(
        (text: string) =>
            text.replace(TEMPLATE_TOKEN_RE, (match: string, variableName: string) => {
                const value = previewVariableValues[variableName]
                if (value === undefined || value === null) {
                    return match
                }
                return String(value)
            }),
        [previewVariableValues]
    )

    const sanitizePreviewHtml = React.useCallback((html: string) => {
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
    }, [])

    const syncPreviewEditorToBody = React.useCallback(() => {
        const editor = previewEditorRef.current
        if (!editor || !isPreview) return body

        const editedHtml = editor.innerHTML.trim()
        const normalizedHtml = editedHtml ? normalizeTemplateHtml(editedHtml) : ""
        const sanitizedEditedHtml = normalizedHtml ? sanitizePreviewHtml(normalizedHtml) : ""

        if (sanitizedEditedHtml !== body) {
            setBody(sanitizedEditedHtml)
        }

        return sanitizedEditedHtml
    }, [body, isPreview, sanitizePreviewHtml])

    const handleSend = async () => {
        try {
            const bodyForSend = isPreview ? syncPreviewEditorToBody() : body
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

    const handleCancel = () => {
        onOpenChange(false)
    }

    const handlePreviewToggle = React.useCallback(() => {
        if (isPreview) {
            syncPreviewEditorToBody()
        }
        setIsPreview((current) => !current)
    }, [isPreview, syncPreviewEditorToBody])

    const previewSubject = React.useMemo(
        () => replaceTemplateVariables(subject),
        [replaceTemplateVariables, subject]
    )

    const previewMessageHtml = React.useMemo(() => {
        if (!body) return ""

        let html = replaceTemplateVariables(body)
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
    }, [body, replaceTemplateVariables, sanitizePreviewHtml])

    const previewFooterHtml = React.useMemo(() => {
        const signatureHtml = personalSignaturePreview?.html || ""

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
    }, [personalSignaturePreview?.html, sanitizePreviewHtml])

    // Highlight variables in edit mode
    const renderWithHighlights = (text: string) => {
        const parts = text.split(/(\{\{[^}]+\}\})/g)
        return parts.map((part, index) => {
            if (part.match(/\{\{[^}]+\}\}/)) {
                return (
                    <span key={index} className="bg-teal-500/20 text-teal-400 px-1 py-0.5 rounded font-medium">
                        {part}
                    </span>
                )
            }
            return <span key={index}>{part}</span>
        })
    }

    const availableVariables = [
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

    const handleBodyDragEnter = React.useCallback((event: React.DragEvent<HTMLElement>) => {
        if (!dataTransferHasFiles(event.dataTransfer)) return
        event.preventDefault()
        dragDepthRef.current += 1
        setIsBodyDropActive(true)
    }, [])

    const handleBodyDragOver = React.useCallback((event: React.DragEvent<HTMLElement>) => {
        if (!dataTransferHasFiles(event.dataTransfer)) return
        event.preventDefault()
        event.dataTransfer.dropEffect = "copy"
        if (!isBodyDropActive) {
            setIsBodyDropActive(true)
        }
    }, [isBodyDropActive])

    const handleBodyDragLeave = React.useCallback((event: React.DragEvent<HTMLElement>) => {
        if (!dataTransferHasFiles(event.dataTransfer)) return
        event.preventDefault()
        dragDepthRef.current = Math.max(0, dragDepthRef.current - 1)
        if (dragDepthRef.current === 0) {
            setIsBodyDropActive(false)
        }
    }, [])

    const handleBodyDrop = React.useCallback(async (event: React.DragEvent<HTMLElement>) => {
        if (!dataTransferHasFiles(event.dataTransfer)) return
        event.preventDefault()
        dragDepthRef.current = 0
        setIsBodyDropActive(false)

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
                    {/* Template Selector */}
                    <div className="grid gap-2">
                        <Label id="email-template-label">Email Template</Label>
                        <Select value={selectedTemplate} onValueChange={(value) => setSelectedTemplate(value || "")} disabled={templatesLoading}>
                            <SelectTrigger
                                id="template"
                                className="w-full"
                                aria-label="Email Template"
                                aria-labelledby="email-template-label"
                            >
                                <SelectValue
                                    placeholder={
                                        templatesLoading
                                            ? "Loading templates..."
                                            : "Select a template..."
                                    }
                                >
                                    {(value: string | null) => resolveTemplateLabel(value)}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {templates.map((template) => {
                                    const resolvedLabel = resolveTemplateLabel(template.id)

                                    return (
                                        <SelectItem key={template.id} value={template.id}>
                                            {resolvedLabel}
                                        </SelectItem>
                                    )
                                })}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Recipient Email (Read-only) */}
                    <div className="grid gap-2">
                        <Label htmlFor="recipient">To</Label>
                        <Input
                            id="recipient"
                            name="recipient"
                            value={surrogateData.email}
                            readOnly
                            autoComplete="email"
                            spellCheck={false}
                            className="bg-muted/50 cursor-not-allowed"
                        />
                    </div>

                    <EmailAttachmentsPanel
                        ref={attachmentsPanelRef}
                        surrogateId={surrogateData.id}
                        onSelectionChange={setAttachmentSelection}
                    />

                    {/* Subject Line */}
                    <div className="grid gap-2">
                        <Label htmlFor="subject">Subject</Label>
                        <Input
                            id="subject"
                            name="subject"
                            value={subject}
                            onChange={(e) => setSubject(e.target.value)}
                            placeholder="Enter email subject..."
                            autoComplete="off"
                        />
                        {!isPreview && subject && (
                            <div className="text-xs text-muted-foreground">{renderWithHighlights(subject)}</div>
                        )}
                    </div>

                    {/* Body with Preview Toggle */}
                    <div
                        className={cn(
                            "grid gap-2 rounded-lg transition-colors",
                            isBodyDropActive && "ring-1 ring-primary/40 bg-primary/5 px-2 py-2"
                        )}
                        onDragEnter={handleBodyDragEnter}
                        onDragOver={handleBodyDragOver}
                        onDragLeave={handleBodyDragLeave}
                        onDrop={handleBodyDrop}
                    >
                        <div className="flex items-center justify-between">
                            <Label id="message-label" htmlFor={isPreview ? undefined : "body"}>
                                Message
                            </Label>
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={handlePreviewToggle}
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

                        {isBodyDropActive && (
                            <p className="text-xs font-medium text-primary">
                                Drop files to attach to this email.
                            </p>
                        )}

                        {isPreview && (
                            <div className="rounded-xl border border-input overflow-hidden">
                                <div className="bg-muted/30 border-b px-4 py-3 space-y-2">
                                    <div className="flex items-center gap-2 text-sm">
                                        <span className="font-medium text-muted-foreground w-16">To:</span>
                                        <span className="text-foreground">{surrogateData.email}</span>
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
                                        onBlur={syncPreviewEditorToBody}
                                        className="prose prose-sm prose-stone max-w-none min-h-40 rounded-md border border-transparent px-1 text-stone-900 outline-none transition-colors [&_p]:whitespace-pre-wrap focus:border-ring"
                                        dangerouslySetInnerHTML={{ __html: previewMessageHtml }}
                                    />
                                    <div className="border-t border-stone-200 pt-4">
                                        <div
                                            className="prose prose-sm prose-stone max-w-none text-stone-900 [&_p]:whitespace-pre-wrap"
                                            dangerouslySetInnerHTML={{ __html: previewFooterHtml }}
                                        />
                                    </div>
                                </div>
                                <div className="border-t bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
                                    You can edit the message directly in preview mode.
                                </div>
                            </div>
                        )}

                        {!isPreview && (
                            <Textarea
                                id="body"
                                aria-labelledby="message-label"
                                value={body}
                                onChange={(e) => setBody(e.target.value)}
                                placeholder="Enter email message..."
                                className="min-h-48 font-mono text-sm"
                            />
                        )}

                        {body && !isPreview && (
                            <div className="bg-muted/30 rounded-lg px-3 py-2 text-xs">
                                <div className="font-medium mb-2 text-muted-foreground">Available Variables:</div>
                                <div className="flex flex-wrap gap-2">
                                    {availableVariables.map((variable) => (
                                        <code key={variable} className="bg-teal-500/20 text-teal-400 px-2 py-1 rounded text-xs">
                                            {variable}
                                        </code>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Error Message */}
                    {sendEmailMutation.isError && (
                        <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg text-sm">
                            {sendEmailMutation.error instanceof Error
                                ? sendEmailMutation.error.message
                                : "Failed to send email. Please try again."}
                        </div>
                    )}

                    {/* Success Message */}
                    {sendEmailMutation.isSuccess && (
                        <div className="bg-green-500/10 text-green-600 dark:text-green-400 px-4 py-3 rounded-lg text-sm">
                            Email sent successfully!
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button
                        type="button"
                        variant="outline"
                        onClick={handleCancel}
                        disabled={sendEmailMutation.isPending}
                    >
                        Cancel
                    </Button>
                    <Button
                        type="button"
                        onClick={handleSend}
                        disabled={
                            !selectedTemplate ||
                            !subject ||
                            !body ||
                            attachmentSelection.hasBlockingAttachments ||
                            sendEmailMutation.isPending
                        }
                        className="gap-2"
                    >
                        {sendEmailMutation.isPending ? (
                            <>
                                <Loader2Icon className="size-4 animate-spin" />
                                Sending...
                            </>
                        ) : (
                            <>
                                <SendIcon className="size-4" />
                                Send Email
                            </>
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
