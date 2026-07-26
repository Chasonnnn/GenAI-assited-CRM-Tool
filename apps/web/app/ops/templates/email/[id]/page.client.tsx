"use client"

import { useReducer, useRef, type MutableRefObject } from "react"
import { useParams, useRouter } from "next/navigation"
import DOMPurify from "dompurify"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Loader2Icon, ArrowLeftIcon, EyeIcon, AlertTriangleIcon, SendIcon, Trash2Icon } from "lucide-react"
import { toast } from "@/components/ui/toast"
import { PublishDialog } from "@/components/ops/templates/PublishDialog"
import { TemplateVariablePicker } from "@/components/email/TemplateVariablePicker"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { TrustedSanitizedHtmlContent } from "@/components/safe-html-content"
import { RichTextEditor, type RichTextEditorHandle } from "@/components/rich-text-editor"
import { normalizeTemplateHtml } from "@/lib/email-template-html"
import { insertAtCursor } from "@/lib/insert-at-cursor"
import {
    useCreatePlatformEmailTemplate,
    usePlatformEmailTemplate,
    usePlatformEmailTemplateVariables,
    useDeletePlatformEmailTemplate,
    usePublishPlatformEmailTemplate,
    useSendTestPlatformEmailTemplate,
    useUpdatePlatformEmailTemplate,
} from "@/lib/hooks/use-platform-templates"
import type { PlatformEmailTemplate } from "@/lib/api/platform"
import type { TemplateVariableRead } from "@/lib/types/template-variable"

type EditorMode = "visual" | "html"

type ActiveInsertionTarget = "subject" | "body_html" | "body_visual" | null

type TextFieldName = "name" | "subject" | "fromEmail" | "category" | "testOrgId" | "testEmail"

type BusyFlagName = "isSaving" | "isPublishing" | "isSendingTest"

type DialogName = "publish" | "delete"

type TemplatePageMode = "new" | "existing"

type PublicationState = "published" | "draft"

function createEmailTestOccurrenceId(): string {
    const cryptoApi = globalThis.crypto
    if (typeof cryptoApi?.randomUUID === "function") {
        return cryptoApi.randomUUID()
    }
    if (typeof cryptoApi?.getRandomValues !== "function") {
        throw new Error("Secure random UUID generation is unavailable")
    }
    const bytes = cryptoApi.getRandomValues(new Uint8Array(16))
    bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40
    bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"))
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`
}

interface TemplatePageBusyState {
    deletePending: boolean
    saving: boolean
    publishing: boolean
}

interface EmailTemplateEditorState {
    name: string
    subject: string
    fromEmail: string
    category: string
    body: string
    editorMode: EditorMode
    editorModeTouched: boolean
    isPublished: boolean
    showPublishDialog: boolean
    showDeleteDialog: boolean
    isSaving: boolean
    isPublishing: boolean
    testOrgId: string
    testEmail: string
    testVariables: Record<string, string>
    testTouched: Record<string, boolean>
    isSendingTest: boolean
    activeInsertionTarget: ActiveInsertionTarget
}

type EmailTemplateEditorAction =
    | { type: "setTextField"; field: TextFieldName; value: string }
    | { type: "setBody"; value: string; activeInsertionTarget?: ActiveInsertionTarget }
    | { type: "setEditorMode"; mode: EditorMode }
    | { type: "setActiveInsertionTarget"; target: ActiveInsertionTarget }
    | { type: "setPublished"; isPublished: boolean }
    | { type: "setDialog"; dialog: DialogName; open: boolean }
    | { type: "setBusy"; flag: BusyFlagName; value: boolean }
    | { type: "setTestVariable"; name: string; value: string }

const PREVIEW_ALLOWED_TAGS = [
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
]

const PREVIEW_ALLOWED_ATTRS = [
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
]

function extractTemplateVariables(text: string): string[] {
    if (!text) return []
    const matches = text.match(/{{\s*([a-zA-Z0-9_]+)\s*}}/g) ?? []
    const variables = matches.map((match) => match.replace(/{{\s*|\s*}}/g, ""))
    return Array.from(new Set(variables))
}

function getEditableVariableNames(subject: string, body: string): string[] {
    return extractTemplateVariables(`${subject}\n${body}`).filter((variable) => variable !== "unsubscribe_url")
}

function hasComplexTemplateHtml(body: string): boolean {
    return /<table|<tbody|<thead|<tr|<td|<img|<div/i.test(body)
}

function buildTestVariableSample(variableName: string, testEmail: string): string {
    const toEmail = testEmail.trim()
    switch (variableName) {
        case "first_name":
            return "Jordan"
        case "full_name":
            return "Jordan Smith"
        case "email":
            return toEmail
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
            return "Operator"
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
            return "Sample Org"
        case "org_logo_url":
            return ""
        default:
            return `TEST_${variableName.toUpperCase()}`
    }
}

function syncTestFields(state: EmailTemplateEditorState): EmailTemplateEditorState {
    const editableVariables = new Set(getEditableVariableNames(state.subject, state.body))
    const nextVariables: Record<string, string> = { ...state.testVariables }
    const nextTouched: Record<string, boolean> = { ...state.testTouched }

    for (const variableName of editableVariables) {
        if (nextVariables[variableName] === undefined) {
            nextVariables[variableName] = buildTestVariableSample(variableName, state.testEmail)
        }
    }

    for (const key of Object.keys(nextVariables)) {
        if (!editableVariables.has(key)) {
            delete nextVariables[key]
        }
    }

    for (const key of Object.keys(nextTouched)) {
        if (!editableVariables.has(key)) {
            delete nextTouched[key]
        }
    }

    return {
        ...state,
        testVariables: nextVariables,
        testTouched: nextTouched,
    }
}

function createEditorState(templateData: PlatformEmailTemplate | null): EmailTemplateEditorState {
    const draft = templateData?.draft
    const body = draft?.body ?? ""
    const editorMode: EditorMode = body && hasComplexTemplateHtml(body) ? "html" : "visual"

    return syncTestFields({
        name: draft?.name ?? "",
        subject: draft?.subject ?? "",
        fromEmail: draft?.from_email ?? "",
        category: draft?.category ?? "",
        body,
        editorMode,
        editorModeTouched: false,
        isPublished: (templateData?.published_version ?? 0) > 0,
        showPublishDialog: false,
        showDeleteDialog: false,
        isSaving: false,
        isPublishing: false,
        testOrgId: "",
        testEmail: "",
        testVariables: {},
        testTouched: {},
        isSendingTest: false,
        activeInsertionTarget: null,
    })
}

function templateEditorReducer(
    state: EmailTemplateEditorState,
    action: EmailTemplateEditorAction
): EmailTemplateEditorState {
    switch (action.type) {
        case "setTextField": {
            const nextState = { ...state, [action.field]: action.value }
            return action.field === "subject" ? syncTestFields(nextState) : nextState
        }
        case "setBody": {
            const nextState: EmailTemplateEditorState = {
                ...state,
                body: action.value,
                activeInsertionTarget:
                    action.activeInsertionTarget === undefined
                        ? state.activeInsertionTarget
                        : action.activeInsertionTarget,
            }
            if (
                !nextState.editorModeTouched &&
                nextState.editorMode !== "html" &&
                hasComplexTemplateHtml(action.value)
            ) {
                nextState.editorMode = "html"
                nextState.activeInsertionTarget = null
            }
            return syncTestFields(nextState)
        }
        case "setEditorMode":
            return {
                ...state,
                editorMode: action.mode,
                editorModeTouched: true,
                activeInsertionTarget:
                    state.activeInsertionTarget === "subject"
                        ? "subject"
                        : action.mode === "html"
                          ? "body_html"
                          : "body_visual",
            }
        case "setActiveInsertionTarget":
            return { ...state, activeInsertionTarget: action.target }
        case "setPublished":
            return { ...state, isPublished: action.isPublished }
        case "setDialog":
            return action.dialog === "publish"
                ? { ...state, showPublishDialog: action.open }
                : { ...state, showDeleteDialog: action.open }
        case "setBusy":
            return { ...state, [action.flag]: action.value }
        case "setTestVariable":
            return {
                ...state,
                testVariables: {
                    ...state.testVariables,
                    [action.name]: action.value,
                },
                testTouched: {
                    ...state.testTouched,
                    [action.name]: true,
                },
            }
    }
}

function recordSelection(
    el: HTMLInputElement | HTMLTextAreaElement,
    ref: MutableRefObject<{ start: number; end: number } | null>
) {
    ref.current = {
        start: el.selectionStart ?? el.value.length,
        end: el.selectionEnd ?? el.value.length,
    }
}

function applyTextInsertion(
    el: HTMLInputElement | HTMLTextAreaElement | null,
    selectionRef: MutableRefObject<{ start: number; end: number } | null>,
    currentValue: string,
    token: string,
    commit: (value: string) => void
) {
    const value = el?.value ?? currentValue
    const selection = el
        ? selectionRef.current ?? {
              start: el.selectionStart ?? value.length,
              end: el.selectionEnd ?? value.length,
          }
        : { start: value.length, end: value.length }
    const result = insertAtCursor(value, token, selection.start, selection.end)
    commit(result.nextValue)

    if (!el) return
    requestAnimationFrame(() => {
        el.focus()
        el.setSelectionRange(result.nextSelectionStart, result.nextSelectionEnd)
        selectionRef.current = {
            start: result.nextSelectionStart,
            end: result.nextSelectionEnd,
        }
    })
}

function getFromEmailError(fromEmail: string): string | null {
    const value = fromEmail.trim()
    if (!value) return null
    const basicEmail = /^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/
    const namedEmail = /^.+<\s*[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+\s*>$/
    if (basicEmail.test(value) || namedEmail.test(value)) return null
    return "Use a valid email or name <email@domain> format."
}

function buildPreviewHtml(body: string): string {
    let html = normalizeTemplateHtml(body || "")

    html = html.replace(/\{\{\s*unsubscribe_url\s*\}\}/gi, "")
    html = html.replace(
        /<a\b[^>]*\bhref\s*=\s*(["'])\s*\{\{\s*unsubscribe_url\s*\}\}\s*\1[^>]*>[\s\S]*?<\/a>/gi,
        ""
    )

    const unsubscribeUrl = "https://app.surrogacyforce.com/email/unsubscribe/EXAMPLE"
    const footerHtml = `
        <div style="margin-top: 14px; padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280;">
            <p style="margin: 0;">
                Manage email preferences:
                <a href="${unsubscribeUrl}" target="_blank" style="color: #2563eb; text-decoration: none;">Unsubscribe</a>
            </p>
        </div>
    `.trim()

    if (/<\/body\s*>/i.test(html)) {
        html = html.replace(/<\/body\s*>/i, `${footerHtml}</body>`)
    } else if (/<\/html\s*>/i.test(html)) {
        html = html.replace(/<\/html\s*>/i, `${footerHtml}</html>`)
    } else {
        html = `${html}${footerHtml}`
    }

    return DOMPurify.sanitize(html, {
        USE_PROFILES: { html: true },
        ADD_TAGS: PREVIEW_ALLOWED_TAGS,
        ADD_ATTR: PREVIEW_ALLOWED_ATTRS,
    })
}

function LoadingTemplate() {
    return (
        <div className="flex h-dvh items-center justify-center bg-stone-100 dark:bg-stone-950">
            <div className="flex items-center gap-2 text-stone-600 dark:text-stone-400">
                <Loader2Icon className="size-5 animate-spin" />
                <span>Loading template&hellip;</span>
            </div>
        </div>
    )
}

function TemplateLoadError({
    isRetrying,
    onRetry,
}: {
    isRetrying: boolean
    onRetry: () => void
}) {
    return (
        <div className="flex min-h-dvh items-center justify-center bg-stone-100 p-6 dark:bg-stone-950">
            <Card className="w-full max-w-lg">
                <CardHeader>
                    <CardTitle>Template unavailable</CardTitle>
                    <CardDescription>
                        The editor could not retrieve this template.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <Alert variant="destructive">
                        <AlertTriangleIcon aria-hidden="true" />
                        <AlertTitle>Unable to load email template</AlertTitle>
                        <AlertDescription>
                            Check your connection and access, then try loading the template again.
                        </AlertDescription>
                    </Alert>
                    <Button
                        type="button"
                        variant="outline"
                        disabled={isRetrying}
                        onClick={onRetry}
                    >
                        {isRetrying ? (
                            <>
                                <Loader2Icon className="animate-spin" aria-hidden="true" />
                                Retrying&hellip;
                            </>
                        ) : (
                            "Retry"
                        )}
                    </Button>
                </CardContent>
            </Card>
        </div>
    )
}

export default function PlatformEmailTemplatePage() {
    const params = useParams()
    const id = params?.id as string
    const isNew = id === "new"
    const templateId = isNew ? null : id

    const {
        data: templateData,
        isError,
        isFetching,
        isLoading,
        refetch,
    } = usePlatformEmailTemplate(templateId)
    const { data: templateVariables = [], isLoading: variablesLoading } = usePlatformEmailTemplateVariables()

    if (!isNew && isLoading) {
        return <LoadingTemplate />
    }

    if (!isNew && isError && !templateData) {
        return (
            <TemplateLoadError
                isRetrying={isFetching}
                onRetry={() => {
                    void refetch()
                }}
            />
        )
    }

    if (!isNew && !templateData) return null

    const editorTemplateData: PlatformEmailTemplate | null = isNew ? null : templateData ?? null
    const editorKey = editorTemplateData
        ? `${editorTemplateData.id}:${editorTemplateData.current_version}:${editorTemplateData.published_version}`
        : "new"

    return (
        <PlatformEmailTemplateEditor
            key={editorKey}
            id={id}
            isNew={isNew}
            templateId={templateId}
            templateData={editorTemplateData}
            templateVariables={templateVariables}
            variablesLoading={variablesLoading}
        />
    )
}

interface PlatformEmailTemplateEditorProps {
    id: string
    isNew: boolean
    templateId: string | null
    templateData: PlatformEmailTemplate | null
    templateVariables: TemplateVariableRead[]
    variablesLoading: boolean
}

function PlatformEmailTemplateEditor({
    id,
    isNew,
    templateId,
    templateData,
    templateVariables,
    variablesLoading,
}: PlatformEmailTemplateEditorProps) {
    const controller = useEmailTemplateController({
        id,
        isNew,
        templateId,
        templateData,
        templateVariables,
        variablesLoading,
    })
    const { actions, derived, refs, state } = controller
    const mode: TemplatePageMode = isNew ? "new" : "existing"

    return (
        <div className="min-h-dvh bg-stone-100 dark:bg-stone-950">
            <TemplatePageHeader
                mode={mode}
                name={state.name}
                publicationState={state.isPublished ? "published" : "draft"}
                busy={{
                    deletePending: controller.deletePending,
                    saving: state.isSaving,
                    publishing: state.isPublishing,
                }}
                onBack={actions.navigateBack}
                onNameChange={(value) => actions.setTextField("name", value)}
                onRequestDelete={() => actions.setDialog("delete", true)}
                onSave={actions.handleSave}
                onPublish={actions.handlePublish}
            />

            <DeleteTemplateDialog
                open={state.showDeleteDialog}
                name={state.name}
                deletePending={controller.deletePending}
                onOpenChange={(open) => actions.setDialog("delete", open)}
                onConfirm={actions.handleDelete}
            />

            <div className="grid gap-6 p-6 lg:grid-cols-[1.1fr_0.9fr]">
                <EmailContentCard
                    subject={state.subject}
                    fromEmail={state.fromEmail}
                    category={state.category}
                    body={state.body}
                    editorMode={state.editorMode}
                    hasComplexHtml={derived.hasComplexHtml}
                    fromEmailError={derived.fromEmailError}
                    templateVariables={templateVariables}
                    variablesLoading={variablesLoading}
                    unknownVariables={derived.unknownVariables}
                    missingRequiredVariables={derived.missingRequiredVariables}
                    subjectRef={refs.subjectRef}
                    htmlBodyRef={refs.htmlBodyRef}
                    visualBodyRef={refs.visualBodyRef}
                    onSubjectChange={(value) => actions.setTextField("subject", value)}
                    onFromEmailChange={(value) => actions.setTextField("fromEmail", value)}
                    onCategoryChange={(value) => actions.setTextField("category", value)}
                    onBodyChange={actions.setBody}
                    onEditorModeChange={actions.setEditorMode}
                    onInsertVariable={actions.insertVariable}
                    onInsertLogo={actions.insertOrgLogo}
                    onActiveInsertionTargetChange={actions.setActiveInsertionTarget}
                    onSubjectSelection={actions.recordSubjectSelection}
                    onHtmlBodySelection={actions.recordHtmlBodySelection}
                />

                <div className="space-y-6">
                    <PreviewCard previewHtml={derived.previewHtml} />
                    <SendTestEmailCard
                        mode={mode}
                        test={{
                            orgId: state.testOrgId,
                            email: state.testEmail,
                            variables: state.testVariables,
                            hasUnsubscribeUrl: derived.testHasUnsubscribeUrl,
                            editableVariableNames: derived.testEditableVariableNames,
                        }}
                        busy={{
                            sending: state.isSendingTest,
                            saving: state.isSaving,
                            publishing: state.isPublishing,
                        }}
                        onTestOrgIdChange={(value) => actions.setTextField("testOrgId", value)}
                        onTestEmailChange={(value) => actions.setTextField("testEmail", value)}
                        onTestVariableChange={actions.setTestVariable}
                        onSendTest={actions.handleSendTest}
                    />
                </div>
            </div>

            <PublishDialog
                open={state.showPublishDialog}
                onOpenChange={(open) => actions.setDialog("publish", open)}
                onPublish={actions.confirmPublish}
                isLoading={state.isPublishing}
                defaultPublishAll={templateData?.is_published_globally ?? true}
                initialOrgIds={templateData?.target_org_ids ?? []}
            />
        </div>
    )
}

function useEmailTemplateController({
    id,
    isNew,
    templateId,
    templateData,
    templateVariables,
    variablesLoading,
}: PlatformEmailTemplateEditorProps) {
    const { push, replace } = useRouter()
    const createTemplate = useCreatePlatformEmailTemplate()
    const updateTemplate = useUpdatePlatformEmailTemplate()
    const publishTemplate = usePublishPlatformEmailTemplate()
    const deleteTemplate = useDeletePlatformEmailTemplate()
    const sendTest = useSendTestPlatformEmailTemplate()
    const [state, dispatch] = useReducer(templateEditorReducer, templateData, createEditorState)

    const subjectRef = useRef<HTMLInputElement | null>(null)
    const subjectSelectionRef = useRef<{ start: number; end: number } | null>(null)
    const htmlBodyRef = useRef<HTMLTextAreaElement | null>(null)
    const htmlBodySelectionRef = useRef<{ start: number; end: number } | null>(null)
    const visualBodyRef = useRef<RichTextEditorHandle | null>(null)
    const testSendOccurrenceIdRef = useRef<string | null>(null)

    const canValidateVariables = !variablesLoading && templateVariables.length > 0
    const allowedVariableNames = new Set(templateVariables.map((variable) => variable.name))
    const requiredVariableNames: string[] = []
    for (const variable of templateVariables) {
        if (variable.required) {
            requiredVariableNames.push(variable.name)
        }
    }
    const usedVariableNames = extractTemplateVariables(`${state.subject}\n${state.body}`)
    const usedVariableNamesSet = new Set(usedVariableNames)
    const unknownVariables = canValidateVariables
        ? usedVariableNames.filter((variable) => !allowedVariableNames.has(variable))
        : []
    const missingRequiredVariables = canValidateVariables
        ? requiredVariableNames.filter((variable) => !usedVariableNamesSet.has(variable))
        : []
    const testEditableVariableNames = usedVariableNames.filter((variable) => variable !== "unsubscribe_url")
    const testHasUnsubscribeUrl = usedVariableNames.includes("unsubscribe_url")
    const fromEmailError = getFromEmailError(state.fromEmail)
    const hasComplexHtml = hasComplexTemplateHtml(state.body)
    const previewHtml = buildPreviewHtml(state.body)

    const setTextField = (field: TextFieldName, value: string) => {
        testSendOccurrenceIdRef.current = null
        dispatch({ type: "setTextField", field, value })
    }

    const setBody = (value: string) => {
        testSendOccurrenceIdRef.current = null
        dispatch({ type: "setBody", value })
    }

    const setDialog = (dialog: DialogName, open: boolean) => {
        dispatch({ type: "setDialog", dialog, open })
    }

    const setActiveInsertionTarget = (target: ActiveInsertionTarget) => {
        dispatch({ type: "setActiveInsertionTarget", target })
    }

    const setEditorMode = (mode: EditorMode) => {
        dispatch({ type: "setEditorMode", mode })
    }

    const setTestVariable = (name: string, value: string) => {
        testSendOccurrenceIdRef.current = null
        dispatch({ type: "setTestVariable", name, value })
    }

    const navigateBack = () => {
        push("/ops/templates?tab=email")
    }

    const recordSubjectSelection = (el: HTMLInputElement) => {
        recordSelection(el, subjectSelectionRef)
    }

    const recordHtmlBodySelection = (el: HTMLTextAreaElement) => {
        recordSelection(el, htmlBodySelectionRef)
    }

    const insertToken = (token: string) => {
        testSendOccurrenceIdRef.current = null
        if (state.activeInsertionTarget === "subject") {
            applyTextInsertion(subjectRef.current, subjectSelectionRef, state.subject, token, (value) =>
                dispatch({ type: "setTextField", field: "subject", value })
            )
            return
        }
        if (state.activeInsertionTarget === "body_html") {
            applyTextInsertion(htmlBodyRef.current, htmlBodySelectionRef, state.body, token, (value) =>
                dispatch({ type: "setBody", value })
            )
            return
        }
        if (state.activeInsertionTarget === "body_visual") {
            visualBodyRef.current?.insertText(token)
            return
        }

        if (state.editorMode === "html") {
            applyTextInsertion(htmlBodyRef.current, htmlBodySelectionRef, state.body, token, (value) =>
                dispatch({ type: "setBody", value })
            )
            return
        }
        visualBodyRef.current?.insertText(token)
    }

    const insertOrgLogo = () => {
        if (state.body.includes("{{org_logo_url}}")) return
        testSendOccurrenceIdRef.current = null
        const logo = `<p><img src="{{org_logo_url}}" alt="{{org_name}} logo" style="max-width: 160px; height: auto; display: block;" /></p>\n`
        if (state.editorMode === "visual") {
            visualBodyRef.current?.insertHtml(logo)
            dispatch({ type: "setActiveInsertionTarget", target: "body_visual" })
            return
        }
        applyTextInsertion(htmlBodyRef.current, htmlBodySelectionRef, state.body, logo, (value) =>
            dispatch({ type: "setBody", value, activeInsertionTarget: "body_html" })
        )
    }

    const insertVariable = (variableName: string) => {
        if (variableName === "unsubscribe_url") {
            toast.info("Unsubscribe link is added automatically.")
            return
        }
        insertToken(`{{${variableName}}}`)
    }

    const persistTemplate = async (): Promise<PlatformEmailTemplate> => {
        const payload = {
            name: state.name.trim(),
            subject: state.subject.trim(),
            body: state.body || "",
            from_email: state.fromEmail.trim() ? state.fromEmail.trim() : null,
            category: state.category.trim() ? state.category.trim() : null,
        }

        if (isNew) {
            const created = await createTemplate.mutateAsync(payload)
            replace(`/ops/templates/email/${created.id}`)
            return created
        }

        return updateTemplate.mutateAsync({
            id,
            payload: {
                ...payload,
                expected_version: templateData?.current_version ?? null,
            },
        })
    }

    const handleSave = async () => {
        if (!state.name.trim() || !state.subject.trim()) {
            toast.error("Name and subject are required")
            return
        }
        if (fromEmailError) {
            toast.error(fromEmailError)
            return
        }
        dispatch({ type: "setBusy", flag: "isSaving", value: true })
        const finishSaving = () => dispatch({ type: "setBusy", flag: "isSaving", value: false })
        try {
            const saved = await persistTemplate()
            dispatch({ type: "setPublished", isPublished: (saved.published_version ?? 0) > 0 })
            toast.success("Template saved")
            finishSaving()
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to save template")
            finishSaving()
        }
    }

    const handlePublish = () => {
        if (!state.name.trim() || !state.subject.trim()) {
            toast.error("Name and subject are required")
            return
        }
        if (fromEmailError) {
            toast.error(fromEmailError)
            return
        }
        if (!state.body.trim()) {
            toast.error("Email body is required")
            return
        }
        dispatch({ type: "setDialog", dialog: "publish", open: true })
    }

    const confirmPublish = async (publishAll: boolean, orgIds: string[]) => {
        dispatch({ type: "setBusy", flag: "isPublishing", value: true })
        const finishPublishing = () => dispatch({ type: "setBusy", flag: "isPublishing", value: false })
        try {
            const saved = await persistTemplate()
            await publishTemplate.mutateAsync({
                id: saved.id,
                payload: {
                    publish_all: publishAll,
                    org_ids: publishAll ? null : orgIds,
                },
            })
            dispatch({ type: "setPublished", isPublished: true })
            dispatch({ type: "setDialog", dialog: "publish", open: false })
            toast.success("Template published")
            finishPublishing()
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to publish template")
            finishPublishing()
        }
    }

    const handleSendTest = async () => {
        if (isNew) return

        if (!state.testOrgId.trim()) {
            toast.error("Organization ID is required")
            return
        }
        if (!state.testEmail.trim()) {
            toast.error("Test email is required")
            return
        }

        const overrides: Record<string, string> = {}
        for (const variableName of testEditableVariableNames) {
            if (!state.testTouched[variableName]) continue
            const trimmed = (state.testVariables[variableName] ?? "").trim()
            if (!trimmed) continue
            overrides[variableName] = trimmed
        }

        dispatch({ type: "setBusy", flag: "isSendingTest", value: true })
        const finishSendingTest = () => dispatch({ type: "setBusy", flag: "isSendingTest", value: false })
        try {
            const saved = await persistTemplate()
            const occurrenceId =
                testSendOccurrenceIdRef.current ?? createEmailTestOccurrenceId()
            testSendOccurrenceIdRef.current = occurrenceId
            const result = await sendTest.mutateAsync({
                id: saved.id,
                payload: {
                    org_id: state.testOrgId.trim(),
                    to_email: state.testEmail.trim(),
                    variables: overrides,
                    idempotency_key: occurrenceId,
                },
            })

            const providerLabel =
                result.provider_used === "resend"
                    ? "Resend"
                    : result.provider_used === "gmail"
                      ? "Gmail"
                      : "provider"
            toast.success(
                result.queued
                    ? `Test email queued via ${providerLabel}`
                    : `Test email sent via ${providerLabel}`,
            )
            testSendOccurrenceIdRef.current = null
            finishSendingTest()
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to send test email")
            finishSendingTest()
        }
    }

    const handleDelete = async () => {
        if (!templateId) return
        try {
            await deleteTemplate.mutateAsync({ id: templateId })
            toast.success("Template deleted")
            dispatch({ type: "setDialog", dialog: "delete", open: false })
            push("/ops/templates?tab=email")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to delete template")
        }
    }

    return {
        actions: {
            confirmPublish,
            handleDelete,
            handlePublish,
            handleSave,
            handleSendTest,
            insertOrgLogo,
            insertVariable,
            navigateBack,
            recordHtmlBodySelection,
            recordSubjectSelection,
            setActiveInsertionTarget,
            setBody,
            setDialog,
            setEditorMode,
            setTestVariable,
            setTextField,
        },
        deletePending: deleteTemplate.isPending,
        derived: {
            fromEmailError,
            hasComplexHtml,
            missingRequiredVariables,
            previewHtml,
            testEditableVariableNames,
            testHasUnsubscribeUrl,
            unknownVariables,
        },
        refs: {
            htmlBodyRef,
            subjectRef,
            visualBodyRef,
        },
        state,
    }
}

interface TemplatePageHeaderProps {
    mode: TemplatePageMode
    name: string
    publicationState: PublicationState
    busy: TemplatePageBusyState
    onBack: () => void
    onNameChange: (value: string) => void
    onRequestDelete: () => void
    onSave: () => void
    onPublish: () => void
}

function TemplatePageHeader({
    mode,
    name,
    publicationState,
    busy,
    onBack,
    onNameChange,
    onRequestDelete,
    onSave,
    onPublish,
}: TemplatePageHeaderProps) {
    const isPublished = publicationState === "published"
    const actionsDisabled = busy.saving || busy.publishing

    return (
        <div className="flex h-16 items-center justify-between border-b border-stone-200 bg-white px-6 dark:border-stone-800 dark:bg-stone-900">
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" aria-label="Back to email templates" onClick={onBack}>
                    <ArrowLeftIcon className="size-5" aria-hidden="true" />
                </Button>
                <Input
                    id="template-name"
                    aria-label="Template name"
                    value={name}
                    onChange={(event) => onNameChange(event.target.value)}
                    placeholder="Template name..."
                    className="h-9 w-64 border-none bg-transparent px-0 text-lg font-semibold focus-visible:ring-0"
                />
                <Badge variant={isPublished ? "default" : "secondary"} className={isPublished ? "bg-teal-500" : ""}>
                    {isPublished ? "Published" : "Draft"}
                </Badge>
            </div>
            <div className="flex items-center gap-3">
                {mode === "existing" && (
                    <Button
                        variant="destructive"
                        size="sm"
                        onClick={onRequestDelete}
                        disabled={busy.deletePending || actionsDisabled}
                    >
                        {busy.deletePending ? (
                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                        ) : (
                            <Trash2Icon className="mr-2 size-4" />
                        )}
                        Delete
                    </Button>
                )}
                <Button variant="outline" size="sm" onClick={onSave} disabled={actionsDisabled}>
                    {busy.saving && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                    Save Draft
                </Button>
                <Button size="sm" onClick={onPublish} disabled={actionsDisabled}>
                    {busy.publishing && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                    Publish
                </Button>
            </div>
        </div>
    )
}

interface DeleteTemplateDialogProps {
    open: boolean
    name: string
    deletePending: boolean
    onOpenChange: (open: boolean) => void
    onConfirm: () => void
}

function DeleteTemplateDialog({
    open,
    name,
    deletePending,
    onOpenChange,
    onConfirm,
}: DeleteTemplateDialogProps) {
    return (
        <AlertDialog open={open} onOpenChange={onOpenChange}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>Delete template?</AlertDialogTitle>
                    <AlertDialogDescription>
                        This permanently deletes{" "}
                        <span className="font-medium text-foreground">{name || "this template"}</span>. This cannot be
                        undone.
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel disabled={deletePending}>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                        onClick={onConfirm}
                        disabled={deletePending}
                        className="bg-destructive text-white hover:bg-destructive/90"
                    >
                        Delete
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    )
}

interface EmailContentCardProps {
    subject: string
    fromEmail: string
    category: string
    body: string
    editorMode: EditorMode
    hasComplexHtml: boolean
    fromEmailError: string | null
    templateVariables: TemplateVariableRead[]
    variablesLoading: boolean
    unknownVariables: string[]
    missingRequiredVariables: string[]
    subjectRef: MutableRefObject<HTMLInputElement | null>
    htmlBodyRef: MutableRefObject<HTMLTextAreaElement | null>
    visualBodyRef: MutableRefObject<RichTextEditorHandle | null>
    onSubjectChange: (value: string) => void
    onFromEmailChange: (value: string) => void
    onCategoryChange: (value: string) => void
    onBodyChange: (value: string) => void
    onEditorModeChange: (mode: EditorMode) => void
    onInsertVariable: (variableName: string) => void
    onInsertLogo: () => void
    onActiveInsertionTargetChange: (target: ActiveInsertionTarget) => void
    onSubjectSelection: (el: HTMLInputElement) => void
    onHtmlBodySelection: (el: HTMLTextAreaElement) => void
}

function EmailContentCard(props: EmailContentCardProps) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Email Content</CardTitle>
                <CardDescription>Design the default template shared to org libraries.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <TemplateDetailsFields {...props} />
                <EmailBodyEditor {...props} />
            </CardContent>
        </Card>
    )
}

function TemplateDetailsFields({
    subject,
    fromEmail,
    category,
    fromEmailError,
    subjectRef,
    onSubjectChange,
    onFromEmailChange,
    onCategoryChange,
    onActiveInsertionTargetChange,
    onSubjectSelection,
}: EmailContentCardProps) {
    return (
        <>
            <div className="space-y-2">
                <Label htmlFor="template-subject">Subject *</Label>
                <Input
                    id="template-subject"
                    ref={subjectRef}
                    value={subject}
                    onChange={(event) => onSubjectChange(event.target.value)}
                    onFocus={(event) => {
                        onActiveInsertionTargetChange("subject")
                        onSubjectSelection(event.currentTarget)
                    }}
                    onKeyUp={(event) => onSubjectSelection(event.currentTarget)}
                    onMouseUp={(event) => onSubjectSelection(event.currentTarget)}
                    onSelect={(event) => onSubjectSelection(event.currentTarget)}
                    placeholder="You're invited to join {{org_name}}"
                />
                <p className="text-xs text-muted-foreground">Used as the default subject in org copies.</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                    <Label htmlFor="template-from-email">From (optional)</Label>
                    <Input
                        id="template-from-email"
                        value={fromEmail}
                        onChange={(event) => onFromEmailChange(event.target.value)}
                        placeholder="Invites <invites@surrogacyforce.com>"
                    />
                    {fromEmailError ? (
                        <p className="text-xs text-red-600">{fromEmailError}</p>
                    ) : (
                        <p className="text-xs text-muted-foreground">Leave blank to use the org default sender.</p>
                    )}
                </div>
                <div className="space-y-2">
                    <Label htmlFor="template-category">Category (optional)</Label>
                    <Input
                        id="template-category"
                        value={category}
                        onChange={(event) => onCategoryChange(event.target.value)}
                        placeholder="onboarding"
                    />
                    <p className="text-xs text-muted-foreground">Helps orgs filter templates in their library.</p>
                </div>
            </div>
        </>
    )
}

function EmailBodyEditor({
    body,
    editorMode,
    hasComplexHtml,
    templateVariables,
    variablesLoading,
    unknownVariables,
    missingRequiredVariables,
    htmlBodyRef,
    visualBodyRef,
    onBodyChange,
    onEditorModeChange,
    onInsertVariable,
    onInsertLogo,
    onActiveInsertionTargetChange,
    onHtmlBodySelection,
}: EmailContentCardProps) {
    return (
        <div className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <Label id="template-body-label" htmlFor={editorMode === "html" ? "template-body-html" : undefined}>
                    Email Body *
                </Label>
                <div className="flex flex-wrap items-center gap-2">
                    <ToggleGroup
                        multiple={false}
                        value={editorMode ? [editorMode] : []}
                        onValueChange={(value) => {
                            const next = value[0] as EditorMode | undefined
                            if (next) onEditorModeChange(next)
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
                        disabled={variablesLoading || templateVariables.length === 0}
                        triggerLabel={variablesLoading ? "Loading..." : "Insert Variable"}
                        onSelect={(variable) => onInsertVariable(variable.name)}
                    />
                    <Button type="button" variant="ghost" size="sm" onClick={onInsertLogo}>
                        Insert Logo
                    </Button>
                </div>
            </div>
            {editorMode === "visual" ? (
                <RichTextEditor
                    ref={visualBodyRef}
                    content={body}
                    onChange={onBodyChange}
                    onFocus={() => onActiveInsertionTargetChange("body_visual")}
                    ariaLabelledBy="template-body-label"
                    placeholder="Write your email content here..."
                    minHeight="220px"
                    maxHeight="420px"
                    enableImages
                    enableEmojiPicker
                />
            ) : (
                <Textarea
                    id="template-body-html"
                    aria-labelledby="template-body-label"
                    ref={htmlBodyRef}
                    value={body}
                    onChange={(event) => onBodyChange(event.target.value)}
                    onFocus={(event) => {
                        onActiveInsertionTargetChange("body_html")
                        onHtmlBodySelection(event.currentTarget)
                    }}
                    onKeyUp={(event) => onHtmlBodySelection(event.currentTarget)}
                    onMouseUp={(event) => onHtmlBodySelection(event.currentTarget)}
                    onSelect={(event) => onHtmlBodySelection(event.currentTarget)}
                    placeholder="Paste or edit the HTML for this template..."
                    className="min-h-[240px] font-mono text-xs leading-relaxed"
                />
            )}
            {editorMode === "visual" && hasComplexHtml && (
                <p className="text-xs text-amber-600">
                    This template contains advanced HTML. Switch to HTML mode to preserve layout.
                </p>
            )}
            <p className="text-xs text-muted-foreground">
                Use double braces for variables, e.g. <span className="font-mono">{"{{first_name}}"}</span>.
            </p>
            <VariableValidationAlert
                subjectOrBodyHasContent={Boolean(body.trim())}
                unknownVariables={unknownVariables}
                missingRequiredVariables={missingRequiredVariables}
            />
        </div>
    )
}

interface VariableValidationAlertProps {
    subjectOrBodyHasContent: boolean
    unknownVariables: string[]
    missingRequiredVariables: string[]
}

function VariableValidationAlert({
    subjectOrBodyHasContent,
    unknownVariables,
    missingRequiredVariables,
}: VariableValidationAlertProps) {
    if (!subjectOrBodyHasContent || (unknownVariables.length === 0 && missingRequiredVariables.length === 0)) {
        return null
    }

    return (
        <Alert className="border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-50">
            <AlertTriangleIcon className="size-4" />
            <AlertTitle>Template variables</AlertTitle>
            <AlertDescription className="text-amber-800 dark:text-amber-100">
                {unknownVariables.length > 0 && (
                    <p>
                        Unknown:{" "}
                        <span className="font-mono">{unknownVariables.map((v) => `{{${v}}}`).join(", ")}</span>
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
    )
}

function PreviewCard({ previewHtml }: { previewHtml: string }) {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <EyeIcon className="size-4" />
                    Preview
                </CardTitle>
                <CardDescription>Sanitized preview of the HTML output.</CardDescription>
            </CardHeader>
            <CardContent>
                {previewHtml ? (
                    <TrustedSanitizedHtmlContent html={previewHtml} className="prose prose-sm max-w-none" />
                ) : (
                    <div className="text-sm text-muted-foreground">Add content to preview the template.</div>
                )}
            </CardContent>
        </Card>
    )
}

interface SendTestEmailCardProps {
    mode: TemplatePageMode
    test: {
        orgId: string
        email: string
        variables: Record<string, string>
        hasUnsubscribeUrl: boolean
        editableVariableNames: string[]
    }
    busy: {
        sending: boolean
        saving: boolean
        publishing: boolean
    }
    onTestOrgIdChange: (value: string) => void
    onTestEmailChange: (value: string) => void
    onTestVariableChange: (name: string, value: string) => void
    onSendTest: () => void
}

function SendTestEmailCard({
    mode,
    test,
    busy,
    onTestOrgIdChange,
    onTestEmailChange,
    onTestVariableChange,
    onSendTest,
}: SendTestEmailCardProps) {
    const isNew = mode === "new"

    return (
        <Card>
            <CardHeader>
                <CardTitle>Send test email</CardTitle>
                <CardDescription>Render this template for a specific organization and send to a test inbox.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
                <div className="space-y-2">
                    <Label htmlFor="test-org-id">Organization ID</Label>
                    <Input
                        id="test-org-id"
                        value={test.orgId}
                        onChange={(event) => onTestOrgIdChange(event.target.value)}
                        placeholder="UUID of an organization"
                    />
                </div>
                <div className="space-y-2">
                    <Label htmlFor="test-email">Test email</Label>
                    <Input
                        id="test-email"
                        type="email"
                        value={test.email}
                        onChange={(event) => onTestEmailChange(event.target.value)}
                        placeholder="test@example.com"
                    />
                </div>

                <Accordion defaultValue={[]} className="rounded-lg">
                    <AccordionItem value="variables">
                        <AccordionTrigger>Variables (optional)</AccordionTrigger>
                        <AccordionContent>
                            <div className="space-y-3">
                                {test.hasUnsubscribeUrl && (
                                    <div className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
                                        <span className="font-mono">{"{{unsubscribe_url}}"}</span> is generated
                                        automatically for the recipient.
                                    </div>
                                )}

                                {test.editableVariableNames.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">
                                        No variables found in this template.
                                    </p>
                                ) : (
                                    test.editableVariableNames.map((variableName) => (
                                        <div key={variableName} className="space-y-1">
                                            <Label htmlFor={`test-var-${variableName}`} className="font-mono text-xs">
                                                {`{{${variableName}}}`}
                                            </Label>
                                            <Input
                                                id={`test-var-${variableName}`}
                                                value={test.variables[variableName] ?? ""}
                                                onChange={(event) =>
                                                    onTestVariableChange(variableName, event.target.value)
                                                }
                                            />
                                        </div>
                                    ))
                                )}
                            </div>
                        </AccordionContent>
                    </AccordionItem>
                </Accordion>

                {isNew && <p className="text-xs text-muted-foreground">Save template first.</p>}

                <Button onClick={onSendTest} disabled={isNew || busy.sending || busy.saving || busy.publishing}>
                    {busy.sending ? (
                        <Loader2Icon className="mr-2 size-4 animate-spin" />
                    ) : (
                        <SendIcon className="mr-2 size-4" />
                    )}
                    Send test
                </Button>
            </CardContent>
        </Card>
    )
}
