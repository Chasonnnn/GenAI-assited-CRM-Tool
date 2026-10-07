import { type ReactNode, useState, useRef } from "react"
import Link from "@/components/app-link"
import { Card, CardHeader, CardDescription, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DialogHeader, DialogTitle, DialogStatusBar, DialogBody, DialogFooter, DialogClose } from "@/components/ui/dialog"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { CopyButton } from "@/components/ui/copy-button"
import { CopyField } from "@/components/ui/copy-field"
import { ValidatedField } from "@/components/ui/field"
import { type SaveStatusState, SaveStatus } from "@/components/ui/save-bar"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Loader2Icon, AlertTriangleIcon, PlusIcon, RotateCwIcon, TrashIcon, SparklesIcon, ActivityIcon, ZapIcon } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { usePipelines } from "@/lib/hooks/use-pipelines"
import { useZapierOutboundEventsSummary, useZapierOutboundEvents, useRetryZapierOutboundEvent, useReplayZapierOutboundEvent, useZapierDonorOutboundTest, useZapierSettings, useCreateZapierInboundWebhook, useRotateZapierInboundWebhook, useUpdateZapierInboundWebhook, useZapierFieldPaste, useDeleteZapierInboundWebhook, useUpdateZapierOutboundSettings, useZapierTestLead, useZapierOutboundTest } from "@/lib/hooks/use-zapier"
import { useMetaForms } from "@/lib/hooks/use-meta-forms"
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table"
import { formatRelativeTime } from "@/lib/formatters"
import { toast } from "@/components/ui/toast"
import type { Pipeline } from "@/lib/api/pipelines"
import type { ZapierDonorEventMappingItem, ZapierDonorAttributionSource, ZapierOutboundEvent, ZapierEventMappingItem, ZapierFieldPasteResponse, ZapierStageBucket, ZapierDonorOutboundTestRequest } from "@/lib/api/zapier"
import { getStageSemantics } from "@/lib/surrogate-stage-context"
import { StageEventMappingTable, UNTRACKED_BUCKET_VALUE, ZAPIER_BUCKET_EVENT_NAME, ZAPIER_OUTBOUND_STATUS_BADGE, buildRecommendedBucketByStage, buildStageLabelByKey, formatZapierRate, formatZapierReason, formatZapierSource, getSelectOptionLabel, mergeEventMappingWithPipelineStages, type BadgeVariant, type IconComponent } from "./integration-shared"

type ZapierDonorEventName = ZapierDonorEventMappingItem["event_name"]
// Form rows keep untracked stages with an empty event name; saving drops them.
type ZapierDonorMappingDraftItem = Omit<ZapierDonorEventMappingItem, "event_name"> & {
    event_name: ZapierDonorEventName | ""
}

const ZAPIER_EVENT_OPTIONS: Array<{ value: ZapierDonorEventName; label: string }> = [
    { value: "Lead", label: "Lead" },
    { value: "Qualified", label: "Qualified" },
    { value: "Converted", label: "Converted" },
    { value: "Lost", label: "Lost" },
    { value: "Not Qualified", label: "Not Qualified" },
]

const ZAPIER_FORM_ROUTE_HEADERS = [
    { label: "Form", className: undefined },
    { label: "Creates", className: undefined },
    { label: "Status", className: undefined },
    { label: "Action", className: "text-right" },
]

const DONOR_TYPES = ["egg", "sperm"] as const
export type ZapierDonorType = (typeof DONOR_TYPES)[number]

const ZAPIER_DONOR_TYPE_OPTIONS: Array<{ value: ZapierDonorType; label: string }> = DONOR_TYPES.map(
    (donorType) => ({ value: donorType, label: getDonorTypeLabel(donorType) }),
)

const ZAPIER_DONOR_ATTRIBUTION_OPTIONS: Array<{ value: ZapierDonorAttributionSource; label: string }> = [
    { value: "meta", label: "Meta lead" },
    { value: "website", label: "Website form" },
]

function getDonorTypeLabel(donorType: ZapierDonorType): string {
    return donorType === "egg" ? "Egg donor" : "Sperm donor"
}

function getLeadKindLabel(leadKind: ZapierMetaFormOption["lead_kind"]): string {
    if (leadKind === "egg_donor") return "Egg donor"
    if (leadKind === "sperm_donor") return "Sperm donor"
    return "Surrogate"
}

function getDonorEventLabel(value: string | null | undefined): string {
    if (!value || value === UNTRACKED_BUCKET_VALUE) return "Not Tracked"
    return getSelectOptionLabel(ZAPIER_EVENT_OPTIONS, value)
}

function getDefaultDonorEventName(stage: Pipeline["stages"][number]): ZapierDonorEventName | "" {
    const bucket = getStageSemantics(stage).integration_bucket
    if (bucket === "lost") return "Lost"
    if (bucket === "not_qualified") return "Not Qualified"
    // A terminal stage reports only a negative outcome, never Lead or Converted.
    if (stage.stage_type === "terminal") return ""
    if (bucket === "intake") return "Lead"
    if (bucket === "qualified") return "Qualified"
    if (bucket === "converted") return "Converted"
    return ""
}

function isTrackedDonorMappingItem(
    item: ZapierDonorMappingDraftItem,
): item is ZapierDonorEventMappingItem {
    return item.event_name !== ""
}

function buildDonorEventMapping(
    savedMapping: ZapierDonorEventMappingItem[] | null | undefined,
    pipelinesByType: Record<ZapierDonorType, Pipeline[] | null | undefined>,
): ZapierDonorMappingDraftItem[] {
    const savedByStage = new Map(
        (savedMapping ?? []).map((item) => [
            `${item.donor_type}:${item.pipeline_id}:${item.stage_id}`,
            item,
        ]),
    )
    const result: ZapierDonorMappingDraftItem[] = []
    // Unsaved stages start from the suggestion only before the first donor mapping save.
    // A saved mapping can be empty when every stage is Not Tracked.
    const suggest = savedMapping == null

    for (const donorType of DONOR_TYPES) {
        for (const pipeline of pipelinesByType[donorType] ?? []) {
            for (const stage of pipeline.stages ?? []) {
                if (stage.is_active === false) continue
                const key = `${donorType}:${pipeline.id}:${stage.id}`
                const eventName = suggest ? getDefaultDonorEventName(stage) : ""
                result.push(savedByStage.get(key) ?? {
                    donor_type: donorType,
                    pipeline_id: pipeline.id,
                    stage_id: stage.id,
                    event_name: eventName,
                    enabled: eventName !== "",
                })
            }
        }
    }

    return result
}

export function hasUnresolvedDonorMappings(
    savedMapping: ZapierDonorEventMappingItem[] | null | undefined,
    pipelinesByType: Record<ZapierDonorType, Pipeline[] | null | undefined>,
): boolean {
    const validKeys = new Set(
        buildDonorEventMapping([], pipelinesByType).map(
            (item) => `${item.donor_type}:${item.pipeline_id}:${item.stage_id}`,
        ),
    )
    return (savedMapping ?? []).some(
        (item) => !validKeys.has(`${item.donor_type}:${item.pipeline_id}:${item.stage_id}`),
    )
}

function getDonorEventStageLabel(
    event: ZapierOutboundEvent,
    pipelinesByType: Record<ZapierDonorType, Pipeline[] | null | undefined>,
): string | null {
    if (!event.donor_type) return null
    const donorType = event.donor_type
    const pipeline = pipelinesByType[donorType]?.find((item) => item.id === event.pipeline_id)
    const stage = pipeline?.stages.find((item) => item.id === event.stage_id)
    const donorLabel = getDonorTypeLabel(donorType)
    if (event.source === "test" && !event.stage_id) return `${donorLabel} · Test event`
    if (pipeline && stage) return `${donorLabel} · ${pipeline.name} · ${stage.label}`
    if (event.stage_label) {
        return pipeline
            ? `${donorLabel} · ${pipeline.name} · ${event.stage_label}`
            : `${donorLabel} · ${event.stage_label}`
    }
    return `${donorLabel} stage unavailable`
}

function getWebhookSelectLabel(
    webhooks:
        | Array<{
            webhook_id: string
            label?: string | null
        }>
        | null
        | undefined,
    value: string | null | undefined,
): string {
    if (!value) return ""
    const webhook = webhooks?.find((item) => item.webhook_id === value)
    if (!webhook) return ""
    return webhook.label || `Webhook ${webhook.webhook_id.slice(0, 8)}`
}

function getZapierFormSelectLabel(
    forms: ZapierMetaFormOption[],
    value: string | null | undefined,
): string {
    if (!value) return ""
    const form = forms.find((item) => item.form_external_id === value)
    if (!form) return ""
    return `${form.form_name || "Unnamed Zapier form"} · ${getLeadKindLabel(form.lead_kind)}`
}

function formatZapierAttribution(event: ZapierOutboundEvent): string {
    if (event.attribution_source === "website") return "Attribution: Website form"
    if (event.attribution_source === "meta") {
        return `Meta lead: ${event.lead_id || "Unavailable"}`
    }
    return `Lead: ${event.lead_id || "—"}`
}

type ZapierInboundWebhookDraftSource = {
    webhook_id: string
    label?: string | null
}

type ZapierWebhookDraftState = {
    webhookKey: string
    labelDrafts: Record<string, string>
    webhookSecrets: Record<string, string>
}

type ZapierOutboundFormState = {
    outboundUrl: string
    outboundEnabled: boolean
    donorOutboundEnabled: boolean
    sendHashedPii: boolean
    eventMapping: ZapierEventMappingItem[]
    donorEventMapping: ZapierDonorMappingDraftItem[]
    removeUnavailableDonorMappings: boolean
    selectedOutboundStage: string
}

type ZapierOutboundDraftState = {
    outboundKey: string
    form: ZapierOutboundFormState
}

function createZapierWebhookDraftKey(
    webhooks: ZapierInboundWebhookDraftSource[] | null | undefined,
) {
    return (webhooks ?? [])
        .map((webhook) => `${webhook.webhook_id}:${webhook.label ?? ""}`)
        .join("\u0000")
}

function createZapierWebhookDraftState(
    webhookKey: string,
    webhooks: ZapierInboundWebhookDraftSource[] | null | undefined,
    currentSecrets: Record<string, string> = {},
): ZapierWebhookDraftState {
    const labelDrafts: Record<string, string> = {}
    const webhookSecrets: Record<string, string> = {}

    for (const webhook of webhooks ?? []) {
        labelDrafts[webhook.webhook_id] = webhook.label || ""
        const existingSecret = currentSecrets[webhook.webhook_id]
        if (existingSecret) {
            webhookSecrets[webhook.webhook_id] = existingSecret
        }
    }

    return {
        webhookKey,
        labelDrafts,
        webhookSecrets,
    }
}

function getActiveZapierWebhookDraft(
    draft: ZapierWebhookDraftState,
    webhookKey: string,
    webhooks: ZapierInboundWebhookDraftSource[] | null | undefined,
): ZapierWebhookDraftState {
    if (draft.webhookKey === webhookKey) return draft
    return createZapierWebhookDraftState(webhookKey, webhooks, draft.webhookSecrets)
}

function getActiveFieldPasteWebhookId(
    requestedWebhookId: string,
    webhooks: ZapierInboundWebhookDraftSource[] | null | undefined,
) {
    const inbound = webhooks ?? []
    if (!inbound.length) return ""
    if (inbound.some((webhook) => webhook.webhook_id === requestedWebhookId)) {
        return requestedWebhookId
    }
    return inbound[0]?.webhook_id ?? ""
}

// A Zapier payload that carries a Meta page id creates its form under that page id, so every
// active form can receive Zapier leads; filtering on page_id "zapier" would hide those routes.
function getActiveZapierRouteForms<T extends { is_active?: boolean }>(forms: T[]): T[] {
    return forms.filter((form) => form.is_active)
}

function getSingleZapierFormId(
    forms: Array<{
        is_active?: boolean
        form_external_id?: string | null
    }>,
) {
    const activeForms = getActiveZapierRouteForms(forms)
    if (activeForms.length !== 1) return ""
    return activeForms[0]?.form_external_id?.trim() ?? ""
}

function createZapierOutboundDraftKey(
    settings:
        | {
            outbound_webhook_url?: string | null
            outbound_enabled?: boolean | null
            send_hashed_pii?: boolean | null
            event_mapping?: ZapierEventMappingItem[] | null
            donor_outbound_enabled?: boolean | null
            donor_event_mapping?: ZapierDonorEventMappingItem[] | null
        }
        | null
        | undefined,
    pipelines: Pipeline[] | null | undefined,
    donorPipelinesByType: Record<ZapierDonorType, Pipeline[] | null | undefined>,
) {
    const defaultPipeline = pipelines?.find((pipeline) => pipeline.is_default) ?? pipelines?.[0]
    const stageKey = (defaultPipeline?.stages ?? [])
        .map((stage) => `${stage.stage_key ?? ""}:${stage.slug ?? ""}:${stage.is_active === false ? "0" : "1"}`)
        .join("|")

    return [
        settings?.outbound_webhook_url ?? "",
        settings?.outbound_enabled ? "1" : "0",
        settings?.send_hashed_pii ? "1" : "0",
        JSON.stringify(settings?.event_mapping ?? []),
        settings?.donor_outbound_enabled ? "1" : "0",
        JSON.stringify(settings?.donor_event_mapping ?? null),
        stageKey,
        ...DONOR_TYPES.map((donorType) =>
            (donorPipelinesByType[donorType] ?? [])
                .flatMap((pipeline) => pipeline.stages.map((stage) => (
                    `${donorType}:${pipeline.id}:${stage.id}:${stage.is_active === false ? "0" : "1"}`
                )))
                .join("|"),
        ),
    ].join("\u0000")
}

function createZapierOutboundDraftState(
    outboundKey: string,
    settings:
        | {
            outbound_webhook_url?: string | null
            outbound_enabled?: boolean | null
            send_hashed_pii?: boolean | null
            event_mapping?: ZapierEventMappingItem[] | null
            donor_outbound_enabled?: boolean | null
            donor_event_mapping?: ZapierDonorEventMappingItem[] | null
        }
        | null
        | undefined,
    pipelines: Pipeline[] | null | undefined,
    donorPipelinesByType: Record<ZapierDonorType, Pipeline[] | null | undefined>,
    currentStage: string = "",
): ZapierOutboundDraftState {
    const eventMapping = mergeEventMappingWithPipelineStages(
        settings?.event_mapping || [],
        pipelines,
    )
    const selectedOutboundStage =
        currentStage && eventMapping.some((item) => item.stage_key === currentStage)
            ? currentStage
            : eventMapping[0]?.stage_key || ""

    return {
        outboundKey,
        form: {
            outboundUrl: settings?.outbound_webhook_url || "",
            outboundEnabled: Boolean(settings?.outbound_enabled),
            donorOutboundEnabled: Boolean(settings?.donor_outbound_enabled),
            sendHashedPii: Boolean(settings?.send_hashed_pii),
            eventMapping,
            donorEventMapping: buildDonorEventMapping(
                settings?.donor_event_mapping,
                donorPipelinesByType,
            ),
            removeUnavailableDonorMappings: false,
            selectedOutboundStage,
        },
    }
}

function getActiveZapierOutboundDraft(
    draft: ZapierOutboundDraftState,
    outboundKey: string,
    settings: Parameters<typeof createZapierOutboundDraftState>[1],
    pipelines: Pipeline[] | null | undefined,
    donorPipelinesByType: Record<ZapierDonorType, Pipeline[] | null | undefined>,
): ZapierOutboundDraftState {
    if (draft.outboundKey === outboundKey) return draft
    return createZapierOutboundDraftState(
        outboundKey,
        settings,
        pipelines,
        donorPipelinesByType,
        draft.form.selectedOutboundStage,
    )
}

export function getZapierDonorSettingsState({
    settings,
    eggPipelines,
    spermPipelines,
    eggLoading,
    spermLoading,
    eggError,
    spermError,
}: {
    settings:
        | {
            donor_outbound_enabled?: boolean | null
            donor_event_mapping?: ZapierDonorEventMappingItem[] | null
        }
        | null
        | undefined
    eggPipelines: Pipeline[] | null | undefined
    spermPipelines: Pipeline[] | null | undefined
    eggLoading: boolean
    spermLoading: boolean
    eggError: boolean
    spermError: boolean
}) {
    const pipelinesByType: Record<ZapierDonorType, Pipeline[] | null | undefined> = {
        egg: eggPipelines,
        sperm: spermPipelines,
    }
    const pipelinesLoading = eggLoading || spermLoading
    const pipelinesError = eggError || spermError
    const settingsAvailable = Boolean(
        settings
        && Object.prototype.hasOwnProperty.call(settings, "donor_outbound_enabled")
        && Object.prototype.hasOwnProperty.call(settings, "donor_event_mapping"),
    )
    const mappingsUnresolved = settingsAvailable
        && !pipelinesLoading
        && !pipelinesError
        && hasUnresolvedDonorMappings(settings?.donor_event_mapping, pipelinesByType)

    return {
        canSave: settingsAvailable && !pipelinesLoading && !pipelinesError && !mappingsUnresolved,
        mappingsUnresolved,
        pipelinesByType,
        pipelinesError,
        pipelinesLoading,
        settingsAvailable,
    }
}

function ZapierMonitoringSection({
    variant = "page",
    donorPipelinesByType,
}: {
    variant?: "page" | "dialog"
    donorPipelinesByType: Record<ZapierDonorType, Pipeline[] | null | undefined>
}) {
    const {
        data: summary,
        isLoading: summaryLoading,
        isError: summaryError,
    } = useZapierOutboundEventsSummary()
    const {
        data: events,
        isLoading: eventsLoading,
        isError: eventsError,
    } = useZapierOutboundEvents({ limit: 20 })
    const retryOutboundEvent = useRetryZapierOutboundEvent()
    const replayOutboundEvent = useReplayZapierOutboundEvent()
    const isDialog = variant === "dialog"

    const handleRetry = async (eventId: string) => {
        try {
            await retryOutboundEvent.mutateAsync({ eventId })
            toast.success("Retry queued")
        } catch {
            toast.error("Failed to retry outbound event")
        }
    }

    const handleReplay = async (eventId: string) => {
        try {
            const replayed = await replayOutboundEvent.mutateAsync({ eventId })
            if (replayed.status === "skipped") {
                toast.warning(`Replay skipped: ${formatZapierReason(replayed.reason)}`)
            } else {
                toast.success("Replay queued")
            }
        } catch (error) {
            toast.error(error instanceof Error && error.message ? error.message : "Failed to replay outbound event")
        }
    }

    if (summaryLoading || eventsLoading) {
        return (
            <div className="flex items-center justify-center py-8">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground motion-reduce:animate-none" aria-hidden="true" />
            </div>
        )
    }

    if (summaryError || eventsError) {
        return (
            <Alert variant="destructive">
                <AlertTriangleIcon className="size-4" aria-hidden="true" />
                <AlertTitle>Activity unavailable</AlertTitle>
                <AlertDescription>Zapier delivery activity could not be loaded.</AlertDescription>
            </Alert>
        )
    }

    return (
        <div className="space-y-4">
            <Alert>
                <AlertTitle>Recent delivery health</AlertTitle>
                <AlertDescription>
                    Summary rates are calculated per organization over the last {summary?.window_hours ?? 24} hours and exclude manual test events.
                </AlertDescription>
            </Alert>

            {summary?.warning_messages?.length ? (
                <Alert variant="destructive">
                    <AlertTriangleIcon className="size-4" aria-hidden="true" />
                    <AlertTitle>Attention needed</AlertTitle>
                    <AlertDescription className="space-y-1">
                        {summary.warning_messages.map((message) => (
                            <p key={message}>{message}</p>
                        ))}
                    </AlertDescription>
                </Alert>
            ) : null}

            <div className="grid gap-3 md:grid-cols-4">
                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription>Recent events</CardDescription>
                        <CardTitle className="text-2xl">{summary?.total_count ?? 0}</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-xs text-muted-foreground">
                            {summary?.queued_count ?? 0} still queued
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription>Delivered</CardDescription>
                        <CardTitle className="text-2xl">{summary?.delivered_count ?? 0}</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-xs text-muted-foreground">
                            Failure rate: {formatZapierRate(summary?.failure_rate ?? 0)}
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription>Failed</CardDescription>
                        <CardTitle className="text-2xl">{summary?.failed_count ?? 0}</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-xs text-muted-foreground">
                            Retries available for terminal delivery failures
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription>Skipped</CardDescription>
                        <CardTitle className="text-2xl">{summary?.skipped_count ?? 0}</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-xs text-muted-foreground">
                            Actionable skip rate: {formatZapierRate(summary?.skipped_rate ?? 0)}
                        </p>
                    </CardContent>
                </Card>
            </div>

            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base">Recent outbound events</CardTitle>
                    <CardDescription className="text-xs">
                        Review delivery outcomes, skip reasons, and replay failed jobs.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {!events?.items?.length ? (
                        <p className="text-sm text-muted-foreground">
                            No outbound Zapier events recorded yet.
                        </p>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Time</TableHead>
                                    <TableHead>Source</TableHead>
                                    <TableHead>Event</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Details</TableHead>
                                    <TableHead className="text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {events.items.map((event) => {
                                    const donorStageLabel = getDonorEventStageLabel(
                                        event,
                                        donorPipelinesByType,
                                    )
                                    return (
                                    <TableRow key={event.id}>
                                        <TableCell className="text-xs text-muted-foreground">
                                            {formatRelativeTime(event.created_at)}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="secondary">{formatZapierSource(event.source)}</Badge>
                                        </TableCell>
                                        <TableCell>
                                            <div className="font-medium">{event.event_name || "Unmapped event"}</div>
                                            <div className="text-xs text-muted-foreground">
                                                {donorStageLabel || event.stage_label || event.stage_key || "No stage"}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={ZAPIER_OUTBOUND_STATUS_BADGE[event.status].variant}>
                                                {ZAPIER_OUTBOUND_STATUS_BADGE[event.status].label}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="max-w-xs">
                                            <div className="space-y-1 text-xs text-muted-foreground">
                                                <p>{formatZapierAttribution(event)}</p>
                                                <p>
                                                    {event.last_error
                                                        || (event.reason ? formatZapierReason(event.reason) : "No issues recorded")}
                                                </p>
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-right">
                                            {event.status === "skipped" ? (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => handleReplay(event.id)}
                                                    disabled={!event.can_replay || replayOutboundEvent.isPending}
                                                    className={isDialog ? "" : "min-w-24"}
                                                >
                                                    {replayOutboundEvent.isPending ? "Replaying…" : "Replay"}
                                                </Button>
                                            ) : (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => handleRetry(event.id)}
                                                    disabled={!event.can_retry || retryOutboundEvent.isPending}
                                                    className={isDialog ? "" : "min-w-24"}
                                                >
                                                    {retryOutboundEvent.isPending ? "Retrying…" : "Retry"}
                                                </Button>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                    )
                                })}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}

type ZapierInboundWebhookView = {
    webhook_id: string
    webhook_url: string
    is_active: boolean
    created_at: string
    label?: string | null
}

type ZapierMetaFormOption = {
    id: string
    form_name?: string | null
    form_external_id: string
    lead_kind?: "surrogate" | "egg_donor" | "sperm_donor"
    mapping_status?: string
    is_active?: boolean
}

type UpdateZapierWebhookDraft = (
    updater: (draft: ZapierWebhookDraftState) => ZapierWebhookDraftState,
) => void

type UpdateZapierOutboundForm = <K extends keyof ZapierOutboundFormState>(
    field: K,
    value: ZapierOutboundFormState[K],
) => void

function ZapierInboundWebhooksCard({
    inboundWebhooks,
    webhookSecrets,
    labelDrafts,
    createPending,
    rotatePending,
    rotatingWebhookId,
    deletingWebhookId,
    onCreateInbound,
    onUpdateWebhookDraft,
    onLabelBlur,
    onToggleInbound,
    onRotateInbound,
    onDeleteInbound,
    inlineSaveStates,
    children,
}: {
    inboundWebhooks: ZapierInboundWebhookView[]
    webhookSecrets: Record<string, string>
    labelDrafts: Record<string, string>
    createPending: boolean
    rotatePending: boolean
    rotatingWebhookId: string | null
    deletingWebhookId: string | null
    onCreateInbound: () => void
    onUpdateWebhookDraft: UpdateZapierWebhookDraft
    onLabelBlur: (webhookId: string) => Promise<void>
    onToggleInbound: (webhookId: string, enabled: boolean) => Promise<void>
    onRotateInbound: (webhookId: string) => Promise<void>
    onDeleteInbound: (webhookId: string) => Promise<void>
    inlineSaveStates: Record<string, SaveStatusState>
    children?: ReactNode
}) {
    return (
        <section className="space-y-4" aria-labelledby="zapier-webhooks-heading">
            <div
                className="flex flex-wrap items-center justify-between gap-3"
                data-testid="zapier-inbound-header"
            >
                <h3 id="zapier-webhooks-heading" className="text-base font-medium">Webhooks</h3>
                <Button
                    variant="outline"
                    onClick={onCreateInbound}
                    disabled={createPending}
                >
                    {createPending ? (
                        <>
                            <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                            Creating…
                        </>
                    ) : (
                        <>
                            <PlusIcon aria-hidden="true" />
                            Add webhook
                        </>
                    )}
                </Button>
            </div>

            {!inboundWebhooks.length ? (
                <p className="text-sm text-muted-foreground">No inbound webhooks configured yet.</p>
            ) : (
                <div className="space-y-4">
                    {inboundWebhooks.map((webhook) => (
                        <ZapierInboundWebhookItem
                            key={webhook.webhook_id}
                            webhook={webhook}
                            labelValue={labelDrafts[webhook.webhook_id] ?? ""}
                            secret={webhookSecrets[webhook.webhook_id]}
                            canDelete={inboundWebhooks.length > 1}
                            rotatePending={rotatePending}
                            rotatingWebhookId={rotatingWebhookId}
                            deletingWebhookId={deletingWebhookId}
                            labelSaveState={inlineSaveStates[`${webhook.webhook_id}:label`] ?? "idle"}
                            activeSaveState={inlineSaveStates[`${webhook.webhook_id}:active`] ?? "idle"}
                            onUpdateWebhookDraft={onUpdateWebhookDraft}
                            onLabelBlur={onLabelBlur}
                            onToggleInbound={onToggleInbound}
                            onRotateInbound={onRotateInbound}
                            onDeleteInbound={onDeleteInbound}
                        />
                    ))}
                </div>
            )}

            {children ? <div className="border-t pt-4">{children}</div> : null}
        </section>
    )
}

function ZapierInboundWebhookItem({
    webhook,
    labelValue,
    secret,
    canDelete,
    rotatePending,
    rotatingWebhookId,
    deletingWebhookId,
    labelSaveState,
    activeSaveState,
    onUpdateWebhookDraft,
    onLabelBlur,
    onToggleInbound,
    onRotateInbound,
    onDeleteInbound,
}: {
    webhook: ZapierInboundWebhookView
    labelValue: string
    secret: string | undefined
    canDelete: boolean
    rotatePending: boolean
    rotatingWebhookId: string | null
    deletingWebhookId: string | null
    labelSaveState: SaveStatusState
    activeSaveState: SaveStatusState
    onUpdateWebhookDraft: UpdateZapierWebhookDraft
    onLabelBlur: (webhookId: string) => Promise<void>
    onToggleInbound: (webhookId: string, enabled: boolean) => Promise<void>
    onRotateInbound: (webhookId: string) => Promise<void>
    onDeleteInbound: (webhookId: string) => Promise<void>
}) {
    const isRotating = rotatePending && rotatingWebhookId === webhook.webhook_id
    const isDeleting = deletingWebhookId === webhook.webhook_id
    const fieldId = `zapier-webhook-${webhook.webhook_id}`

    return (
        <div className="min-w-0 space-y-4 rounded-md border p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex items-center gap-2">
                        <Label htmlFor={`${fieldId}-label`}>Label</Label>
                        <SaveStatus state={labelSaveState} />
                    </div>
                    <Input
                        id={`${fieldId}-label`}
                        value={labelValue}
                        onChange={(event) =>
                            onUpdateWebhookDraft((current) => ({
                                ...current,
                                labelDrafts: {
                                    ...current.labelDrafts,
                                    [webhook.webhook_id]: event.target.value,
                                },
                            }))
                        }
                        onBlur={() => {
                            void onLabelBlur(webhook.webhook_id)
                        }}
                        placeholder="Optional label"
                        name={`zapier-label-${webhook.webhook_id}`}
                    />
                    <p className="text-xs text-muted-foreground">
                        Created {formatRelativeTime(webhook.created_at)}
                    </p>
                </div>
                <div className="flex items-center gap-2 sm:pt-7">
                    <SaveStatus state={activeSaveState} />
                    <Badge variant={webhook.is_active ? "default" : "secondary"}>
                        {webhook.is_active ? "Active" : "Inactive"}
                    </Badge>
                    <Switch
                        checked={webhook.is_active}
                        onCheckedChange={(checked) => {
                            void onToggleInbound(webhook.webhook_id, checked)
                        }}
                        aria-label={`Toggle ${webhook.webhook_id}`}
                    />
                </div>
            </div>

            <div className="space-y-2">
                <Label htmlFor={`${fieldId}-url`}>Webhook URL</Label>
                <CopyField
                    id={`${fieldId}-url`}
                    value={webhook.webhook_url}
                    copyLabel="Copy webhook URL"
                />
            </div>

            <div className="space-y-2">
                <Label>Authentication Header</Label>
                <div className="rounded-md border border-dashed bg-muted/50 p-3 text-xs">
                    <div className="flex items-center justify-between">
                        <span>X-Webhook-Token: &lt;your secret&gt;</span>
                    </div>
                </div>
                <p className="text-xs text-muted-foreground">
                    Rotate the secret if you need to reconfigure Zapier.
                </p>
            </div>

            <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                    <ConfirmDialog
                        trigger={(
                            <Button variant="outline" disabled={isRotating}>
                                {isRotating ? (
                                    <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                ) : (
                                    <RotateCwIcon aria-hidden="true" />
                                )}
                                {isRotating ? "Rotating…" : "Rotate Webhook Secret"}
                            </Button>
                        )}
                        title="Rotate webhook secret?"
                        description="Zaps that send the current secret fail until you update them with the new one."
                        confirmLabel="Rotate secret"
                        errorFallback="Couldn't rotate the webhook secret. Try again."
                        onConfirm={() => onRotateInbound(webhook.webhook_id)}
                    />

                    <ConfirmDialog
                        trigger={(
                            <Button variant="destructive-ghost" disabled={!canDelete || isDeleting}>
                                <TrashIcon aria-hidden="true" />
                                Delete Webhook
                            </Button>
                        )}
                        title="Delete webhook?"
                        description="The incoming URL stops working at once. Zaps that use it fail until updated."
                        confirmLabel="Delete"
                        errorFallback="Couldn't delete the webhook. Try again."
                        onConfirm={() => onDeleteInbound(webhook.webhook_id)}
                    />
                </div>

                {!canDelete ? (
                    <p className="text-xs text-muted-foreground">
                        Keep at least one inbound webhook active.
                    </p>
                ) : null}

                {secret ? (
                    <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-100">
                        <p className="mb-2 font-medium">
                            New Webhook Secret (copy now, shown once):
                        </p>
                        <div className="flex items-center gap-2">
                            <code className="min-w-0 flex-1 break-all">
                                {secret}
                            </code>
                            <CopyButton
                                value={secret}
                                aria-label="Copy webhook secret"
                                variant="outline"
                                size="icon-sm"
                            />
                        </div>
                    </div>
                ) : null}
            </div>
        </div>
    )
}

function ZapierFieldPasteCard({
    isDialog,
    inboundWebhooks,
    activeWebhookId,
    canManageMetaLeads,
    fieldPaste,
    fieldPasteError,
    fieldPasteFormId,
    fieldPasteResult,
    parsePending,
    onWebhookChange,
    onFieldPasteChange,
    onFieldPasteFormIdChange,
    onParse,
    onClear,
}: {
    isDialog: boolean
    inboundWebhooks: ZapierInboundWebhookView[]
    activeWebhookId: string
    canManageMetaLeads: boolean
    fieldPaste: string
    fieldPasteError: string | null
    fieldPasteFormId: string
    fieldPasteResult: ZapierFieldPasteResponse | null
    parsePending: boolean
    onWebhookChange: (webhookId: string) => void
    onFieldPasteChange: (value: string) => void
    onFieldPasteFormIdChange: (value: string) => void
    onParse: () => void
    onClear: () => void
}) {
    return (
        <div className="space-y-4">
            {inboundWebhooks.length ? (
                <div className="space-y-2">
                    <Label>Webhook</Label>
                    <Select value={activeWebhookId} onValueChange={(value) => onWebhookChange(value ?? "")}>
                        <SelectTrigger className={isDialog ? "w-full" : "w-full md:w-72"} aria-label="Select webhook">
                            <SelectValue placeholder="Select webhook">
                                {(value: string | null) => getWebhookSelectLabel(inboundWebhooks, value)}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {inboundWebhooks.map((webhook) => (
                                <SelectItem key={webhook.webhook_id} value={webhook.webhook_id}>
                                    {webhook.label || `Webhook ${webhook.webhook_id.slice(0, 8)}`}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                        Pick the webhook this form belongs to if you have more than one.
                    </p>
                </div>
            ) : null}

            <div className="space-y-2">
                <Label htmlFor="zapier-field-paste-form-id">Meta form ID (optional)</Label>
                <Input
                    id="zapier-field-paste-form-id"
                    value={fieldPasteFormId}
                    onChange={(event) => onFieldPasteFormIdChange(event.target.value)}
                    className={isDialog ? "w-full" : "w-full md:w-72"}
                    name="zapier-field-paste-form-id"
                    inputMode="numeric"
                    autoComplete="off"
                />
            </div>

            <ValidatedField
                id="zapier-field-paste"
                label="Paste Zapier Field List"
                error={fieldPasteError}
                description="Paste the token lines or the sample field/value list from Zapier."
            >
                {(control) => (
                    <Textarea
                        {...control}
                        value={fieldPaste}
                        onChange={(event) => onFieldPasteChange(event.target.value)}
                        placeholder={'Paste lines like {{=gives["312067957"]["full_name"]}} or "Full Name: Jane Doe"'}
                        rows={6}
                        name="zapier-field-paste"
                    />
                )}
            </ValidatedField>
            <div className="flex flex-wrap items-center gap-2">
                <Button
                    variant="outline"
                    onClick={onParse}
                    disabled={parsePending}
                >
                    {parsePending ? (
                        <>
                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                            Extracting…
                        </>
                    ) : (
                        <>
                            <SparklesIcon className="mr-2 size-4" aria-hidden="true" />
                            Extract Fields
                        </>
                    )}
                </Button>
                <Button variant="ghost" onClick={onClear}>
                    Clear
                </Button>
            </div>

            {fieldPasteResult ? (
                <Alert>
                    <AlertTitle>Fields detected</AlertTitle>
                    <AlertDescription>
                        Found {fieldPasteResult.field_count} fields for{" "}
                        {fieldPasteResult.form_name || fieldPasteResult.form_id}.
                        {canManageMetaLeads ? (
                            <>
                                {" "}
                                <Link href={fieldPasteResult.mapping_url} className="text-primary underline">
                                    Open mapping
                                </Link>
                            </>
                        ) : null}
                    </AlertDescription>
                </Alert>
            ) : null}
        </div>
    )
}

function ZapierTestLeadControls({
    activeTestFormId,
    zapierForms,
    sendPending,
    onTestFormIdChange,
    onSendTestLead,
}: {
    activeTestFormId: string
    zapierForms: ZapierMetaFormOption[]
    sendPending: boolean
    onTestFormIdChange: (value: string) => void
    onSendTestLead: () => void
}) {
    return (
        <div className="space-y-3">
            <div className="space-y-2">
                <Label>Form</Label>
                <Select
                    value={activeTestFormId}
                    onValueChange={(value) => onTestFormIdChange(value ?? "")}
                    disabled={!zapierForms.length}
                >
                    <SelectTrigger aria-label="Incoming test form" className="w-full">
                        <SelectValue placeholder="Select a Zapier form">
                            {(value: string | null) => getZapierFormSelectLabel(zapierForms, value)}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {zapierForms.map((form) => (
                            <SelectItem key={form.id} value={form.form_external_id}>
                                {form.form_name || "Unnamed Zapier form"} · {getLeadKindLabel(form.lead_kind)}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                {!zapierForms.length ? (
                    <p className="text-sm text-muted-foreground">No active Zapier forms available.</p>
                ) : null}
                <p className="text-xs text-muted-foreground">
                    Mapping for Zapier leads is managed in Meta Lead Forms.{" "}
                    <Link href="/settings/integrations/meta/forms" className="text-primary underline">
                        Manage form mappings
                    </Link>
                </p>
            </div>
            <Button
                variant="outline"
                onClick={onSendTestLead}
                disabled={sendPending || !activeTestFormId}
            >
                {sendPending ? (
                    <>
                        <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                        Sending…
                    </>
                ) : (
                    <>
                        <ActivityIcon className="mr-2 size-4" aria-hidden="true" />
                        Send Test Lead
                    </>
                )}
            </Button>
        </div>
    )
}

function ZapierFormRouting({
    canManageMetaLeads,
    forms,
    metaFormsLoading,
    mappingHref,
    fieldPasteContent,
}: {
    canManageMetaLeads: boolean
    forms: ZapierMetaFormOption[]
    metaFormsLoading: boolean
    mappingHref: string
    fieldPasteContent: ReactNode
}) {
    // Route links open the Meta form mapping page, which requires manage_meta_leads.
    const routeHeaders = canManageMetaLeads
        ? ZAPIER_FORM_ROUTE_HEADERS
        : ZAPIER_FORM_ROUTE_HEADERS.filter((header) => header.label !== "Action")
    return (
        <div className="space-y-4">
            {metaFormsLoading ? (
                <div className="flex items-center justify-center py-8">
                    <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                </div>
            ) : !forms.length ? (
                <Alert>
                    <AlertTitle>No Zapier form routes</AlertTitle>
                    <AlertDescription>
                        Extract fields from a Zapier sample to create the first route.
                    </AlertDescription>
                </Alert>
            ) : (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Form routes</CardTitle>
                    </CardHeader>
                    <CardContent className="overflow-x-auto">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    {routeHeaders.map((header) => (
                                        <TableHead key={header.label} className={header.className}>
                                            {header.label}
                                        </TableHead>
                                    ))}
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {forms.map((form) => (
                                    <TableRow key={form.id}>
                                        <TableCell>
                                            <div className="font-medium">
                                                {form.form_name || "Unnamed form"}
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                {form.form_external_id || "Form ID unavailable"}
                                            </div>
                                        </TableCell>
                                        <TableCell>{getLeadKindLabel(form.lead_kind)}</TableCell>
                                        <TableCell>
                                            <Badge variant={form.mapping_status === "mapped" ? "default" : "secondary"}>
                                                {form.mapping_status === "mapped" ? "Mapped" : "Needs mapping"}
                                            </Badge>
                                        </TableCell>
                                        {canManageMetaLeads ? (
                                            <TableCell className="text-right">
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    render={<Link href={`/settings/integrations/meta/forms/${form.id}`} />}
                                                >
                                                    Edit route
                                                </Button>
                                            </TableCell>
                                        ) : null}
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            )}

            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between gap-3">
                        <CardTitle className="text-base">Add or refresh a route</CardTitle>
                        {forms.length && canManageMetaLeads ? (
                            <Button variant="outline" size="sm" render={<Link href={mappingHref} />}>
                                Open form mappings
                            </Button>
                        ) : null}
                    </div>
                </CardHeader>
                <CardContent>{fieldPasteContent}</CardContent>
            </Card>
        </div>
    )
}

function ZapierOutboundSettingsCard({
    outboundForm,
    outboundSecret,
    outboundSecretConfigured,
    donorSettingsAvailable,
    donorPipelinesByType,
    donorPipelinesLoading,
    donorPipelinesError,
    donorMappingsUnresolved,
    recommendedBucketByStage,
    getStageKeyLabel,
    onOutboundFormChange,
    onOutboundSecretChange,
    onApplyRecommendedMapping,
}: {
    outboundForm: ZapierOutboundFormState
    outboundSecret: string
    outboundSecretConfigured: boolean
    donorSettingsAvailable: boolean
    donorPipelinesByType: Record<ZapierDonorType, Pipeline[] | null | undefined>
    donorPipelinesLoading: boolean
    donorPipelinesError: boolean
    donorMappingsUnresolved: boolean
    recommendedBucketByStage: Record<string, ZapierStageBucket>
    getStageKeyLabel: (stageKey: string) => string
    onOutboundFormChange: UpdateZapierOutboundForm
    onOutboundSecretChange: (value: string) => void
    onApplyRecommendedMapping: () => void
}) {
    const donorControlsUnavailable =
        !donorSettingsAvailable
        || donorPipelinesLoading
        || donorPipelinesError
    const hasDonorPipelines = DONOR_TYPES.some((donorType) => donorPipelinesByType[donorType]?.length)
    const donorMappingNeedsRepair = donorMappingsUnresolved && !outboundForm.removeUnavailableDonorMappings

    return (
        <div className="space-y-6">
            <div className="grid gap-3 sm:grid-cols-2">
                <div className="flex items-center justify-between rounded-md border p-3">
                    <Label>Surrogate stage events</Label>
                    <Switch
                        checked={outboundForm.outboundEnabled}
                        onCheckedChange={(checked) => onOutboundFormChange("outboundEnabled", checked)}
                        aria-label="Enable surrogate stage events"
                    />
                </div>
                <div className="flex items-center justify-between rounded-md border p-3">
                    <Label>Donor stage events</Label>
                    <Switch
                        checked={outboundForm.donorOutboundEnabled}
                        onCheckedChange={(checked) => onOutboundFormChange("donorOutboundEnabled", checked)}
                        disabled={donorControlsUnavailable || ((!hasDonorPipelines || donorMappingNeedsRepair) && !outboundForm.donorOutboundEnabled)}
                        aria-label="Enable donor stage events"
                    />
                </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                    <Label>Outbound Webhook URL</Label>
                    <Input
                        value={outboundForm.outboundUrl}
                        onChange={(event) => onOutboundFormChange("outboundUrl", event.target.value)}
                        placeholder="https://hooks.zapier.com/hooks/catch/…"
                        name="zapier-outbound-url"
                        autoComplete="off"
                    />
                </div>

                <div className="space-y-2">
                    <Label>Webhook Secret (optional)</Label>
                    <Input
                        type="password"
                        value={outboundSecret}
                        onChange={(event) => onOutboundSecretChange(event.target.value)}
                        placeholder={outboundSecretConfigured ? "•••••••• (set)" : "Enter secret"}
                        name="zapier-outbound-secret"
                        autoComplete="off"
                    />
                    <p className="text-xs text-muted-foreground">
                        Sent as the X-Webhook-Token header.
                    </p>
                </div>
            </div>

            <div className="flex items-center justify-between rounded-md border p-3">
                <div>
                    <p className="text-sm font-medium">Include hashed PII</p>
                    <p className="text-xs text-muted-foreground">
                        Optional hashed email/phone for better match rates.
                    </p>
                </div>
                <Switch
                    checked={outboundForm.sendHashedPii}
                    onCheckedChange={(checked) => onOutboundFormChange("sendHashedPii", checked)}
                    aria-label="Include hashed PII"
                />
            </div>

            <Tabs defaultValue="surrogates" className="gap-3 border-t pt-5">
                <div className="overflow-x-auto pb-1">
                    <TabsList
                        variant="line"
                        aria-label="Stage mapping record type"
                        className="min-w-max"
                    >
                        <TabsTrigger value="surrogates">Surrogates</TabsTrigger>
                        <TabsTrigger value="egg-donors">Egg donors</TabsTrigger>
                        <TabsTrigger value="sperm-donors">Sperm donors</TabsTrigger>
                    </TabsList>
                </div>
                <TabsContent value="surrogates" keepMounted>
                    <ZapierStageMappingRows
                        eventMapping={outboundForm.eventMapping}
                        recommendedBucketByStage={recommendedBucketByStage}
                        getStageKeyLabel={getStageKeyLabel}
                        onOutboundFormChange={onOutboundFormChange}
                        onApplyRecommendedMapping={onApplyRecommendedMapping}
                    />
                </TabsContent>
                {DONOR_TYPES.map((donorType) => (
                    <TabsContent
                        key={donorType}
                        value={`${donorType}-donors`}
                        keepMounted
                    >
                        <ZapierDonorStageMappingRows
                            donorType={donorType}
                            outboundForm={outboundForm}
                            settingsAvailable={donorSettingsAvailable}
                            pipelinesByType={donorPipelinesByType}
                            pipelinesLoading={donorPipelinesLoading}
                            pipelinesError={donorPipelinesError}
                            mappingsUnresolved={donorMappingsUnresolved && !outboundForm.removeUnavailableDonorMappings}
                            onOutboundFormChange={onOutboundFormChange}
                        />
                    </TabsContent>
                ))}
            </Tabs>
        </div>
    )
}

function ZapierStageMappingRows({
    eventMapping,
    recommendedBucketByStage,
    getStageKeyLabel,
    onOutboundFormChange,
    onApplyRecommendedMapping,
}: {
    eventMapping: ZapierEventMappingItem[]
    recommendedBucketByStage: Record<string, ZapierStageBucket>
    getStageKeyLabel: (stageKey: string) => string
    onOutboundFormChange: UpdateZapierOutboundForm
    onApplyRecommendedMapping: () => void
}) {
    return (
        <div className="space-y-2">
            <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
                <h4 className="text-sm font-medium">Stage → Event Mapping</h4>
                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full sm:w-auto"
                    onClick={onApplyRecommendedMapping}
                >
                    Apply Recommended Mapping
                </Button>
            </div>
            <p className="text-xs text-muted-foreground">
                Map each stage to the event sent to Zapier.
            </p>
            <StageEventMappingTable
                items={eventMapping}
                namePrefix="zapier"
                getStageKeyLabel={getStageKeyLabel}
                getSendLabel={(stageLabel) => `Send ${stageLabel} event`}
                getUntrackedEnabled={(item) =>
                    recommendedBucketByStage[item.stage_key] ? false : item.enabled
                }
                onChange={(next) => onOutboundFormChange("eventMapping", next)}
            />
        </div>
    )
}

type ZapierDonorStageMappingRowsProps = {
    donorType: ZapierDonorType
    outboundForm: ZapierOutboundFormState
    settingsAvailable: boolean
    pipelinesByType: Record<ZapierDonorType, Pipeline[] | null | undefined>
    pipelinesLoading: boolean
    pipelinesError: boolean
    mappingsUnresolved: boolean
    onOutboundFormChange: UpdateZapierOutboundForm
}

type ZapierDonorMappingAvailability =
    | "unavailable"
    | "loading"
    | "error"
    | "unresolved"
    | "empty"
    | "ready"

function getZapierDonorMappingAvailability({
    settingsAvailable,
    pipelinesLoading,
    pipelinesError,
    mappingsUnresolved,
    pipelineCount,
}: Pick<
    ZapierDonorStageMappingRowsProps,
    "settingsAvailable" | "pipelinesLoading" | "pipelinesError" | "mappingsUnresolved"
> & { pipelineCount: number }): ZapierDonorMappingAvailability {
    if (!settingsAvailable) return "unavailable"
    if (pipelinesLoading) return "loading"
    if (pipelinesError) return "error"
    if (mappingsUnresolved) return "unresolved"
    if (!pipelineCount) return "empty"
    return "ready"
}

function ZapierDonorMappingAvailabilityMessage({
    availability,
    donorType,
    onRemoveUnavailableMappings,
}: {
    availability: Exclude<ZapierDonorMappingAvailability, "ready">
    donorType: ZapierDonorType
    onRemoveUnavailableMappings?: () => void
}) {
    switch (availability) {
        case "unavailable":
            return (
                <Alert>
                    <AlertTitle>Donor reporting unavailable</AlertTitle>
                    <AlertDescription>
                        Donor reporting controls are unavailable. Existing settings will be preserved.
                    </AlertDescription>
                </Alert>
            )
        case "loading":
            return (
                <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
                    <Loader2Icon className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                    Loading donor pipelines…
                </div>
            )
        case "error":
            return (
                <Alert variant="destructive">
                    <AlertTriangleIcon className="size-4" aria-hidden="true" />
                    <AlertTitle>Donor pipelines unavailable</AlertTitle>
                    <AlertDescription>
                        Donor reporting settings are read-only until pipeline access is restored.
                    </AlertDescription>
                </Alert>
            )
        case "unresolved":
            return (
                <Alert variant="destructive">
                    <AlertTriangleIcon className="size-4" aria-hidden="true" />
                    <AlertTitle>Saved donor mapping needs review</AlertTitle>
                    <AlertDescription>
                        Remove unavailable stages before saving mappings, or turn off donor stage events. Live mappings will be preserved.
                    </AlertDescription>
                    <Button variant="outline" size="sm" onClick={onRemoveUnavailableMappings}>
                        Remove unavailable mappings
                    </Button>
                </Alert>
            )
        case "empty":
            return (
                <Alert>
                    <AlertTitle>No {getDonorTypeLabel(donorType).toLowerCase()} pipeline available</AlertTitle>
                    <AlertDescription>
                        Configure this donor pipeline before mapping stage events.
                    </AlertDescription>
                </Alert>
            )
    }
}

function updateZapierDonorMappingItem(
    mapping: ZapierDonorMappingDraftItem[],
    target: ZapierDonorMappingDraftItem,
    updater: (item: ZapierDonorMappingDraftItem) => ZapierDonorMappingDraftItem,
): ZapierDonorMappingDraftItem[] {
    return mapping.map((item) =>
        item.donor_type === target.donor_type
        && item.pipeline_id === target.pipeline_id
        && item.stage_id === target.stage_id
            ? updater(item)
            : item,
    )
}

function ZapierDonorPipelineMapping({
    donorType,
    pipeline,
    mapping,
    onUpdateItem,
}: {
    donorType: ZapierDonorType
    pipeline: Pipeline
    mapping: ZapierDonorMappingDraftItem[]
    onUpdateItem: (
        target: ZapierDonorMappingDraftItem,
        updater: (item: ZapierDonorMappingDraftItem) => ZapierDonorMappingDraftItem,
    ) => void
}) {
    return (
        <div className="overflow-hidden rounded-md border">
            <div className="border-b bg-muted/40 px-3 py-2 text-sm font-medium">
                {pipeline.name}
            </div>
            <div className="divide-y">
                {pipeline.stages.filter((stage) => stage.is_active !== false).map((stage) => {
                    const item = mapping.find((candidate) =>
                        candidate.donor_type === donorType
                        && candidate.pipeline_id === pipeline.id
                        && candidate.stage_id === stage.id,
                    )
                    return item ? (
                        <div
                            key={stage.id}
                            className="grid gap-3 p-3 sm:grid-cols-[minmax(0,1fr)_12rem_auto] sm:items-center"
                        >
                            <span className="text-sm font-medium">{stage.label}</span>
                            <Select
                                value={item.event_name || UNTRACKED_BUCKET_VALUE}
                                onValueChange={(value) => {
                                    if (value === UNTRACKED_BUCKET_VALUE) {
                                        onUpdateItem(item, (current) => ({
                                            ...current,
                                            event_name: "",
                                            enabled: false,
                                        }))
                                        return
                                    }
                                    const eventName = ZAPIER_EVENT_OPTIONS.find(
                                        (option) => option.value === value,
                                    )?.value
                                    if (!eventName) return
                                    onUpdateItem(item, (current) => ({
                                        ...current,
                                        event_name: eventName,
                                        enabled: true,
                                    }))
                                }}
                            >
                                <SelectTrigger aria-label={`Zapier event for ${getDonorTypeLabel(donorType)} ${stage.label}`}>
                                    <SelectValue>
                                        {(value: string | null) => getDonorEventLabel(value)}
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value={UNTRACKED_BUCKET_VALUE}>
                                        {getDonorEventLabel(UNTRACKED_BUCKET_VALUE)}
                                    </SelectItem>
                                    {ZAPIER_EVENT_OPTIONS.map((option) => (
                                        <SelectItem key={option.value} value={option.value}>
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <div className="flex items-center gap-2 sm:justify-end">
                                <Switch
                                    checked={item.enabled}
                                    disabled={item.event_name === ""}
                                    onCheckedChange={(checked) => onUpdateItem(
                                        item,
                                        (current) => ({ ...current, enabled: checked }),
                                    )}
                                    aria-label={`Enable ${getDonorTypeLabel(donorType)} ${pipeline.name} ${stage.label}`}
                                />
                                <span className="text-xs text-muted-foreground">Enabled</span>
                            </div>
                        </div>
                    ) : null
                })}
            </div>
        </div>
    )
}

function ZapierDonorStageMappingRows({
    donorType,
    outboundForm,
    settingsAvailable,
    pipelinesByType,
    pipelinesLoading,
    pipelinesError,
    mappingsUnresolved,
    onOutboundFormChange,
}: ZapierDonorStageMappingRowsProps) {
    const pipelines = pipelinesByType[donorType] ?? []
    const availability = getZapierDonorMappingAvailability({
        settingsAvailable,
        pipelinesLoading,
        pipelinesError,
        mappingsUnresolved,
        pipelineCount: pipelines.length,
    })

    if (availability !== "ready") {
        return (
            <ZapierDonorMappingAvailabilityMessage
                availability={availability}
                donorType={donorType}
                onRemoveUnavailableMappings={() => {
                    onOutboundFormChange("removeUnavailableDonorMappings", true)
                    if (!outboundForm.donorEventMapping.some((item) => item.enabled)) {
                        onOutboundFormChange("donorOutboundEnabled", false)
                    }
                }}
            />
        )
    }

    const updateItem = (
        target: ZapierDonorMappingDraftItem,
        updater: (item: ZapierDonorMappingDraftItem) => ZapierDonorMappingDraftItem,
    ) => {
        onOutboundFormChange(
            "donorEventMapping",
            updateZapierDonorMappingItem(outboundForm.donorEventMapping, target, updater),
        )
    }

    return (
        <div className="space-y-3">
            {pipelines.map((pipeline) => (
                <ZapierDonorPipelineMapping
                    key={pipeline.id}
                    donorType={donorType}
                    pipeline={pipeline}
                    mapping={outboundForm.donorEventMapping}
                    onUpdateItem={updateItem}
                />
            ))}
        </div>
    )
}

function ZapierOutboundTestControls({
    isDialog,
    outboundForm,
    outboundTestLeadId,
    testPending,
    getStageKeyLabel,
    onOutboundFormChange,
    onOutboundTestLeadIdChange,
    onSendOutboundTest,
}: {
    isDialog: boolean
    outboundForm: ZapierOutboundFormState
    outboundTestLeadId: string
    testPending: boolean
    getStageKeyLabel: (stageKey: string) => string
    onOutboundFormChange: UpdateZapierOutboundForm
    onOutboundTestLeadIdChange: (value: string) => void
    onSendOutboundTest: () => void
}) {
    return (
        <div className={`flex flex-col gap-2 ${isDialog ? "" : "md:flex-row md:items-center"}`}>
            <div className={isDialog ? "flex flex-col gap-2" : "flex flex-1 flex-col gap-2"}>
                <div className={isDialog ? "space-y-2" : "flex flex-col gap-2 md:max-w-sm"}>
                    <Label htmlFor="zapier-outbound-test-lead-id">Meta Lead ID (optional)</Label>
                    <Input
                        id="zapier-outbound-test-lead-id"
                        value={outboundTestLeadId}
                        onChange={(event) => onOutboundTestLeadIdChange(event.target.value)}
                        placeholder="Use a real Meta lead ID for end-to-end testing"
                        name="zapier-outbound-test-lead-id"
                        autoComplete="off"
                    />
                    <p className="text-xs text-muted-foreground">
                        Real Meta funnel updates generally only work for leads created within 90 days.
                    </p>
                </div>
                <div className={isDialog ? "flex flex-col gap-2" : "flex flex-1 items-center gap-2"}>
                    <Select
                        value={outboundForm.selectedOutboundStage}
                        onValueChange={(value) => onOutboundFormChange("selectedOutboundStage", value ?? "")}
                    >
                        <SelectTrigger className={isDialog ? "w-full" : "w-full md:w-56"} aria-label="Select stage">
                            <SelectValue placeholder="Select stage">
                                {(value: string | null) => (value ? getStageKeyLabel(value) : "")}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {outboundForm.eventMapping.map((item) => (
                                <SelectItem key={item.stage_key} value={item.stage_key}>
                                    {getStageKeyLabel(item.stage_key)}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Button
                        variant="outline"
                        onClick={onSendOutboundTest}
                        disabled={testPending || !outboundForm.outboundEnabled}
                        className={isDialog ? "w-full" : undefined}
                    >
                        {testPending ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                Sending…
                            </>
                        ) : (
                            <>
                                <ActivityIcon className="mr-2 size-4" aria-hidden="true" />
                                Send Test Event
                            </>
                        )}
                    </Button>
                </div>
            </div>
        </div>
    )
}

function ZapierDonorOutboundTestControls({
    isDialog,
    donorOutboundEnabled,
}: {
    isDialog: boolean
    donorOutboundEnabled: boolean
}) {
    const sendDonorTest = useZapierDonorOutboundTest()
    const [donorType, setDonorType] = useState<ZapierDonorType>("egg")
    const [eventName, setEventName] = useState<ZapierDonorEventName>("Lead")
    const [attributionSource, setAttributionSource] = useState<ZapierDonorAttributionSource>("meta")
    const [leadId, setLeadId] = useState("")

    const handleSend = async () => {
        const payload: ZapierDonorOutboundTestRequest = {
            donor_type: donorType,
            event_name: eventName,
            attribution_source: attributionSource,
        }
        const trimmedLeadId = leadId.trim()
        if (attributionSource === "meta" && trimmedLeadId) {
            payload.lead_id = trimmedLeadId
        }
        try {
            const result = await sendDonorTest.mutateAsync(payload)
            toast.success(
                result.lead_id
                    ? `Test event queued: ${result.event_name} for ${result.lead_id}`
                    : `Test event queued: ${result.event_name}`,
            )
        } catch (error) {
            const message = getActionErrorMessage(error, "Failed to send donor test event")
            if (message) toast.error(message)
        }
    }

    return (
        <div className="flex flex-col gap-2">
            <div className={isDialog ? "grid gap-2" : "grid gap-2 md:grid-cols-3"}>
                <Select
                    value={donorType}
                    onValueChange={(value) => {
                        const option = ZAPIER_DONOR_TYPE_OPTIONS.find((item) => item.value === value)
                        if (option) setDonorType(option.value)
                    }}
                >
                    <SelectTrigger className="w-full" aria-label="Donor test type">
                        <SelectValue>
                            {(value: string | null) => getSelectOptionLabel(ZAPIER_DONOR_TYPE_OPTIONS, value)}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {ZAPIER_DONOR_TYPE_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <Select
                    value={eventName}
                    onValueChange={(value) => {
                        const option = ZAPIER_EVENT_OPTIONS.find((item) => item.value === value)
                        if (option) setEventName(option.value)
                    }}
                >
                    <SelectTrigger className="w-full" aria-label="Donor test event">
                        <SelectValue>
                            {(value: string | null) => getSelectOptionLabel(ZAPIER_EVENT_OPTIONS, value)}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {ZAPIER_EVENT_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <Select
                    value={attributionSource}
                    onValueChange={(value) => {
                        const option = ZAPIER_DONOR_ATTRIBUTION_OPTIONS.find((item) => item.value === value)
                        if (option) setAttributionSource(option.value)
                    }}
                >
                    <SelectTrigger className="w-full" aria-label="Donor test attribution">
                        <SelectValue>
                            {(value: string | null) => getSelectOptionLabel(ZAPIER_DONOR_ATTRIBUTION_OPTIONS, value)}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {ZAPIER_DONOR_ATTRIBUTION_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>
            {attributionSource === "meta" ? (
                <div className={isDialog ? "space-y-2" : "flex flex-col gap-2 md:max-w-sm"}>
                    <Label htmlFor="zapier-donor-test-lead-id">Lead ID (optional)</Label>
                    <Input
                        id="zapier-donor-test-lead-id"
                        value={leadId}
                        onChange={(event) => setLeadId(event.target.value)}
                        name="zapier-donor-test-lead-id"
                        autoComplete="off"
                        maxLength={120}
                    />
                </div>
            ) : null}
            <Button
                variant="outline"
                onClick={() => {
                    void handleSend()
                }}
                disabled={sendDonorTest.isPending || !donorOutboundEnabled}
                className={isDialog ? "w-full" : "self-start"}
            >
                {sendDonorTest.isPending ? (
                    <>
                        <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                        Sending…
                    </>
                ) : (
                    <>
                        <ActivityIcon className="mr-2 size-4" aria-hidden="true" />
                        Send Donor Test Event
                    </>
                )}
            </Button>
        </div>
    )
}

function useZapierWebhookController(variant: "page" | "dialog") {
    const { user } = useAuth()
    const { data: effectivePermissions } = useEffectivePermissions(user?.user_id ?? null)
    const permissions = effectivePermissions?.permissions ?? []
    const canEditDonorSettings = user?.role === "developer"
        || (permissions.includes("view_donors") && permissions.includes("edit_donors"))
    const canManageMetaLeads = user?.role === "developer" || permissions.includes("manage_meta_leads")
    const { data: pipelines } = usePipelines("surrogate")
    const eggDonorPipelinesQuery = usePipelines("egg_donor")
    const spermDonorPipelinesQuery = usePipelines("sperm_donor")
    const recommendedBucketByStage = buildRecommendedBucketByStage(pipelines)
    const stageLabelByKey = buildStageLabelByKey(pipelines)
    const getStageKeyLabel = (stageKey: string) => stageLabelByKey[stageKey] ?? "Unknown stage"
    const { data: settings, isLoading, isError } = useZapierSettings()
    const donorSettingsState = getZapierDonorSettingsState({
        settings: canEditDonorSettings ? settings : undefined,
        eggPipelines: eggDonorPipelinesQuery.data,
        spermPipelines: spermDonorPipelinesQuery.data,
        eggLoading: eggDonorPipelinesQuery.isLoading,
        spermLoading: spermDonorPipelinesQuery.isLoading,
        eggError: eggDonorPipelinesQuery.isError,
        spermError: spermDonorPipelinesQuery.isError,
    })
    const {
        canSave: canSaveDonorSettings,
        mappingsUnresolved: donorMappingsUnresolved,
        pipelinesByType: donorPipelinesByType,
        pipelinesError: donorPipelinesError,
        pipelinesLoading: donorPipelinesLoading,
        settingsAvailable: donorSettingsAvailable,
    } = donorSettingsState
    const { data: metaForms = [], isLoading: metaFormsLoading } = useMetaForms()
    const createInboundWebhook = useCreateZapierInboundWebhook()
    const rotateInboundWebhook = useRotateZapierInboundWebhook()
    const updateInboundWebhook = useUpdateZapierInboundWebhook()
    const parseFieldPaste = useZapierFieldPaste()
    const deleteInboundWebhook = useDeleteZapierInboundWebhook()
    const updateOutbound = useUpdateZapierOutboundSettings()
    const [rotatingWebhookId, setRotatingWebhookId] = useState<string | null>(null)
    const [deletingWebhookId, setDeletingWebhookId] = useState<string | null>(null)
    const [inlineSaveStates, setInlineSaveStates] = useState<Record<string, SaveStatusState>>({})
    const [testFormId, setTestFormId] = useState('')
    const [fieldPaste, setFieldPaste] = useState('')
    const [fieldPasteError, setFieldPasteError] = useState<string | null>(null)
    const [fieldPasteWebhookId, setFieldPasteWebhookId] = useState('')
    const [fieldPasteFormId, setFieldPasteFormId] = useState('')
    const [fieldPasteResult, setFieldPasteResult] = useState<ZapierFieldPasteResponse | null>(null)
    const sendTestLead = useZapierTestLead()
    const sendOutboundTest = useZapierOutboundTest()
    const [outboundSecret, setOutboundSecret] = useState('')
    const [outboundTestLeadId, setOutboundTestLeadId] = useState('')
    const inboundWebhooks = settings?.inbound_webhooks ?? []
    const activeWebhookKey = createZapierWebhookDraftKey(inboundWebhooks)
    const [webhookDraft, setWebhookDraft] = useState<ZapierWebhookDraftState>(() =>
        createZapierWebhookDraftState(activeWebhookKey, inboundWebhooks)
    )
    const activeWebhookDraft = getActiveZapierWebhookDraft(
        webhookDraft,
        activeWebhookKey,
        inboundWebhooks,
    )
    const { labelDrafts, webhookSecrets } = activeWebhookDraft
    const activeFieldPasteWebhookId = getActiveFieldPasteWebhookId(fieldPasteWebhookId, inboundWebhooks)
    const singleZapierFormId = getSingleZapierFormId(metaForms)
    const activeTestFormId = testFormId.trim() || singleZapierFormId
    const activeOutboundKey = createZapierOutboundDraftKey(
        settings,
        pipelines,
        donorPipelinesByType,
    )
    const [outboundDraft, setOutboundDraft] = useState<ZapierOutboundDraftState>(() =>
        createZapierOutboundDraftState(
            activeOutboundKey,
            settings,
            pipelines,
            donorPipelinesByType,
        )
    )
    const activeOutboundDraft = getActiveZapierOutboundDraft(
        outboundDraft,
        activeOutboundKey,
        settings,
        pipelines,
        donorPipelinesByType,
    )
    const outboundForm = activeOutboundDraft.form

    const updateWebhookDraft = (
        updater: (draft: ZapierWebhookDraftState) => ZapierWebhookDraftState,
    ) => {
        setWebhookDraft((current) => {
            const activeDraft = getActiveZapierWebhookDraft(
                current,
                activeWebhookKey,
                inboundWebhooks,
            )
            return updater(activeDraft)
        })
    }

    const updateOutboundForm = <K extends keyof ZapierOutboundFormState>(
        field: K,
        value: ZapierOutboundFormState[K],
    ) => {
        setOutboundDraft((current) => {
            const activeDraft = getActiveZapierOutboundDraft(
                current,
                activeOutboundKey,
                settings,
                pipelines,
                donorPipelinesByType,
            )

            return {
                outboundKey: activeOutboundKey,
                form: {
                    ...activeDraft.form,
                    [field]: value,
                },
            }
        })
    }

    const handleCreateInbound = async () => {
        try {
            const result = await createInboundWebhook.mutateAsync({ label: null })
            updateWebhookDraft((current) => ({
                ...current,
                webhookSecrets: {
                    ...current.webhookSecrets,
                    [result.webhook_id]: result.webhook_secret,
                },
            }))
            toast.success("Webhook created")
        } catch {
            toast.error("Failed to create webhook")
        }
    }

    // Rotate and delete run from confirm dialogs, which show a failure inline, so errors propagate.
    const handleRotateInbound = async (webhookId: string) => {
        setRotatingWebhookId(webhookId)
        try {
            const result = await rotateInboundWebhook.mutateAsync({ webhookId })
            const secretId = result.webhook_id ?? webhookId
            updateWebhookDraft((current) => ({
                ...current,
                webhookSecrets: {
                    ...current.webhookSecrets,
                    [secretId]: result.webhook_secret,
                },
            }))
            toast.success("Webhook secret rotated")
        } finally {
            setRotatingWebhookId(null)
        }
    }

    const handleDeleteInbound = async (webhookId: string) => {
        setDeletingWebhookId(webhookId)
        try {
            await deleteInboundWebhook.mutateAsync({ webhookId })
            updateWebhookDraft((current) => {
                const webhookSecrets = { ...current.webhookSecrets }
                const labelDrafts = { ...current.labelDrafts }
                delete webhookSecrets[webhookId]
                delete labelDrafts[webhookId]
                return {
                    ...current,
                    labelDrafts,
                    webhookSecrets,
                }
            })
            toast.success("Webhook deleted")
        } finally {
            setDeletingWebhookId(null)
        }
    }

    // The label and Active switch save on their own; SaveStatus next to each shows the result.
    const setInlineSaveState = (key: string, state: SaveStatusState) => {
        setInlineSaveStates((current) => ({ ...current, [key]: state }))
    }

    const handleLabelBlur = async (webhookId: string) => {
        const draft = (labelDrafts[webhookId] || "").trim()
        const current = settings?.inbound_webhooks?.find((item) => item.webhook_id === webhookId)?.label || ""
        if (draft === (current || "")) {
            return
        }
        const key = `${webhookId}:label`
        setInlineSaveState(key, "saving")
        try {
            await updateInboundWebhook.mutateAsync({
                webhookId,
                payload: { label: draft || null },
            })
            setInlineSaveState(key, "saved")
        } catch (error) {
            setInlineSaveState(key, "error")
            const message = getActionErrorMessage(error, "Couldn't update the webhook label")
            if (message) toast.error(message)
        }
    }

    const handleToggleInbound = async (webhookId: string, enabled: boolean) => {
        const key = `${webhookId}:active`
        setInlineSaveState(key, "saving")
        try {
            await updateInboundWebhook.mutateAsync({
                webhookId,
                payload: { is_active: enabled },
            })
            setInlineSaveState(key, "saved")
        } catch (error) {
            setInlineSaveState(key, "error")
            const message = getActionErrorMessage(error, "Couldn't update the webhook")
            if (message) toast.error(message)
        }
    }

    const handleTestLead = async () => {
        try {
            const formId = activeTestFormId.trim()
            const payload = formId ? { form_id: formId } : {}
            const result = await sendTestLead.mutateAsync(payload)
            if (result.status === "converted") {
                toast.success(result.message ?? "Test lead converted successfully")
            } else if (result.status === "awaiting_mapping") {
                toast.message(result.message ?? "Test lead stored. Mapping review required.")
            } else {
                toast.message(result.message ?? `Test lead stored with status: ${result.status}`)
            }
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't send the test lead")
            if (message) toast.error(message)
        }
    }

    const handleFieldPaste = async () => {
        const paste = fieldPaste.trim()
        if (!paste) {
            setFieldPasteError("Paste the Zapier field list first.")
            return
        }
        setFieldPasteError(null)
        try {
            const payload: { paste: string; webhook_id?: string; form_id?: string } = { paste }
            if (activeFieldPasteWebhookId) {
                payload.webhook_id = activeFieldPasteWebhookId
            }
            const formId = fieldPasteFormId.trim()
            if (formId) {
                payload.form_id = formId
            }
            const result = await parseFieldPaste.mutateAsync(payload)
            setFieldPasteResult(result)
            if (result.form_id) {
                setTestFormId(result.form_id)
            }
            toast.success(`Detected ${result.field_count} fields`)
        } catch (error) {
            const message = getActionErrorMessage(
                error,
                "Unable to parse fields. Check the pasted data and try again.",
            )
            if (message) setFieldPasteError(message)
        }
    }

    const handleFieldPasteClear = () => {
        setFieldPaste('')
        setFieldPasteFormId('')
        setFieldPasteResult(null)
        setFieldPasteError(null)
    }

    const handleFieldPasteChange = (value: string) => {
        setFieldPaste(value)
        if (value.trim()) setFieldPasteError(null)
    }

    const handleSaveOutbound = async () => {
        try {
            const payload: {
                outbound_webhook_url: string | null
                outbound_webhook_secret?: string | null
                outbound_enabled: boolean
                send_hashed_pii: boolean
                event_mapping: ZapierEventMappingItem[]
                donor_outbound_enabled?: boolean
                donor_event_mapping?: ZapierDonorEventMappingItem[]
            } = {
                outbound_webhook_url: outboundForm.outboundUrl.trim() || null,
                outbound_enabled: outboundForm.outboundEnabled,
                send_hashed_pii: outboundForm.sendHashedPii,
                event_mapping: outboundForm.eventMapping,
            }
            if (canSaveDonorSettings || (
                donorSettingsAvailable
                && !donorPipelinesLoading
                && !donorPipelinesError
                && outboundForm.removeUnavailableDonorMappings
            )) {
                payload.donor_outbound_enabled = outboundForm.donorOutboundEnabled
                payload.donor_event_mapping = outboundForm.donorEventMapping.filter(
                    isTrackedDonorMappingItem,
                )
            } else if (
                donorSettingsAvailable
                && !donorPipelinesLoading
                && !donorPipelinesError
                && settings?.donor_outbound_enabled
                && !outboundForm.donorOutboundEnabled
            ) {
                payload.donor_outbound_enabled = false
            }
            const secret = outboundSecret.trim()
            if (secret) {
                payload.outbound_webhook_secret = secret
            }
            await updateOutbound.mutateAsync(payload)
            setOutboundSecret('')
            toast.success("Zapier configuration saved")
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't save Zapier configuration")
            if (message) toast.error(message)
        }
    }

    const handleOutboundTest = async () => {
        try {
            const leadId = outboundTestLeadId.trim()
            const payload: { stage_key?: string; lead_id?: string } = {}
            if (outboundForm.selectedOutboundStage) {
                payload.stage_key = outboundForm.selectedOutboundStage
            }
            if (leadId) {
                payload.lead_id = leadId
            }
            const result = await sendOutboundTest.mutateAsync(payload)
            toast.success(`Test event queued: ${result.event_name} for ${result.lead_id}`)
        } catch {
            toast.error("Failed to send outbound test event")
        }
    }

    const applyRecommendedBucketMapping = () => {
        updateOutboundForm(
            "eventMapping",
            outboundForm.eventMapping.map((item) => {
                const recommendedBucket = recommendedBucketByStage[item.stage_key]
                if (!recommendedBucket) {
                    return item
                }
                return {
                    ...item,
                    bucket: recommendedBucket,
                    event_name: ZAPIER_BUCKET_EVENT_NAME[recommendedBucket],
                    enabled: true,
                }
            }),
        )
        toast.success("Applied recommended Meta conversion stage mapping")
    }
    const showHeading = variant === "page"
    const isDialog = variant === "dialog"
    const containerClass = showHeading ? "border-t pt-6" : "space-y-4"
    const zapierForms = getActiveZapierRouteForms(metaForms)
    const singleZapierForm = zapierForms.length === 1 ? zapierForms[0] : null
    const mappingHref = singleZapierForm
        ? `/settings/integrations/meta/forms/${singleZapierForm.id}`
        : "/settings/integrations/meta/forms"

    return {
        activeFieldPasteWebhookId,
        activeTestFormId,
        applyRecommendedBucketMapping,
        canManageMetaLeads,
        containerClass,
        createInboundPending: createInboundWebhook.isPending,
        deletingWebhookId,
        donorMappingsUnresolved,
        donorPipelinesByType,
        donorPipelinesError,
        donorPipelinesLoading,
        donorSettingsAvailable,
        fieldPaste,
        fieldPasteError,
        fieldPasteFormId,
        fieldPasteResult,
        getStageKeyLabel,
        handleCreateInbound,
        handleDeleteInbound,
        handleFieldPaste,
        handleFieldPasteChange,
        handleFieldPasteClear,
        handleLabelBlur,
        handleOutboundTest,
        handleRotateInbound,
        handleSaveOutbound,
        handleTestLead,
        handleToggleInbound,
        inboundWebhooks,
        inlineSaveStates,
        isDialog,
        isError,
        isLoading,
        labelDrafts,
        mappingHref,
        metaFormsLoading,
        outboundForm,
        outboundSecret,
        outboundSecretConfigured: Boolean(settings?.outbound_secret_configured),
        outboundTestLeadId,
        parseFieldPastePending: parseFieldPaste.isPending,
        recommendedBucketByStage,
        rotateInboundPending: rotateInboundWebhook.isPending,
        rotatingWebhookId,
        sendOutboundTestPending: sendOutboundTest.isPending,
        sendTestLeadPending: sendTestLead.isPending,
        setFieldPaste,
        setFieldPasteFormId,
        setFieldPasteWebhookId,
        setOutboundSecret,
        setOutboundTestLeadId,
        setTestFormId,
        showHeading,
        updateOutboundForm,
        updateOutboundPending: updateOutbound.isPending,
        updateWebhookDraft,
        variant,
        webhookSecrets,
        zapierForms,
    }
}

type ZapierDialogTab = "incoming" | "routing" | "reporting" | "activity"

function isZapierDialogTab(value: unknown): value is ZapierDialogTab {
    return value === "incoming" || value === "routing" || value === "reporting" || value === "activity"
}

/** Header, tabbed DialogBody and DialogFooter of the Zapier dialog (sectioned layout). */
export function ZapierWebhookSection({
    statusLabel,
    statusVariant,
    StatusIcon,
    mappingBadgeLabel,
    mappingBadgeVariant,
}: {
    statusLabel: string
    statusVariant: BadgeVariant
    StatusIcon: IconComponent
    mappingBadgeLabel: string
    mappingBadgeVariant: BadgeVariant
}) {
    const variant = "dialog" as const
    const controller = useZapierWebhookController(variant)
    const [activeTab, setActiveTab] = useState<ZapierDialogTab>("incoming")
    // All tabs share one scroll body, so it returns to the top on each tab change.
    const bodyRef = useRef<HTMLDivElement | null>(null)

    return (
        <>
            <DialogHeader
                icon={<ZapIcon />}
                status={(
                    <Badge variant={statusVariant}>
                        <StatusIcon aria-hidden="true" />
                        {statusLabel}
                    </Badge>
                )}
            >
                <DialogTitle>Zapier Configuration</DialogTitle>
            </DialogHeader>
            {/* The header holds one status badge; mapping health gets its own row so the title keeps its width at 390px. */}
            <DialogStatusBar>
                <span className="text-muted-foreground">Stage reporting</span>
                <Badge
                    data-testid="zapier-mapping-health-dialog-badge"
                    variant={mappingBadgeVariant}
                >
                    {mappingBadgeLabel}
                </Badge>
            </DialogStatusBar>
            <Tabs
                value={activeTab}
                onValueChange={(value) => {
                    if (isZapierDialogTab(value)) setActiveTab(value)
                }}
                resetScrollRef={bodyRef}
                className="min-h-0 flex-1 gap-0"
            >
                <div className="shrink-0 overflow-x-auto border-b px-6">
                    <TabsList variant="line" aria-label="Zapier configuration sections">
                        <TabsTrigger value="incoming">Incoming leads</TabsTrigger>
                        <TabsTrigger value="routing">Form routing</TabsTrigger>
                        <TabsTrigger value="reporting">Stage reporting</TabsTrigger>
                        <TabsTrigger value="activity">Activity</TabsTrigger>
                    </TabsList>
                </div>
                <DialogBody
                    ref={bodyRef}
                    className="overflow-x-hidden"
                    data-testid="zapier-dialog-body"
                >
                    {controller.isLoading ? (
                        <div className="flex items-center justify-center py-12">
                            <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                        </div>
                    ) : controller.isError ? (
                        <Alert variant="destructive">
                            <AlertTriangleIcon className="size-4" aria-hidden="true" />
                            <AlertTitle>Zapier settings unavailable</AlertTitle>
                            <AlertDescription>Configuration could not be loaded.</AlertDescription>
                        </Alert>
                    ) : (
                        <>
                <TabsContent value="incoming" keepMounted className="space-y-4">
                    <ZapierInboundWebhooksCard
                        inboundWebhooks={controller.inboundWebhooks}
                        webhookSecrets={controller.webhookSecrets}
                        labelDrafts={controller.labelDrafts}
                        createPending={controller.createInboundPending}
                        rotatePending={controller.rotateInboundPending}
                        rotatingWebhookId={controller.rotatingWebhookId}
                        deletingWebhookId={controller.deletingWebhookId}
                        onCreateInbound={() => {
                            void controller.handleCreateInbound()
                        }}
                        onUpdateWebhookDraft={controller.updateWebhookDraft}
                        onLabelBlur={controller.handleLabelBlur}
                        onToggleInbound={controller.handleToggleInbound}
                        onRotateInbound={controller.handleRotateInbound}
                        onDeleteInbound={controller.handleDeleteInbound}
                        inlineSaveStates={controller.inlineSaveStates}
                    />
                </TabsContent>

                <TabsContent value="routing" keepMounted className="space-y-4">
                    <ZapierFormRouting
                        canManageMetaLeads={controller.canManageMetaLeads}
                        forms={controller.zapierForms}
                        metaFormsLoading={controller.metaFormsLoading}
                        mappingHref={controller.mappingHref}
                        fieldPasteContent={(
                        <ZapierFieldPasteCard
                            isDialog={controller.isDialog}
                            inboundWebhooks={controller.inboundWebhooks}
                            activeWebhookId={controller.activeFieldPasteWebhookId}
                            canManageMetaLeads={controller.canManageMetaLeads}
                            fieldPaste={controller.fieldPaste}
                            fieldPasteError={controller.fieldPasteError}
                            fieldPasteFormId={controller.fieldPasteFormId}
                            fieldPasteResult={controller.fieldPasteResult}
                            parsePending={controller.parseFieldPastePending}
                            onWebhookChange={controller.setFieldPasteWebhookId}
                            onFieldPasteChange={controller.handleFieldPasteChange}
                            onFieldPasteFormIdChange={controller.setFieldPasteFormId}
                            onParse={() => {
                                void controller.handleFieldPaste()
                            }}
                            onClear={controller.handleFieldPasteClear}
                        />
                        )}
                    />
                </TabsContent>

                <TabsContent value="reporting" keepMounted>
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base">Stage reporting</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <ZapierOutboundSettingsCard
                                outboundForm={controller.outboundForm}
                                outboundSecret={controller.outboundSecret}
                                outboundSecretConfigured={controller.outboundSecretConfigured}
                                donorSettingsAvailable={controller.donorSettingsAvailable}
                                donorPipelinesByType={controller.donorPipelinesByType}
                                donorPipelinesLoading={controller.donorPipelinesLoading}
                                donorPipelinesError={controller.donorPipelinesError}
                                donorMappingsUnresolved={controller.donorMappingsUnresolved}
                                recommendedBucketByStage={controller.recommendedBucketByStage}
                                getStageKeyLabel={controller.getStageKeyLabel}
                                onOutboundFormChange={controller.updateOutboundForm}
                                onOutboundSecretChange={controller.setOutboundSecret}
                                onApplyRecommendedMapping={controller.applyRecommendedBucketMapping}
                            />
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="activity" keepMounted className="space-y-4">
                    <div className="grid gap-4 lg:grid-cols-2">
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base">Incoming lead test</CardTitle>
                            </CardHeader>
                            <CardContent>
                        <ZapierTestLeadControls
                            activeTestFormId={controller.activeTestFormId}
                            zapierForms={controller.zapierForms}
                            sendPending={controller.sendTestLeadPending}
                            onTestFormIdChange={controller.setTestFormId}
                            onSendTestLead={() => {
                                void controller.handleTestLead()
                            }}
                        />
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base">Surrogate event test</CardTitle>
                            </CardHeader>
                            <CardContent>
                        <ZapierOutboundTestControls
                            isDialog={controller.isDialog}
                            outboundForm={controller.outboundForm}
                            outboundTestLeadId={controller.outboundTestLeadId}
                            testPending={controller.sendOutboundTestPending}
                            getStageKeyLabel={controller.getStageKeyLabel}
                            onOutboundFormChange={controller.updateOutboundForm}
                            onOutboundTestLeadIdChange={controller.setOutboundTestLeadId}
                            onSendOutboundTest={() => {
                                void controller.handleOutboundTest()
                            }}
                        />
                            </CardContent>
                        </Card>
                        {controller.donorSettingsAvailable ? (
                            <Card>
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-base">Donor event test</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <ZapierDonorOutboundTestControls
                                        isDialog={controller.isDialog}
                                        donorOutboundEnabled={controller.outboundForm.donorOutboundEnabled}
                                    />
                                </CardContent>
                            </Card>
                        ) : null}
                    </div>
                    <ZapierMonitoringSection
                        variant={controller.variant}
                        donorPipelinesByType={controller.donorPipelinesByType}
                    />
                </TabsContent>
                        </>
                    )}
                </DialogBody>
            </Tabs>
            {/* Only Stage reporting has a draft to save; the other tabs save each change on its own. */}
            <DialogFooter>
                {activeTab === "reporting" ? (
                    <>
                        <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
                        <Button
                            onClick={() => {
                                void controller.handleSaveOutbound()
                            }}
                            disabled={controller.updateOutboundPending || controller.isLoading || controller.isError}
                        >
                            {controller.updateOutboundPending ? (
                                <>
                                    <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                    Saving…
                                </>
                            ) : (
                                "Save configuration"
                            )}
                        </Button>
                    </>
                ) : (
                    <DialogClose render={<Button variant="outline" />}>Close</DialogClose>
                )}
            </DialogFooter>
        </>
    )
}
