"use client"

import { useRef, useState, type Dispatch, type MutableRefObject, type SetStateAction } from "react"
import { useRouter } from "next/navigation"
import DOMPurify from "dompurify"
import { toast } from "@/components/ui/toast"
import { EyeIcon, Loader2Icon, PlusIcon } from "lucide-react"
import { TrustedSanitizedHtmlContent } from "@/components/safe-html-content"
import { EmptyState } from "@/components/empty-state"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldError, FieldLabel, ValidatedField } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/page-header"
import { ApiError } from "@/lib/api"
import { useFormValidation, type FormFieldErrors } from "@/lib/forms/use-form-validation"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { TemplateVariablePicker } from "@/components/email/TemplateVariablePicker"
import { RichTextEditor, type RichTextEditorHandle } from "@/components/rich-text-editor"
import { normalizeTemplateHtml } from "@/lib/email-template-html"
import { insertAtCursor } from "@/lib/insert-at-cursor"
import {
    useCreatePlatformSystemEmailTemplate,
    usePlatformSystemEmailTemplateVariables,
} from "@/lib/hooks/use-platform-templates"

type EditorMode = "visual" | "html"

type ActiveInsertionTarget = "subject" | "body_html" | "body_visual" | null
type TextSelectionRef = MutableRefObject<{ start: number; end: number } | null>
type TemplateVariable = NonNullable<ReturnType<typeof usePlatformSystemEmailTemplateVariables>["data"]>[number]

function extractTemplateVariables(text: string): string[] {
    if (!text) return []
    const matches = text.match(/{{\s*([a-zA-Z0-9_]+)\s*}}/g) ?? []
    const variables = matches.map((match) => match.replace(/{{\s*|\s*}}/g, ""))
    return Array.from(new Set(variables))
}

function buildSystemKeyFromName(name: string): string {
    const key = name
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "")
        .replace(/_{2,}/g, "_")
    return key.slice(0, 100)
}

function getFromEmailError(fromEmail: string): string | null {
    const value = fromEmail.trim()
    if (!value) return null
    const basicEmail = /^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/
    const namedEmail = /^.+<\s*[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+\s*>$/
    if (basicEmail.test(value) || namedEmail.test(value)) return null
    return "Use a valid email or name <email@domain> format."
}

function getSystemKeyError(systemKey: string): string | null {
    const value = systemKey.trim()
    if (!value) return "System key is required."
    if (!/^[a-z0-9_]+$/.test(value)) {
        return "Use only lowercase letters, numbers, and underscores."
    }
    if (value.length < 2 || value.length > 100) {
        return "System key must be between 2 and 100 characters."
    }
    if (value === "new") return "System key cannot be 'new'."
    return null
}

function getNameError(name: string): string | null {
    if (!name.trim()) return "Name is required."
    if (name.trim().length > 120) return "Name must be 120 characters or less."
    return null
}

function getSubjectError(subject: string): string | null {
    if (!subject.trim()) return "Subject is required."
    if (subject.trim().length > 200) return "Subject must be 200 characters or less."
    return null
}

function getBodyError(body: string): string | null {
    if (!body.trim()) return "Body is required."
    return null
}

type NewSystemTemplateValues = {
    system_key: string
    name: string
    subject: string
    from_email: string
    body: string
}

function validateNewSystemTemplate(values: NewSystemTemplateValues): FormFieldErrors<NewSystemTemplateValues> {
    return {
        system_key: getSystemKeyError(values.system_key) ?? undefined,
        name: getNameError(values.name) ?? undefined,
        subject: getSubjectError(values.subject) ?? undefined,
        from_email: getFromEmailError(values.from_email) ?? undefined,
        body: getBodyError(values.body) ?? undefined,
    }
}

type NewSystemTemplateField = keyof NewSystemTemplateValues

function hasComplexEmailHtml(body: string): boolean {
    return /<table|<tbody|<thead|<tr|<td|<img|<div/i.test(body)
}

function buildPreviewHtml(body: string): string {
    const platformLogoUrl =
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='180' height='54'><rect width='100%' height='100%' rx='10' fill='%23e5e7eb'/><text x='50%' y='55%' text-anchor='middle' font-family='Arial' font-size='14' fill='%236b7280'>Logo</text></svg>"
    const rawHtml = body
        .replace(/\{\{org_name\}\}/g, "Sample Organization")
        .replace(/\{\{org_slug\}\}/g, "sample-org")
        .replace(/\{\{first_name\}\}/g, "Avery")
        .replace(/\{\{full_name\}\}/g, "Avery James")
        .replace(/\{\{email\}\}/g, "avery@example.com")
        .replace(/\{\{inviter_text\}\}/g, "")
        .replace(/\{\{role_title\}\}/g, "Admin")
        .replace(/\{\{invite_url\}\}/g, "https://app.surrogacyforce.com/invite/EXAMPLE")
        .replace(/\{\{expires_block\}\}/g, "<p>This invitation expires in 7 days.</p>")
        .replace(/\{\{platform_logo_url\}\}/g, platformLogoUrl)
        .replace(
            /\{\{platform_logo_block\}\}/g,
            `<img src="${platformLogoUrl}" alt="Platform logo" style="max-width: 180px; height: auto; display: block; margin: 0 auto 6px auto;" />`
        )
        .replace(/\{\{unsubscribe_url\}\}/g, "https://app.surrogacyforce.com/email/unsubscribe/EXAMPLE")

    return DOMPurify.sanitize(normalizeTemplateHtml(rawHtml), {
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
            "src",
            "alt",
            "href",
            "target",
        ],
    })
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

function insertIntoTextControl(
    el: HTMLInputElement | HTMLTextAreaElement | null,
    selectionRef: MutableRefObject<{ start: number; end: number } | null>,
    setValue: Dispatch<SetStateAction<string>>,
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

export default function PlatformSystemEmailTemplateNewPage() {
    const { push } = useRouter()
    const createTemplate = useCreatePlatformSystemEmailTemplate()
    const { data: templateVariables = [], isLoading: variablesLoading } =
        usePlatformSystemEmailTemplateVariables("org_invite")

    const [manualSystemKey, setManualSystemKey] = useState<string | null>(null)
    const [name, setName] = useState("")
    const [subject, setSubject] = useState("")
    const [fromEmail, setFromEmail] = useState("")
    const [body, setBody] = useState("")
    const [isActive, setIsActive] = useState(true)
    const [saving, setSaving] = useState(false)

    const [editorMode, setEditorMode] = useState<EditorMode>("visual")
    const [editorModeTouched, setEditorModeTouched] = useState(false)

    const subjectRef = useRef<HTMLInputElement | null>(null)
    const subjectSelectionRef = useRef<{ start: number; end: number } | null>(null)
    const htmlBodyRef = useRef<HTMLTextAreaElement | null>(null)
    const htmlBodySelectionRef = useRef<{ start: number; end: number } | null>(null)
    const visualBodyRef = useRef<RichTextEditorHandle | null>(null)
    const activeInsertionTargetRef = useRef<ActiveInsertionTarget>(null)

    const setActiveInsertionTarget = (target: ActiveInsertionTarget) => {
        activeInsertionTargetRef.current = target
    }

    const systemKey = manualSystemKey ?? buildSystemKeyFromName(name)

    const validation = useFormValidation({
        values: { system_key: systemKey, name, subject, from_email: fromEmail, body },
        validate: validateNewSystemTemplate,
    })
    const hasComplexHtml = hasComplexEmailHtml(body)

    const effectiveEditorMode: EditorMode =
        editorMode === "visual" && hasComplexHtml && !editorModeTouched ? "html" : editorMode

    const canValidateVariables = !variablesLoading && templateVariables.length > 0
    const allowedVariableNames = new Set(templateVariables.map((variable) => variable.name))
    const requiredVariableNames: string[] = []
    for (const variable of templateVariables) {
        if (variable.required) {
            requiredVariableNames.push(variable.name)
        }
    }
    const usedVariableNames = extractTemplateVariables(`${subject}\n${body}`)
    const unknownVariables = canValidateVariables
        ? usedVariableNames.filter((variable) => !allowedVariableNames.has(variable))
        : []
    const usedVariableNamesSet = new Set(usedVariableNames)
    const missingRequiredVariables = canValidateVariables
        ? requiredVariableNames.filter((variable) => !usedVariableNamesSet.has(variable))
        : []
    const previewHtml = buildPreviewHtml(body)

    const insertToken = (token: string) => {
        const activeInsertionTarget = activeInsertionTargetRef.current
        const insertionTarget =
            activeInsertionTarget === "body_visual" && effectiveEditorMode === "html" ? null : activeInsertionTarget

        if (insertionTarget === "subject") {
            insertIntoTextControl(subjectRef.current, subjectSelectionRef, setSubject, token)
            return
        }
        if (insertionTarget === "body_html") {
            insertIntoTextControl(htmlBodyRef.current, htmlBodySelectionRef, setBody, token)
            return
        }
        if (insertionTarget === "body_visual") {
            visualBodyRef.current?.insertText(token)
            return
        }

        if (effectiveEditorMode === "html") {
            insertIntoTextControl(htmlBodyRef.current, htmlBodySelectionRef, setBody, token)
            return
        }
        visualBodyRef.current?.insertText(token)
    }

    const insertPlatformLogo = () => {
        if (body.includes("{{platform_logo_block}}")) return
        const block = `<p>{{platform_logo_block}}</p>\n`
        if (effectiveEditorMode === "visual") {
            visualBodyRef.current?.insertHtml(block)
            setActiveInsertionTarget("body_visual")
            return
        }
        insertIntoTextControl(htmlBodyRef.current, htmlBodySelectionRef, setBody, block)
        setActiveInsertionTarget("body_html")
    }

    const handleCreate = async (values: NewSystemTemplateValues) => {
        if (saving) return
        setSaving(true)
        const finishSaving = () => setSaving(false)
        try {
            const created = await createTemplate.mutateAsync({
                system_key: values.system_key.trim(),
                name: values.name.trim(),
                subject: values.subject.trim(),
                from_email: values.from_email.trim() ? values.from_email.trim() : null,
                body: values.body,
                is_active: isActive,
            })
            toast.success("System email template created")
            push(`/ops/templates/system/${created.system_key}`)
            finishSaving()
        } catch (error) {
            finishSaving()
            if (error instanceof ApiError && error.status === 409) {
                validation.setServerErrors({ system_key: "A template with this system key already exists." })
                return
            }
            const message = validation.applyApiError(error, {
                fields: ["system_key", "name", "subject", "from_email", "body"],
                fallback: "Couldn't create system email.",
            })
            if (message) toast.error(message)
        }
    }

    return (
        <div>
            <PageHeader
                title="New System Email"
                back={{ href: "/ops/templates?tab=system", label: "Back to templates" }}
                sticky
                className="top-14"
                actions={
                    <Button onClick={validation.handleSubmit(handleCreate)} disabled={saving}>
                        {saving ? (
                            <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                        ) : (
                            <PlusIcon className="size-4" aria-hidden="true" />
                        )}
                        Create
                    </Button>
                }
            />

            <div className="grid gap-6 p-6 lg:grid-cols-3">
                <div className="space-y-6 lg:col-span-2">
                    <TemplateSettingsCard
                        systemKey={systemKey}
                        systemKeyError={validation.errorFor("system_key")}
                        name={name}
                        nameError={validation.errorFor("name")}
                        subject={subject}
                        subjectError={validation.errorFor("subject")}
                        fromEmail={fromEmail}
                        fromEmailError={validation.errorFor("from_email")}
                        onFieldBlur={validation.touch}
                        isActive={isActive}
                        templateVariables={templateVariables}
                        variablesLoading={variablesLoading}
                        subjectRef={subjectRef}
                        subjectSelectionRef={subjectSelectionRef}
                        onSystemKeyChange={setManualSystemKey}
                        onNameChange={setName}
                        onSubjectChange={setSubject}
                        onFromEmailChange={setFromEmail}
                        onActiveChange={setIsActive}
                        onInsertToken={insertToken}
                        onActiveInsertionTargetChange={setActiveInsertionTarget}
                    />

                    <TemplateContentCard
                        effectiveEditorMode={effectiveEditorMode}
                        hasComplexHtml={hasComplexHtml}
                        body={body}
                        bodyError={validation.errorFor("body")}
                        onBodyBlur={() => validation.touch("body")}
                        templateVariables={templateVariables}
                        variablesLoading={variablesLoading}
                        visualBodyRef={visualBodyRef}
                        htmlBodyRef={htmlBodyRef}
                        htmlBodySelectionRef={htmlBodySelectionRef}
                        activeInsertionTargetRef={activeInsertionTargetRef}
                        unknownVariables={unknownVariables}
                        missingRequiredVariables={missingRequiredVariables}
                        showVariableWarnings={Boolean(subject.trim() || body.trim())}
                        onBodyChange={setBody}
                        onEditorModeChange={setEditorMode}
                        onEditorModeTouchedChange={setEditorModeTouched}
                        onInsertToken={insertToken}
                        onInsertPlatformLogo={insertPlatformLogo}
                        onActiveInsertionTargetChange={setActiveInsertionTarget}
                    />
                </div>

                <TemplatePreviewCard hasContent={Boolean(body.trim())} previewHtml={previewHtml} />
            </div>
        </div>
    )
}

function TemplateSettingsCard({
    systemKey,
    systemKeyError,
    name,
    nameError,
    subject,
    subjectError,
    fromEmail,
    fromEmailError,
    isActive,
    templateVariables,
    variablesLoading,
    subjectRef,
    subjectSelectionRef,
    onFieldBlur,
    onSystemKeyChange,
    onNameChange,
    onSubjectChange,
    onFromEmailChange,
    onActiveChange,
    onInsertToken,
    onActiveInsertionTargetChange,
}: {
    systemKey: string
    systemKeyError: string | undefined
    name: string
    nameError: string | undefined
    subject: string
    subjectError: string | undefined
    fromEmail: string
    fromEmailError: string | undefined
    onFieldBlur: (field: NewSystemTemplateField) => void
    isActive: boolean
    templateVariables: TemplateVariable[]
    variablesLoading: boolean
    subjectRef: MutableRefObject<HTMLInputElement | null>
    subjectSelectionRef: TextSelectionRef
    onSystemKeyChange: Dispatch<SetStateAction<string | null>>
    onNameChange: Dispatch<SetStateAction<string>>
    onSubjectChange: Dispatch<SetStateAction<string>>
    onFromEmailChange: Dispatch<SetStateAction<string>>
    onActiveChange: Dispatch<SetStateAction<boolean>>
    onInsertToken: (token: string) => void
    onActiveInsertionTargetChange: (target: ActiveInsertionTarget) => void
}) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Template settings</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
                <ValidatedField
                    id="system-key"
                    label="System key"
                    description="Lowercase letters, numbers, and underscores. Cannot be changed later."
                    error={systemKeyError}
                >
                    {(control) => (
                        <Input
                            {...control}
                            value={systemKey}
                            onChange={(event) => {
                                onSystemKeyChange(event.target.value)
                            }}
                            onBlur={() => onFieldBlur("system_key")}
                            placeholder="e.g. password_reset"
                        />
                    )}
                </ValidatedField>
                <ValidatedField id="name" label="Name" error={nameError}>
                    {(control) => (
                        <Input
                            {...control}
                            value={name}
                            onChange={(event) => onNameChange(event.target.value)}
                            onBlur={() => onFieldBlur("name")}
                            placeholder="Human-friendly label"
                        />
                    )}
                </ValidatedField>
                <Field data-invalid={subjectError ? true : undefined} className="sm:col-span-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <FieldLabel htmlFor="subject">Subject</FieldLabel>
                        <TemplateVariablePicker
                            variables={templateVariables}
                            disabled={variablesLoading || templateVariables.length === 0}
                            triggerLabel={variablesLoading ? "Loading..." : "Insert Variable"}
                            onSelect={(variable) => onInsertToken(`{{${variable.name}}}`)}
                        />
                    </div>
                    <Input
                        ref={subjectRef}
                        id="subject"
                        value={subject}
                        aria-invalid={subjectError ? true : undefined}
                        aria-describedby={subjectError ? "subject-error" : undefined}
                        onChange={(event) => onSubjectChange(event.target.value)}
                        onFocus={() => onActiveInsertionTargetChange("subject")}
                        onBlur={() => onFieldBlur("subject")}
                        onKeyUp={(event) =>
                            recordSelection(event.currentTarget, subjectSelectionRef)
                        }
                        onMouseUp={(event) =>
                            recordSelection(event.currentTarget, subjectSelectionRef)
                        }
                        onSelect={(event) =>
                            recordSelection(event.currentTarget, subjectSelectionRef)
                        }
                        placeholder="Email subject..."
                    />
                    {subjectError ? <FieldError id="subject-error">{subjectError}</FieldError> : null}
                </Field>
                <ValidatedField
                    id="from-email"
                    label="From email (optional)"
                    error={fromEmailError}
                    className="sm:col-span-2"
                >
                    {(control) => (
                        <Input
                            {...control}
                            value={fromEmail}
                            onChange={(event) => onFromEmailChange(event.target.value)}
                            onBlur={() => onFieldBlur("from_email")}
                            placeholder="e.g. Surrogacy Force <no-reply@surrogacyforce.com>"
                        />
                    )}
                </ValidatedField>
                <div className="flex items-center justify-between gap-3 rounded-lg border p-3 sm:col-span-2">
                    <div>
                        <p className="text-sm font-medium">Active</p>
                        <p className="text-xs text-muted-foreground">
                            Inactive templates cannot be used for campaigns or transactional sends.
                        </p>
                    </div>
                    <Switch checked={isActive} onCheckedChange={onActiveChange} />
                </div>
            </CardContent>
        </Card>
    )
}

function TemplateContentCard({
    effectiveEditorMode,
    hasComplexHtml,
    body,
    bodyError,
    onBodyBlur,
    templateVariables,
    variablesLoading,
    visualBodyRef,
    htmlBodyRef,
    htmlBodySelectionRef,
    activeInsertionTargetRef,
    unknownVariables,
    missingRequiredVariables,
    showVariableWarnings,
    onBodyChange,
    onEditorModeChange,
    onEditorModeTouchedChange,
    onInsertToken,
    onInsertPlatformLogo,
    onActiveInsertionTargetChange,
}: {
    effectiveEditorMode: EditorMode
    hasComplexHtml: boolean
    body: string
    bodyError: string | undefined
    onBodyBlur: () => void
    templateVariables: TemplateVariable[]
    variablesLoading: boolean
    visualBodyRef: MutableRefObject<RichTextEditorHandle | null>
    htmlBodyRef: MutableRefObject<HTMLTextAreaElement | null>
    htmlBodySelectionRef: TextSelectionRef
    activeInsertionTargetRef: MutableRefObject<ActiveInsertionTarget>
    unknownVariables: string[]
    missingRequiredVariables: string[]
    showVariableWarnings: boolean
    onBodyChange: Dispatch<SetStateAction<string>>
    onEditorModeChange: Dispatch<SetStateAction<EditorMode>>
    onEditorModeTouchedChange: Dispatch<SetStateAction<boolean>>
    onInsertToken: (token: string) => void
    onInsertPlatformLogo: () => void
    onActiveInsertionTargetChange: (target: ActiveInsertionTarget) => void
}) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Template content</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <ToggleGroup
                        multiple={false}
                        value={effectiveEditorMode ? [effectiveEditorMode] : []}
                        onValueChange={(value) => {
                            const next = value[0] as EditorMode | undefined
                            if (!next) return
                            onEditorModeChange(next)
                            onEditorModeTouchedChange(true)
                            const currentTarget = activeInsertionTargetRef.current
                            onActiveInsertionTargetChange(
                                currentTarget === "subject"
                                    ? currentTarget
                                    : next === "html"
                                      ? "body_html"
                                      : "body_visual"
                            )
                        }}
                    >
                        <ToggleGroupItem value="visual" className="h-8">
                            Visual
                        </ToggleGroupItem>
                        <ToggleGroupItem value="html" className="h-8">
                            HTML
                        </ToggleGroupItem>
                    </ToggleGroup>
                    <div className="flex flex-wrap items-center gap-2">
                        <TemplateVariablePicker
                            variables={templateVariables}
                            disabled={variablesLoading || templateVariables.length === 0}
                            triggerLabel={variablesLoading ? "Loading..." : "Insert Variable"}
                            onSelect={(variable) => onInsertToken(`{{${variable.name}}}`)}
                        />
                        <Button type="button" variant="ghost" size="sm" onClick={onInsertPlatformLogo}>
                            Insert Logo
                        </Button>
                    </div>
                </div>

                {effectiveEditorMode === "visual" ? (
                    <RichTextEditor
                        ref={visualBodyRef}
                        content={body}
                        onChange={(html) => onBodyChange(html)}
                        onFocus={() => onActiveInsertionTargetChange("body_visual")}
                        placeholder="Write your system email content here..."
                        minHeight="240px"
                        maxHeight="480px"
                        enableImages
                        enableEmojiPicker
                    />
                ) : (
                    <Textarea
                        ref={htmlBodyRef}
                        value={body}
                        onChange={(event) => onBodyChange(event.target.value)}
                        onFocus={(event) => {
                            onActiveInsertionTargetChange("body_html")
                            recordSelection(event.currentTarget, htmlBodySelectionRef)
                        }}
                        onKeyUp={(event) => recordSelection(event.currentTarget, htmlBodySelectionRef)}
                        onMouseUp={(event) => recordSelection(event.currentTarget, htmlBodySelectionRef)}
                        onSelect={(event) => recordSelection(event.currentTarget, htmlBodySelectionRef)}
                        onBlur={onBodyBlur}
                        aria-label="HTML body"
                        aria-invalid={bodyError ? true : undefined}
                        aria-describedby={bodyError ? "body-error" : undefined}
                        placeholder="Paste or edit the HTML for this template..."
                        className="min-h-[280px] max-h-[60vh] font-mono text-xs leading-relaxed"
                    />
                )}

                {bodyError ? <FieldError id="body-error">{bodyError}</FieldError> : null}

                {effectiveEditorMode === "visual" && hasComplexHtml && (
                    <p className="text-xs text-amber-600">
                        This template contains advanced HTML. Switch to HTML mode to preserve layout.
                    </p>
                )}

                <TemplateVariableWarnings
                    unknownVariables={unknownVariables}
                    missingRequiredVariables={missingRequiredVariables}
                    show={showVariableWarnings}
                />
            </CardContent>
        </Card>
    )
}

function TemplateVariableWarnings({
    unknownVariables,
    missingRequiredVariables,
    show,
}: {
    unknownVariables: string[]
    missingRequiredVariables: string[]
    show: boolean
}) {
    if (!show || (unknownVariables.length === 0 && missingRequiredVariables.length === 0)) {
        return null
    }

    return (
        <Alert className="border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-50">
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
    )
}

function TemplatePreviewCard({ hasContent, previewHtml }: { hasContent: boolean; previewHtml: string }) {
    return (
        <Card className="h-fit">
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <EyeIcon className="size-4" />
                    Preview
                </CardTitle>
                <CardDescription>Rendered using sample values.</CardDescription>
            </CardHeader>
            <CardContent>
                {hasContent ? (
                    // Email preview surface: stays white in dark mode; fixed-width tables scroll inside it.
                    <div className="overflow-x-auto rounded-md border border-stone-200 bg-white shadow-sm">
                        <TrustedSanitizedHtmlContent
                            html={previewHtml}
                            className="p-6 prose prose-sm prose-stone max-w-none text-stone-900"
                        />
                    </div>
                ) : (
                    <EmptyState
                        icon={EyeIcon}
                        title="No content yet"
                        headingLevel={3}
                        className="rounded-md border border-dashed"
                    />
                )}
            </CardContent>
        </Card>
    )
}
