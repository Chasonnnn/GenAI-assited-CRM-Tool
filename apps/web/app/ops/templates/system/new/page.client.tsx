"use client"

import { useRef, useState, type Dispatch, type MutableRefObject, type SetStateAction } from "react"
import { useRouter } from "next/navigation"
import DOMPurify from "dompurify"
import { toast } from "sonner"
import { ArrowLeftIcon, EyeIcon, Loader2Icon, PlusIcon } from "lucide-react"
import { TrustedSanitizedHtmlContent } from "@/components/safe-html-content"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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

    const fromEmailError = getFromEmailError(fromEmail)
    const systemKeyError = getSystemKeyError(systemKey)
    const nameError = getNameError(name)
    const subjectError = getSubjectError(subject)
    const bodyError = getBodyError(body)
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
    const missingRequiredVariables = canValidateVariables
        ? requiredVariableNames.filter((variable) => !usedVariableNames.includes(variable))
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

    const canSubmit =
        !saving &&
        !systemKeyError &&
        !nameError &&
        !subjectError &&
        !fromEmailError &&
        !bodyError

    const handleCreate = async () => {
        if (!canSubmit) return
        setSaving(true)
        const finishSaving = () => setSaving(false)
        try {
            const created = await createTemplate.mutateAsync({
                system_key: systemKey.trim(),
                name: name.trim(),
                subject: subject.trim(),
                from_email: fromEmail.trim() ? fromEmail.trim() : null,
                body,
                is_active: isActive,
            })
            toast.success("System email template created")
            push(`/ops/templates/system/${created.system_key}`)
            finishSaving()
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to create system template")
            finishSaving()
        }
    }

    return (
        <div className="p-6 space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <Button variant="ghost" onClick={() => push("/ops/templates?tab=system")}>
                        <ArrowLeftIcon className="mr-2 size-4" />
                        Back to templates
                    </Button>
                    <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                        New System Email
                    </h1>
                    <p className="text-sm text-muted-foreground">
                        Create a new platform system email template. Use a stable system key for future sends.
                    </p>
                </div>
                <Button onClick={handleCreate} disabled={!canSubmit}>
                    {saving ? (
                        <Loader2Icon className="mr-2 size-4 animate-spin" />
                    ) : (
                        <PlusIcon className="mr-2 size-4" />
                    )}
                    Create
                </Button>
            </div>

            <div className="grid gap-6 lg:grid-cols-3">
                <div className="space-y-6 lg:col-span-2">
                    <Card>
                        <CardHeader>
                            <CardTitle>Template settings</CardTitle>
                            <CardDescription>
                                System keys must be unique and cannot be changed later.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="grid gap-4 sm:grid-cols-2">
                            <div className="space-y-2">
                                <Label htmlFor="system-key">System key</Label>
                                <Input
                                    id="system-key"
                                    value={systemKey}
                                    onChange={(event) => {
                                        setManualSystemKey(event.target.value)
                                    }}
                                    placeholder="e.g. password_reset"
                                    className={systemKeyError ? "border-red-500" : ""}
                                />
                                {systemKeyError ? (
                                    <p className="text-xs text-red-600">{systemKeyError}</p>
                                ) : (
                                    <p className="text-xs text-muted-foreground">
                                        Lowercase letters, numbers, and underscores only.
                                    </p>
                                )}
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="name">Name</Label>
                                <Input
                                    id="name"
                                    value={name}
                                    onChange={(event) => setName(event.target.value)}
                                    placeholder="Human-friendly label"
                                    className={nameError ? "border-red-500" : ""}
                                />
                                {nameError && <p className="text-xs text-red-600">{nameError}</p>}
                            </div>
                            <div className="space-y-2 sm:col-span-2">
                                <Label htmlFor="subject">Subject</Label>
                                <div className="flex flex-wrap items-center gap-2">
                                    <Input
                                        ref={subjectRef}
                                        id="subject"
                                        value={subject}
                                        onChange={(event) => setSubject(event.target.value)}
                                        onFocus={() => setActiveInsertionTarget("subject")}
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
                                        className={subjectError ? "border-red-500" : ""}
                                    />
                                    <TemplateVariablePicker
                                        variables={templateVariables}
                                        disabled={variablesLoading || templateVariables.length === 0}
                                        triggerLabel={variablesLoading ? "Loading..." : "Insert Variable"}
                                        onSelect={(variable) => insertToken(`{{${variable.name}}}`)}
                                    />
                                </div>
                                {subjectError && <p className="text-xs text-red-600">{subjectError}</p>}
                            </div>
                            <div className="space-y-2 sm:col-span-2">
                                <Label htmlFor="from-email">From email (optional)</Label>
                                <Input
                                    id="from-email"
                                    value={fromEmail}
                                    onChange={(event) => setFromEmail(event.target.value)}
                                    placeholder="e.g. Surrogacy Force <no-reply@surrogacyforce.com>"
                                    className={fromEmailError ? "border-red-500" : ""}
                                />
                                {fromEmailError && <p className="text-xs text-red-600">{fromEmailError}</p>}
                            </div>
                            <div className="flex items-center justify-between gap-3 rounded-lg border p-3 sm:col-span-2">
                                <div>
                                    <p className="text-sm font-medium">Active</p>
                                    <p className="text-xs text-muted-foreground">
                                        Inactive templates cannot be used for campaigns or transactional sends.
                                    </p>
                                </div>
                                <Switch checked={isActive} onCheckedChange={setIsActive} />
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Template content</CardTitle>
                            <CardDescription>
                                Write the HTML body for this system email. Variables render at send time.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <ToggleGroup
                                    multiple={false}
                                    value={effectiveEditorMode ? [effectiveEditorMode] : []}
                                    onValueChange={(value) => {
                                        const next = value[0] as EditorMode | undefined
                                        if (!next) return
                                        setEditorMode(next)
                                        setEditorModeTouched(true)
                                        const currentTarget = activeInsertionTargetRef.current
                                        setActiveInsertionTarget(
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
                                        onSelect={(variable) => insertToken(`{{${variable.name}}}`)}
                                    />
                                    <Button type="button" variant="ghost" size="sm" onClick={insertPlatformLogo}>
                                        Insert Logo
                                    </Button>
                                </div>
                                {bodyError && <p className="text-xs text-red-600">{bodyError}</p>}
                            </div>

                            {effectiveEditorMode === "visual" ? (
                                <RichTextEditor
                                    ref={visualBodyRef}
                                    content={body}
                                    onChange={(html) => setBody(html)}
                                    onFocus={() => setActiveInsertionTarget("body_visual")}
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
                                    onChange={(event) => setBody(event.target.value)}
                                    onFocus={(event) => {
                                        setActiveInsertionTarget("body_html")
                                        recordSelection(event.currentTarget, htmlBodySelectionRef)
                                    }}
                                    onKeyUp={(event) => recordSelection(event.currentTarget, htmlBodySelectionRef)}
                                    onMouseUp={(event) => recordSelection(event.currentTarget, htmlBodySelectionRef)}
                                    onSelect={(event) => recordSelection(event.currentTarget, htmlBodySelectionRef)}
                                    placeholder="Paste or edit the HTML for this template..."
                                    className="min-h-[280px] font-mono text-xs leading-relaxed"
                                />
                            )}

                            {effectiveEditorMode === "visual" && hasComplexHtml && (
                                <p className="text-xs text-amber-600">
                                    This template contains advanced HTML. Switch to HTML mode to preserve layout.
                                </p>
                            )}

                            {(unknownVariables.length > 0 || missingRequiredVariables.length > 0) &&
                                (subject.trim() || body.trim()) && (
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
                                )}
                        </CardContent>
                    </Card>
                </div>

                <Card className="h-fit">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <EyeIcon className="size-4" />
                            Preview
                        </CardTitle>
                        <CardDescription>Rendered using sample values.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="rounded-md border border-stone-200 bg-white shadow-sm">
                            <TrustedSanitizedHtmlContent
                                html={previewHtml}
                                className="p-6 prose prose-sm prose-stone max-w-none text-stone-900"
                            />
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
