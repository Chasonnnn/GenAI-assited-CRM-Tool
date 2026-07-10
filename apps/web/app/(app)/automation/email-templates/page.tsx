"use client"

import * as React from "react"
import NextImage from "next/image"
import { useState, useRef, useEffect, useReducer } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
    DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    PlusIcon,
    MoreVerticalIcon,
    EditIcon,
    TrashIcon,
    EyeIcon,
    CameraIcon,
    Loader2Icon,
    CodeIcon,
    XIcon,
    LinkIcon,
    ImageIcon,
    CopyIcon,
    ShareIcon,
    UserIcon,
    BuildingIcon,
    LayoutTemplateIcon,
    LockIcon,
    SparklesIcon,
    AlertTriangleIcon,
    SendIcon,
} from "lucide-react"
import DOMPurify from "dompurify"
import {
    useEmailTemplates,
    useEmailTemplate,
    useCreateEmailTemplate,
    useUpdateEmailTemplate,
    useDeleteEmailTemplate,
    useCopyTemplateToPersonal,
    useShareTemplateWithOrg,
    useSendTestEmailTemplate,
    useEmailTemplateVariables,
    useEmailTemplateLibrary,
    useEmailTemplateLibraryItem,
    useCopyTemplateFromLibrary,
} from "@/lib/hooks/use-email-templates"
import {
    useUserSignature,
    useUpdateUserSignature,
    useSignaturePreview,
    useUploadSignaturePhoto,
    useDeleteSignaturePhoto,
    useOrgSignaturePreview,
} from "@/lib/hooks/use-signature"
import { getSignaturePreview } from "@/lib/api/signature"
import { RichTextEditor, type RichTextEditorHandle } from "@/components/rich-text-editor"
import { TemplateVariablePicker } from "@/components/email/TemplateVariablePicker"
import type { EmailTemplateListItem, EmailTemplateScope, EmailTemplateLibraryItem } from "@/lib/api/email-templates"
import { toast } from "@/components/ui/toast"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import Link from "@/components/app-link"
import { normalizeTemplateHtml } from "@/lib/email-template-html"
import { formatDate } from "@/lib/formatters"
import { insertAtCursor } from "@/lib/insert-at-cursor"
import { SafeHtmlContent } from "@/components/safe-html-content"

// =============================================================================
// Signature Override Field Component
// =============================================================================

interface SignatureOverrideFieldProps {
    id: string
    label: string
    value: string
    profileDefault: string | null
    onChange: (value: string) => void
    onClear: () => void
    placeholder?: string
    type?: string
}

function SignatureOverrideField({
    id,
    label,
    value,
    profileDefault,
    onChange,
    onClear,
    placeholder,
    type = "text",
}: SignatureOverrideFieldProps) {
    const hasOverride = value !== ""
    const displayPlaceholder = profileDefault
        ? `Defaults to: ${profileDefault}`
        : placeholder || `Enter ${label.toLowerCase()}`

    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <Label htmlFor={id} className="text-sm font-medium">
                    {label}
                </Label>
                {hasOverride && (
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
                        onClick={onClear}
                    >
                        <XIcon className="mr-1 size-3" />
                        Clear
                    </Button>
                )}
            </div>
            <Input
                id={id}
                type={type}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={displayPlaceholder}
                className={hasOverride ? "border-primary/50" : ""}
            />
            {!hasOverride && profileDefault && (
                <p className="text-xs text-muted-foreground">
                    Using profile: <span className="font-medium">{profileDefault}</span>
                </p>
            )}
            {hasOverride && (
                <p className="text-xs text-primary">
                    Custom signature value
                </p>
            )}
        </div>
    )
}

// =============================================================================
// Signature Photo Upload Component
// =============================================================================

interface SignaturePhotoFieldProps {
    signaturePhotoUrl: string | null
    profilePhotoUrl: string | null
    profileName: string
    avatarAction: React.ReactNode
    customPhotoAction?: React.ReactNode
}

function SignaturePhotoField({
    signaturePhotoUrl,
    profilePhotoUrl,
    profileName,
    avatarAction,
    customPhotoAction,
}: SignaturePhotoFieldProps) {
    const hasSignaturePhoto = !!signaturePhotoUrl
    const displayPhoto = signaturePhotoUrl || profilePhotoUrl

    const initials = profileName
        ?.split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2) || "??"

    return (
        <div className="space-y-3">
            <Label className="text-sm font-medium">Signature Photo</Label>
            <div className="flex items-center gap-4">
                <div className="relative group">
                    <Avatar className="size-20 border-2 border-border">
                        <AvatarImage src={displayPhoto || undefined} />
                        <AvatarFallback className="text-lg bg-muted">
                            {initials}
                        </AvatarFallback>
                    </Avatar>
                    {avatarAction}
                </div>
                <div className="flex-1 space-y-1">
                    {hasSignaturePhoto ? (
                        <>
                            <p className="text-sm font-medium text-primary">
                                Custom signature photo
                            </p>
                            <p className="text-xs text-muted-foreground">
                                Different from your profile avatar
                            </p>
                            {customPhotoAction}
                        </>
                    ) : (
                        <>
                            <p className="text-sm text-muted-foreground">
                                {profilePhotoUrl ? "Using profile photo" : "No photo set"}
                            </p>
                            <p className="text-xs text-muted-foreground">
                                Click camera to upload a signature-specific photo
                            </p>
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}

// =============================================================================
// Signature Preview Component
// =============================================================================

function SignaturePreviewComponent() {
    const { data: preview, isLoading } = useSignaturePreview()

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-8">
                <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!preview?.html) {
        return (
            <div className="flex flex-col items-center justify-center py-8 text-center">
                <ImageIcon className="size-10 text-muted-foreground/40 mb-2" />
                <p className="text-sm text-muted-foreground">
                    No signature configured yet
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                    Add your details and save to see preview
                </p>
            </div>
        )
    }

    return (
        <SafeHtmlContent
            html={preview.html}
            className="prose prose-sm prose-stone max-w-none text-stone-900"
        />
    )
}

// =============================================================================
// Org Signature Preview Component
// =============================================================================

function OrgSignaturePreviewComponent() {
    const { data: preview, isLoading } = useOrgSignaturePreview({ enabled: true, mode: "org_only" })

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-8">
                <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!preview?.html) {
        return (
            <div className="flex flex-col items-center justify-center py-8 text-center">
                <ImageIcon className="size-10 text-muted-foreground/40 mb-2" />
                <p className="text-sm text-muted-foreground">
                    No organization signature configured yet
                </p>
            </div>
        )
    }

    return (
        <SafeHtmlContent
            html={preview.html}
            className="prose prose-sm prose-stone max-w-none text-stone-900"
        />
    )
}

// =============================================================================
// Available template variables
// =============================================================================

type EditorMode = "visual" | "html"
type ActiveInsertionTarget = "subject" | "body_html" | "body_visual" | null
type TextSelectionRef = React.MutableRefObject<{ start: number; end: number } | null>
const PREVIEW_FONT_STACK =
    '-apple-system, BlinkMacSystemFont, "Segoe UI", "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", Arial, sans-serif'

type EmailTemplateEditorState = {
    isOpen: boolean
    template: EmailTemplateListItem | null
    name: string
    subject: string
    bodyOverride: string | null
    bodyModeOverride: EditorMode | null
    scope: EmailTemplateScope
}

type EmailTemplateEditorAction =
    | { type: "openCreate"; scope: EmailTemplateScope }
    | { type: "openEdit"; template: EmailTemplateListItem }
    | { type: "close" }
    | { type: "changeName"; value: string }
    | { type: "changeSubject"; value: string }
    | { type: "changeBody"; value: string }
    | { type: "changeBodyMode"; value: EditorMode }

const initialEmailTemplateEditorState: EmailTemplateEditorState = {
    isOpen: false,
    template: null,
    name: "",
    subject: "",
    bodyOverride: null,
    bodyModeOverride: null,
    scope: "personal",
}

function emailTemplateEditorReducer(
    state: EmailTemplateEditorState,
    action: EmailTemplateEditorAction,
): EmailTemplateEditorState {
    switch (action.type) {
        case "openCreate":
            return {
                ...initialEmailTemplateEditorState,
                isOpen: true,
                scope: action.scope,
            }
        case "openEdit":
            return {
                isOpen: true,
                template: action.template,
                name: action.template.name,
                subject: action.template.subject,
                bodyOverride: null,
                bodyModeOverride: null,
                scope: action.template.scope,
            }
        case "close":
            return {
                ...state,
                isOpen: false,
            }
        case "changeName":
            return { ...state, name: action.value }
        case "changeSubject":
            return { ...state, subject: action.value }
        case "changeBody":
            return { ...state, bodyOverride: action.value }
        case "changeBodyMode":
            return { ...state, bodyModeOverride: action.value }
        default:
            return state
    }
}

type SignatureDraftState = {
    name: string
    title: string
    phone: string
    linkedin: string
    twitter: string
    instagram: string
}

type SignatureDraftField = keyof SignatureDraftState

type SignatureDraftAction =
    | { type: "hydrate"; draft: SignatureDraftState }
    | { type: "changeField"; field: SignatureDraftField; value: string }

const initialSignatureDraftState: SignatureDraftState = {
    name: "",
    title: "",
    phone: "",
    linkedin: "",
    twitter: "",
    instagram: "",
}

function createSignatureDraftState(
    signatureData: {
        signature_name?: string | null
        signature_title?: string | null
        signature_phone?: string | null
        signature_linkedin?: string | null
        signature_twitter?: string | null
        signature_instagram?: string | null
    } | null | undefined,
): SignatureDraftState {
    return {
        name: signatureData?.signature_name || "",
        title: signatureData?.signature_title || "",
        phone: signatureData?.signature_phone || "",
        linkedin: signatureData?.signature_linkedin || "",
        twitter: signatureData?.signature_twitter || "",
        instagram: signatureData?.signature_instagram || "",
    }
}

function signatureDraftReducer(
    state: SignatureDraftState,
    action: SignatureDraftAction,
): SignatureDraftState {
    switch (action.type) {
        case "hydrate":
            return action.draft
        case "changeField":
            return { ...state, [action.field]: action.value }
        default:
            return state
    }
}

type TestSendDialogState = {
    isOpen: boolean
    target: EmailTemplateListItem | null
    toEmail: string
    ignoreOptOut: boolean
    variables: Record<string, string>
}

type TestSendDialogAction =
    | { type: "open"; target: EmailTemplateListItem; toEmail: string }
    | { type: "close" }
    | { type: "changeToEmail"; value: string }
    | { type: "changeIgnoreOptOut"; value: boolean }
    | { type: "initializeVariables"; variables: Record<string, string> }
    | { type: "changeVariable"; name: string; value: string }

const initialTestSendDialogState: TestSendDialogState = {
    isOpen: false,
    target: null,
    toEmail: "",
    ignoreOptOut: false,
    variables: {},
}

function testSendDialogReducer(
    state: TestSendDialogState,
    action: TestSendDialogAction,
): TestSendDialogState {
    switch (action.type) {
        case "open":
            return {
                isOpen: true,
                target: action.target,
                toEmail: action.toEmail,
                ignoreOptOut: false,
                variables: {},
            }
        case "close":
            return initialTestSendDialogState
        case "changeToEmail":
            return { ...state, toEmail: action.value }
        case "changeIgnoreOptOut":
            return { ...state, ignoreOptOut: action.value }
        case "initializeVariables":
            if (Object.keys(state.variables).length > 0) return state
            return { ...state, variables: action.variables }
        case "changeVariable":
            return {
                ...state,
                variables: {
                    ...state.variables,
                    [action.name]: action.value,
                },
            }
        default:
            return state
    }
}

function hasAdvancedTemplateHtml(body: string | null | undefined) {
    return /<table|<tbody|<thead|<tr|<td|<img|<div/i.test(body || "")
}

function getTemplateBodyMode(body: string | null | undefined): EditorMode {
    return hasAdvancedTemplateHtml(body) ? "html" : "visual"
}

function extractTemplateVariables(text: string): string[] {
    if (!text) return []
    const matches = text.match(/{{\s*([a-zA-Z0-9_]+)\s*}}/g) ?? []
    const variables = matches.map((match) => match.replace(/{{\s*|\s*}}/g, ""))
    return Array.from(new Set(variables))
}

function sanitizeTemplateHtml(html: string) {
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

function buildTestVariableSample(
    variableName: string,
    context: {
        toEmail: string
        ownerName: string | null | undefined
        orgName: string | null | undefined
    }
): string {
    switch (variableName) {
        case "first_name":
            return "Jordan"
        case "full_name":
            return "Jordan Smith"
        case "email":
            return context.toEmail
        case "phone":
            return "(555) 555-5555"
        case "surrogate_number":
            return "S10001"
        case "intended_parent_number":
            return "I10001"
        case "status_label":
            return "Pre-Qualified"
        case "state":
            return "CA"
        case "owner_name":
            return context.ownerName || "Case Manager"
        case "form_link":
            return "https://app.surrogacyforce.com/intake/EXAMPLE_SLUG"
        case "appointment_link":
            return "https://app.surrogacyforce.com/book/EXAMPLE_APPOINTMENT_SLUG"
        case "appointment_manage_url":
            return "https://app.surrogacyforce.com/book/self-service/EXAMPLE_ORG/manage/EXAMPLE_TOKEN"
        case "appointment_reschedule_url":
            return "https://app.surrogacyforce.com/book/self-service/EXAMPLE_ORG/reschedule/EXAMPLE_TOKEN"
        case "appointment_cancel_url":
            return "https://app.surrogacyforce.com/book/self-service/EXAMPLE_ORG/cancel/EXAMPLE_TOKEN"
        case "appointment_date":
            return "2026-01-01"
        case "appointment_time":
            return "09:00"
        case "appointment_location":
            return "Zoom"
        case "org_name":
            return context.orgName || ""
        case "org_logo_url":
            return ""
        default:
            return `TEST_${variableName.toUpperCase()}`
    }
}

function recordSelection(el: HTMLInputElement | HTMLTextAreaElement, ref: TextSelectionRef) {
    ref.current = {
        start: el.selectionStart ?? el.value.length,
        end: el.selectionEnd ?? el.value.length,
    }
}

function insertIntoTextControl(
    el: HTMLInputElement | HTMLTextAreaElement | null,
    selectionRef: TextSelectionRef,
    setValue: React.Dispatch<React.SetStateAction<string>>,
    token: string
) {
    if (!el) {
        setValue((prev) => `${prev}${token}`)
        return
    }
    const selection = selectionRef.current ?? {
        start: el.selectionStart ?? el.value.length,
        end: el.selectionEnd ?? el.value.length,
    }
    const result = insertAtCursor(el.value, token, selection.start, selection.end)
    setValue(result.nextValue)
    requestAnimationFrame(() => {
        el.focus()
        el.setSelectionRange(result.nextSelectionStart, result.nextSelectionEnd)
        selectionRef.current = { start: result.nextSelectionStart, end: result.nextSelectionEnd }
    })
}

function buildPreviewHtml(
    rawHtml: string,
    options: {
        orgSignatureCompanyName: string | null | undefined
        previewScope: EmailTemplateScope
        personalSignatureHtml: string | null | undefined
        orgSignatureHtml: string | null | undefined
    }
) {
    let html = rawHtml
        .replace(/\{\{full_name\}\}/g, "John Smith")
        .replace(/\{\{email\}\}/g, "john@example.com")
        .replace(/\{\{phone\}\}/g, "(555) 123-4567")
        .replace(/\{\{surrogate_number\}\}/g, "S10001")
        .replace(/\{\{status_label\}\}/g, "Pre-Qualified")
        .replace(/\{\{owner_name\}\}/g, "Sara Manager")
        .replace(/\{\{form_link\}\}/g, "https://app.surrogacyforce.com/intake/EXAMPLE_SLUG")
        .replace(/\{\{appointment_link\}\}/g, "https://app.surrogacyforce.com/book/EXAMPLE_APPOINTMENT_SLUG")
        .replace(
            /\{\{appointment_manage_url\}\}/g,
            "https://app.surrogacyforce.com/book/self-service/EXAMPLE_ORG/manage/EXAMPLE_TOKEN"
        )
        .replace(
            /\{\{appointment_reschedule_url\}\}/g,
            "https://app.surrogacyforce.com/book/self-service/EXAMPLE_ORG/reschedule/EXAMPLE_TOKEN"
        )
        .replace(
            /\{\{appointment_cancel_url\}\}/g,
            "https://app.surrogacyforce.com/book/self-service/EXAMPLE_ORG/cancel/EXAMPLE_TOKEN"
        )
        .replace(/\{\{org_name\}\}/g, options.orgSignatureCompanyName || "ABC Surrogacy")
        .replace(/\{\{appointment_date\}\}/g, "January 15, 2025")
        .replace(/\{\{appointment_time\}\}/g, "2:00 PM PST")
        .replace(/\{\{appointment_location\}\}/g, "Virtual Appointment")
        .replace(/\{\{\s*unsubscribe_url\s*\}\}/g, "")

    html = html.replace(
        /<a\b[^>]*\bhref\s*=\s*(["'])\s*\{\{\s*unsubscribe_url\s*\}\}\s*\1[^>]*>[\s\S]*?<\/a>/gi,
        ""
    )

    const hasHtmlTags = /<[a-z][\s\S]*>/i.test(html)
    if (!hasHtmlTags) {
        const lines = html.split(/\n/)
        html = lines
            .map((line) => {
                if (!line.trim()) {
                    return `<p style="margin: 0 0 1em 0;">&nbsp;</p>`
                }
                return `<p style="margin: 0 0 1em 0;">${line}</p>`
            })
            .join("")
    } else {
        html = normalizeTemplateHtml(html)
    }

    if (!/<html\b|<body\b/i.test(html)) {
        html = `<div style="font-family: ${PREVIEW_FONT_STACK}; font-size: 16px; line-height: 24px; color: #111827;">${html}</div>`
    }

    const signatureHtml = options.previewScope === "personal"
        ? options.personalSignatureHtml || ""
        : options.orgSignatureHtml || ""
    const unsubscribeUrl = "https://app.surrogacyforce.com/email/unsubscribe/EXAMPLE"
    const includeDivider = !signatureHtml
    const unsubscribeFooterHtml = `
        <div style="margin-top: 14px; font-size: 12px; color: #6b7280; ${includeDivider ? "padding-top: 16px; border-top: 1px solid #e5e7eb;" : ""}">
            <p style="margin: 0;">
                Manage email preferences:
                <a href="${unsubscribeUrl}" target="_blank" style="color: #2563eb; text-decoration: none;">Unsubscribe</a>
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

    return sanitizeTemplateHtml(html)
}

async function handleCopySignatureHtml() {
    try {
        const data = await getSignaturePreview()
        const html = data.html || ""

        try {
            await navigator.clipboard.writeText(html)
            toast.success("Signature HTML copied to clipboard!")
        } catch {
            const textarea = document.createElement("textarea")
            textarea.value = html
            document.body.appendChild(textarea)
            textarea.select()
            document.execCommand("copy")
            document.body.removeChild(textarea)
            toast.success("Signature HTML copied to clipboard!")
        }
    } catch (error) {
        console.error("Failed to copy signature:", error)
    }
}

// =============================================================================
// Template Card Component
// =============================================================================

interface TemplateCardProps {
    template: EmailTemplateListItem
    controls: TemplateCardControls
}

type TemplateCardActionKind = "send_test" | "edit" | "copy" | "share" | "delete"
type TemplateCardActionGroup = "test" | "edit" | "share" | "danger"

type TemplateCardActionConfig = {
    group: TemplateCardActionGroup
    label: string
}

type TemplateCardControls =
    | {
        kind: "actions"
        actions: TemplateCardActionKind[]
        onAction: (action: TemplateCardActionKind) => void
    }
    | { kind: "read_only" }

function getTemplateCardActionConfig(kind: TemplateCardActionKind): TemplateCardActionConfig {
    switch (kind) {
        case "send_test":
            return { group: "test", label: "Send test email" }
        case "edit":
            return { group: "edit", label: "Edit" }
        case "copy":
            return { group: "share", label: "Copy to My Templates" }
        case "share":
            return { group: "share", label: "Share with Org" }
        case "delete":
            return { group: "danger", label: "Delete" }
    }
}

function getTemplateCardActionIcon(kind: TemplateCardActionKind) {
    switch (kind) {
        case "send_test":
            return <SendIcon className="mr-2 size-4" />
        case "edit":
            return <EditIcon className="mr-2 size-4" />
        case "copy":
            return <CopyIcon className="mr-2 size-4" />
        case "share":
            return <ShareIcon className="mr-2 size-4" />
        case "delete":
            return <TrashIcon className="mr-2 size-4" />
    }
}

function TemplateCard({ template, controls }: TemplateCardProps) {
    return (
        <Card className="group relative min-w-0">
            <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-start gap-2">
                            <CardTitle className="text-base leading-6 line-clamp-2 min-h-12 break-words">
                                {template.name}
                            </CardTitle>
                            {template.is_system_template && (
                                <Badge variant="secondary" className="text-xs shrink-0">
                                    System
                                </Badge>
                            )}
                        </div>
                        <CardDescription className="mt-1 line-clamp-2 min-h-10 break-words" title={template.subject}>
                            {template.subject}
                        </CardDescription>
                        {template.owner_name && (
                            <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                                <UserIcon className="size-3" />
                                {template.owner_name}
                            </p>
                        )}
                    </div>
                    {controls.kind === "actions" && controls.actions.length > 0 && (
                        <DropdownMenu>
                            <DropdownMenuTrigger
                                render={
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="icon"
                                        className="size-8 shrink-0"
                                        aria-label={`Actions for ${template.name}`}
                                    >
                                        <MoreVerticalIcon className="size-4" aria-hidden="true" />
                                    </Button>
                                }
                            />
                            <DropdownMenuContent align="end">
                                {controls.actions.map((action, index) => {
                                    const actionConfig = getTemplateCardActionConfig(action)
                                    const previousAction = controls.actions[index - 1]
                                    const previousActionConfig = previousAction
                                        ? getTemplateCardActionConfig(previousAction)
                                        : null
                                    return (
                                        <React.Fragment key={action}>
                                            {previousActionConfig && previousActionConfig.group !== actionConfig.group && (
                                                <DropdownMenuSeparator />
                                            )}
                                            <DropdownMenuItem
                                                onClick={() => controls.onAction(action)}
                                                className={actionConfig.group === "danger" ? "text-destructive" : undefined}
                                            >
                                                {getTemplateCardActionIcon(action)}
                                                {actionConfig.label}
                                            </DropdownMenuItem>
                                        </React.Fragment>
                                    )
                                })}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    )}
                    {controls.kind === "read_only" && (
                        <Badge variant="outline" className="text-xs shrink-0">
                            <LockIcon className="size-3 mr-1" />
                            View Only
                        </Badge>
                    )}
                </div>
            </CardHeader>
            <CardContent className="pt-0">
                <div className="flex items-center gap-2">
                    <Badge variant={template.is_active ? "default" : "secondary"}>
                        {template.is_active ? "Active" : "Inactive"}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                        Updated {formatDate(template.updated_at)}
                    </span>
                </div>
            </CardContent>
        </Card>
    )
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function EmailTemplatesPage() {
    const { user } = useAuth()
    const isAdmin = user?.role === "admin" || user?.role === "developer"
    const { data: effectivePermissions } = useEffectivePermissions(user?.user_id ?? null)
    const permissions = effectivePermissions?.permissions || []
    const canUseAI = Boolean(user?.ai_enabled) && permissions.includes("use_ai_assistant")
    const canManageEmailTemplates = isAdmin || permissions.includes("manage_email_templates")

    const [activeTab, setActiveTab] = useState("personal")
    const [showAllPersonal, setShowAllPersonal] = useState(false)
    const [editorState, dispatchEditor] = useReducer(
        emailTemplateEditorReducer,
        initialEmailTemplateEditorState,
    )
    const [showPreview, setShowPreview] = useState(false)
    const [previewHtml, setPreviewHtml] = useState("")
    const [signaturePreviewMode, setSignaturePreviewMode] = useState<"personal" | "org">("personal")

    const subjectRef = useRef<HTMLInputElement | null>(null)
    const subjectSelectionRef = useRef<{ start: number; end: number } | null>(null)
    const htmlBodyRef = useRef<HTMLTextAreaElement | null>(null)
    const htmlBodySelectionRef = useRef<{ start: number; end: number } | null>(null)
    const visualBodyRef = useRef<RichTextEditorHandle | null>(null)
    const activeInsertionTargetRef = useRef<ActiveInsertionTarget>(null)
    const signaturePhotoInputRef = useRef<HTMLInputElement>(null)

    // Copy/Share dialog state
    const [copyDialogOpen, setCopyDialogOpen] = useState(false)
    const [shareDialogOpen, setShareDialogOpen] = useState(false)
    const copyShareTargetRef = useRef<EmailTemplateListItem | null>(null)
    const [copyShareName, setCopyShareName] = useState("")

    // Test send dialog state
    const [testSendState, dispatchTestSend] = useReducer(
        testSendDialogReducer,
        initialTestSendDialogState,
    )
    const testSendTouchedRef = useRef<Record<string, boolean>>({})

    // Platform library copy/preview state
    const [libraryCopyOpen, setLibraryCopyOpen] = useState(false)
    const libraryCopyTargetRef = useRef<EmailTemplateLibraryItem | null>(null)
    const [libraryCopyName, setLibraryCopyName] = useState("")
    const [libraryPreviewId, setLibraryPreviewId] = useState<string | null>(null)

    const [signatureDraft, dispatchSignatureDraft] = useReducer(
        signatureDraftReducer,
        initialSignatureDraftState,
    )

    const { data: templateVariables = [], isLoading: templateVariablesLoading } = useEmailTemplateVariables()

    // API hooks for templates
    const { data: personalTemplates, isLoading: loadingPersonal } = useEmailTemplates({
        activeOnly: true,
        scope: "personal",
        showAllPersonal: isAdmin && showAllPersonal,
    })
    const { data: orgTemplates, isLoading: loadingOrg } = useEmailTemplates({
        activeOnly: true,
        scope: "org",
    })
    const { data: libraryTemplates, isLoading: loadingLibrary } = useEmailTemplateLibrary()

    const createTemplate = useCreateEmailTemplate()
    const updateTemplate = useUpdateEmailTemplate()
    const deleteTemplate = useDeleteEmailTemplate()
    const copyToPersonal = useCopyTemplateToPersonal()
    const shareWithOrg = useShareTemplateWithOrg()
    const copyFromLibrary = useCopyTemplateFromLibrary()
    const sendTest = useSendTestEmailTemplate()

    // Signature hooks
    const { data: signatureData, refetch: refetchSignature } = useUserSignature()
    const updateSignatureMutation = useUpdateUserSignature()
    const uploadPhotoMutation = useUploadSignaturePhoto()
    const deletePhotoMutation = useDeleteSignaturePhoto()
    const { data: personalSignaturePreview } = useSignaturePreview()
    const { data: orgSignaturePreview } = useOrgSignaturePreview({ enabled: true, mode: "org_only" })

    const hasChanges = Boolean(
            signatureData &&
            (
            signatureDraft.name !== (signatureData.signature_name || "") ||
            signatureDraft.title !== (signatureData.signature_title || "") ||
            signatureDraft.phone !== (signatureData.signature_phone || "") ||
            signatureDraft.linkedin !== (signatureData.signature_linkedin || "") ||
            signatureDraft.twitter !== (signatureData.signature_twitter || "") ||
            signatureDraft.instagram !== (signatureData.signature_instagram || "")
        )
    )

    // Get full template details when editing
    const { data: fullTemplate } = useEmailTemplate(editorState.template?.id || null)
    const { data: testSendTemplateDetail, isLoading: testSendTemplateLoading } = useEmailTemplate(
        testSendState.target?.id || null
    )
    const { data: libraryTemplateDetail } = useEmailTemplateLibraryItem(libraryPreviewId)
    const templateBody = editorState.bodyOverride ?? (editorState.template ? fullTemplate?.body ?? "" : "")
    const templateBodyMode = editorState.bodyModeOverride ?? getTemplateBodyMode(editorState.template ? fullTemplate?.body : null)
    const hasComplexHtml = hasAdvancedTemplateHtml(templateBody)
    const changeTemplateSubjectDraft: React.Dispatch<React.SetStateAction<string>> = (nextValue) => {
        dispatchEditor({
            type: "changeSubject",
            value: typeof nextValue === "function" ? nextValue(editorState.subject) : nextValue,
        })
    }
    const setTemplateBodyDraft: React.Dispatch<React.SetStateAction<string>> = (nextValue) => {
        dispatchEditor({
            type: "changeBody",
            value: typeof nextValue === "function" ? nextValue(templateBody) : nextValue,
        })
    }

    const testSendUsedVariables = testSendTemplateDetail
        ? extractTemplateVariables(`${testSendTemplateDetail.subject}\n${testSendTemplateDetail.body}`)
            .slice()
            .sort((a, b) => a.localeCompare(b))
        : []
    const testSendHasUnsubscribeUrl = testSendUsedVariables.includes("unsubscribe_url")
    const testSendEditableVariables = testSendUsedVariables.filter((name) => name !== "unsubscribe_url")

    useEffect(() => {
        if (!testSendState.isOpen) return
        if (!testSendTemplateDetail) return
        const editableVariables = extractTemplateVariables(`${testSendTemplateDetail.subject}\n${testSendTemplateDetail.body}`)
            .slice()
            .sort((a, b) => a.localeCompare(b))
            .filter((name) => name !== "unsubscribe_url")
        if (editableVariables.length === 0) return

        React.startTransition(() => {
            const toEmail = testSendState.toEmail.trim() || user?.email || ""
            const variables: Record<string, string> = {}
            for (const variableName of editableVariables) {
                variables[variableName] = buildTestVariableSample(variableName, {
                    toEmail,
                    ownerName: user?.display_name,
                    orgName: user?.org_name,
                })
            }
            dispatchTestSend({ type: "initializeVariables", variables })
        })
    }, [
        testSendState.isOpen,
        testSendState.toEmail,
        testSendTemplateDetail,
        user?.display_name,
        user?.email,
        user?.org_name,
    ])

    const canValidateVariables = !templateVariablesLoading && templateVariables.length > 0
    const allowedVariableNames = new Set(templateVariables.map((variable) => variable.name))
    const requiredVariableNames: string[] = []
    for (const variable of templateVariables) {
        if (variable.required) {
            requiredVariableNames.push(variable.name)
        }
    }
    const usedVariableNames = extractTemplateVariables(`${editorState.subject}\n${templateBody}`)
    const usedVariableNamesSet = new Set(usedVariableNames)
    const unknownVariables = canValidateVariables
        ? usedVariableNames.filter((variable) => !allowedVariableNames.has(variable))
        : []
    const missingRequiredVariables = canValidateVariables
        ? requiredVariableNames.filter((variable) => !usedVariableNamesSet.has(variable))
        : []

    // Load signature data on mount
    useEffect(() => {
        if (signatureData) {
            React.startTransition(() => {
                dispatchSignatureDraft({
                    type: "hydrate",
                    draft: createSignatureDraftState(signatureData),
                })
            })
        }
    }, [signatureData])

    const handleOpenModal = (template?: EmailTemplateListItem, scope: EmailTemplateScope = "personal") => {
        activeInsertionTargetRef.current = null
        if (template) {
            dispatchEditor({ type: "openEdit", template })
        } else {
            dispatchEditor({ type: "openCreate", scope })
        }
    }

    const handleSave = () => {
        if (!editorState.name.trim() || !editorState.subject.trim() || !templateBody.trim()) return

        if (editorState.template) {
            updateTemplate.mutate(
                {
                    id: editorState.template.id,
                    data: {
                        name: editorState.name,
                        subject: editorState.subject,
                        body: templateBody,
                    },
                },
                { onSuccess: () => dispatchEditor({ type: "close" }) }
            )
        } else {
            createTemplate.mutate(
                {
                    name: editorState.name,
                    subject: editorState.subject,
                    body: templateBody,
                    scope: editorState.scope,
                },
                { onSuccess: () => dispatchEditor({ type: "close" }) }
            )
        }
    }

    const handleDelete = (id: string) => {
        if (confirm("Are you sure you want to delete this template?")) {
            deleteTemplate.mutate(id)
        }
    }

    const handleOpenCopyDialog = (template: EmailTemplateListItem) => {
        copyShareTargetRef.current = template
        setCopyShareName(`${template.name} (Copy)`)
        setCopyDialogOpen(true)
    }

    const handleOpenShareDialog = (template: EmailTemplateListItem) => {
        copyShareTargetRef.current = template
        setCopyShareName(template.name)
        setShareDialogOpen(true)
    }

    const handleOpenTestDialog = (template: EmailTemplateListItem) => {
        testSendTouchedRef.current = {}
        dispatchTestSend({ type: "open", target: template, toEmail: user?.email || "" })
    }

    const handleCloseTestDialog = () => {
        dispatchTestSend({ type: "close" })
        testSendTouchedRef.current = {}
    }

    const handleSendTest = async () => {
        if (!testSendState.target) return
        const toEmail = testSendState.toEmail.trim()
        if (!toEmail) {
            toast.error("To email is required")
            return
        }

        const overrides: Record<string, string> = {}
        for (const [key, value] of Object.entries(testSendState.variables)) {
            if (!testSendTouchedRef.current[key]) continue
            const trimmed = value.trim()
            if (!trimmed) continue
            overrides[key] = trimmed
        }

        try {
            const result = await sendTest.mutateAsync({
                id: testSendState.target.id,
                payload: {
                    to_email: toEmail,
                    variables: overrides,
                    ...(testSendState.ignoreOptOut ? { ignore_opt_out: true } : {}),
                },
            })
            const providerLabel =
                result.provider_used === "resend"
                    ? "Resend"
                    : result.provider_used === "gmail"
                        ? "Gmail"
                        : "provider"
            toast.success(`Test email sent via ${providerLabel}`)
            handleCloseTestDialog()
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to send test email")
        }
    }

    const handleCopy = () => {
        const target = copyShareTargetRef.current
        if (!target || !copyShareName.trim()) return
        copyToPersonal.mutate(
            { id: target.id, data: { name: copyShareName.trim() } },
            {
                onSuccess: () => {
                    toast.success("Template copied to your personal templates")
                    setCopyDialogOpen(false)
                    copyShareTargetRef.current = null
                    setCopyShareName("")
                },
                onError: (error: Error) => {
                    toast.error(error.message || "Failed to copy template")
                },
            }
        )
    }

    const handleShare = () => {
        const target = copyShareTargetRef.current
        if (!target || !copyShareName.trim()) return
        shareWithOrg.mutate(
            { id: target.id, data: { name: copyShareName.trim() } },
            {
                onSuccess: () => {
                    toast.success("Template shared with the organization")
                    setShareDialogOpen(false)
                    copyShareTargetRef.current = null
                    setCopyShareName("")
                },
                onError: (error: Error) => {
                    toast.error(error.message || "Failed to share template")
                },
            }
        )
    }

    const previewScope: EmailTemplateScope = libraryPreviewId
        ? "org"
        : editorState.template?.scope === "personal" || editorState.template?.scope === "org"
          ? editorState.template.scope
          : editorState.scope
    const previewSubjectTemplate = libraryPreviewId && libraryTemplateDetail?.subject
        ? libraryTemplateDetail.subject
        : editorState.subject
    const previewSubject = previewSubjectTemplate
        .replace(/\{\{full_name\}\}/g, "John Smith")
        .replace(/\{\{org_name\}\}/g, signatureData?.org_signature_company_name || "ABC Surrogacy")
    useEffect(() => {
        if (!showPreview) return

        const rawHtml = libraryPreviewId ? libraryTemplateDetail?.body : templateBody
        if (libraryPreviewId && !rawHtml) return

        React.startTransition(() => {
            setPreviewHtml(buildPreviewHtml(rawHtml || "", {
                orgSignatureCompanyName: signatureData?.org_signature_company_name,
                previewScope,
                personalSignatureHtml: personalSignaturePreview?.html,
                orgSignatureHtml: orgSignaturePreview?.html,
            }))
        })
    }, [
        libraryPreviewId,
        libraryTemplateDetail?.body,
        orgSignaturePreview?.html,
        personalSignaturePreview?.html,
        previewScope,
        showPreview,
        signatureData?.org_signature_company_name,
        templateBody,
    ])

    const handlePreview = () => {
        setPreviewHtml(buildPreviewHtml(templateBody, {
            orgSignatureCompanyName: signatureData?.org_signature_company_name,
            previewScope,
            personalSignatureHtml: personalSignaturePreview?.html,
            orgSignatureHtml: orgSignaturePreview?.html,
        }))
        setShowPreview(true)
    }

    const handleLibraryPreview = (templateId: string) => {
        setLibraryPreviewId(templateId)
        setShowPreview(true)
    }

    const handlePreviewOpenChange = (open: boolean) => {
        setShowPreview(open)
        if (!open) {
            setLibraryPreviewId(null)
        }
    }

    const handleLibraryCopy = () => {
        const target = libraryCopyTargetRef.current
        if (!target || !libraryCopyName.trim()) return
        copyFromLibrary.mutate(
            { id: target.id, data: { name: libraryCopyName.trim() } },
            {
                onSuccess: () => {
                    toast.success("Template copied to org templates")
                    setLibraryCopyOpen(false)
                    libraryCopyTargetRef.current = null
                    setLibraryCopyName("")
                },
                onError: (error: Error) => {
                    toast.error(error.message || "Failed to copy template")
                },
            }
        )
    }

    const insertToken = (token: string) => {
        const activeInsertionTarget = activeInsertionTargetRef.current
        if (activeInsertionTarget === "subject") {
            insertIntoTextControl(subjectRef.current, subjectSelectionRef, changeTemplateSubjectDraft, token)
            return
        }
        if (activeInsertionTarget === "body_html") {
            insertIntoTextControl(htmlBodyRef.current, htmlBodySelectionRef, setTemplateBodyDraft, token)
            return
        }
        if (activeInsertionTarget === "body_visual") {
            visualBodyRef.current?.insertText(token)
            return
        }

        if (templateBodyMode === "html") {
            insertIntoTextControl(htmlBodyRef.current, htmlBodySelectionRef, setTemplateBodyDraft, token)
            return
        }
        visualBodyRef.current?.insertText(token)
    }

    const insertOrgLogo = () => {
        if (templateBody.includes("{{org_logo_url}}")) return
        const logo = `<p><img src="{{org_logo_url}}" alt="{{org_name}} logo" style="max-width: 160px; height: auto; display: block;" /></p>\n`
        if (templateBodyMode === "visual") {
            visualBodyRef.current?.insertHtml(logo)
            activeInsertionTargetRef.current = "body_visual"
            return
        }
        insertIntoTextControl(htmlBodyRef.current, htmlBodySelectionRef, setTemplateBodyDraft, logo)
        activeInsertionTargetRef.current = "body_html"
    }

    // Save all signature settings
    const handleSaveSignature = () => {
        updateSignatureMutation.mutate(
            {
                signature_name: signatureDraft.name || null,
                signature_title: signatureDraft.title || null,
                signature_phone: signatureDraft.phone || null,
                signature_linkedin: signatureDraft.linkedin || null,
                signature_twitter: signatureDraft.twitter || null,
                signature_instagram: signatureDraft.instagram || null,
            },
            {
                onSuccess: () => {
                    void refetchSignature()
                },
            }
        )
    }

    const handleUploadPhoto = (file: File) => {
        uploadPhotoMutation.mutate(file, {
            onSuccess: () => {
                void refetchSignature()
            },
        })
    }

    const handleSignaturePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return

        const allowedTypes = ["image/png", "image/jpeg", "image/webp"]
        if (!allowedTypes.includes(file.type)) {
            toast.error("Please select a PNG, JPEG, or WebP image")
            return
        }

        if (file.size > 2 * 1024 * 1024) {
            toast.error("Image must be less than 2MB")
            return
        }

        handleUploadPhoto(file)
        e.target.value = ""
    }

    const handleDeletePhoto = () => {
        if (confirm("Remove your signature photo? Your profile avatar will be used instead.")) {
            deletePhotoMutation.mutate(undefined, {
                onSuccess: () => {
                    void refetchSignature()
                },
            })
        }
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Email Templates</h1>
                    <div className="flex items-center gap-2">
                        {activeTab === "personal" && (
                            <>
                                {canUseAI ? (
                                    <Button
                                        variant="outline"
                                        title="Generate email template with AI"
                                        render={<Link href="/automation/ai-builder?mode=email_template" />}
                                    >
                                        <SparklesIcon className="mr-2 size-4" />
                                        Generate with AI
                                    </Button>
                                ) : (
                                    <Button
                                        variant="outline"
                                        disabled
                                        title="AI is disabled or permission is missing"
                                    >
                                        <SparklesIcon className="mr-2 size-4" />
                                        Generate with AI
                                    </Button>
                                )}
                                <Button onClick={() => handleOpenModal(undefined, "personal")}>
                                    <PlusIcon className="mr-2 size-4" />
                                    Create Template
                                </Button>
                            </>
                        )}
                        {activeTab === "org" && canManageEmailTemplates && (
                            <Button onClick={() => handleOpenModal(undefined, "org")}>
                                <PlusIcon className="mr-2 size-4" />
                                Create Org Template
                            </Button>
                        )}
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 p-6">
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                    <div className="flex items-center justify-between mb-6">
                        <TabsList>
                            <TabsTrigger value="personal" className="gap-2">
                                <UserIcon className="size-4" />
                                My Email Templates
                            </TabsTrigger>
                            <TabsTrigger value="org" className="gap-2">
                                <BuildingIcon className="size-4" />
                                Organization Templates
                            </TabsTrigger>
                            <TabsTrigger value="platform" className="gap-2">
                                <LayoutTemplateIcon className="size-4" />
                                Platform Templates
                            </TabsTrigger>
                            <TabsTrigger value="signature">My Signature</TabsTrigger>
                        </TabsList>

                        {/* Admin filter for personal templates */}
                        {activeTab === "personal" && isAdmin && (
                            <Select
                                value={showAllPersonal ? "all" : "mine"}
                                onValueChange={(v) => setShowAllPersonal(v === "all")}
                            >
                                <SelectTrigger className="w-[180px]">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="mine">My Templates</SelectItem>
                                    <SelectItem value="all">All Personal Templates</SelectItem>
                                </SelectContent>
                            </Select>
                        )}
                    </div>

                    {/* Personal Templates Tab */}
                    <TabsContent value="personal" className="space-y-4">
                        {loadingPersonal ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : !personalTemplates?.length ? (
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center py-12">
                                    <UserIcon className="size-12 text-muted-foreground mb-4" />
                                    <p className="text-muted-foreground mb-4">
                                        {showAllPersonal
                                            ? "No personal templates found"
                                            : "You don't have any personal templates yet"}
                                    </p>
                                    {!showAllPersonal && (
                                        <Button onClick={() => handleOpenModal(undefined, "personal")}>
                                            <PlusIcon className="mr-2 size-4" />
                                            Create Your First Template
                                        </Button>
                                    )}
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {personalTemplates.map((template) => {
                                    const isOwner = template.owner_user_id === user?.user_id
                                    const canSendPersonalTest = isOwner || canManageEmailTemplates
                                    const actions: TemplateCardActionKind[] = []
                                    if (canSendPersonalTest) {
                                        actions.push("send_test")
                                    }
                                    if (!template.is_system_template) {
                                        actions.push("edit")
                                    }
                                    if (isOwner) {
                                        actions.push("share")
                                    }
                                    if (isOwner && !template.is_system_template) {
                                        actions.push("delete")
                                    }
                                    const controls: TemplateCardControls = !isOwner && !isAdmin
                                        ? { kind: "read_only" }
                                        : {
                                            kind: "actions",
                                            actions,
                                            onAction: (action) => {
                                                if (action === "send_test") {
                                                    handleOpenTestDialog(template)
                                                    return
                                                }
                                                if (action === "edit") {
                                                    handleOpenModal(template)
                                                    return
                                                }
                                                if (action === "share") {
                                                    handleOpenShareDialog(template)
                                                    return
                                                }
                                                if (action === "delete") {
                                                    handleDelete(template.id)
                                                }
                                            },
                                        }
                                    return (
                                        <TemplateCard
                                            key={template.id}
                                            template={template}
                                            controls={controls}
                                        />
                                    )
                                })}
                            </div>
                        )}
                    </TabsContent>

                    {/* Org Templates Tab */}
                    <TabsContent value="org" className="space-y-4">
                        {loadingOrg ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : !orgTemplates?.length ? (
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center py-12">
                                    <BuildingIcon className="size-12 text-muted-foreground mb-4" />
                                    <p className="text-muted-foreground mb-4">No organization templates yet</p>
                                    {canManageEmailTemplates && (
                                        <Button onClick={() => handleOpenModal(undefined, "org")}>
                                            <PlusIcon className="mr-2 size-4" />
                                            Create Org Template
                                        </Button>
                                    )}
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {orgTemplates.map((template) => {
                                    const actions: TemplateCardActionKind[] = []
                                    if (canManageEmailTemplates) {
                                        actions.push("send_test")
                                    }
                                    if (canManageEmailTemplates && !template.is_system_template) {
                                        actions.push("edit")
                                    }
                                    actions.push("copy")
                                    if (canManageEmailTemplates && !template.is_system_template) {
                                        actions.push("delete")
                                    }
                                    const controls: TemplateCardControls = !canManageEmailTemplates && !template.is_system_template
                                        ? { kind: "read_only" }
                                        : {
                                            kind: "actions",
                                            actions,
                                            onAction: (action) => {
                                                if (action === "send_test") {
                                                    handleOpenTestDialog(template)
                                                    return
                                                }
                                                if (action === "edit") {
                                                    handleOpenModal(template)
                                                    return
                                                }
                                                if (action === "copy") {
                                                    handleOpenCopyDialog(template)
                                                    return
                                                }
                                                if (action === "delete") {
                                                    handleDelete(template.id)
                                                }
                                            },
                                        }
                                    return (
                                        <TemplateCard
                                            key={template.id}
                                            template={template}
                                            controls={controls}
                                        />
                                    )
                                })}
                            </div>
                        )}
                    </TabsContent>

                    {/* Platform Templates Tab */}
                    <TabsContent value="platform" className="space-y-4">
                        {loadingLibrary ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : !libraryTemplates?.length ? (
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center py-12">
                                    <LayoutTemplateIcon className="size-12 text-muted-foreground mb-4" />
                                    <p className="text-muted-foreground">No platform templates available</p>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {libraryTemplates.map((template) => (
                                    <Card key={template.id}>
                                        <CardHeader className="pb-2">
                                            <div className="flex items-start justify-between">
                                                <div className="space-y-1">
                                                    <CardTitle className="text-base">{template.name}</CardTitle>
                                                    <CardDescription className="line-clamp-2">
                                                        {template.subject}
                                                    </CardDescription>
                                                </div>
                                                {template.category && (
                                                    <Badge variant="outline" className="capitalize">
                                                        {template.category}
                                                    </Badge>
                                                )}
                                            </div>
                                        </CardHeader>
                                        <CardContent className="flex items-center justify-between">
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => handleLibraryPreview(template.id)}
                                            >
                                                <EyeIcon className="mr-2 size-4" />
                                                Preview
                                            </Button>
                                            <Button
                                                size="sm"
                                                onClick={() => {
                                                    libraryCopyTargetRef.current = template
                                                    setLibraryCopyName(template.name)
                                                    setLibraryCopyOpen(true)
                                                }}
                                            >
                                                <CopyIcon className="mr-2 size-4" />
                                                Copy to Org
                                            </Button>
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        )}
                    </TabsContent>

                    {/* Signature Tab */}
                    <TabsContent value="signature">
                        <div className="grid gap-6 lg:grid-cols-2">
                            {/* Editor Column */}
                            <div className="space-y-6">
                                {/* Main Signature Card */}
                                <Card>
                                    <CardHeader>
                                        <CardTitle>My Signature</CardTitle>
                                        <CardDescription>
                                            Customize your email signature. Leave fields empty to use your profile defaults.
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        {/* Signature Photo */}
                                        <SignaturePhotoField
                                            signaturePhotoUrl={signatureData?.signature_photo_url || null}
                                            profilePhotoUrl={signatureData?.profile_photo_url || null}
                                            profileName={signatureData?.profile_name || ""}
                                            avatarAction={
                                                <>
                                                    <input
                                                        id="signature-photo-upload"
                                                        name="signature_photo_upload"
                                                        type="file"
                                                        ref={signaturePhotoInputRef}
                                                        onChange={handleSignaturePhotoChange}
                                                        accept="image/png,image/jpeg,image/webp"
                                                        aria-label="Upload signature photo"
                                                        className="hidden"
                                                    />
                                                    <Button unstyled
                                                        type="button"
                                                        onClick={() => signaturePhotoInputRef.current?.click()}
                                                        disabled={uploadPhotoMutation.isPending}
                                                        className="absolute bottom-0 right-0 flex size-7 items-center justify-center rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-md"
                                                        aria-label="Upload signature photo"
                                                    >
                                                        {uploadPhotoMutation.isPending ? (
                                                            <Loader2Icon className="size-3.5 animate-spin" />
                                                        ) : (
                                                            <CameraIcon className="size-3.5" />
                                                        )}
                                                    </Button>
                                                </>
                                            }
                                            customPhotoAction={
                                                <Button
                                                    type="button"
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-7 px-2 text-xs text-destructive hover:text-destructive hover:bg-destructive/10"
                                                    onClick={handleDeletePhoto}
                                                    disabled={deletePhotoMutation.isPending}
                                                >
                                                    {deletePhotoMutation.isPending ? (
                                                        <Loader2Icon className="mr-1 size-3 animate-spin" />
                                                    ) : (
                                                        <TrashIcon className="mr-1 size-3" />
                                                    )}
                                                    Remove & use profile photo
                                                </Button>
                                            }
                                        />

                                        <div className="border-t pt-4" />

                                        {/* Override Fields */}
                                        <div className="space-y-3">
                                            <SignatureOverrideField
                                                id="sig-name"
                                                label="Name"
                                                value={signatureDraft.name}
                                                profileDefault={signatureData?.profile_name || null}
                                                onChange={(value) =>
                                                    dispatchSignatureDraft({
                                                        type: "changeField",
                                                        field: "name",
                                                        value,
                                                    })
                                                }
                                                onClear={() =>
                                                    dispatchSignatureDraft({
                                                        type: "changeField",
                                                        field: "name",
                                                        value: "",
                                                    })
                                                }
                                            />

                                            <SignatureOverrideField
                                                id="sig-title"
                                                label="Title"
                                                value={signatureDraft.title}
                                                profileDefault={signatureData?.profile_title || null}
                                                onChange={(value) =>
                                                    dispatchSignatureDraft({
                                                        type: "changeField",
                                                        field: "title",
                                                        value,
                                                    })
                                                }
                                                onClear={() =>
                                                    dispatchSignatureDraft({
                                                        type: "changeField",
                                                        field: "title",
                                                        value: "",
                                                    })
                                                }
                                                placeholder="e.g., Case Manager"
                                            />

                                            <SignatureOverrideField
                                                id="sig-phone"
                                                label="Phone"
                                                value={signatureDraft.phone}
                                                profileDefault={signatureData?.profile_phone || null}
                                                onChange={(value) =>
                                                    dispatchSignatureDraft({
                                                        type: "changeField",
                                                        field: "phone",
                                                        value,
                                                    })
                                                }
                                                onClear={() =>
                                                    dispatchSignatureDraft({
                                                        type: "changeField",
                                                        field: "phone",
                                                        value: "",
                                                    })
                                                }
                                                type="tel"
                                                placeholder="e.g., (555) 123-4567"
                                            />
                                        </div>

                                        <div className="border-t pt-4" />

                                        {/* Social Links */}
                                        <div className="space-y-3">
                                            <h4 className="text-sm font-medium flex items-center gap-2">
                                                Social Links
                                                <span className="text-xs font-normal text-muted-foreground">
                                                    (optional)
                                                </span>
                                            </h4>

                                            <div className="space-y-2">
                                                <div className="space-y-1">
                                                    <Label htmlFor="sig-linkedin" className="text-xs flex items-center gap-1.5">
                                                        <LinkIcon className="size-3.5 text-muted-foreground" />
                                                        LinkedIn
                                                    </Label>
                                                    <Input
                                                        id="sig-linkedin"
                                                        placeholder="https://linkedin.com/in/yourprofile"
                                                        value={signatureDraft.linkedin}
                                                        onChange={(e) =>
                                                            dispatchSignatureDraft({
                                                                type: "changeField",
                                                                field: "linkedin",
                                                                value: e.target.value,
                                                            })
                                                        }
                                                        className="h-9"
                                                    />
                                                </div>

                                                <div className="space-y-1">
                                                    <Label htmlFor="sig-twitter" className="text-xs flex items-center gap-1.5">
                                                        <svg className="size-3.5 text-muted-foreground" viewBox="0 0 24 24" fill="currentColor">
                                                            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                                                        </svg>
                                                        X (Twitter)
                                                    </Label>
                                                    <Input
                                                        id="sig-twitter"
                                                        placeholder="https://x.com/yourhandle"
                                                        value={signatureDraft.twitter}
                                                        onChange={(e) =>
                                                            dispatchSignatureDraft({
                                                                type: "changeField",
                                                                field: "twitter",
                                                                value: e.target.value,
                                                            })
                                                        }
                                                        className="h-9"
                                                    />
                                                </div>

                                                <div className="space-y-1">
                                                    <Label htmlFor="sig-instagram" className="text-xs flex items-center gap-1.5">
                                                        <CameraIcon className="size-3.5 text-muted-foreground" />
                                                        Instagram
                                                    </Label>
                                                    <Input
                                                        id="sig-instagram"
                                                        placeholder="https://instagram.com/yourhandle"
                                                        value={signatureDraft.instagram}
                                                        onChange={(e) =>
                                                            dispatchSignatureDraft({
                                                                type: "changeField",
                                                                field: "instagram",
                                                                value: e.target.value,
                                                            })
                                                        }
                                                        className="h-9"
                                                    />
                                                </div>
                                            </div>
                                        </div>

                                        {/* Save Button */}
                                        <div className="flex items-center gap-3 pt-1">
                                            <Button
                                                onClick={handleSaveSignature}
                                                disabled={updateSignatureMutation.isPending || !hasChanges}
                                                className="flex-1"
                                            >
                                                {updateSignatureMutation.isPending ? (
                                                    <>
                                                        <Loader2Icon className="mr-2 size-4 animate-spin" />
                                                        Saving…
                                                    </>
                                                ) : (
                                                    "Save Signature"
                                                )}
                                            </Button>
                                            <Button
                                                variant="outline"
                                                onClick={handleCopySignatureHtml}
                                            >
                                                <CodeIcon className="mr-2 size-4" />
                                                Copy HTML
                                            </Button>
                                        </div>
                                        {hasChanges && (
                                            <p className="text-xs text-amber-600">
                                                You have unsaved changes
                                            </p>
                                        )}
                                    </CardContent>
                                </Card>

                                {/* Organization Branding (read-only) */}
                                {(signatureData?.org_signature_company_name ||
                                    signatureData?.org_signature_address ||
                                    signatureData?.org_signature_phone ||
                                    signatureData?.org_signature_website ||
                                    signatureData?.org_signature_logo_url) && (
                                    <Card className="border-dashed">
                                        <CardHeader className="pb-3">
                                            <div className="flex items-center justify-between">
                                                <CardTitle className="text-base">Organization Branding</CardTitle>
                                                <Badge variant="secondary" className="text-xs">
                                                    Read-only
                                                </Badge>
                                            </div>
                                            <CardDescription>
                                                Managed by your organization admin in Settings
                                            </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="flex items-center gap-3">
                                                {signatureData.org_signature_logo_url && (
                                                    <NextImage
                                                        src={signatureData.org_signature_logo_url}
                                                        alt="Logo"
                                                        width={160}
                                                        height={40}
                                                        unoptimized
                                                        className="h-10 w-auto rounded border"
                                                    />
                                                )}
                                                <div>
                                                    <p className="font-medium">
                                                        {signatureData.org_signature_company_name || "Organization"}
                                                    </p>
                                                    {signatureData.org_signature_template && (
                                                        <p className="text-sm text-muted-foreground">
                                                            {signatureData.org_signature_template} template
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                            {(signatureData?.org_signature_address ||
                                                signatureData?.org_signature_phone ||
                                                signatureData?.org_signature_website) && (
                                                <div className="mt-3 pt-3 border-t space-y-1 text-sm text-muted-foreground">
                                                    {signatureData?.org_signature_address && (
                                                        <p>{signatureData.org_signature_address}</p>
                                                    )}
                                                    {signatureData?.org_signature_phone && (
                                                        <p>{signatureData.org_signature_phone}</p>
                                                    )}
                                                    {signatureData?.org_signature_website && (
                                                        <a
                                                            className="underline hover:text-foreground transition-colors"
                                                            href={signatureData.org_signature_website}
                                                            rel="noreferrer"
                                                            target="_blank"
                                                        >
                                                            {signatureData.org_signature_website}
                                                        </a>
                                                    )}
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>
                                )}
                            </div>

                            {/* Preview Column */}
                            <div className="space-y-6 lg:sticky lg:top-6 h-fit">
                                <Card>
                                    <CardHeader>
                                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                                            <div>
                                                <CardTitle>Signature Preview</CardTitle>
                                                <CardDescription>
                                                    {signaturePreviewMode === "personal"
                                                        ? "Personal email signature (your info + org branding)"
                                                        : "Org workflow signature (org branding only)"}
                                                </CardDescription>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <Button
                                                    size="sm"
                                                    variant={signaturePreviewMode === "personal" ? "default" : "outline"}
                                                    onClick={() => setSignaturePreviewMode("personal")}
                                                >
                                                    Personal Email
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant={signaturePreviewMode === "org" ? "default" : "outline"}
                                                    onClick={() => setSignaturePreviewMode("org")}
                                                >
                                                    Org Workflow
                                                </Button>
                                            </div>
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="border rounded-lg p-4 bg-white min-h-[200px]">
                                            <p className="text-muted-foreground text-sm mb-4 border-b pb-4">
                                                [Your email content here…]
                                            </p>
                                            {signaturePreviewMode === "personal" ? (
                                                <SignaturePreviewComponent />
                                            ) : (
                                                <OrgSignaturePreviewComponent />
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    </TabsContent>
                </Tabs>
            </div>

            {/* Create/Edit Template Modal */}
            <Dialog
                open={editorState.isOpen}
                onOpenChange={(open) => {
                    if (!open) {
                        activeInsertionTargetRef.current = null
                        dispatchEditor({ type: "close" })
                    }
                }}
            >
                <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
                    <DialogHeader>
                        <DialogTitle>
                            {editorState.template ? "Edit Template" : "Create Template"}
                        </DialogTitle>
                        <DialogDescription>
                            Create reusable email templates with dynamic variables.
                            {!editorState.template && (
                                <span className="block mt-1">
                                    Creating a{" "}
                                    <Badge variant="outline" className="text-xs">
                                        {editorState.scope === "personal" ? "Personal" : "Organization"}
                                    </Badge>{" "}
                                    template
                                </span>
                            )}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="flex-1 overflow-y-auto space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="name">Template Name</Label>
                            <Input
                                id="name"
                                placeholder="Welcome Email"
                                value={editorState.name}
                                onChange={(e) =>
                                    dispatchEditor({
                                        type: "changeName",
                                        value: e.target.value,
                                    })
                                }
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="subject">Subject Line</Label>
                            <Input
                                id="subject"
                                placeholder="Welcome to {{org_name}}, {{full_name}}!"
                                ref={subjectRef}
                                value={editorState.subject}
                                onChange={(e) =>
                                    dispatchEditor({
                                        type: "changeSubject",
                                        value: e.target.value,
                                    })
                                }
                                onFocus={(e) => {
                                    activeInsertionTargetRef.current = "subject"
                                    recordSelection(e.currentTarget, subjectSelectionRef)
                                }}
                                onKeyUp={(e) => recordSelection(e.currentTarget, subjectSelectionRef)}
                                onMouseUp={(e) => recordSelection(e.currentTarget, subjectSelectionRef)}
                                onSelect={(e) => recordSelection(e.currentTarget, subjectSelectionRef)}
                            />
                        </div>

                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <Label
                                    id="template-body-label"
                                    htmlFor={templateBodyMode === "html" ? "template-body-html" : undefined}
                                >
                                    Email Body
                                </Label>
                                <div className="flex flex-wrap items-center gap-2">
                                    <ToggleGroup
                                        multiple={false}
                                        value={templateBodyMode ? [templateBodyMode] : []}
                                        onValueChange={(value) => {
                                            const next = value[0] as EditorMode | undefined
                                            if (!next) return
                                            dispatchEditor({
                                                type: "changeBodyMode",
                                                value: next,
                                            })
                                            const current = activeInsertionTargetRef.current
                                            activeInsertionTargetRef.current = current === "subject"
                                                ? current
                                                : next === "html"
                                                  ? "body_html"
                                                  : "body_visual"
                                        }}
                                    >
                                        <ToggleGroupItem value="visual" className="h-8">
                                            Visual
                                        </ToggleGroupItem>
                                        <ToggleGroupItem value="html" className="h-8">
                                            HTML
                                        </ToggleGroupItem>
                                    </ToggleGroup>
                                    <TemplateVariablePicker
                                        variables={templateVariables}
                                        disabled={templateVariablesLoading || templateVariables.length === 0}
                                        triggerLabel={templateVariablesLoading ? "Loading…" : "Insert Variable"}
                                        onSelect={(variable) => {
                                            if (variable.name === "unsubscribe_url") {
                                                toast.info("Unsubscribe link is added automatically.")
                                                return
                                            }
                                            insertToken(`{{${variable.name}}}`)
                                        }}
                                    />
                                    <Button variant="outline" size="sm" onClick={insertOrgLogo}>
                                        Insert Logo
                                    </Button>
                                </div>
                            </div>
                            {templateBodyMode === "visual" ? (
                                <RichTextEditor
                                    ref={visualBodyRef}
                                    content={templateBody}
                                    onChange={(html) =>
                                        dispatchEditor({
                                            type: "changeBody",
                                            value: html,
                                        })
                                    }
                                    onFocus={() => {
                                        activeInsertionTargetRef.current = "body_visual"
                                    }}
                                    ariaLabelledBy="template-body-label"
                                    placeholder="Write your email content here… Use the toolbar to format text."
                                    minHeight="200px"
                                    maxHeight="350px"
                                    enableImages
                                    enableEmojiPicker
                                />
                            ) : (
                                <Textarea
                                    id="template-body-html"
                                    aria-labelledby="template-body-label"
                                    ref={htmlBodyRef}
                                    value={templateBody}
                                    onChange={(event) =>
                                        dispatchEditor({
                                            type: "changeBody",
                                            value: event.target.value,
                                        })
                                    }
                                    onFocus={(event) => {
                                        activeInsertionTargetRef.current = "body_html"
                                        recordSelection(event.currentTarget, htmlBodySelectionRef)
                                    }}
                                    onKeyUp={(event) => recordSelection(event.currentTarget, htmlBodySelectionRef)}
                                    onMouseUp={(event) => recordSelection(event.currentTarget, htmlBodySelectionRef)}
                                    onSelect={(event) => recordSelection(event.currentTarget, htmlBodySelectionRef)}
                                    placeholder="Paste or edit the HTML for this template…"
                                    className="min-h-[220px] font-mono text-xs leading-relaxed"
                                />
                            )}
                            {templateBodyMode === "visual" && hasComplexHtml && (
                                <p className="text-xs text-amber-600">
                                    This template contains advanced HTML. Switch to HTML mode to preserve layout.
                                </p>
                            )}
                            <p className="text-xs text-muted-foreground">
                                Use the Insert Variable button above to add dynamic placeholders like {"{{full_name}}"}
                            </p>
                            {(unknownVariables.length > 0 || missingRequiredVariables.length > 0) &&
                                (editorState.subject.trim() || templateBody.trim()) && (
                                    <Alert className="border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-50">
                                        <AlertTriangleIcon className="size-4" />
                                        <AlertTitle>Template variables</AlertTitle>
                                        <AlertDescription className="text-amber-800 dark:text-amber-100">
                                            {unknownVariables.length > 0 && (
                                                <p>
                                                    Unknown:{" "}
                                                    <span className="font-mono">
                                                        {unknownVariables.map((v) => `{{${v}}}`).join(", ")}
                                                    </span>
                                                </p>
                                            )}
                                            {missingRequiredVariables.length > 0 && (
                                                <p>
                                                    Missing required:{" "}
                                                    <span className="font-mono">
                                                        {missingRequiredVariables.map((v) => `{{${v}}}`).join(", ")}
                                                    </span>
                                                </p>
                                            )}
                                        </AlertDescription>
                                    </Alert>
                                )}
                        </div>
                    </div>

                    <DialogFooter className="flex gap-2">
                        <Button variant="outline" onClick={handlePreview}>
                            <EyeIcon className="mr-2 size-4" />
                            Preview
                        </Button>
                        <Button
                            onClick={handleSave}
                            disabled={createTemplate.isPending || updateTemplate.isPending}
                        >
                            {(createTemplate.isPending || updateTemplate.isPending) && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            {editorState.template ? "Save Changes" : "Create Template"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Copy Template Dialog */}
            <Dialog open={copyDialogOpen} onOpenChange={setCopyDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Copy to My Templates</DialogTitle>
                        <DialogDescription>
                            Create a personal copy of this template that you can customize.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="copy-name">Template Name</Label>
                            <Input
                                id="copy-name"
                                placeholder="My Template Name"
                                value={copyShareName}
                                onChange={(e) => setCopyShareName(e.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setCopyDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleCopy}
                            disabled={copyToPersonal.isPending || !copyShareName.trim()}
                        >
                            {copyToPersonal.isPending && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            <CopyIcon className="mr-2 size-4" />
                            Copy Template
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Platform Library Copy Dialog */}
            <Dialog open={libraryCopyOpen} onOpenChange={setLibraryCopyOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Copy to Org Templates</DialogTitle>
                        <DialogDescription>
                            Create an organization template from this platform template.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="library-copy-name">Template Name</Label>
                            <Input
                                id="library-copy-name"
                                placeholder="Org Template Name"
                                value={libraryCopyName}
                                onChange={(e) => setLibraryCopyName(e.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setLibraryCopyOpen(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleLibraryCopy} disabled={copyFromLibrary.isPending}>
                            {copyFromLibrary.isPending && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            Copy Template
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Share Template Dialog */}
            <Dialog open={shareDialogOpen} onOpenChange={setShareDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Share with Organization</DialogTitle>
                        <DialogDescription>
                            Share this template with your organization. Your personal copy will remain unchanged.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="share-name">Template Name</Label>
                            <Input
                                id="share-name"
                                placeholder="Shared Template Name"
                                value={copyShareName}
                                onChange={(e) => setCopyShareName(e.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShareDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleShare}
                            disabled={shareWithOrg.isPending || !copyShareName.trim()}
                        >
                            {shareWithOrg.isPending && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            <ShareIcon className="mr-2 size-4" />
                            Share Template
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Send Test Email Dialog */}
            <Dialog
                open={testSendState.isOpen}
                onOpenChange={(open) => {
                    if (!open) {
                        handleCloseTestDialog()
                    }
                }}
            >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Send test email</DialogTitle>
                        <DialogDescription>
                            Send a test email for{" "}
                            <span className="font-medium">{testSendState.target?.name || "this template"}</span>.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="test-send-to">To email</Label>
                            <Input
                                id="test-send-to"
                                type="email"
                                value={testSendState.toEmail}
                                onChange={(e) => dispatchTestSend({
                                    type: "changeToEmail",
                                    value: e.target.value,
                                })}
                                placeholder="test@example.com"
                            />
                            <div className="flex items-start gap-3 rounded-lg border bg-muted/20 p-3">
                                <Checkbox
                                    id="test-send-ignore-opt-out"
                                    checked={testSendState.ignoreOptOut}
                                    onCheckedChange={(checked) => dispatchTestSend({
                                        type: "changeIgnoreOptOut",
                                        value: checked === true,
                                    })}
                                />
                                <div className="space-y-1">
                                    <Label htmlFor="test-send-ignore-opt-out" className="cursor-pointer">
                                        Send even if unsubscribed
                                    </Label>
                                    <p className="text-xs text-muted-foreground">
                                        Test-only override for marketing opt-outs. Hard bounces and complaints
                                        remain suppressed.
                                    </p>
                                </div>
                            </div>
                        </div>

                        <Accordion defaultValue={[]} className="rounded-lg">
                            <AccordionItem value="variables">
                                <AccordionTrigger>Variables (optional)</AccordionTrigger>
                                <AccordionContent>
                                    <div className="space-y-3">
                                        {testSendTemplateLoading ? (
                                            <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
                                                <Loader2Icon className="size-4 animate-spin" />
                                                Loading variables…
                                            </div>
                                        ) : (
                                            <>
                                                {testSendHasUnsubscribeUrl && (
                                                    <div className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
                                                        <span className="font-mono">
                                                            {"{{unsubscribe_url}}"}
                                                        </span>{" "}
                                                        is generated automatically for the recipient.
                                                    </div>
                                                )}

                                                {testSendEditableVariables.length === 0 ? (
                                                    <p className="text-sm text-muted-foreground">
                                                        No variables found in this template.
                                                    </p>
                                                ) : (
                                                    testSendEditableVariables.map((variableName) => (
                                                        <div key={variableName} className="space-y-1">
                                                            <Label
                                                                htmlFor={`test-var-${variableName}`}
                                                                className="font-mono text-xs"
                                                            >
                                                                {`{{${variableName}}}`}
                                                            </Label>
                                                            <Input
                                                                id={`test-var-${variableName}`}
                                                                value={testSendState.variables[variableName] ?? ""}
                                                                onChange={(e) => {
                                                                    dispatchTestSend({
                                                                        type: "changeVariable",
                                                                        name: variableName,
                                                                        value: e.target.value,
                                                                    })
                                                                    testSendTouchedRef.current[variableName] = true
                                                                }}
                                                            />
                                                        </div>
                                                    ))
                                                )}
                                            </>
                                        )}
                                    </div>
                                </AccordionContent>
                            </AccordionItem>
                        </Accordion>
                    </div>

                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={handleCloseTestDialog}
                            disabled={sendTest.isPending}
                        >
                            Cancel
                        </Button>
                        <Button onClick={handleSendTest} disabled={sendTest.isPending}>
                            {sendTest.isPending ? (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            ) : (
                                <SendIcon className="mr-2 size-4" />
                            )}
                            Send test
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Preview Modal */}
            <Dialog open={showPreview} onOpenChange={handlePreviewOpenChange}>
                <DialogContent className="max-w-2xl max-h-[80vh]">
                    <DialogHeader>
                        <DialogTitle>Email Preview</DialogTitle>
                        <DialogDescription>
                            Preview with sample data
                        </DialogDescription>
                    </DialogHeader>
                    <div className="border rounded-lg bg-white overflow-y-auto max-h-[60vh]">
                        {/* Email header section */}
                        <div className="bg-muted/30 border-b px-4 py-3 space-y-2">
                            <div className="flex items-center gap-2 text-sm">
                                <span className="font-medium text-muted-foreground w-16">From:</span>
                                <span className="text-foreground">
                                    {signatureData?.org_signature_company_name || "Your Company"} &lt;you@company.com&gt;
                                </span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <span className="font-medium text-muted-foreground w-16">To:</span>
                                <span className="text-foreground">John Smith &lt;john@example.com&gt;</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <span className="font-medium text-muted-foreground w-16">Subject:</span>
                                <span className="font-medium text-foreground">
                                    {previewSubject}
                                </span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <span className="font-medium text-muted-foreground w-16">Signature:</span>
                                <span className="text-foreground">
                                    {previewScope === "personal" ? "Personal signature" : "Organization signature"}
                                </span>
                            </div>
                        </div>
                        {/* Email body section */}
                        <div className="p-4">
                            <SafeHtmlContent
                                html={previewHtml}
                                className="prose prose-sm prose-stone max-w-none text-stone-900 [&_p]:whitespace-pre-wrap"
                            />
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    )
}
