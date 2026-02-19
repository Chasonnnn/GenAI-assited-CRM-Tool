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
import { useOrgSignaturePreview, useSignaturePreview } from "@/lib/hooks/use-signature"
import { useSendSurrogateEmail } from "@/lib/hooks/use-surrogates"

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
    }
    onSuccess?: () => void
}

const PREVIEW_FONT_STACK =
    '-apple-system, BlinkMacSystemFont, "Segoe UI", "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", Arial, sans-serif'

const LEGACY_UNSUBSCRIBE_TOKEN_RE = /\{\{\s*unsubscribe_url\s*\}\}/gi
const LEGACY_UNSUBSCRIBE_ANCHOR_RE =
    /<a\b[^>]*\bhref\s*=\s*(["'])\s*\{\{\s*unsubscribe_url\s*\}\}\s*\1[^>]*>[\s\S]*?<\/a>/gi

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
    const idempotencyKeyRef = React.useRef<string | null>(null)
    const hydratedTemplateIdRef = React.useRef<string | null>(null)

    // Fetch email templates list
    const { data: templates = [], isLoading: templatesLoading } = useEmailTemplates({ activeOnly: true })
    // Fetch full template when one is selected
    const { data: fullTemplate } = useEmailTemplate(selectedTemplate || null)
    const { data: personalSignaturePreview } = useSignaturePreview()
    const { data: orgSignaturePreview } = useOrgSignaturePreview({
        enabled: fullTemplate?.scope !== "personal",
        mode: "org_only",
    })
    const sendEmailMutation = useSendSurrogateEmail()

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
            idempotencyKeyRef.current = null
            hydratedTemplateIdRef.current = null
        }
    }, [open])

    const handleSend = async () => {
        try {
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
                    body,
                    idempotency_key: idempotencyKeyRef.current,
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

    const replaceTemplateVariables = React.useCallback(
        (text: string) => {
            return text
            .replace(/\{\{full_name\}\}/g, surrogateData.full_name)
            .replace(/\{\{surrogate_number\}\}/g, surrogateData.surrogate_number)
            .replace(/\{\{status_label\}\}/g, surrogateData.status)
            .replace(/\{\{state\}\}/g, surrogateData.state || "")
            .replace(/\{\{email\}\}/g, surrogateData.email)
            .replace(/\{\{phone\}\}/g, surrogateData.phone || "")
            .replace(/\{\{owner_name\}\}/g, "")
            .replace(/\{\{org_name\}\}/g, "")
        },
        [surrogateData]
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

    const previewSubject = React.useMemo(
        () => replaceTemplateVariables(subject),
        [replaceTemplateVariables, subject]
    )

    const previewBodyHtml = React.useMemo(() => {
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

        const signatureHtml =
            fullTemplate?.scope === "personal"
                ? (personalSignaturePreview?.html || "")
                : (orgSignaturePreview?.html || "")

        const includeDivider = !signatureHtml
        const unsubscribeFooterHtml = `
            <div style="margin-top: 14px; font-size: 12px; color: #6b7280; ${includeDivider ? "padding-top: 16px; border-top: 1px solid #e5e7eb;" : ""}">
                <p style="margin: 0;">
                    If you no longer wish to receive these emails, you can
                    <a href="https://app.example.com/email/unsubscribe/preview" target="_blank" rel="noopener noreferrer" style="color: #6b7280; text-decoration: underline;">Unsubscribe</a>.
                </p>
            </div>
        `.trim()

        const insertion = `${signatureHtml}${unsubscribeFooterHtml}`
        if (/<\/body\s*>/i.test(html)) {
            html = html.replace(/<\/body\s*>/i, `${insertion}</body>`)
        } else if (/<\/html\s*>/i.test(html)) {
            html = html.replace(/<\/html\s*>/i, `${insertion}</html>`)
        } else {
            html = `${html}${insertion}`
        }

        return sanitizePreviewHtml(html)
    }, [
        body,
        fullTemplate?.scope,
        orgSignaturePreview?.html,
        personalSignaturePreview?.html,
        replaceTemplateVariables,
        sanitizePreviewHtml,
    ])

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
        "{{full_name}}",
        "{{email}}",
        "{{phone}}",
        "{{surrogate_number}}",
        "{{status_label}}",
        "{{state}}",
        "{{owner_name}}",
        "{{org_name}}",
    ]

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
                        <Label htmlFor="template">Email Template</Label>
                        <Select value={selectedTemplate} onValueChange={(value) => setSelectedTemplate(value || "")} disabled={templatesLoading}>
                            <SelectTrigger id="template" className="w-full">
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
                    <div className="grid gap-2">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="body">Message</Label>
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => setIsPreview(!isPreview)}
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
                                <div className="bg-white p-4">
                                    <div
                                        className="prose prose-sm prose-stone max-w-none text-stone-900 [&_p]:whitespace-pre-wrap"
                                        dangerouslySetInnerHTML={{ __html: previewBodyHtml }}
                                    />
                                </div>
                            </div>
                        )}

                        {!isPreview && (
                            <Textarea
                                id="body"
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
                        disabled={!selectedTemplate || !subject || !body || sendEmailMutation.isPending}
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
