"use client"

import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type MutableRefObject, type SetStateAction } from "react"
import { useParams, useRouter } from "next/navigation"
import DOMPurify from "dompurify"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Loader2Icon, ArrowLeftIcon, EyeIcon, AlertTriangleIcon, SendIcon } from "lucide-react"
import { toast } from "sonner"
import { PublishDialog } from "@/components/ops/templates/PublishDialog"
import { NotFoundState } from "@/components/not-found-state"
import { TemplateVariablePicker } from "@/components/email/TemplateVariablePicker"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { RichTextEditor, type RichTextEditorHandle } from "@/components/rich-text-editor"
import { normalizeTemplateHtml } from "@/lib/email-template-html"
import { insertAtCursor } from "@/lib/insert-at-cursor"
import {
    useCreatePlatformEmailTemplate,
    usePlatformEmailTemplate,
    usePlatformEmailTemplateVariables,
    usePublishPlatformEmailTemplate,
    useSendTestPlatformEmailTemplate,
    useUpdatePlatformEmailTemplate,
} from "@/lib/hooks/use-platform-templates"
import type { PlatformEmailTemplate } from "@/lib/api/platform"

type EditorMode = "visual" | "html"

type ActiveInsertionTarget = "subject" | "body_html" | "body_visual" | null

function extractTemplateVariables(text: string): string[] {
    if (!text) return []
    const matches = text.match(/{{\s*([a-zA-Z0-9_]+)\s*}}/g) ?? []
    const variables = matches.map((match) => match.replace(/{{\s*|\s*}}/g, ""))
    return Array.from(new Set(variables))
}

export default function PlatformEmailTemplatePage() {
    const router = useRouter()
    const params = useParams()
    const id = params?.id as string
    const isNew = id === "new"
    const templateId = isNew ? null : id

    const { data: templateData, isLoading } = usePlatformEmailTemplate(templateId)
    const { data: templateVariables = [], isLoading: variablesLoading } = usePlatformEmailTemplateVariables()
    const createTemplate = useCreatePlatformEmailTemplate()
    const updateTemplate = useUpdatePlatformEmailTemplate()
    const publishTemplate = usePublishPlatformEmailTemplate()
    const sendTest = useSendTestPlatformEmailTemplate()

    const [name, setName] = useState("")
    const [subject, setSubject] = useState("")
    const [fromEmail, setFromEmail] = useState("")
    const [category, setCategory] = useState("")
    const [body, setBody] = useState("")
    const [editorMode, setEditorMode] = useState<EditorMode>("visual")
    const [editorModeTouched, setEditorModeTouched] = useState(false)
    const [isPublished, setIsPublished] = useState(false)
    const [showPublishDialog, setShowPublishDialog] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [isPublishing, setIsPublishing] = useState(false)

    const [testOrgId, setTestOrgId] = useState("")
    const [testEmail, setTestEmail] = useState("")
    const [testVariables, setTestVariables] = useState<Record<string, string>>({})
    const [testTouched, setTestTouched] = useState<Record<string, boolean>>({})
    const [isSendingTest, setIsSendingTest] = useState(false)

    const subjectRef = useRef<HTMLInputElement | null>(null)
    const subjectSelectionRef = useRef<{ start: number; end: number } | null>(null)
    const htmlBodyRef = useRef<HTMLTextAreaElement | null>(null)
    const htmlBodySelectionRef = useRef<{ start: number; end: number } | null>(null)
    const visualBodyRef = useRef<RichTextEditorHandle | null>(null)
    const [activeInsertionTarget, setActiveInsertionTarget] = useState<ActiveInsertionTarget>(null)

    const canValidateVariables = !variablesLoading && templateVariables.length > 0
    const allowedVariableNames = useMemo(
        () => new Set(templateVariables.map((variable) => variable.name)),
        [templateVariables]
    )
    const requiredVariableNames = useMemo(
        () => templateVariables.filter((variable) => variable.required).map((variable) => variable.name),
        [templateVariables]
    )
    const usedVariableNames = useMemo(
        () => extractTemplateVariables(`${subject}\n${body}`),
        [subject, body]
    )
    const unknownVariables = useMemo(() => {
        if (!canValidateVariables) return []
        return usedVariableNames.filter((variable) => !allowedVariableNames.has(variable))
    }, [allowedVariableNames, canValidateVariables, usedVariableNames])
    const missingRequiredVariables = useMemo(() => {
        if (!canValidateVariables) return []
        return requiredVariableNames.filter((variable) => !usedVariableNames.includes(variable))
    }, [canValidateVariables, requiredVariableNames, usedVariableNames])

    const testHasUnsubscribeUrl = usedVariableNames.includes("unsubscribe_url")
    const testEditableVariableNames = useMemo(
        () => usedVariableNames.filter((variable) => variable !== "unsubscribe_url"),
        [usedVariableNames]
    )

    const buildTestVariableSample = useCallback(
        (variableName: string): string => {
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
                    return "Qualified"
                case "state":
                    return "CA"
                case "owner_name":
                    return "Operator"
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
        },
        [testEmail]
    )

    useEffect(() => {
        setTestVariables((prev) => {
            const next: Record<string, string> = { ...prev }

            for (const variableName of testEditableVariableNames) {
                if (next[variableName] === undefined) {
                    next[variableName] = buildTestVariableSample(variableName)
                }
            }

            // Drop stale values when variables are removed from the template.
            for (const key of Object.keys(next)) {
                if (!testEditableVariableNames.includes(key)) {
                    delete next[key]
                }
            }

            return next
        })

        setTestTouched((prev) => {
            const next: Record<string, boolean> = { ...prev }
            for (const key of Object.keys(next)) {
                if (!testEditableVariableNames.includes(key)) {
                    delete next[key]
                }
            }
            return next
        })
    }, [buildTestVariableSample, testEditableVariableNames])

    const recordSelection = (
        el: HTMLInputElement | HTMLTextAreaElement,
        ref: MutableRefObject<{ start: number; end: number } | null>
    ) => {
        ref.current = {
            start: el.selectionStart ?? el.value.length,
            end: el.selectionEnd ?? el.value.length,
        }
    }
    const fromEmailError = useMemo(() => {
        const value = fromEmail.trim()
        if (!value) return null
        const basicEmail = /^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/
        const namedEmail = /^.+<\s*[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+\s*>$/
        if (basicEmail.test(value) || namedEmail.test(value)) return null
        return "Use a valid email or name <email@domain> format."
    }, [fromEmail])

    useEffect(() => {
        if (!templateData || isNew) return
        const draft = templateData.draft
        setName(draft.name ?? "")
        setSubject(draft.subject ?? "")
        setFromEmail(draft.from_email ?? "")
        setCategory(draft.category ?? "")
        setBody(draft.body ?? "")
        setIsPublished((templateData.published_version ?? 0) > 0)
    }, [templateData, isNew])

    const hasComplexHtml = useMemo(
        () => /<table|<tbody|<thead|<tr|<td|<img|<div/i.test(body),
        [body]
    )

    useEffect(() => {
        if (editorModeTouched) return
        if (body && hasComplexHtml && editorMode !== "html") {
            setEditorMode("html")
        }
    }, [body, editorModeTouched, hasComplexHtml, editorMode])

    const effectiveEditorMode: EditorMode =
        editorMode === "visual" && hasComplexHtml && !editorModeTouched ? "html" : editorMode

    const previewHtml = useMemo(() => {
        return DOMPurify.sanitize(normalizeTemplateHtml(body || ""), {
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
    }, [body])

    const insertIntoTextControl = (
        el: HTMLInputElement | HTMLTextAreaElement | null,
        selectionRef: MutableRefObject<{ start: number; end: number } | null>,
        setValue: Dispatch<SetStateAction<string>>,
        token: string
    ) => {
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

    const insertToken = (token: string) => {
        if (activeInsertionTarget === "subject") {
            insertIntoTextControl(subjectRef.current, subjectSelectionRef, setSubject, token)
            return
        }
        if (activeInsertionTarget === "body_html") {
            insertIntoTextControl(htmlBodyRef.current, htmlBodySelectionRef, setBody, token)
            return
        }
        if (activeInsertionTarget === "body_visual") {
            visualBodyRef.current?.insertText(token)
            return
        }

        if (effectiveEditorMode === "html") {
            insertIntoTextControl(htmlBodyRef.current, htmlBodySelectionRef, setBody, token)
            return
        }
        visualBodyRef.current?.insertText(token)
    }

    const insertOrgLogo = () => {
        if (body.includes("{{org_logo_url}}")) return
        const logo = `<p><img src="{{org_logo_url}}" alt="{{org_name}} logo" style="max-width: 160px; height: auto; display: block;" /></p>\n`
        if (effectiveEditorMode === "visual") {
            visualBodyRef.current?.insertHtml(logo)
            setActiveInsertionTarget("body_visual")
            return
        }
        insertIntoTextControl(htmlBodyRef.current, htmlBodySelectionRef, setBody, logo)
        setActiveInsertionTarget("body_html")
    }

    const persistTemplate = useCallback(
        async (): Promise<PlatformEmailTemplate> => {
            const payload = {
                name: name.trim(),
                subject: subject.trim(),
                body: body || "",
                from_email: fromEmail.trim() ? fromEmail.trim() : null,
                category: category.trim() ? category.trim() : null,
            }

            if (isNew) {
                const created = await createTemplate.mutateAsync(payload)
                router.replace(`/ops/templates/email/${created.id}`)
                return created
            }

            return updateTemplate.mutateAsync({
                id,
                payload: {
                    ...payload,
                    expected_version: templateData?.current_version ?? null,
                },
            })
        },
        [body, category, createTemplate, fromEmail, id, isNew, name, router, subject, templateData?.current_version, updateTemplate]
    )

    const handleSave = async () => {
        if (!name.trim() || !subject.trim()) {
            toast.error("Name and subject are required")
            return
        }
        if (fromEmailError) {
            toast.error(fromEmailError)
            return
        }
        setIsSaving(true)
        try {
            const saved = await persistTemplate()
            setIsPublished((saved.published_version ?? 0) > 0)
            toast.success("Template saved")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to save template")
        } finally {
            setIsSaving(false)
        }
    }

    const handlePublish = () => {
        if (!name.trim() || !subject.trim()) {
            toast.error("Name and subject are required")
            return
        }
        if (fromEmailError) {
            toast.error(fromEmailError)
            return
        }
        if (!body.trim()) {
            toast.error("Email body is required")
            return
        }
        setShowPublishDialog(true)
    }

    const confirmPublish = async (publishAll: boolean, orgIds: string[]) => {
        setIsPublishing(true)
        try {
            const saved = await persistTemplate()
            await publishTemplate.mutateAsync({
                id: saved.id,
                payload: {
                    publish_all: publishAll,
                    org_ids: publishAll ? null : orgIds,
                },
            })
            setIsPublished(true)
            setShowPublishDialog(false)
            toast.success("Template published")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to publish template")
        } finally {
            setIsPublishing(false)
        }
    }

    const handleSendTest = async () => {
        if (isNew) return

        if (!testOrgId.trim()) {
            toast.error("Organization ID is required")
            return
        }
        if (!testEmail.trim()) {
            toast.error("Test email is required")
            return
        }

        const overrides: Record<string, string> = {}
        for (const [key, value] of Object.entries(testVariables)) {
            if (!testTouched[key]) continue
            const trimmed = value.trim()
            if (!trimmed) continue
            overrides[key] = trimmed
        }

        setIsSendingTest(true)
        try {
            const saved = await persistTemplate()
            const result = await sendTest.mutateAsync({
                id: saved.id,
                payload: {
                    org_id: testOrgId.trim(),
                    to_email: testEmail.trim(),
                    variables: overrides,
                },
            })

            const providerLabel =
                result.provider_used === "resend"
                    ? "Resend"
                    : result.provider_used === "gmail"
                        ? "Gmail"
                        : "provider"
            toast.success(`Test email sent via ${providerLabel}`)
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to send test email")
        } finally {
            setIsSendingTest(false)
        }
    }

    if (!isNew && isLoading) {
        return (
            <div className="flex h-screen items-center justify-center bg-stone-100 dark:bg-stone-950">
                <div className="flex items-center gap-2 text-stone-600 dark:text-stone-400">
                    <Loader2Icon className="size-5 animate-spin" />
                    <span>Loading template...</span>
                </div>
            </div>
        )
    }

    if (!isNew && !templateData) {
        return (
            <NotFoundState title="Template not found" backUrl="/ops/templates?tab=email" />
        )
    }

    return (
        <div className="min-h-screen bg-stone-100 dark:bg-stone-950">
            <div className="flex h-16 items-center justify-between border-b border-stone-200 bg-white px-6 dark:border-stone-800 dark:bg-stone-900">
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="icon" onClick={() => router.push("/ops/templates?tab=email")}>
                        <ArrowLeftIcon className="size-5" />
                    </Button>
                    <Input
                        id="template-name"
                        aria-label="Template name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Template name..."
                        className="h-9 w-64 border-none bg-transparent px-0 text-lg font-semibold focus-visible:ring-0"
                    />
                    <Badge variant={isPublished ? "default" : "secondary"} className={isPublished ? "bg-teal-500" : ""}>
                        {isPublished ? "Published" : "Draft"}
                    </Badge>
                </div>
                <div className="flex items-center gap-3">
                    <Button variant="outline" size="sm" onClick={handleSave} disabled={isSaving || isPublishing}>
                        {isSaving && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Save Draft
                    </Button>
                    <Button size="sm" onClick={handlePublish} disabled={isSaving || isPublishing}>
                        {isPublishing && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Publish
                    </Button>
                </div>
            </div>

            <div className="grid gap-6 p-6 lg:grid-cols-[1.1fr_0.9fr]">
                <Card>
                    <CardHeader>
                        <CardTitle>Email Content</CardTitle>
                        <CardDescription>Design the default template shared to org libraries.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Label>Subject *</Label>
                            <Input
                                ref={subjectRef}
                                value={subject}
                                onChange={(e) => setSubject(e.target.value)}
                                onFocus={(e) => {
                                    setActiveInsertionTarget("subject")
                                    recordSelection(e.currentTarget, subjectSelectionRef)
                                }}
                                onKeyUp={(e) => recordSelection(e.currentTarget, subjectSelectionRef)}
                                onMouseUp={(e) => recordSelection(e.currentTarget, subjectSelectionRef)}
                                onSelect={(e) => recordSelection(e.currentTarget, subjectSelectionRef)}
                                placeholder="You're invited to join {{org_name}}"
                            />
                            <p className="text-xs text-muted-foreground">
                                Used as the default subject in org copies.
                            </p>
                        </div>
                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="space-y-2">
                                <Label>From (optional)</Label>
                                <Input
                                    value={fromEmail}
                                    onChange={(e) => setFromEmail(e.target.value)}
                                    placeholder="Invites <invites@surrogacyforce.com>"
                                />
                                {fromEmailError ? (
                                    <p className="text-xs text-red-600">{fromEmailError}</p>
                                ) : (
                                    <p className="text-xs text-muted-foreground">
                                        Leave blank to use the org default sender.
                                    </p>
                                )}
                            </div>
                            <div className="space-y-2">
                                <Label>Category (optional)</Label>
                                <Input
                                    value={category}
                                    onChange={(e) => setCategory(e.target.value)}
                                    placeholder="onboarding"
                                />
                                <p className="text-xs text-muted-foreground">
                                    Helps orgs filter templates in their library.
                                </p>
                            </div>
                        </div>
                        <div className="space-y-2">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <Label>Email Body *</Label>
                                <div className="flex flex-wrap items-center gap-2">
                                    <ToggleGroup
                                        multiple={false}
                                        value={effectiveEditorMode ? [effectiveEditorMode] : []}
                                        onValueChange={(value) => {
                                            const next = value[0] as EditorMode | undefined
                                            if (!next) return
                                            setEditorMode(next)
                                            setEditorModeTouched(true)
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
                                        onSelect={(variable) => insertToken(`{{${variable.name}}}`)}
                                    />
                                    <Button type="button" variant="ghost" size="sm" onClick={insertOrgLogo}>
                                        Insert Logo
                                    </Button>
                                </div>
                            </div>
                            {effectiveEditorMode === "visual" ? (
                                <RichTextEditor
                                    ref={visualBodyRef}
                                    content={body}
                                    onChange={(html) => setBody(html)}
                                    onFocus={() => setActiveInsertionTarget("body_visual")}
                                    placeholder="Write your email content here..."
                                    minHeight="220px"
                                    maxHeight="420px"
                                    enableImages
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
                                    className="min-h-[240px] font-mono text-xs leading-relaxed"
                                />
                            )}
                            {effectiveEditorMode === "visual" && hasComplexHtml && (
                                <p className="text-xs text-amber-600">
                                    This template contains advanced HTML. Switch to HTML mode to preserve layout.
                                </p>
                            )}
                            <p className="text-xs text-muted-foreground">
                                Use double braces for variables, e.g. <span className="font-mono">{"{{first_name}}"}</span>.
                            </p>
                            {(unknownVariables.length > 0 || missingRequiredVariables.length > 0) &&
                                (subject.trim() || body.trim()) && (
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
                    </CardContent>
                </Card>

                <div className="space-y-6">
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
                                <div
                                    className="prose prose-sm max-w-none"
                                    dangerouslySetInnerHTML={{ __html: previewHtml }}
                                />
                            ) : (
                                <div className="text-sm text-muted-foreground">
                                    Add content to preview the template.
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Send test email</CardTitle>
                            <CardDescription>
                                Render this template for a specific organization and send to a test inbox.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <div className="space-y-2">
                                <Label htmlFor="test-org-id">Organization ID</Label>
                                <Input
                                    id="test-org-id"
                                    value={testOrgId}
                                    onChange={(event) => setTestOrgId(event.target.value)}
                                    placeholder="UUID of an organization"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="test-email">Test email</Label>
                                <Input
                                    id="test-email"
                                    type="email"
                                    value={testEmail}
                                    onChange={(event) => setTestEmail(event.target.value)}
                                    placeholder="test@example.com"
                                />
                            </div>

                            <Accordion defaultValue={[]} className="rounded-lg">
                                <AccordionItem value="variables">
                                    <AccordionTrigger>Variables (optional)</AccordionTrigger>
                                    <AccordionContent>
                                        <div className="space-y-3">
                                            {testHasUnsubscribeUrl && (
                                                <div className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
                                                    <span className="font-mono">
                                                        {"{{unsubscribe_url}}"}
                                                    </span>{" "}
                                                    is generated automatically for the recipient.
                                                </div>
                                            )}

                                            {testEditableVariableNames.length === 0 ? (
                                                <p className="text-sm text-muted-foreground">
                                                    No variables found in this template.
                                                </p>
                                            ) : (
                                                testEditableVariableNames.map((variableName) => (
                                                    <div key={variableName} className="space-y-1">
                                                        <Label
                                                            htmlFor={`test-var-${variableName}`}
                                                            className="font-mono text-xs"
                                                        >
                                                            {`{{${variableName}}}`}
                                                        </Label>
                                                        <Input
                                                            id={`test-var-${variableName}`}
                                                            value={testVariables[variableName] ?? ""}
                                                            onChange={(event) => {
                                                                const value = event.target.value
                                                                setTestVariables((prev) => ({
                                                                    ...prev,
                                                                    [variableName]: value,
                                                                }))
                                                                setTestTouched((prev) => ({
                                                                    ...prev,
                                                                    [variableName]: true,
                                                                }))
                                                            }}
                                                        />
                                                    </div>
                                                ))
                                            )}
                                        </div>
                                    </AccordionContent>
                                </AccordionItem>
                            </Accordion>

                            {isNew && (
                                <p className="text-xs text-muted-foreground">
                                    Save template first.
                                </p>
                            )}

                            <Button
                                onClick={handleSendTest}
                                disabled={isNew || isSendingTest || isSaving || isPublishing}
                            >
                                {isSendingTest ? (
                                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                                ) : (
                                    <SendIcon className="mr-2 size-4" />
                                )}
                                Send test
                            </Button>
                        </CardContent>
                    </Card>
                </div>
            </div>

            <PublishDialog
                open={showPublishDialog}
                onOpenChange={setShowPublishDialog}
                onPublish={confirmPublish}
                isLoading={isPublishing}
                defaultPublishAll={templateData?.is_published_globally ?? true}
                initialOrgIds={templateData?.target_org_ids ?? []}
            />
        </div>
    )
}
