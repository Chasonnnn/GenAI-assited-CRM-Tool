"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import type { Route } from "next"
import { useRouter } from "next/navigation"
import { ArrowLeftIcon, HistoryIcon } from "lucide-react"

import { EmailTemplateHistorySheet } from "@/components/email/EmailTemplateHistorySheet"
import { TemplateVariablePicker } from "@/components/email/TemplateVariablePicker"
import {
    RichTextEditor,
    type RichTextEditorHandle,
} from "@/components/rich-text-editor"
import { TrustedSanitizedHtmlContent } from "@/components/safe-html-content"
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
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type {
    EmailTemplateDraft,
    EmailTemplateDraftUpdate,
} from "@/lib/api/email-template-drafts"
import type { EmailTemplate } from "@/lib/api/email-templates"
import { ApiError } from "@/lib/api"
import {
    buildEmailTemplatePreviewHtml,
    extractEmailTemplateVariables,
    getEmailTemplateBodyMode,
    hasAdvancedEmailTemplateHtml,
    type EmailTemplateBodyMode,
} from "@/lib/email-template-preview"
import {
    useCreateEmailTemplateDraft,
    useCreateEmailTemplateDraftFromTemplate,
    useDiscardEmailTemplateDraft,
    useEmailTemplateDraft,
    useEmailTemplateDrafts,
    usePublishEmailTemplateDraft,
    useRestoreEmailTemplateDraftVersion,
    useSendTestEmailTemplateDraft,
    useUpdateEmailTemplateDraft,
} from "@/lib/hooks/use-email-template-drafts"
import {
    useEmailTemplate,
    useEmailTemplateVersions,
    useEmailTemplateVariables,
} from "@/lib/hooks/use-email-templates"
import { useOrgSignaturePreview } from "@/lib/hooks/use-signature"
import type { TemplateVariableRead } from "@/lib/types/template-variable"

type OrganizationEmailTemplateStudioProps = {
    templateId?: string
}

type EditorFields = {
    name: string
    subject: string
    from_email: string | null
    body: string
    is_active: boolean
}

type ActiveEditorField = "subject" | "body"

function fieldsFromTemplate(
    value: EmailTemplateDraft | EmailTemplate | null | undefined,
): EditorFields {
    return {
        name: value?.name ?? "",
        subject: value?.subject ?? "",
        from_email: value?.from_email ?? null,
        body: value?.body ?? "",
        is_active: value?.is_active ?? true,
    }
}

function buildChangedFields(
    current: EditorFields,
    baseline: EditorFields,
): Omit<EmailTemplateDraftUpdate, "expected_revision"> {
    const changed: Omit<EmailTemplateDraftUpdate, "expected_revision"> = {}
    if (current.name !== baseline.name) changed.name = current.name
    if (current.subject !== baseline.subject) changed.subject = current.subject
    if (current.from_email !== baseline.from_email) {
        changed.from_email = current.from_email
    }
    if (current.body !== baseline.body) changed.body = current.body
    if (current.is_active !== baseline.is_active) {
        changed.is_active = current.is_active
    }
    return changed
}

function hasOverlappingServerChanges(
    localChanges: Omit<EmailTemplateDraftUpdate, "expected_revision">,
    localBaseline: EditorFields,
    serverBaseline: EditorFields,
) {
    return (Object.keys(localChanges) as Array<keyof EditorFields>).some(
        (field) => localBaseline[field] !== serverBaseline[field],
    )
}

const SUBJECT_PREVIEW_VALUES: Record<string, string> = {
    first_name: "John",
    full_name: "John Smith",
    org_name: "ABC Surrogacy",
    owner_name: "Sara Manager",
}

function buildPreviewSubject(subject: string) {
    return subject.replace(
        /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g,
        (token, variableName: string) =>
            SUBJECT_PREVIEW_VALUES[variableName] ?? token,
    )
}

function createTestOccurrenceId() {
    if (typeof crypto.randomUUID === "function") {
        return crypto.randomUUID()
    }
    const bytes = crypto.getRandomValues(new Uint8Array(16))
    bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40
    bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"))
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`
}

function useUnsavedChangesWarning(
    isDirty: boolean,
    onInternalNavigation: (destination: string) => void,
) {
    useEffect(() => {
        if (!isDirty) return

        const warnBeforeUnload = (event: BeforeUnloadEvent) => {
            event.preventDefault()
            event.returnValue = ""
        }
        const guardInternalNavigation = (event: MouseEvent) => {
            if (
                event.defaultPrevented ||
                event.button !== 0 ||
                event.metaKey ||
                event.ctrlKey ||
                event.shiftKey ||
                event.altKey
            ) {
                return
            }
            const target =
                event.target instanceof Element
                    ? event.target.closest<HTMLAnchorElement>("a[href]")
                    : null
            if (
                !target ||
                target.hasAttribute("download") ||
                (target.target && target.target !== "_self")
            ) {
                return
            }
            const destination = new URL(target.href, window.location.href)
            if (
                destination.origin !== window.location.origin ||
                destination.href === window.location.href
            ) {
                return
            }

            event.preventDefault()
            event.stopPropagation()
            onInternalNavigation(
                `${destination.pathname}${destination.search}${destination.hash}`,
            )
        }
        window.addEventListener("beforeunload", warnBeforeUnload)
        document.addEventListener("click", guardInternalNavigation, true)
        return () => {
            window.removeEventListener("beforeunload", warnBeforeUnload)
            document.removeEventListener("click", guardInternalNavigation, true)
        }
    }, [isDirty, onInternalNavigation])
}

export default function OrganizationEmailTemplateStudio({
    templateId,
}: OrganizationEmailTemplateStudioProps) {
    const draftList = useEmailTemplateDrafts({ scope: "org" })
    const matchingDraft = draftList.data?.find(
        (draft) => draft.id === templateId || draft.template_id === templateId,
    )
    const publishedTemplateId = matchingDraft
        ? matchingDraft.template_id
        : draftList.data && templateId
          ? templateId
          : null
    const publishedTemplate = useEmailTemplate(publishedTemplateId)
    const draftDetail = useEmailTemplateDraft(matchingDraft?.id ?? null)
    const variables = useEmailTemplateVariables()

    if (draftList.isLoading || publishedTemplate.isLoading || draftDetail.isLoading) {
        return <div className="p-6 text-sm text-muted-foreground">Loading template studio…</div>
    }

    if (draftList.isError || publishedTemplate.isError || draftDetail.isError) {
        const retryFailedQueries = () => {
            if (draftList.isError) void draftList.refetch()
            if (publishedTemplate.isError) void publishedTemplate.refetch()
            if (draftDetail.isError) void draftDetail.refetch()
        }

        return (
            <div className="p-6">
                <h1 className="text-xl font-semibold">Unable to load template studio</h1>
                <p className="mt-2 text-sm text-muted-foreground">
                    Refresh the page and try again.
                </p>
                <Button
                    type="button"
                    variant="outline"
                    className="mt-4"
                    onClick={retryFailedQueries}
                >
                    Retry
                </Button>
            </div>
        )
    }

    const draft = draftDetail.data ?? matchingDraft ?? null
    const published = publishedTemplate.data ?? null

    return (
        <OrganizationEmailTemplateEditor
            key={draft?.id ?? published?.id ?? "new"}
            routeTemplateId={templateId}
            initialDraft={draft}
            publishedTemplate={published}
            variables={variables.data ?? []}
        />
    )
}

type OrganizationEmailTemplateEditorProps = {
    routeTemplateId: string | undefined
    initialDraft: EmailTemplateDraft | null
    publishedTemplate: EmailTemplate | null
    variables: ReturnType<typeof useEmailTemplateVariables>["data"]
}

function OrganizationEmailTemplateEditor({
    routeTemplateId,
    initialDraft,
    publishedTemplate,
    variables,
}: OrganizationEmailTemplateEditorProps) {
    const { push, replace } = useRouter()
    const createDraft = useCreateEmailTemplateDraft()
    const createDraftFromTemplate = useCreateEmailTemplateDraftFromTemplate()
    const updateDraft = useUpdateEmailTemplateDraft()
    const discardDraft = useDiscardEmailTemplateDraft()
    const publishDraft = usePublishEmailTemplateDraft()
    const restoreDraftVersion = useRestoreEmailTemplateDraftVersion()
    const sendTestDraft = useSendTestEmailTemplateDraft()
    const orgSignaturePreview = useOrgSignaturePreview({
        enabled: true,
        mode: "org_only",
    })

    const initialFields = fieldsFromTemplate(initialDraft ?? publishedTemplate)
    const [fields, setFields] = useState<EditorFields>(initialFields)
    const [savedFields, setSavedFields] = useState<EditorFields>(initialFields)
    const [draft, setDraft] = useState<EmailTemplateDraft | null>(initialDraft)
    const [bodyMode, setBodyMode] = useState<EmailTemplateBodyMode>(() =>
        getEmailTemplateBodyMode(initialFields.body),
    )
    const [activeEditorField, setActiveEditorField] =
        useState<ActiveEditorField>("body")
    const [isSaving, setIsSaving] = useState(false)
    const [saveError, setSaveError] = useState<string | null>(null)
    const [saveConflict, setSaveConflict] = useState(false)
    const [copyStatus, setCopyStatus] = useState<string | null>(null)
    const [discardOpen, setDiscardOpen] = useState(false)
    const [isDiscarding, setIsDiscarding] = useState(false)
    const [discardError, setDiscardError] = useState<string | null>(null)
    const [publishOpen, setPublishOpen] = useState(false)
    const [historyOpen, setHistoryOpen] = useState(false)
    const [isPublishing, setIsPublishing] = useState(false)
    const [publishError, setPublishError] = useState<string | null>(null)
    const [pendingNavigation, setPendingNavigation] = useState<string | null>(null)
    const [testOpen, setTestOpen] = useState(false)
    const [testRecipient, setTestRecipient] = useState("")
    const [testVariables, setTestVariables] = useState<Record<string, string>>({})
    const [ignoreOptOut, setIgnoreOptOut] = useState(false)
    const [isSendingTest, setIsSendingTest] = useState(false)
    const [testError, setTestError] = useState<string | null>(null)
    const subjectRef = useRef<HTMLInputElement>(null)
    const htmlBodyRef = useRef<HTMLTextAreaElement>(null)
    const visualBodyRef = useRef<RichTextEditorHandle | null>(null)
    const testOccurrenceIdRef = useRef<string | null>(null)

    const isDirty = Object.keys(buildChangedFields(fields, savedFields)).length > 0
    const blockInternalNavigation = useCallback((destination: string) => {
        setPendingNavigation(destination)
    }, [])
    useUnsavedChangesWarning(isDirty, blockInternalNavigation)
    const previewHtml = buildEmailTemplatePreviewHtml(fields.body, {
        scope: "org",
        orgCompanyName: null,
        personalSignatureHtml: null,
        orgSignatureHtml: orgSignaturePreview.data?.html,
    })
    const previewSubject = buildPreviewSubject(fields.subject)
    const advancedBody = hasAdvancedEmailTemplateHtml(fields.body)
    const testVariableNames = extractEmailTemplateVariables(
        `${fields.subject}\n${fields.body}`,
    ).filter((name) => name !== "unsubscribe_url")
    const isTestCurrent =
        Boolean(draft) && draft?.last_tested_revision === draft?.revision
    const requiresRefresh = saveConflict || Boolean(draft?.is_stale)
    const publishedVersion =
        draft?.published_version ?? publishedTemplate?.current_version ?? null
    const templateVersions = useEmailTemplateVersions(
        publishedTemplate?.id ?? null,
        historyOpen,
    )

    const leaveStudio = (destination = "/automation/email-templates") => {
        setPendingNavigation(null)
        push(destination as Route)
    }

    const handleBack = () => {
        if (isDirty) {
            setPendingNavigation("/automation/email-templates")
            return
        }
        leaveStudio()
    }

    const insertIntoTextField = (
        field: "subject" | "body",
        element: HTMLInputElement | HTMLTextAreaElement | null,
        token: string,
    ) => {
        const currentValue = fields[field]
        const start = element?.selectionStart ?? currentValue.length
        const end = element?.selectionEnd ?? currentValue.length
        const nextValue = `${currentValue.slice(0, start)}${token}${currentValue.slice(end)}`
        setFields((current) => ({ ...current, [field]: nextValue }))
        requestAnimationFrame(() => {
            element?.focus()
            element?.setSelectionRange(start + token.length, start + token.length)
        })
    }

    const handleInsertVariable = (variable: TemplateVariableRead) => {
        const token = `{{${variable.name}}}`
        if (activeEditorField === "subject") {
            insertIntoTextField("subject", subjectRef.current, token)
            return
        }
        if (bodyMode === "html") {
            insertIntoTextField("body", htmlBodyRef.current, token)
            return
        }
        if (visualBodyRef.current) {
            visualBodyRef.current.insertText(token)
            return
        }
        setFields((current) => ({ ...current, body: `${current.body}${token}` }))
    }

    const handleSaveDraft = async () => {
        setSaveError(null)
        if (
            !fields.name.trim() ||
            !fields.subject.trim() ||
            !fields.body.trim()
        ) {
            setSaveError("Name, subject, and email body are required.")
            return
        }

        setIsSaving(true)
        setCopyStatus(null)
        try {
            const explicitLocalChanges = buildChangedFields(fields, savedFields)
            let activeDraft = draft
            if (!activeDraft && publishedTemplate && routeTemplateId) {
                activeDraft = await createDraftFromTemplate.mutateAsync({
                    templateId: routeTemplateId,
                })
                if (
                    hasOverlappingServerChanges(
                        explicitLocalChanges,
                        savedFields,
                        fieldsFromTemplate(activeDraft),
                    )
                ) {
                    setDraft(activeDraft)
                    setSaveConflict(true)
                    return
                }
            } else if (!activeDraft) {
                activeDraft = await createDraft.mutateAsync({
                    name: fields.name,
                    subject: fields.subject,
                    from_email: fields.from_email,
                    body: fields.body,
                    scope: "org",
                })
                const createdFields = fieldsFromTemplate(activeDraft)
                setDraft(activeDraft)
                setFields(createdFields)
                setSavedFields(createdFields)
                push(`/automation/email-templates/org/${activeDraft.id}` as Route)
                return
            }

            const savedDraft =
                Object.keys(explicitLocalChanges).length > 0
                    ? await updateDraft.mutateAsync({
                          id: activeDraft.id,
                          data: {
                              expected_revision: activeDraft.revision,
                              ...explicitLocalChanges,
                          },
                      })
                    : activeDraft

            const nextSavedFields = fieldsFromTemplate(savedDraft)
            setDraft(savedDraft)
            setFields(nextSavedFields)
            setSavedFields(nextSavedFields)
        } catch (error) {
            if (error instanceof ApiError && error.status === 409) {
                setSaveConflict(true)
            } else {
                setSaveError("Draft could not be saved. Your changes are still here.")
            }
        } finally {
            setIsSaving(false)
        }
    }

    const handleCopyLocalDraft = async () => {
        const localCopy = [
            `Name: ${fields.name}`,
            `Subject: ${fields.subject}`,
            `From: ${fields.from_email ?? ""}`,
            "",
            fields.body,
        ].join("\n")

        try {
            await navigator.clipboard.writeText(localCopy)
            setCopyStatus("Local draft copied.")
        } catch {
            setCopyStatus("Could not copy automatically. Select and copy your edits.")
        }
    }

    const handleDiscardStaleDraft = async () => {
        if (!draft?.is_stale) return

        setIsDiscarding(true)
        setDiscardError(null)
        try {
            await discardDraft.mutateAsync({
                id: draft.id,
                expectedRevision: draft.revision,
            })
            setDiscardOpen(false)
            replace("/automation/email-templates")
        } catch {
            setDiscardError(
                "The stale draft could not be discarded. Your published template was not changed.",
            )
        } finally {
            setIsDiscarding(false)
        }
    }

    const handlePublish = async () => {
        if (!draft) return
        setIsPublishing(true)
        setPublishError(null)
        try {
            const publishedTemplateResult = await publishDraft.mutateAsync({
                id: draft.id,
                data: {
                    expected_revision: draft.revision,
                    expected_published_version: draft.published_version,
                },
            })
            setPublishOpen(false)
            replace(
                `/automation/email-templates/org/${encodeURIComponent(publishedTemplateResult.id)}` as Route,
            )
        } catch (error) {
            if (error instanceof ApiError && error.status === 409) {
                setPublishOpen(false)
                setSaveConflict(true)
            } else {
                setPublishError(
                    "Template could not be published. Your draft is still saved.",
                )
            }
        } finally {
            setIsPublishing(false)
        }
    }

    const handleRestoreVersion = async (targetVersion: number) => {
        if (!publishedTemplate || isDirty || requiresRefresh) return

        setSaveError(null)
        try {
            let activeDraft = draft
            if (!activeDraft) {
                activeDraft = await createDraftFromTemplate.mutateAsync({
                    templateId: publishedTemplate.id,
                })
            }
            const restoredDraft = await restoreDraftVersion.mutateAsync({
                id: activeDraft.id,
                data: {
                    target_version: targetVersion,
                    expected_revision: activeDraft.revision,
                },
            })
            const restoredFields = fieldsFromTemplate(restoredDraft)
            setDraft(restoredDraft)
            setFields(restoredFields)
            setSavedFields(restoredFields)
            setBodyMode(getEmailTemplateBodyMode(restoredFields.body))
            setHistoryOpen(false)
        } catch (error) {
            setHistoryOpen(false)
            if (error instanceof ApiError && error.status === 409) {
                setSaveConflict(true)
            } else {
                setSaveError(
                    "That version could not be restored. Your published template was not changed.",
                )
            }
            throw error
        }
    }

    const handleTestOpenChange = (open: boolean) => {
        setTestOpen(open)
        if (!open && !isSendingTest) {
            setTestError(null)
            testOccurrenceIdRef.current = null
        }
    }

    const handleSendTest = async () => {
        if (!draft) return
        if (!testRecipient.trim()) {
            setTestError("Enter a recipient email address.")
            return
        }

        const idempotencyKey =
            testOccurrenceIdRef.current ?? createTestOccurrenceId()
        testOccurrenceIdRef.current = idempotencyKey
        const variableOverrides = Object.fromEntries(
            testVariableNames
                .map((name) => [name, (testVariables[name] ?? "").trim()])
                .filter(([, value]) => Boolean(value)),
        )

        setIsSendingTest(true)
        setTestError(null)
        try {
            const result = await sendTestDraft.mutateAsync({
                id: draft.id,
                payload: {
                    to_email: testRecipient.trim(),
                    variables: variableOverrides,
                    idempotency_key: idempotencyKey,
                    ignore_opt_out: ignoreOptOut,
                    expected_revision: draft.revision,
                },
            })
            setDraft({
                ...draft,
                last_tested_revision: result.tested_revision,
            })
            setTestOpen(false)
            testOccurrenceIdRef.current = null
        } catch (error) {
            if (error instanceof ApiError && error.status === 409) {
                setTestOpen(false)
                setSaveConflict(true)
            } else {
                setTestError("Test email failed. Your draft was not changed.")
            }
        } finally {
            setIsSendingTest(false)
        }
    }

    return (
        <main className="mx-auto max-w-7xl space-y-6 p-6">
            <header className="flex flex-wrap items-center justify-between gap-4">
                <div>
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="-ml-3 mb-2"
                        onClick={handleBack}
                    >
                        <ArrowLeftIcon aria-hidden="true" />
                        Back to email templates
                    </Button>
                    <p className="text-sm font-medium text-primary">Organization template</p>
                    <h1 className="text-2xl font-semibold tracking-tight">
                        {publishedTemplate ? "Edit email template" : "New email template"}
                    </h1>
                </div>
                <div className="flex flex-wrap items-center justify-end gap-2">
                    {publishedTemplate ? (
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => setHistoryOpen(true)}
                            disabled={requiresRefresh}
                        >
                            <HistoryIcon aria-hidden="true" />
                            View history
                        </Button>
                    ) : null}
                    <Button
                        type="button"
                        variant="outline"
                        onClick={() => setTestOpen(true)}
                        disabled={!draft || isDirty || requiresRefresh}
                    >
                        Send test
                    </Button>
                    <Button
                        type="button"
                        variant="outline"
                        onClick={handleSaveDraft}
                        disabled={
                            isSaving ||
                            requiresRefresh ||
                            (!isDirty && Boolean(draft))
                        }
                    >
                        {isSaving ? "Saving…" : "Save draft"}
                    </Button>
                    <Button
                        type="button"
                        onClick={() => setPublishOpen(true)}
                        disabled={!draft || isDirty || requiresRefresh}
                    >
                        Publish
                    </Button>
                </div>
            </header>

            {saveError ? (
                <p role="alert" className="text-sm text-destructive">
                    {saveError}
                </p>
            ) : null}
            {requiresRefresh ? (
                <Alert variant="destructive">
                    <h2 className="font-medium">Draft changed elsewhere</h2>
                    <AlertDescription className="space-y-3">
                        <p>
                            {draft?.is_stale
                                ? "This draft no longer matches the published template. Copy anything you need before discarding it."
                                : "Your local edits are intact. Copy anything you need before reloading the latest revision."}
                        </p>
                        <div className="flex flex-wrap gap-2">
                            <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={handleCopyLocalDraft}
                            >
                                Copy local draft
                            </Button>
                            {draft?.is_stale ? (
                                <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    onClick={() => setDiscardOpen(true)}
                                >
                                    Discard stale draft
                                </Button>
                            ) : (
                                <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    onClick={() => window.location.reload()}
                                >
                                    Reload latest
                                </Button>
                            )}
                        </div>
                        {copyStatus ? <p aria-live="polite">{copyStatus}</p> : null}
                    </AlertDescription>
                </Alert>
            ) : null}

            <Card>
                <CardContent className="grid gap-4 py-0 sm:grid-cols-3">
                    <div className="flex items-center justify-between gap-3 sm:block">
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            Draft
                        </p>
                        <div className="mt-1 flex items-center gap-2">
                            <Badge
                                variant={
                                    requiresRefresh
                                        ? "destructive"
                                        : isDirty
                                          ? "secondary"
                                          : "outline"
                                }
                            >
                                {draft?.is_stale
                                    ? "Stale draft"
                                    : saveConflict
                                      ? "Refresh required"
                                      : isDirty
                                        ? "Unsaved changes"
                                        : draft
                                          ? "Saved"
                                          : publishedTemplate
                                            ? "No draft"
                                            : "Not saved"}
                            </Badge>
                            <span className="text-sm text-muted-foreground">
                                {draft
                                    ? `Revision ${draft.revision}`
                                    : publishedTemplate
                                      ? "Create on first save"
                                      : "Not created"}
                            </span>
                        </div>
                    </div>
                    <div className="flex items-center justify-between gap-3 sm:block">
                            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                                Test status
                        </p>
                        <div className="mt-1">
                            <Badge variant={isTestCurrent ? "default" : "secondary"}>
                                {isTestCurrent
                                    ? "Tested current draft"
                                    : draft
                                      ? "Not tested"
                                      : "Save draft to test"}
                            </Badge>
                        </div>
                    </div>
                    <div className="flex items-center justify-between gap-3 sm:block">
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            Production
                        </p>
                        <div className="mt-1">
                            <Badge variant="outline">
                                {publishedVersion
                                    ? `Published version ${publishedVersion}`
                                    : "Not published"}
                            </Badge>
                        </div>
                    </div>
                </CardContent>
            </Card>

            <section className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.8fr)]">
                <Card>
                    <CardHeader>
                        <CardTitle>Draft content</CardTitle>
                        <CardDescription>
                            Changes stay isolated from production until you publish.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-5">
                        <div className="grid gap-2">
                            <Label htmlFor="template-name">Template name</Label>
                            <Input
                                id="template-name"
                                value={fields.name}
                                onChange={(event) =>
                                    setFields((current) => ({
                                        ...current,
                                        name: event.target.value,
                                    }))
                                }
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="template-subject">Subject</Label>
                            <Input
                                ref={subjectRef}
                                id="template-subject"
                                value={fields.subject}
                                onFocus={() => setActiveEditorField("subject")}
                                onChange={(event) =>
                                    setFields((current) => ({
                                        ...current,
                                        subject: event.target.value,
                                    }))
                                }
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="template-from-email">From email</Label>
                            <Input
                                id="template-from-email"
                                value={fields.from_email ?? ""}
                                onChange={(event) =>
                                    setFields((current) => ({
                                        ...current,
                                        from_email: event.target.value || null,
                                    }))
                                }
                            />
                        </div>
                        <div className="flex items-center justify-between gap-3">
                            <div className="space-y-1">
                                <Label id="template-body-label">Email body</Label>
                                {bodyMode === "html" ? (
                                    <p className="text-xs text-muted-foreground">
                                        Source mode protects tables, images, and email-client
                                        layout.
                                    </p>
                                ) : null}
                            </div>
                            <TemplateVariablePicker
                                variables={variables ?? []}
                                onSelect={handleInsertVariable}
                            />
                        </div>
                        <div className="flex items-center gap-1 rounded-lg bg-muted p-1">
                            <Button
                                type="button"
                                size="sm"
                                variant={bodyMode === "visual" ? "secondary" : "ghost"}
                                aria-pressed={bodyMode === "visual"}
                                disabled={advancedBody}
                                onClick={() => setBodyMode("visual")}
                            >
                                Visual editor
                            </Button>
                            <Button
                                type="button"
                                size="sm"
                                variant={bodyMode === "html" ? "secondary" : "ghost"}
                                aria-pressed={bodyMode === "html"}
                                onClick={() => setBodyMode("html")}
                            >
                                HTML source
                            </Button>
                        </div>
                        {bodyMode === "html" ? (
                            <Textarea
                                ref={htmlBodyRef}
                                aria-label="Email HTML"
                                value={fields.body}
                                className="min-h-80 resize-y font-mono text-xs leading-relaxed"
                                onFocus={() => setActiveEditorField("body")}
                                onChange={(event) =>
                                    setFields((current) => ({
                                        ...current,
                                        body: event.target.value,
                                    }))
                                }
                            />
                        ) : (
                            <RichTextEditor
                                ref={visualBodyRef}
                                content={fields.body}
                                onFocus={() => setActiveEditorField("body")}
                                onChange={(body) =>
                                    setFields((current) => ({ ...current, body }))
                                }
                                ariaLabelledBy="template-body-label"
                                ariaLabel="Email body"
                                minHeight="320px"
                                maxHeight="560px"
                                enableImages
                                enableEmojiPicker
                            />
                        )}
                    </CardContent>
                </Card>

                <Card className="xl:sticky xl:top-6">
                    <CardHeader>
                        <CardTitle>
                            <h2>Live preview</h2>
                        </CardTitle>
                        <CardDescription>
                            Organization signature and managed unsubscribe footer included.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="overflow-hidden rounded-xl border bg-white text-slate-950 shadow-sm">
                            <div className="border-b bg-slate-50 px-5 py-4">
                                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                                    Subject
                                </p>
                                <p className="mt-1 font-medium">
                                    {previewSubject || "Your subject will appear here"}
                                </p>
                            </div>
                            <div className="min-h-80 overflow-auto p-5">
                                <TrustedSanitizedHtmlContent
                                    html={previewHtml}
                                    className="text-sm"
                                />
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </section>

            {publishedTemplate ? (
                <EmailTemplateHistorySheet
                    open={historyOpen}
                    onOpenChange={setHistoryOpen}
                    templateName={fields.name || publishedTemplate.name}
                    currentVersion={publishedTemplate.current_version}
                    versions={templateVersions.data ?? []}
                    isLoading={templateVersions.isLoading}
                    isError={templateVersions.isError}
                    onRetry={() => {
                        void templateVersions.refetch()
                    }}
                    onRestore={handleRestoreVersion}
                    isRestoring={
                        restoreDraftVersion.isPending ||
                        isDirty ||
                        requiresRefresh
                    }
                    restoreMode="draft"
                />
            ) : null}

            <AlertDialog open={publishOpen} onOpenChange={setPublishOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Publish this template?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This makes the saved draft available to production email
                            workflows. Existing published content stays unchanged until
                            you confirm.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    {!isTestCurrent ? (
                        <Alert>
                            <AlertDescription>
                                <p>
                                    This saved revision has not been test-sent. Testing is
                                    recommended, but not required to publish.
                                </p>
                            </AlertDescription>
                        </Alert>
                    ) : null}
                    {publishError ? (
                        <p role="alert" className="text-sm text-destructive">
                            {publishError}
                        </p>
                    ) : null}
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={isPublishing}>
                            Keep editing
                        </AlertDialogCancel>
                        <AlertDialogAction
                            type="button"
                            onClick={handlePublish}
                            disabled={isPublishing}
                        >
                            {isPublishing ? "Publishing…" : "Publish now"}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog
                open={pendingNavigation !== null}
                onOpenChange={(open) => {
                    if (!open) setPendingNavigation(null)
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Leave without saving?</AlertDialogTitle>
                        <AlertDialogDescription>
                            Your local edits have not been saved to this draft.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Keep editing</AlertDialogCancel>
                        <AlertDialogAction
                            type="button"
                            onClick={() =>
                                leaveStudio(
                                    pendingNavigation ??
                                        "/automation/email-templates",
                                )
                            }
                        >
                            Leave without saving
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog open={discardOpen} onOpenChange={setDiscardOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Discard this stale draft?</AlertDialogTitle>
                        <AlertDialogDescription>
                            Copy any edits you need first. Discarding removes only this
                            stale draft; the published template stays unchanged. Reopen
                            the template to start from its latest published version.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    {discardError ? (
                        <p role="alert" className="text-sm text-destructive">
                            {discardError}
                        </p>
                    ) : null}
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={isDiscarding}>
                            Keep stale draft
                        </AlertDialogCancel>
                        <Button
                            type="button"
                            variant="destructive"
                            onClick={handleDiscardStaleDraft}
                            disabled={isDiscarding}
                        >
                            {isDiscarding ? "Discarding…" : "Discard draft"}
                        </Button>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <Dialog open={testOpen} onOpenChange={handleTestOpenChange}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Send a draft test</DialogTitle>
                        <DialogDescription>
                            This sends the saved draft only. It does not publish the
                            template.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4">
                        <div className="grid gap-2">
                            <Label htmlFor="test-recipient">Test recipient</Label>
                            <Input
                                id="test-recipient"
                                type="email"
                                placeholder="qa@example.com"
                                value={testRecipient}
                                onChange={(event) =>
                                    setTestRecipient(event.target.value)
                                }
                            />
                        </div>
                        {testVariableNames.map((name) => (
                            <div key={name} className="grid gap-2">
                                <Label htmlFor={`test-variable-${name}`}>
                                    Test value for {name}
                                </Label>
                                <Input
                                    id={`test-variable-${name}`}
                                    value={testVariables[name] ?? ""}
                                    onChange={(event) =>
                                        setTestVariables((current) => ({
                                            ...current,
                                            [name]: event.target.value,
                                        }))
                                    }
                                />
                            </div>
                        ))}
                        <div className="flex items-start gap-3 rounded-lg border p-3 text-sm">
                            <Checkbox
                                id="test-ignore-opt-out"
                                checked={ignoreOptOut}
                                onCheckedChange={(checked) =>
                                    setIgnoreOptOut(checked === true)
                                }
                            />
                            <Label
                                htmlFor="test-ignore-opt-out"
                                className="cursor-pointer font-normal"
                            >
                                <span className="block font-medium">
                                    Send even if unsubscribed
                                </span>
                                <span className="text-muted-foreground">
                                    Test-only override for an authorized recipient.
                                </span>
                            </Label>
                        </div>
                        {testError ? (
                            <p role="alert" className="text-sm text-destructive">
                                {testError}
                            </p>
                        ) : null}
                    </div>
                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => handleTestOpenChange(false)}
                            disabled={isSendingTest}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="button"
                            onClick={handleSendTest}
                            disabled={isSendingTest}
                        >
                            {isSendingTest ? "Sending…" : "Send test email"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </main>
    )
}
