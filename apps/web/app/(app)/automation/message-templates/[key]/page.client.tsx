"use client"

import { useMemo, useRef, useState } from "react"
import type { Route } from "next"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import { CheckIcon, CircleIcon, Loader2Icon } from "lucide-react"

import Link from "@/components/app-link"
import { PermissionDeniedState, QueryErrorState } from "@/components/error-state"
import { SendTestMessageDialog } from "@/components/messaging/send-test-message-dialog"
import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "@/components/ui/toast"
import type { MessagingTemplateVersion, TwilioMessagingPurpose } from "@/lib/api/twilio"
import { getErrorMessage } from "@/lib/error-utils"
import { formatDate } from "@/lib/formatters"
import {
    useCreateMessagingTemplate,
    useMessagingAccess,
    useMessagingSmsVariables,
    useMessagingTemplateUsage,
    useMessagingTemplateVersions,
    usePublishMessagingTemplate,
    useSaveMessagingTemplateDraft,
} from "@/lib/hooks/use-messaging-templates"
import { useTwilioSettings } from "@/lib/hooks/use-twilio"
import { insertAtCursor } from "@/lib/insert-at-cursor"
import {
    countSmsSegments,
    groupTemplateFamilies,
    MAX_SMS_BODY_CHARACTERS,
    optInRequirements,
    PURPOSE_LABELS,
    renderSmsBody,
    type TemplateFamily,
} from "@/lib/messaging/sms-content"
import { templateHref, testTemplateOptions } from "@/lib/messaging/template-library"
import { cn } from "@/lib/utils"

const LIST_HREF = "/automation/message-templates" as Route

interface Draft {
    name: string
    purpose: TwilioMessagingPurpose
    body: string
    isOptIn: boolean
}

function draftFrom(version: MessagingTemplateVersion): Draft {
    return {
        name: version.name,
        purpose: version.purpose,
        body: version.body,
        isOptIn: version.is_enrollment_confirmation,
    }
}

const STATUS_LABELS: Record<MessagingTemplateVersion["status"], string> = {
    draft: "Draft",
    published: "Live",
    retired: "Retired",
}

export default function MessageTemplateEditorPageClient() {
    const params = useParams<{ key: string }>()
    const searchParams = useSearchParams()
    const access = useMessagingAccess()
    const versionsQuery = useMessagingTemplateVersions(access.allowed)
    const key = params.key
    const isNew = key === "new"
    const family = useMemo(
        () => groupTemplateFamilies(versionsQuery.data ?? []).find((item) => item.key === key) ?? null,
        [versionsQuery.data, key],
    )

    if (access.loading || !access.allowed) {
        return (
            <div className="flex min-h-full flex-col">
                <PageHeader title="Message template" back={{ href: LIST_HREF, label: "Back to message templates" }} />
                {access.loading ? (
                    <div className="p-6"><Skeleton className="h-96 w-full" /></div>
                ) : (
                    <PermissionDeniedState
                        title="Message templates are restricted"
                        description="Only organization administrators and developers with integration access can manage text message templates."
                        headingLevel={2}
                    />
                )}
            </div>
        )
    }
    if (!isNew && (versionsQuery.isLoading || versionsQuery.isError || !family)) {
        return (
            <div className="flex min-h-full flex-col">
                <PageHeader title="Message template" back={{ href: LIST_HREF, label: "Back to message templates" }} />
                <div className="p-6">
                    {versionsQuery.isLoading || versionsQuery.isFetching ? (
                        <Skeleton className="h-96 w-full" />
                    ) : (
                        <Card className="py-0">
                            <QueryErrorState
                                error={versionsQuery.error ?? new Error("This message template was not found.")}
                                onRetry={() => void versionsQuery.refetch()}
                                isRetrying={versionsQuery.isFetching}
                                title="Couldn't load this message template"
                                headingLevel={2}
                            />
                        </Card>
                    )}
                </div>
            </div>
        )
    }

    const initialPurpose: TwilioMessagingPurpose =
        searchParams.get("purpose") === "promotional" ? "promotional" : "operational"
    return (
        <TemplateEditor
            key={family?.key ?? "new"}
            family={family}
            initial={
                family
                    ? draftFrom(family.latest)
                    : { name: "", purpose: initialPurpose, body: "", isOptIn: false }
            }
        />
    )
}

function TemplateEditor({ family, initial }: { family: TemplateFamily | null; initial: Draft }) {
    const router = useRouter()
    const [draft, setDraft] = useState<Draft>(initial)
    const [historyOpen, setHistoryOpen] = useState(false)
    const [testOpen, setTestOpen] = useState(false)
    const [testTemplateId, setTestTemplateId] = useState<string | null>(null)
    const bodyRef = useRef<HTMLTextAreaElement>(null)
    const settingsQuery = useTwilioSettings()
    const variablesQuery = useMessagingSmsVariables()
    const usageQuery = useMessagingTemplateUsage(Boolean(family))
    const createTemplate = useCreateMessagingTemplate()
    const saveDraft = useSaveMessagingTemplateDraft()
    const publish = usePublishMessagingTemplate()

    const dirty =
        draft.name !== initial.name || draft.body !== initial.body || draft.isOptIn !== initial.isOptIn
    const busy = createTemplate.isPending || saveDraft.isPending || publish.isPending
    const samples = Object.fromEntries((variablesQuery.data ?? []).map((variable) => [variable.name, variable.sample]))
    const { characters, segments } = countSmsSegments(draft.body)
    const requirements = optInRequirements(draft.body, settingsQuery.data ?? null)
    const uses = usageQuery.data?.find((item) => item.template_key === family?.key)?.uses ?? []
    const sender = settingsQuery.data?.routes[draft.purpose]?.sender_phone_masked
    const publishVersion = family?.draft?.version ?? (family && dirty ? family.latest.version + 1 : null)
    const canPublish = Boolean(draft.name.trim() && draft.body.trim()) && (!family || dirty || family.draft !== null)

    const update = (patch: Partial<Draft>) => setDraft((current) => ({ ...current, ...patch }))

    /** Save the form; returns the draft version that holds it. */
    const save = async (): Promise<MessagingTemplateVersion | null> => {
        if (!family) {
            const created = await createTemplate.mutateAsync({
                name: draft.name,
                purpose: draft.purpose,
                body: draft.body,
                is_enrollment_confirmation: draft.isOptIn,
            })
            return created
        }
        if (!dirty) return family.draft
        return saveDraft.mutateAsync({
            templateKey: family.key,
            draftId: family.draft?.id ?? null,
            update: { name: draft.name, body: draft.body, is_enrollment_confirmation: draft.isOptIn },
        })
    }

    const handleSave = async () => {
        try {
            const saved = await save()
            toast.success("Draft saved")
            if (!family && saved) router.replace(templateHref(saved.template_key))
        } catch (error) {
            toast.error(getErrorMessage(error, "Could not save the draft."))
        }
    }

    const handlePublish = async () => {
        try {
            const saved = await save()
            if (!saved) return
            const published = await publish.mutateAsync(saved.id)
            toast.success(`Published v${published.version}`)
            if (!family) router.replace(templateHref(published.template_key))
        } catch (error) {
            toast.error(getErrorMessage(error, "Could not publish the template."))
        }
    }

    const handleSendTest = async () => {
        try {
            const saved = dirty ? await save() : null
            setTestTemplateId(saved?.id ?? family?.draft?.id ?? family?.live?.id ?? null)
            setTestOpen(true)
        } catch (error) {
            toast.error(getErrorMessage(error, "Could not save the draft."))
        }
    }

    const insertVariable = (name: string) => {
        const element = bodyRef.current
        const token = `{{${name}}}`
        const result = insertAtCursor(
            draft.body,
            token,
            element?.selectionStart ?? draft.body.length,
            element?.selectionEnd ?? draft.body.length,
        )
        update({ body: result.nextValue })
        requestAnimationFrame(() => {
            element?.focus()
            element?.setSelectionRange(result.nextSelectionStart, result.nextSelectionEnd)
        })
    }

    return (
        <div className="flex min-h-full flex-col">
            <PageHeader
                title={family ? family.name : "New template"}
                back={{ href: LIST_HREF, label: "Back to message templates" }}
                meta={
                    family ? (
                        <>
                            {family.draft ? <Badge variant="outline">Draft v{family.draft.version}</Badge> : null}
                            {family.live ? (
                                <Badge variant="outline" className="border-success/30 bg-success/10 text-success">
                                    Live: v{family.live.version}
                                </Badge>
                            ) : null}
                        </>
                    ) : null
                }
                actions={
                    <>
                        {family ? (
                            <>
                                <Button variant="outline" onClick={() => setHistoryOpen(true)}>
                                    Version history
                                </Button>
                                <Button variant="outline" onClick={() => void handleSendTest()} disabled={busy}>
                                    Send test
                                </Button>
                            </>
                        ) : null}
                        <Button variant="outline" onClick={() => void handleSave()} disabled={busy || !canPublish || (family !== null && !dirty)}>
                            Save draft
                        </Button>
                        <Button onClick={() => void handlePublish()} disabled={busy || !canPublish}>
                            {publish.isPending ? (
                                <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                            ) : null}
                            {publishVersion ? `Publish v${publishVersion}` : "Publish"}
                        </Button>
                    </>
                }
            />

            <div className="flex flex-1 flex-wrap items-start gap-5 p-6">
                <Card className="min-w-0 flex-[999_1_420px]">
                    <CardContent className="space-y-5">
                        <div className="space-y-2">
                            <Label htmlFor="template-name">Name</Label>
                            <Input
                                id="template-name"
                                value={draft.name}
                                maxLength={160}
                                onChange={(event) => update({ name: event.target.value })}
                            />
                        </div>

                        <fieldset className="space-y-2">
                            <legend className="mb-2 text-sm font-medium">Purpose</legend>
                            {family ? (
                                <p className="text-sm">{PURPOSE_LABELS[draft.purpose]}</p>
                            ) : (
                                <RadioGroup
                                    aria-label="Purpose"
                                    value={draft.purpose}
                                    onValueChange={(value) => update({ purpose: value as TwilioMessagingPurpose })}
                                    className="flex flex-wrap gap-x-5 gap-y-2"
                                >
                                    {(["operational", "promotional"] as const).map((purpose) => (
                                        <div key={purpose} className="flex items-center gap-2">
                                            <RadioGroupItem id={`template-purpose-${purpose}`} value={purpose} />
                                            <Label htmlFor={`template-purpose-${purpose}`} className="font-normal">
                                                {PURPOSE_LABELS[purpose]}
                                            </Label>
                                        </div>
                                    ))}
                                </RadioGroup>
                            )}
                        </fieldset>

                        <div className="flex items-start gap-2">
                            <Checkbox
                                id="template-opt-in"
                                checked={draft.isOptIn}
                                onCheckedChange={(checked) => update({ isOptIn: checked === true })}
                                className="mt-0.5"
                            />
                            <Label htmlFor="template-opt-in" className="font-normal">
                                Opt-in confirmation: sent as the first text after a person opts in
                            </Label>
                        </div>

                        <div className="space-y-2">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <Label htmlFor="template-body">Message</Label>
                                <DropdownMenu>
                                    <DropdownMenuTrigger className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
                                        Insert variable
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end">
                                        {(variablesQuery.data ?? []).map((variable) => (
                                            <DropdownMenuItem key={variable.name} onClick={() => insertVariable(variable.name)}>
                                                {variable.description}
                                            </DropdownMenuItem>
                                        ))}
                                    </DropdownMenuContent>
                                </DropdownMenu>
                            </div>
                            <Textarea
                                id="template-body"
                                ref={bodyRef}
                                rows={5}
                                maxLength={MAX_SMS_BODY_CHARACTERS}
                                value={draft.body}
                                onChange={(event) => update({ body: event.target.value })}
                            />
                            <div className="flex flex-wrap justify-between gap-2 text-xs text-muted-foreground">
                                <span>
                                    {characters.toLocaleString()} characters · {segments} segment{segments === 1 ? "" : "s"}
                                </span>
                                <span>Max {MAX_SMS_BODY_CHARACTERS.toLocaleString()}</span>
                            </div>
                        </div>

                        {draft.isOptIn ? (
                            <div className="space-y-3 rounded-lg border bg-muted/30 p-4">
                                <p className="text-sm font-medium">Required for opt-in confirmation</p>
                                <ul aria-label="Required for opt-in confirmation" className="grid gap-2 sm:grid-cols-2">
                                    {requirements.map((requirement) => (
                                        <li key={requirement.label} className="flex items-center gap-2 text-sm">
                                            {requirement.met ? (
                                                <CheckIcon className="size-4 text-success" aria-hidden="true" />
                                            ) : (
                                                <CircleIcon className="size-4 text-muted-foreground" aria-hidden="true" />
                                            )}
                                            {requirement.label}
                                            <span className="sr-only">{requirement.met ? "(included)" : "(missing)"}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ) : null}
                    </CardContent>
                </Card>

                <Card className="min-w-0 flex-[1_1_300px]">
                    <CardContent className="space-y-4">
                        <h2 className="text-sm font-medium">Preview with sample data</h2>
                        <div className="flex min-h-64 flex-col gap-2 rounded-2xl bg-muted p-4">
                            {draft.body.trim() ? (
                                <p className="max-w-[88%] self-start rounded-2xl rounded-bl-sm bg-background px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap">
                                    {renderSmsBody(draft.body, samples)}
                                </p>
                            ) : null}
                        </div>
                        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                            <dt className="text-muted-foreground">Route</dt>
                            <dd>
                                {PURPOSE_LABELS[draft.purpose]}
                                {sender ? ` · ${sender}` : ""}
                            </dd>
                            {family ? (
                                <>
                                    <dt className="text-muted-foreground">Used by</dt>
                                    <dd>
                                        {uses.length === 0 ? (
                                            <span className="text-muted-foreground">—</span>
                                        ) : (
                                            <ul className="space-y-1">
                                                {uses.map((use) => (
                                                    <li key={`${use.kind}-${use.id}`}>
                                                        <Link
                                                            href={(use.kind === "workflow" ? `/automation/workflows/${use.id}` : `/automation/campaigns/${use.id}`) as Route}
                                                            className="text-primary hover:underline"
                                                        >
                                                            {use.name}
                                                        </Link>
                                                    </li>
                                                ))}
                                            </ul>
                                        )}
                                    </dd>
                                </>
                            ) : null}
                        </dl>
                    </CardContent>
                </Card>
            </div>

            {family ? (
                <>
                    <VersionHistoryDialog family={family} open={historyOpen} onOpenChange={setHistoryOpen} />
                    <SendTestMessageDialog
                        open={testOpen}
                        onOpenChange={setTestOpen}
                        templates={testTemplateOptions([family])}
                        defaultTemplateId={testTemplateId}
                    />
                </>
            ) : null}
        </div>
    )
}

function VersionHistoryDialog({
    family,
    open,
    onOpenChange,
}: {
    family: TemplateFamily
    open: boolean
    onOpenChange: (open: boolean) => void
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent size="lg">
                <DialogHeader>
                    <DialogTitle>Version history</DialogTitle>
                </DialogHeader>
                <ol className="max-h-[60vh] space-y-3 overflow-y-auto">
                    {family.versions.map((version) => (
                        <li key={version.id} className="space-y-1.5 rounded-lg border p-3">
                            <div className="flex flex-wrap items-center gap-2 text-sm">
                                <span className="font-medium">v{version.version}</span>
                                <Badge variant="outline">{STATUS_LABELS[version.status]}</Badge>
                                <span className="text-muted-foreground">
                                    {formatDate(version.published_at ?? version.created_at, { month: "short", day: "numeric", year: "numeric" })}
                                </span>
                            </div>
                            <p className="text-sm whitespace-pre-wrap text-muted-foreground">{version.body}</p>
                        </li>
                    ))}
                </ol>
            </DialogContent>
        </Dialog>
    )
}
