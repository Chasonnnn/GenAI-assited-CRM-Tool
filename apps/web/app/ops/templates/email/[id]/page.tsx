"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import dynamic from "next/dynamic"
import DOMPurify from "dompurify"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Loader2Icon, ArrowLeftIcon, EyeIcon, CodeIcon } from "lucide-react"
import { toast } from "sonner"
import { PublishDialog } from "@/components/ops/templates/PublishDialog"
import { NotFoundState } from "@/components/not-found-state"
import {
    useCreatePlatformEmailTemplate,
    usePlatformEmailTemplate,
    usePublishPlatformEmailTemplate,
    useUpdatePlatformEmailTemplate,
} from "@/lib/hooks/use-platform-templates"
import type { PlatformEmailTemplate } from "@/lib/api/platform"

const RichTextEditor = dynamic(
    () => import("@/components/rich-text-editor").then((mod) => mod.RichTextEditor),
    {
        ssr: false,
        loading: () => (
            <div className="rounded-md border border-border bg-muted/20 p-4 text-sm text-muted-foreground">
                Loading editor...
            </div>
        ),
    }
)

const TEMPLATE_VARIABLES = [
    { name: "first_name", description: "Contact first name" },
    { name: "full_name", description: "Contact full name" },
    { name: "email", description: "Contact email" },
    { name: "phone", description: "Contact phone" },
    { name: "surrogate_number", description: "Surrogate number" },
    { name: "intended_parent_number", description: "Intended parent number" },
    { name: "status_label", description: "Current status" },
    { name: "owner_name", description: "Surrogate owner name" },
    { name: "org_name", description: "Organization name" },
    { name: "org_logo_url", description: "Organization logo URL (use as image src)" },
    { name: "appointment_date", description: "Appointment date" },
    { name: "appointment_time", description: "Appointment time" },
    { name: "appointment_location", description: "Appointment location" },
    { name: "unsubscribe_url", description: "Unsubscribe link" },
]

type EditorMode = "visual" | "html"

export default function PlatformEmailTemplatePage() {
    const router = useRouter()
    const params = useParams()
    const id = params?.id as string
    const isNew = id === "new"
    const templateId = isNew ? null : id

    const { data: templateData, isLoading } = usePlatformEmailTemplate(templateId)
    const createTemplate = useCreatePlatformEmailTemplate()
    const updateTemplate = useUpdatePlatformEmailTemplate()
    const publishTemplate = usePublishPlatformEmailTemplate()

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
        return DOMPurify.sanitize(body || "", {
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

    const insertVariable = (nameToInsert: string) => {
        setBody((prev) => `${prev}{{${nameToInsert}}}`)
    }

    const insertOrgLogo = () => {
        setBody((prev) => {
            if (prev.includes("{{org_logo_url}}")) return prev
            const logo = `<p><img src="{{org_logo_url}}" alt="{{org_name}} logo" style="max-width: 160px; height: auto; display: block;" /></p>\n`
            return `${logo}${prev}`
        })
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
                                value={subject}
                                onChange={(e) => setSubject(e.target.value)}
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
                                    <DropdownMenu>
                                        <DropdownMenuTrigger>
                                            <span className="inline-flex items-center justify-center gap-2 rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground h-8 px-3 text-sm cursor-pointer">
                                                <CodeIcon className="size-4" />
                                                Insert Variable
                                            </span>
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end" className="w-56">
                                            {TEMPLATE_VARIABLES.map((v) => (
                                                <DropdownMenuItem key={v.name} onClick={() => insertVariable(v.name)}>
                                                    <span className="font-mono text-xs">{`{{${v.name}}}`}</span>
                                                    <span className="ml-2 text-muted-foreground text-xs">
                                                        {v.description}
                                                    </span>
                                                </DropdownMenuItem>
                                            ))}
                                        </DropdownMenuContent>
                                    </DropdownMenu>
                                    <Button type="button" variant="ghost" size="sm" onClick={insertOrgLogo}>
                                        Insert Logo
                                    </Button>
                                </div>
                            </div>
                            {effectiveEditorMode === "visual" ? (
                                <RichTextEditor
                                    content={body}
                                    onChange={(html) => setBody(html)}
                                    placeholder="Write your email content here..."
                                    minHeight="220px"
                                    maxHeight="420px"
                                    enableImages
                                />
                            ) : (
                                <Textarea
                                    value={body}
                                    onChange={(event) => setBody(event.target.value)}
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
                        </div>
                    </CardContent>
                </Card>

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
