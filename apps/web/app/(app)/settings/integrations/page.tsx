"use client"

import { useReducer, useRef, useState, type ReactNode } from "react"
import Link from "@/components/app-link"
import { PageHeader } from "@/components/page-header"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogBody,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogStatusBar,
    DialogTitle,
} from "@/components/ui/dialog"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { CopyButton } from "@/components/ui/copy-button"
import { CopyField } from "@/components/ui/copy-field"
import { ValidatedField } from "@/components/ui/field"
import { SaveStatus, type SaveStatusState } from "@/components/ui/save-bar"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
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
import {
    CheckCircleIcon,
    AlertTriangleIcon,
    XCircleIcon,
    Loader2Icon,
    RefreshCwIcon,
    KeyIcon,
    MegaphoneIcon,
    ServerIcon,
    ZapIcon,
    VideoIcon,
    MailIcon,
    CalendarIcon,
    LinkIcon,
    UnlinkIcon,
    SparklesIcon,
    CheckIcon,
    TrashIcon,
    MessageSquareTextIcon,
} from "lucide-react"
import { useIntegrationHealth } from "@/lib/hooks/use-ops"
import { GoogleCalendarBindingSettings } from "@/components/appointments/GoogleCalendarBindingSettings"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { usePipelines } from "@/lib/hooks/use-pipelines"
import {
    useUserIntegrations,
    useConnectZoom,
    useConnectGmail,
    useConnectGoogleCalendar,
    useConnectGcp,
    useDisconnectIntegration,
    useGoogleCalendarStatus,
    useSyncGoogleCalendarNow,
} from "@/lib/hooks/use-user-integrations"
import { useAISettings, useUpdateAISettings, useTestAPIKey, useAIConsent, useAcceptConsent } from "@/lib/hooks/use-ai"
import { useResendSettings, useUpdateResendSettings, useTestResendKey, useRotateWebhook, useEligibleSenders } from "@/lib/hooks/use-resend"
import { useTwilioReadiness, useTwilioSettings } from "@/lib/hooks/use-twilio"
import {
    useZapierSettings,
    useZapierTestLead,
    useUpdateZapierOutboundSettings,
    useZapierOutboundTest,
    useZapierDonorOutboundTest,
    useZapierOutboundEvents,
    useZapierOutboundEventsSummary,
    useCreateZapierInboundWebhook,
    useRotateZapierInboundWebhook,
    useUpdateZapierInboundWebhook,
    useRetryZapierOutboundEvent,
    useZapierFieldPaste,
    useDeleteZapierInboundWebhook,
} from "@/lib/hooks/use-zapier"
import { useMetaForms } from "@/lib/hooks/use-meta-forms"
import {
    useMetaConnections,
    useMetaConnectUrl,
    useDisconnectMetaConnection,
} from "@/lib/hooks/use-meta-oauth"
import { useAdminMetaAdAccounts, useUpdateMetaAdAccount, useDeleteMetaAdAccount } from "@/lib/hooks/use-admin-meta"
import {
    useMetaCrmDatasetSettings,
    useUpdateMetaCrmDatasetSettings,
    useMetaCrmDatasetOutboundTest,
    useMetaCrmDatasetEvents,
    useMetaCrmDatasetEventsSummary,
    useRetryMetaCrmDatasetEvent,
} from "@/lib/hooks/use-meta-crm-dataset"
import type { MetaAdAccount, MetaAdAccountUpdate } from "@/lib/api/admin-meta"
import { getConnectionHealthStatus, parseMetaError, type MetaOAuthConnection } from "@/lib/api/meta-oauth"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Checkbox } from "@/components/ui/checkbox"
import { PencilIcon } from "lucide-react"
import { formatDateTime, formatRelativeTime } from "@/lib/formatters"
import { SendIcon, RotateCwIcon, ActivityIcon, PlusIcon } from "lucide-react"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { toast } from "@/components/ui/toast"
import type { IntegrationStatus, GoogleCalendarStatusResponse } from "@/lib/api/integrations"
import type { IntegrationHealth } from "@/lib/api/ops"
import type { TwilioReadinessStatus } from "@/lib/api/twilio"
import type {
    EligibleSender,
    ResendSettings,
    ResendSettingsUpdate,
    TestKeyResponse,
} from "@/lib/api/resend"
import type { Pipeline, StageSemantics } from "@/lib/api/pipelines"
import type {
    MetaCrmDatasetEventMappingItem,
} from "@/lib/api/meta-crm-dataset"
import type {
    ZapierDonorAttributionSource,
    ZapierDonorEventMappingItem,
    ZapierDonorOutboundTestRequest,
    ZapierEventMappingItem,
    ZapierFieldPasteResponse,
    ZapierOutboundEvent,
    ZapierStageBucket,
} from "@/lib/api/zapier"
import { getStageSemantics } from "@/lib/surrogate-stage-context"
import { humanizeSelectKey } from "@/lib/select-labels"

const statusConfig = {
    healthy: { icon: CheckCircleIcon, color: "text-green-600", badge: "default" as const, label: "Healthy" },
    degraded: { icon: AlertTriangleIcon, color: "text-yellow-600", badge: "secondary" as const, label: "Degraded" },
    error: { icon: XCircleIcon, color: "text-red-600", badge: "destructive" as const, label: "Error" },
}

const configStatusLabels: Record<string, { label: string; variant: "default" | "destructive" | "secondary" }> = {
    configured: { label: "Configured", variant: "default" },
    missing_token: { label: "Missing Token", variant: "destructive" },
    expired_token: { label: "Token Expired", variant: "destructive" },
}

const integrationTypeConfig: Record<string, { icon: typeof MegaphoneIcon; label: string; description: string }> = {
    meta_leads: {
        icon: MegaphoneIcon,
        label: "Meta Lead Ads",
        description: "Automatic lead capture from Facebook/Instagram ads"
    },
    meta_capi: {
        icon: ZapIcon,
        label: "Meta Conversions API",
        description: "Send conversion events back to Meta for ad optimization"
    },
    worker: {
        icon: ServerIcon,
        label: "Background Worker",
        description: "Processes jobs, emails, and scheduled tasks"
    },
    zapier: {
        icon: LinkIcon,
        label: "Zapier",
        description: "Outbound stage events and inbound lead webhooks"
    },
}

const ZAPIER_BUCKET_EVENT_NAME: Record<ZapierStageBucket, string> = {
    qualified: "Qualified",
    converted: "Converted",
    lost: "Lost",
    not_qualified: "Not Qualified",
}

const ZAPIER_BUCKET_OPTIONS: Array<{ value: ZapierStageBucket; label: string }> = [
    { value: "qualified", label: "Qualified" },
    { value: "converted", label: "Converted" },
    { value: "lost", label: "Lost" },
    { value: "not_qualified", label: "Not Qualified" },
]

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
type ZapierDonorType = (typeof DONOR_TYPES)[number]

const UNTRACKED_BUCKET_VALUE = "__none__"

const ZAPIER_DONOR_TYPE_OPTIONS: Array<{ value: ZapierDonorType; label: string }> = DONOR_TYPES.map(
    (donorType) => ({ value: donorType, label: getDonorTypeLabel(donorType) }),
)

const ZAPIER_DONOR_ATTRIBUTION_OPTIONS: Array<{ value: ZapierDonorAttributionSource; label: string }> = [
    { value: "meta", label: "Meta lead" },
    { value: "website", label: "Website form" },
]

const isZapierStageBucket = (value: unknown): value is ZapierStageBucket =>
    value === "qualified" ||
    value === "converted" ||
    value === "lost" ||
    value === "not_qualified"

type StageEventMappingLike = {
    stage_key: string
    event_name: string
    enabled: boolean
    bucket?: ZapierStageBucket | null
}

function buildDefaultStageEventMappingItem<T extends StageEventMappingLike>(
    stageKey: string,
    bucket: ZapierStageBucket | null,
): T {
    if (bucket) {
        return {
            stage_key: stageKey,
            event_name: ZAPIER_BUCKET_EVENT_NAME[bucket],
            enabled: true,
            bucket,
        } as T
    }
    return {
        stage_key: stageKey,
        event_name: "",
        enabled: false,
        bucket: null,
    } as T
}

function mergeEventMappingWithPipelineStages<T extends StageEventMappingLike>(
    eventMapping: T[] | null | undefined,
    pipelines: Pipeline[] | null | undefined,
): T[] {
    const defaultPipeline = pipelines?.find((pipeline) => pipeline.is_default) ?? pipelines?.[0]
    if (!defaultPipeline?.stages?.length) {
        return [...(eventMapping ?? [])]
    }

    const byStageKey = new Map((eventMapping ?? []).map((item) => [item.stage_key, item]))
    const merged: T[] = []

    for (const stage of defaultPipeline.stages) {
        if (stage.is_active === false) continue
        const stageKey = (stage.stage_key ?? stage.slug ?? "").trim()
        if (!stageKey) continue

        const existing = byStageKey.get(stageKey)
        if (existing) {
            merged.push(existing)
            continue
        }

        const stageBucket = getStageSemantics(stage).integration_bucket
        merged.push(
            buildDefaultStageEventMappingItem(
                stageKey,
                isZapierStageBucket(stageBucket) ? stageBucket : null,
            ) as T,
        )
    }

    return merged
}

function buildRecommendedBucketByStage(
    pipelines:
        | Array<{
            is_default?: boolean
            stages?: Array<{
                stage_key?: string
                slug?: string
                is_active?: boolean
                semantics?: Partial<StageSemantics>
                stage_type?: string
            }>
        }>
        | null
        | undefined,
): Record<string, ZapierStageBucket> {
    const defaultPipeline = pipelines?.find((pipeline) => pipeline.is_default) ?? pipelines?.[0]
    if (!defaultPipeline?.stages?.length) {
        return {}
    }

    const mapping: Record<string, ZapierStageBucket> = {}
    for (const stage of defaultPipeline.stages) {
        if (stage.is_active === false) continue
        const stageKey = (stage.stage_key ?? stage.slug ?? "").trim()
        if (!stageKey) continue
        const bucket = getStageSemantics(stage).integration_bucket
        if (isZapierStageBucket(bucket)) {
            mapping[stageKey] = bucket
        }
    }
    return mapping
}

function buildStageLabelByKey(pipelines: Pipeline[] | null | undefined): Record<string, string> {
    const defaultPipeline = pipelines?.find((pipeline) => pipeline.is_default) ?? pipelines?.[0]
    if (!defaultPipeline?.stages?.length) {
        return {}
    }

    const labels: Record<string, string> = {}
    for (const stage of defaultPipeline.stages) {
        if (stage.is_active === false) continue
        const stageKey = (stage.stage_key ?? stage.slug ?? "").trim()
        const stageLabel = stage.label?.trim()
        if (!stageKey || !stageLabel) continue
        labels[stageKey] = stageLabel
    }

    return labels
}

function getSelectOptionLabel(
    options: ReadonlyArray<{ value: string; label: string }>,
    value: string | null | undefined,
): string {
    if (!value) return ""
    return options.find((option) => option.value === value)?.label ?? ""
}

function getBucketSelectLabel(value: string | null | undefined): string {
    if (value === UNTRACKED_BUCKET_VALUE) return "Not Tracked"
    return getSelectOptionLabel(ZAPIER_BUCKET_OPTIONS, value)
}

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
    // Unsaved stages start from the suggestion only before any donor mapping is saved.
    const suggest = !savedMapping?.length

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

function hasUnresolvedDonorMappings(
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

function getEligibleSenderLabel(
    senders:
        | Array<{
            user_id: string
            display_name: string
            gmail_email: string
        }>
        | null
        | undefined,
    value: string | null | undefined,
): string {
    if (!value) return ""
    const sender = senders?.find((item) => item.user_id === value)
    if (!sender) return ""
    return `${sender.display_name} (${sender.gmail_email})`
}

function inferZapierBucket(item: ZapierEventMappingItem): ZapierStageBucket | null {
    if (isZapierStageBucket(item.bucket)) {
        return item.bucket
    }
    const normalized = (item.event_name || "").trim().toLowerCase()
    if (normalized === "qualified") return "qualified"
    if (normalized === "converted") return "converted"
    if (normalized === "lost") return "lost"
    if (normalized === "not qualified") return "not_qualified"
    return null
}

function getZapierMappingHealth(
    eventMapping: ZapierEventMappingItem[] | null | undefined,
    recommendedBucketByStage: Record<string, ZapierStageBucket>,
): {
    total: number
    matched: number
    isHealthy: boolean
} {
    const total = Object.keys(recommendedBucketByStage).length
    if (!eventMapping || eventMapping.length === 0) {
        return { total, matched: 0, isHealthy: false }
    }

    const byStage = new Map(eventMapping.map((item) => [item.stage_key, item]))
    let matched = 0
    for (const [stageKey, expectedBucket] of Object.entries(recommendedBucketByStage)) {
        const item = byStage.get(stageKey)
        if (!item || !item.enabled) {
            continue
        }
        if (inferZapierBucket(item) === expectedBucket) {
            matched += 1
        }
    }

    return {
        total,
        matched,
        isHealthy: matched === total && total > 0,
    }
}

type ZapierMappingHealthPresentation = {
    label: "Mapping Healthy" | "Mapping Needs Review" | "Mapping unavailable" | "Reporting disabled"
    variant: "default" | "secondary"
    detail: string
}

type ZapierMappingSettings = {
    outbound_enabled?: boolean | null
    event_mapping?: ZapierEventMappingItem[] | null
    donor_outbound_enabled?: boolean | null
    donor_event_mapping?: ZapierDonorEventMappingItem[] | null
}

function getZapierMappingHealthPresentation({
    surrogateEnabled,
    surrogateMapping,
    recommendedBucketByStage,
    donorSettingsAvailable,
    donorEnabled,
    donorMapping,
    donorPipelinesByType,
    donorPipelinesLoading,
    donorPipelinesError,
}: {
    surrogateEnabled: boolean
    surrogateMapping: ZapierEventMappingItem[] | null | undefined
    recommendedBucketByStage: Record<string, ZapierStageBucket>
    donorSettingsAvailable: boolean
    donorEnabled: boolean
    donorMapping: ZapierDonorEventMappingItem[] | null | undefined
    donorPipelinesByType: Record<ZapierDonorType, Pipeline[] | null | undefined>
    donorPipelinesLoading: boolean
    donorPipelinesError: boolean
}): ZapierMappingHealthPresentation {
    const surrogateHealth = getZapierMappingHealth(
        surrogateMapping,
        recommendedBucketByStage,
    )
    const donorApplicable = donorSettingsAvailable && donorEnabled
    const donorUnavailable = donorApplicable && (donorPipelinesLoading || donorPipelinesError)
    const donorNeedsReview = donorApplicable
        && !donorUnavailable
        && (
            hasUnresolvedDonorMappings(donorMapping, donorPipelinesByType)
            || !(donorMapping ?? []).some((item) => item.enabled)
        )
    const pathDetails: string[] = []

    if (surrogateEnabled) {
        pathDetails.push(
            `Surrogate mapping: ${surrogateHealth.matched}/${surrogateHealth.total} recommended stages`,
        )
    }
    if (donorApplicable) {
        pathDetails.push(
            donorUnavailable
                ? "Donor mapping unavailable"
                : donorNeedsReview
                    ? "Donor mapping needs review"
                    : "Donor mapping configured",
        )
    }

    if ((surrogateEnabled && !surrogateHealth.isHealthy) || donorNeedsReview) {
        return {
            label: "Mapping Needs Review",
            variant: "secondary",
            detail: pathDetails.join(" · "),
        }
    }
    if (donorUnavailable) {
        return {
            label: "Mapping unavailable",
            variant: "secondary",
            detail: pathDetails.join(" · "),
        }
    }
    if (surrogateEnabled || donorApplicable) {
        return {
            label: "Mapping Healthy",
            variant: "default",
            detail: pathDetails.join(" · "),
        }
    }
    // The summary line already states that reporting is off, so no mapping detail is shown.
    return {
        label: "Reporting disabled",
        variant: "secondary",
        detail: "",
    }
}

function useZapierMappingPresentation(
    settings: ZapierMappingSettings | null | undefined,
    surrogatePipelines: Pipeline[] | null | undefined,
    enabled: boolean,
): ZapierMappingHealthPresentation {
    const eggDonorPipelinesQuery = usePipelines("egg_donor", enabled)
    const spermDonorPipelinesQuery = usePipelines("sperm_donor", enabled)
    const donorState = getZapierDonorSettingsState({
        settings,
        eggPipelines: eggDonorPipelinesQuery.data,
        spermPipelines: spermDonorPipelinesQuery.data,
        eggLoading: eggDonorPipelinesQuery.isLoading,
        spermLoading: spermDonorPipelinesQuery.isLoading,
        eggError: eggDonorPipelinesQuery.isError,
        spermError: spermDonorPipelinesQuery.isError,
    })

    return getZapierMappingHealthPresentation({
        surrogateEnabled: Boolean(settings?.outbound_enabled),
        surrogateMapping: mergeEventMappingWithPipelineStages(
            settings?.event_mapping,
            surrogatePipelines,
        ),
        recommendedBucketByStage: buildRecommendedBucketByStage(surrogatePipelines),
        donorSettingsAvailable: donorState.settingsAvailable,
        donorEnabled: Boolean(settings?.donor_outbound_enabled),
        donorMapping: settings?.donor_event_mapping,
        donorPipelinesByType: donorState.pipelinesByType,
        donorPipelinesLoading: donorState.pipelinesLoading,
        donorPipelinesError: donorState.pipelinesError,
    })
}

const ZAPIER_OUTBOUND_STATUS_BADGE: Record<
    ZapierOutboundEvent["status"],
    { label: string; variant: "default" | "secondary" | "destructive" }
> = {
    queued: { label: "Queued", variant: "secondary" },
    delivered: { label: "Delivered", variant: "default" },
    failed: { label: "Failed", variant: "destructive" },
    skipped: { label: "Skipped", variant: "secondary" },
}

function formatZapierRate(rate: number): string {
    return `${Math.round(rate * 100)}%`
}

const ZAPIER_SOURCE_LABELS: Record<string, string> = {
    automatic: "Automatic",
    workflow: "Workflow",
    test: "Test",
}

const ZAPIER_SKIP_REASON_LABELS: Record<string, string> = {
    duplicate: "Already sent",
    not_meta_source: "Not a Meta lead",
    missing_meta_lead_fk: "No linked Meta lead",
    missing_meta_lead: "Meta lead not found",
    missing_meta_lead_id: "Meta lead ID missing",
    synthetic_meta_lead_id: "Not a real Meta lead ID",
    stale_meta_lead: "Meta lead older than 90 days",
    outbound_disabled: "Surrogate reporting disabled",
    missing_webhook_url: "Webhook URL missing",
    unmapped_stage: "Stage not mapped",
    unmapped_donor_stage: "Stage not mapped",
    donor_outbound_disabled: "Donor reporting disabled",
    donor_stage_undo: "Undo of an earlier change",
    donor_stage_undone: "Withdrawn by undo",
    missing_donor_attribution: "No Meta lead or website form",
    missing_matching_data: "No click ID or contact data",
    donor_dispatch_disabled: "Donor reporting disabled before sending",
    donor_dispatch_url_missing: "Webhook URL removed before sending",
    donor_event_invalid: "Invalid event record",
    donor_subject_missing: "Donor stage change not found",
    donor_attribution_missing: "Attribution no longer linked",
    donor_stage_inactive: "Stage no longer active",
    donor_mapping_changed: "Mapping changed before sending",
    donor_config_changed: "Configuration changed before sending",
}

function formatZapierSource(source: string): string {
    return ZAPIER_SOURCE_LABELS[source] ?? humanizeSelectKey(source) ?? "Other"
}

function formatZapierReason(reason: string | null | undefined): string {
    if (!reason) return "—"
    return ZAPIER_SKIP_REASON_LABELS[reason] ?? humanizeSelectKey(reason) ?? "Other reason"
}

function formatZapierAttribution(event: ZapierOutboundEvent): string {
    if (event.attribution_source === "website") return "Attribution: Website form"
    if (event.attribution_source === "meta") {
        return `Meta lead: ${event.lead_id || "Unavailable"}`
    }
    return `Lead: ${event.lead_id || "—"}`
}

// AI provider options
const AI_PROVIDERS = [
    {
        value: "gemini",
        label: "Google Gemini",
        models: ["gemini-3.8-flash"],
    },
    {
        value: "vertex_api_key",
        label: "Vertex AI (API Key)",
        models: ["gemini-3.8-flash"],
    },
    {
        value: "vertex_wif",
        label: "Vertex AI (WIF)",
        models: ["gemini-3.8-flash"],
    },
] as const

const VERTEX_LOCATIONS = [
    { value: "global", label: "Global" },
    { value: "us", label: "United States" },
    { value: "eu", label: "European Union" },
] as const

type AiProvider = (typeof AI_PROVIDERS)[number]["value"]

const isAiProvider = (value: string | null | undefined): value is AiProvider =>
    AI_PROVIDERS.some((providerOption) => providerOption.value === value)

type AiConfigurationFormState = {
    isEnabled: boolean
    provider: AiProvider
    apiKey: string
    model: string
    vertexProjectId: string
    vertexLocation: string
    vertexAudience: string
    vertexServiceAccount: string
    vertexUseExpress: boolean
}

type AiConfigurationUiState = {
    keyTested: boolean | null
    saved: boolean
    editingKey: boolean
}

type EmailConfigurationFormState = {
    provider: "resend" | "gmail" | ""
    apiKey: string
    rateLimitGroupConfigured: boolean
    rateLimitGroupEnabled: boolean
    rateLimitGroupToken: string
    replaceRateLimitGroupToken: boolean
    clearRateLimitGroup: boolean
    verifiedDomain: string
    fromEmail: string
    fromName: string
    replyTo: string
    webhookTrackingEnabled: boolean
    clearWebhookTracking: boolean
    replaceWebhookSigningSecret: boolean
    webhookSigningSecret: string
    defaultSender: string
}

type EmailConfigurationUiState = {
    keyTested: TestKeyResponse | null
    saved: boolean
    isEditingKey: boolean
    hasUserEdited: boolean
}

const createEmailConfigurationFormState = (
    settings: ResendSettings | undefined,
): EmailConfigurationFormState => ({
    provider: settings?.email_provider || "resend",
    apiKey: "",
    rateLimitGroupConfigured: settings?.rate_limit_group_configured ?? false,
    rateLimitGroupEnabled: settings?.rate_limit_group_configured ?? false,
    rateLimitGroupToken: "",
    replaceRateLimitGroupToken: false,
    clearRateLimitGroup: false,
    verifiedDomain: settings?.verified_domain || "",
    fromEmail: settings?.from_email || "",
    fromName: settings?.from_name || "",
    replyTo: settings?.reply_to_email || "",
    webhookTrackingEnabled:
        settings?.webhook_signing_secret_configured ?? false,
    clearWebhookTracking: false,
    replaceWebhookSigningSecret: false,
    webhookSigningSecret: "",
    defaultSender: settings?.default_sender_user_id || "",
})

const changeEmailConfigurationProvider = (
    current: EmailConfigurationFormState,
    provider: EmailConfigurationFormState["provider"],
): EmailConfigurationFormState => ({
    ...current,
    provider,
    apiKey: provider !== "resend" ? "" : current.apiKey,
    rateLimitGroupEnabled:
        provider === "resend"
            ? current.rateLimitGroupConfigured
            : current.rateLimitGroupEnabled,
    rateLimitGroupToken:
        provider !== "resend" ? "" : current.rateLimitGroupToken,
    replaceRateLimitGroupToken:
        provider !== "resend" ? false : current.replaceRateLimitGroupToken,
    clearRateLimitGroup:
        provider !== "resend" ? false : current.clearRateLimitGroup,
    clearWebhookTracking:
        provider !== "resend" ? false : current.clearWebhookTracking,
    replaceWebhookSigningSecret:
        provider !== "resend" ? false : current.replaceWebhookSigningSecret,
    webhookSigningSecret:
        provider !== "resend" ? "" : current.webhookSigningSecret,
})

type MetaCrmDatasetFormState = {
    datasetId: string
    accessToken: string
    enabled: boolean
    crmName: string
    sendHashedPii: boolean
    eventMapping: MetaCrmDatasetEventMappingItem[]
    testEventCode: string
    selectedStage: string
    outboundTestLeadId: string
    outboundTestFbc: string
}

type UpdateMetaCrmDatasetForm = <K extends keyof MetaCrmDatasetFormState>(
    field: K,
    value: MetaCrmDatasetFormState[K],
) => void

type UpdateMetaCrmDatasetEventMapping = (
    updater: (current: MetaCrmDatasetEventMappingItem[]) => MetaCrmDatasetEventMappingItem[],
) => void

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

type MetaAccountEditState = {
    account: MetaAdAccount | null
    error: string
    adAccountName: string
    pixelId: string
    capiEnabled: boolean
    accountActive: boolean
}

type MetaAccountEditAction =
    | { type: "open"; account: MetaAdAccount }
    | { type: "close" }
    | { type: "clearError" }
    | { type: "setError"; error: string }
    | { type: "changeAdAccountName"; value: string }
    | { type: "changePixelId"; value: string }
    | { type: "toggleCapiEnabled"; value: boolean }
    | { type: "toggleAccountActive"; value: boolean }

const initialMetaAccountEditState: MetaAccountEditState = {
    account: null,
    error: "",
    adAccountName: "",
    pixelId: "",
    capiEnabled: false,
    accountActive: true,
}

function createMetaAccountEditState(account: MetaAdAccount): MetaAccountEditState {
    return {
        account,
        error: "",
        adAccountName: account.ad_account_name || "",
        pixelId: account.pixel_id || "",
        capiEnabled: account.capi_enabled,
        accountActive: account.is_active,
    }
}

function metaAccountEditReducer(
    state: MetaAccountEditState,
    action: MetaAccountEditAction,
): MetaAccountEditState {
    switch (action.type) {
        case "open":
            return createMetaAccountEditState(action.account)
        case "close":
            return initialMetaAccountEditState
        case "clearError":
            return { ...state, error: "" }
        case "setError":
            return { ...state, error: action.error }
        case "changeAdAccountName":
            return { ...state, adAccountName: action.value }
        case "changePixelId":
            return { ...state, pixelId: action.value }
        case "toggleCapiEnabled":
            return { ...state, capiEnabled: action.value }
        case "toggleAccountActive":
            return { ...state, accountActive: action.value }
        default:
            return state
    }
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
        JSON.stringify(settings?.donor_event_mapping ?? []),
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

function getZapierDonorSettingsState({
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

/** DialogBody and DialogFooter of the AI Configuration dialog. */
function AIConfigurationSection() {
    const { data: aiSettings, isLoading } = useAISettings()

    return (
        <AIConfigurationSectionContent
            key={aiSettings ? "loaded" : "loading"}
            aiSettings={aiSettings}
            isLoading={isLoading}
        />
    )
}

function AIConfigurationSectionContent({
    aiSettings,
    isLoading,
}: {
    aiSettings: ReturnType<typeof useAISettings>["data"]
    isLoading: boolean
}) {
    const { data: consentInfo } = useAIConsent()
    const acceptConsent = useAcceptConsent()
    const updateSettings = useUpdateAISettings()
    const testKey = useTestAPIKey()
    const { data: userIntegrations } = useUserIntegrations()
    const connectGcp = useConnectGcp()
    const disconnectIntegration = useDisconnectIntegration()
    const { refetch: refetchAuth } = useAuth()

    const [aiForm, setAiForm] = useState<AiConfigurationFormState>(() => ({
        isEnabled: aiSettings?.is_enabled ?? false,
        provider: aiSettings && isAiProvider(aiSettings.provider) ? aiSettings.provider : "gemini",
        apiKey: "",
        model: aiSettings?.model || "",
        vertexProjectId:
            aiSettings?.vertex_wif?.project_id ||
            aiSettings?.vertex_api_key?.project_id ||
            "",
        vertexLocation:
            aiSettings?.vertex_wif?.location ||
            aiSettings?.vertex_api_key?.location ||
            "us",
        vertexAudience: aiSettings?.vertex_wif?.audience || "",
        vertexServiceAccount: aiSettings?.vertex_wif?.service_account_email || "",
        vertexUseExpress:
            aiSettings?.provider === "vertex_api_key"
            && !aiSettings.vertex_api_key?.project_id
            && !aiSettings.vertex_api_key?.location,
    }))
    const [aiUi, setAiUi] = useState<AiConfigurationUiState>({
        keyTested: null,
        saved: false,
        editingKey: false,
    })

    const updateAiForm = <K extends keyof AiConfigurationFormState>(field: K, value: AiConfigurationFormState[K]) => {
        setAiForm((current) => ({ ...current, [field]: value }))
    }

    const selectedProviderModels =
        AI_PROVIDERS.find((providerOption) => providerOption.value === aiForm.provider)?.models ??
        []
    const consentAccepted = Boolean(aiSettings?.consent_accepted_at)
    const gcpIntegration = userIntegrations?.find((integration) => integration.integration_type === "gcp")
    const vertexReady = aiForm.provider !== "vertex_wif"
        || Boolean(
            aiForm.vertexProjectId.trim()
            && aiForm.vertexLocation.trim()
            && aiForm.vertexServiceAccount.trim()
            && aiForm.vertexAudience.trim()
        )

    const handleTestKey = async () => {
        if (aiForm.provider === "vertex_wif" || !aiForm.apiKey.trim()) return
        setAiUi((current) => ({ ...current, keyTested: null }))
        try {
            const payload: {
                provider: "gemini" | "vertex_api_key";
                api_key: string;
                vertex_api_key?: { project_id: string | null; location: string | null };
            } = {
                provider: aiForm.provider,
                api_key: aiForm.apiKey,
            }
            if (aiForm.provider === "vertex_api_key") {
                payload.vertex_api_key = {
                    project_id: aiForm.vertexUseExpress ? null : aiForm.vertexProjectId.trim() || null,
                    location: aiForm.vertexUseExpress ? null : aiForm.vertexLocation.trim() || null,
                }
            }
            const result = await testKey.mutateAsync(payload)
            setAiUi((current) => ({ ...current, keyTested: result.valid }))
        } catch {
            setAiUi((current) => ({ ...current, keyTested: false }))
        }
    }

    const handleSave = async () => {
        const update: {
            is_enabled?: boolean;
            provider?: "gemini" | "vertex_wif" | "vertex_api_key";
            api_key?: string;
            model?: string;
            vertex_wif?: {
                project_id: string | null;
                location: string | null;
                audience: string | null;
                service_account_email: string | null;
            };
            vertex_api_key?: {
                project_id: string | null;
                location: string | null;
            };
        } = {
            is_enabled: aiForm.isEnabled,
            provider: aiForm.provider,
        }
        if (aiForm.apiKey.trim()) {
            update.api_key = aiForm.apiKey
        }
        if (aiForm.model) {
            update.model = aiForm.model
        }
        if (aiForm.provider === "vertex_wif") {
            update.vertex_wif = {
                project_id: aiForm.vertexProjectId.trim() || null,
                location: aiForm.vertexLocation.trim() || null,
                audience: aiForm.vertexAudience.trim() || null,
                service_account_email: aiForm.vertexServiceAccount.trim() || null,
            }
        }
        if (aiForm.provider === "vertex_api_key") {
            update.vertex_api_key = {
                project_id: aiForm.vertexUseExpress ? null : aiForm.vertexProjectId.trim() || null,
                location: aiForm.vertexUseExpress ? null : aiForm.vertexLocation.trim() || null,
            }
        }
        try {
            await updateSettings.mutateAsync(update)
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't save AI configuration")
            if (message) toast.error(message)
            return
        }
        setAiForm((current) => ({ ...current, apiKey: "" }))
        setAiUi((current) => ({
            ...current,
            keyTested: null,
            saved: true,
            editingKey: false,
        }))
        refetchAuth()
        setTimeout(() => {
            setAiUi((current) => ({ ...current, saved: false }))
        }, 2000)
    }

    const handleAcceptConsent = async () => {
        try {
            await acceptConsent.mutateAsync()
            toast.success("AI consent accepted")
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't accept AI consent")
            if (message) toast.error(message)
        }
    }

    if (isLoading) {
        return <IntegrationDialogLoadingState />
    }

    return (
        <>
            <DialogBody>
                {!consentAccepted && consentInfo ? (
                    <AIConsentCard
                        consentText={consentInfo.consent_text}
                        pending={acceptConsent.isPending}
                        onAccept={handleAcceptConsent}
                    />
                ) : null}

                <AISettingsFields
                    aiForm={aiForm}
                    aiUi={aiUi}
                    apiKeyMasked={aiSettings?.api_key_masked ?? null}
                    consentAccepted={consentAccepted}
                    selectedProviderModels={selectedProviderModels}
                    gcpIntegration={gcpIntegration}
                    pendingState={{
                        keyTest: testKey.isPending,
                        gcpConnect: connectGcp.isPending,
                        gcpDisconnect: disconnectIntegration.isPending,
                    }}
                    updateAiForm={updateAiForm}
                    onProviderChange={(provider) => {
                        setAiForm((current) => ({
                            ...current,
                            provider,
                            model: "",
                        }))
                        setAiUi((current) => ({
                            ...current,
                            keyTested: null,
                            editingKey: false,
                        }))
                    }}
                    onApiKeyChange={(apiKey) => {
                        updateAiForm("apiKey", apiKey)
                        setAiUi((current) => ({ ...current, keyTested: null }))
                    }}
                    onEditKey={() => {
                        updateAiForm("apiKey", "")
                        setAiUi((current) => ({ ...current, editingKey: true }))
                    }}
                    onTestKey={handleTestKey}
                    onConnectGcp={() => connectGcp.mutate()}
                    onDisconnectGcp={async () => {
                        await disconnectIntegration.mutateAsync("gcp")
                        toast.success("Google Cloud disconnected")
                    }}
                />
            </DialogBody>
            <DialogFooter>
                <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
                <AISaveButton
                    pending={updateSettings.isPending}
                    saved={aiUi.saved}
                    disabled={!vertexReady}
                    onSave={() => {
                        void handleSave()
                    }}
                />
            </DialogFooter>
        </>
    )
}

type UpdateAiConfigurationForm = <K extends keyof AiConfigurationFormState>(
    field: K,
    value: AiConfigurationFormState[K],
) => void

/** Loading body and footer shared by the sectioned integration dialogs. */
function IntegrationDialogLoadingState() {
    return (
        <>
            <DialogBody>
                <div role="status" className="flex items-center justify-center py-8">
                    <Loader2Icon
                        className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground"
                        aria-hidden="true"
                    />
                    <span className="sr-only">Loading</span>
                </div>
            </DialogBody>
            <DialogFooter>
                <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
            </DialogFooter>
        </>
    )
}

function AIConsentCard({
    consentText,
    pending,
    onAccept,
}: {
    consentText: string
    pending: boolean
    onAccept: () => void
}) {
    return (
        <Card className="mb-4 border-yellow-200 bg-yellow-50/60">
            <CardHeader className="pb-2">
                <CardTitle className="text-base">AI Consent Required</CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                    An admin must accept the AI data processing consent before enabling AI features.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
                <div className="max-h-40 overflow-auto rounded-md border border-yellow-200 bg-white p-3 text-xs leading-relaxed text-muted-foreground">
                    {consentText}
                </div>
                <Button onClick={onAccept} disabled={pending}>
                    {pending ? (
                        <>
                            <Loader2Icon
                                className="mr-2 size-4 animate-spin motion-reduce:animate-none"
                                aria-hidden="true"
                            />
                            Accepting…
                        </>
                    ) : (
                        "Accept Consent"
                    )}
                </Button>
            </CardContent>
        </Card>
    )
}

function AISettingsFields({
    aiForm,
    aiUi,
    apiKeyMasked,
    consentAccepted,
    selectedProviderModels,
    gcpIntegration,
    pendingState,
    updateAiForm,
    onProviderChange,
    onApiKeyChange,
    onEditKey,
    onTestKey,
    onConnectGcp,
    onDisconnectGcp,
}: {
    aiForm: AiConfigurationFormState
    aiUi: AiConfigurationUiState
    apiKeyMasked: string | null
    consentAccepted: boolean
    selectedProviderModels: ReadonlyArray<string>
    gcpIntegration: IntegrationStatus | undefined
    pendingState: {
        keyTest: boolean
        gcpConnect: boolean
        gcpDisconnect: boolean
    }
    updateAiForm: UpdateAiConfigurationForm
    onProviderChange: (provider: AiProvider) => void
    onApiKeyChange: (apiKey: string) => void
    onEditKey: () => void
    onTestKey: () => void
    onConnectGcp: () => void
    onDisconnectGcp: () => Promise<unknown>
}) {
    return (
        <>
            <div className="flex items-center justify-between gap-3 rounded-md border p-3">
                <Label htmlFor="ai-enabled">Enable AI assistant</Label>
                <Switch
                    id="ai-enabled"
                    checked={aiForm.isEnabled}
                    onCheckedChange={(checked) => updateAiForm("isEnabled", checked)}
                    disabled={!consentAccepted && !aiForm.isEnabled}
                />
            </div>

            <div className="space-y-4">
                <AIProviderField
                    provider={aiForm.provider}
                    onProviderChange={onProviderChange}
                />

                {aiForm.provider !== "vertex_wif" ? (
                    <AIApiKeyField
                        provider={aiForm.provider}
                        apiKey={aiForm.apiKey}
                        apiKeyMasked={apiKeyMasked}
                        editingKey={aiUi.editingKey}
                        keyTested={aiUi.keyTested}
                        pending={pendingState.keyTest}
                        onApiKeyChange={onApiKeyChange}
                        onEditKey={onEditKey}
                        onTestKey={onTestKey}
                    />
                ) : null}

                {aiForm.provider === "vertex_api_key" ? (
                    <VertexApiKeySettings
                        form={aiForm}
                        updateAiForm={updateAiForm}
                    />
                ) : null}

                {aiForm.provider === "vertex_wif" ? (
                    <VertexWifSettings
                        form={aiForm}
                        gcpIntegration={gcpIntegration}
                        pendingState={pendingState}
                        updateAiForm={updateAiForm}
                        onConnectGcp={onConnectGcp}
                        onDisconnectGcp={onDisconnectGcp}
                    />
                ) : null}

                <AIModelField
                    model={aiForm.model}
                    selectedProviderModels={selectedProviderModels}
                    onModelChange={(model) => updateAiForm("model", model)}
                />
            </div>
        </>
    )
}

function AIProviderField({
    provider,
    onProviderChange,
}: {
    provider: AiProvider
    onProviderChange: (provider: AiProvider) => void
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor="ai-provider">AI Provider</Label>
            <Select
                value={provider}
                onValueChange={(value) => {
                    if (!value || !isAiProvider(value)) return
                    onProviderChange(value)
                }}
            >
                <SelectTrigger id="ai-provider">
                    <SelectValue placeholder="Select provider">
                        {(value: string | null) => getSelectOptionLabel(AI_PROVIDERS, value)}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {AI_PROVIDERS.map((providerOption) => (
                        <SelectItem key={providerOption.value} value={providerOption.value}>
                            {providerOption.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    )
}

function AIApiKeyField({
    provider,
    apiKey,
    apiKeyMasked,
    editingKey,
    keyTested,
    pending,
    onApiKeyChange,
    onEditKey,
    onTestKey,
}: {
    provider: AiProvider
    apiKey: string
    apiKeyMasked: string | null
    editingKey: boolean
    keyTested: boolean | null
    pending: boolean
    onApiKeyChange: (apiKey: string) => void
    onEditKey: () => void
    onTestKey: () => void
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor="ai-key">API Key</Label>
            <div className="flex gap-2">
                <Input
                    id="ai-key"
                    type="password"
                    value={editingKey ? apiKey : apiKey || (apiKeyMasked ?? "")}
                    onChange={(event) => onApiKeyChange(event.target.value)}
                    placeholder="Enter API key"
                    disabled={!editingKey && !apiKey && !!apiKeyMasked}
                    className="flex-1"
                    name="ai-api-key"
                    autoComplete="off"
                />
                {apiKeyMasked && !apiKey && !editingKey ? (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onEditKey}
                        className="shrink-0"
                    >
                        Change Key
                    </Button>
                ) : (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onTestKey}
                        disabled={!apiKey.trim() || pending}
                    >
                        {pending ? (
                            <Loader2Icon
                                className="size-4 animate-spin motion-reduce:animate-none"
                                aria-hidden="true"
                            />
                        ) : keyTested === true ? (
                            <CheckIcon className="size-4 text-green-600" aria-hidden="true" />
                        ) : keyTested === false ? (
                            <XCircleIcon className="size-4 text-red-600" aria-hidden="true" />
                        ) : (
                            "Test"
                        )}
                    </Button>
                )}
            </div>
            {keyTested === true ? (
                <p className="text-xs text-green-600">API key is valid!</p>
            ) : null}
            {keyTested === false ? (
                <p className="text-xs text-red-600">API key is invalid. Please check and try again.</p>
            ) : null}
            <p className="text-xs text-muted-foreground">
                {provider === "gemini"
                    ? "Get your key from aistudio.google.com"
                    : "Create a Vertex AI API key in Google Cloud"}
            </p>
        </div>
    )
}

function VertexApiKeySettings({
    form,
    updateAiForm,
}: {
    form: AiConfigurationFormState
    updateAiForm: UpdateAiConfigurationForm
}) {
    return (
        <div className="space-y-4 rounded-lg border p-4">
            <div>
                <h3 className="text-sm font-medium">Vertex AI (API Key)</h3>
                <p className="text-xs text-muted-foreground">
                    Express mode works without project or location. Add them to use project-scoped endpoints.
                </p>
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
                <div className="text-sm">
                    {form.vertexUseExpress ? "Express mode active" : "Project-scoped mode"}
                </div>
                <div className="flex items-center gap-2">
                    <Label htmlFor="vertex-express" className="text-xs text-muted-foreground">
                        Use express mode
                    </Label>
                    <Switch
                        id="vertex-express"
                        checked={form.vertexUseExpress}
                        onCheckedChange={(checked) => updateAiForm("vertexUseExpress", checked)}
                    />
                </div>
            </div>
            {!form.vertexUseExpress ? (
                <div className="grid gap-3 md:grid-cols-2">
                    <div className="space-y-2">
                        <Label htmlFor="vertex-project-key">Project ID (optional)</Label>
                        <Input
                            id="vertex-project-key"
                            value={form.vertexProjectId}
                            onChange={(event) => updateAiForm("vertexProjectId", event.target.value)}
                            placeholder="your-gcp-project-id"
                            name="vertex-project-key"
                            autoComplete="off"
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="vertex-location-key">Location (optional)</Label>
                        <Select
                            value={form.vertexLocation}
                            onValueChange={(value) => updateAiForm("vertexLocation", value || "us")}
                        >
                            <SelectTrigger id="vertex-location-key">
                                <SelectValue>
                                    {(value: string | null) => getSelectOptionLabel(VERTEX_LOCATIONS, value)}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {VERTEX_LOCATIONS.map((location) => (
                                    <SelectItem key={location.value} value={location.value}>
                                        {location.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                </div>
            ) : null}
        </div>
    )
}

function VertexWifSettings({
    form,
    gcpIntegration,
    pendingState,
    updateAiForm,
    onConnectGcp,
    onDisconnectGcp,
}: {
    form: AiConfigurationFormState
    gcpIntegration: IntegrationStatus | undefined
    pendingState: {
        gcpConnect: boolean
        gcpDisconnect: boolean
    }
    updateAiForm: UpdateAiConfigurationForm
    onConnectGcp: () => void
    onDisconnectGcp: () => Promise<unknown>
}) {
    return (
        <div className="space-y-4 rounded-lg border p-4">
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-sm font-medium">Vertex AI (WIF)</h3>
                    <p className="text-xs text-muted-foreground">
                        Uses Workload Identity Federation, no long-lived keys stored.
                    </p>
                </div>
                {gcpIntegration ? (
                    <Badge variant="default">GCP Connected</Badge>
                ) : (
                    <Badge variant="secondary">GCP Not Connected</Badge>
                )}
            </div>

            <div className="flex items-center justify-between rounded-md border p-3">
                <div className="text-sm">
                    {gcpIntegration
                        ? `Connected as ${gcpIntegration.account_email ?? "Google account"}`
                        : "Connect a Google Cloud account to verify access."}
                </div>
                {gcpIntegration ? (
                    <ConfirmDialog
                        trigger={(
                            <Button variant="outline" size="sm" disabled={pendingState.gcpDisconnect}>
                                Disconnect…
                            </Button>
                        )}
                        title="Disconnect Google Cloud?"
                        description="Vertex AI (WIF) requests stop until an account is connected again."
                        confirmLabel="Disconnect"
                        errorFallback="Couldn't disconnect Google Cloud. Try again."
                        onConfirm={onDisconnectGcp}
                    />
                ) : (
                    <Button size="sm" onClick={onConnectGcp} disabled={pendingState.gcpConnect}>
                        {pendingState.gcpConnect ? (
                            <Loader2Icon
                                className="mr-2 size-4 animate-spin motion-reduce:animate-none"
                                aria-hidden="true"
                            />
                        ) : null}
                        Connect GCP
                    </Button>
                )}
            </div>

            <div className="space-y-2">
                <Label htmlFor="vertex-project">Project ID</Label>
                <Input
                    id="vertex-project"
                    value={form.vertexProjectId}
                    onChange={(event) => updateAiForm("vertexProjectId", event.target.value)}
                    placeholder="your-gcp-project-id"
                    name="vertex-project"
                    autoComplete="off"
                />
            </div>

            <div className="space-y-2">
                <Label htmlFor="vertex-location">Location</Label>
                <Select
                    value={form.vertexLocation}
                    onValueChange={(value) => updateAiForm("vertexLocation", value || "us")}
                >
                    <SelectTrigger id="vertex-location">
                        <SelectValue>
                            {(value: string | null) => getSelectOptionLabel(VERTEX_LOCATIONS, value)}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {VERTEX_LOCATIONS.map((location) => (
                            <SelectItem key={location.value} value={location.value}>
                                {location.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            <div className="space-y-2">
                <Label htmlFor="vertex-service-account">Service Account Email</Label>
                <Input
                    id="vertex-service-account"
                    value={form.vertexServiceAccount}
                    onChange={(event) => updateAiForm("vertexServiceAccount", event.target.value)}
                    placeholder="vertex-sa@project.iam.gserviceaccount.com"
                    name="vertex-service-account"
                    autoComplete="off"
                />
            </div>

            <div className="space-y-2">
                <Label htmlFor="vertex-audience">Workload Identity Audience</Label>
                <Input
                    id="vertex-audience"
                    value={form.vertexAudience}
                    onChange={(event) => updateAiForm("vertexAudience", event.target.value)}
                    placeholder="//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/provider"
                    name="vertex-audience"
                    autoComplete="off"
                />
                <p className="text-xs text-muted-foreground">
                    Use the provider resource name or full audience from the Workload Identity Provider.
                </p>
            </div>
        </div>
    )
}

function AIModelField({
    model,
    selectedProviderModels,
    onModelChange,
}: {
    model: string
    selectedProviderModels: ReadonlyArray<string>
    onModelChange: (model: string) => void
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor="ai-model">Model</Label>
            <Select value={model} onValueChange={(value) => onModelChange(value || "")}>
                <SelectTrigger id="ai-model">
                    <SelectValue placeholder="Select model (optional)">
                        {(value: string | null) =>
                            value
                                ? getSelectOptionLabel(
                                    selectedProviderModels.map((selectedModel) => ({
                                        value: selectedModel,
                                        label: selectedModel,
                                    })),
                                    value,
                                )
                                : ""
                        }
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {selectedProviderModels.map((selectedModel) => (
                        <SelectItem key={selectedModel} value={selectedModel}>
                            {selectedModel}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
                Leave empty to use the default model
            </p>
        </div>
    )
}

function AISaveButton({
    pending,
    saved,
    disabled,
    onSave,
}: {
    pending: boolean
    saved: boolean
    disabled: boolean
    onSave: () => void
}) {
    return (
        <Button onClick={onSave} disabled={pending || disabled}>
            {pending ? (
                <>
                    <Loader2Icon
                        className="animate-spin motion-reduce:animate-none"
                        aria-hidden="true"
                    />
                    Saving…
                </>
            ) : saved ? (
                <>
                    <CheckIcon aria-hidden="true" />
                    Saved
                </>
            ) : (
                "Save AI Configuration"
            )}
        </Button>
    )
}

/** DialogBody and DialogFooter of the Email Configuration dialog. */
function EmailConfigurationSection() {
    const { data: settings, isLoading } = useResendSettings()

    return (
        <EmailConfigurationSectionContent
            key={settings ? "loaded" : "loading"}
            settings={settings}
            isLoading={isLoading}
        />
    )
}

function EmailConfigurationSectionContent({
    settings,
    isLoading,
}: {
    settings: ReturnType<typeof useResendSettings>["data"]
    isLoading: boolean
}) {
    const updateSettings = useUpdateResendSettings()
    const testKey = useTestResendKey()
    const rotateWebhook = useRotateWebhook()
    const [emailForm, setEmailForm] = useState<EmailConfigurationFormState>(
        () => createEmailConfigurationFormState(settings),
    )
    const [emailUi, setEmailUi] = useState<EmailConfigurationUiState>({
        keyTested: null,
        saved: false,
        isEditingKey: false,
        hasUserEdited: false,
    })
    const { data: eligibleSenders, isLoading: eligibleSendersLoading } = useEligibleSenders(emailForm.provider === "gmail")

    const updateEmailForm = <K extends keyof EmailConfigurationFormState>(
        field: K,
        value: EmailConfigurationFormState[K],
        markEdited = false,
    ) => {
        setEmailForm((current) => ({ ...current, [field]: value }))
        if (markEdited) {
            setEmailUi((current) => ({ ...current, hasUserEdited: true }))
        }
    }

    const handleProviderChange = (value: "resend" | "gmail" | "") => {
        setEmailForm((current) =>
            changeEmailConfigurationProvider(current, value),
        )
        setEmailUi((current) => ({
            ...current,
            hasUserEdited: true,
            saved: false,
            keyTested: null,
            isEditingKey: value !== "resend" ? false : current.isEditingKey,
        }))
    }

    const handleTestKey = async () => {
        if (!emailForm.apiKey.trim()) return
        setEmailUi((current) => ({ ...current, keyTested: null }))
        try {
            const result = await testKey.mutateAsync(emailForm.apiKey)
            setEmailUi((current) => ({ ...current, keyTested: result }))
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't test the API key") ?? "Couldn't test the API key"
            setEmailUi((current) => ({
                ...current,
                keyTested: {
                    valid: false,
                    error: message,
                    verified_domains: [],
                    permission_limited: false,
                    warning: null,
                },
            }))
            toast.error(message)
        }
    }

    const handleSave = async () => {
        const update: ResendSettingsUpdate = {
            email_provider: emailForm.provider,
        }

        if (settings?.current_version !== undefined) {
            update.expected_version = settings.current_version
        }

        if (emailForm.provider === "resend") {
            if (emailForm.apiKey.trim()) {
                update.api_key = emailForm.apiKey
            }
            if (emailForm.clearRateLimitGroup) {
                update.rate_limit_group_token = ""
            } else if (
                emailForm.rateLimitGroupEnabled &&
                (!emailForm.rateLimitGroupConfigured ||
                    emailForm.replaceRateLimitGroupToken) &&
                emailForm.rateLimitGroupToken.trim()
            ) {
                update.rate_limit_group_token = emailForm.rateLimitGroupToken.trim()
            }
            update.verified_domain = emailForm.verifiedDomain.trim()
            update.from_email = emailForm.fromEmail
            update.from_name = emailForm.fromName
            update.reply_to_email = emailForm.replyTo
            if (emailForm.clearWebhookTracking) {
                update.webhook_signing_secret = ""
            } else if (emailForm.webhookSigningSecret.trim()) {
                update.webhook_signing_secret = emailForm.webhookSigningSecret.trim()
            }
        } else if (emailForm.provider === "gmail") {
            update.default_sender_user_id = emailForm.defaultSender || null
        }

        try {
            const savedSettings = await updateSettings.mutateAsync(update)
            setEmailForm((current) => ({
                ...current,
                apiKey: "",
                rateLimitGroupConfigured:
                    savedSettings?.rate_limit_group_configured ??
                    current.rateLimitGroupConfigured,
                rateLimitGroupEnabled:
                    savedSettings?.rate_limit_group_configured ??
                    current.rateLimitGroupEnabled,
                rateLimitGroupToken: "",
                replaceRateLimitGroupToken: false,
                clearRateLimitGroup: false,
                webhookTrackingEnabled:
                    savedSettings?.webhook_signing_secret_configured ??
                    current.webhookTrackingEnabled,
                clearWebhookTracking: false,
                replaceWebhookSigningSecret: false,
                webhookSigningSecret: "",
            }))
            setEmailUi((current) => ({
                ...current,
                keyTested: null,
                isEditingKey: false,
                hasUserEdited: false,
                saved: true,
            }))
            toast.success("Email configuration saved")
            setTimeout(() => {
                setEmailUi((current) => ({ ...current, saved: false }))
            }, 2000)
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't save email configuration")
            if (message) toast.error(message)
        }
    }

    // Runs from the rotate confirmation, which shows a failure inline and stays open.
    const handleRotateWebhook = async () => {
        await rotateWebhook.mutateAsync()
        toast.success("Webhook URL rotated. Update Resend to use the new URL.")
    }

    const hasResendKey = Boolean(emailForm.apiKey.trim() || settings?.api_key_masked)
    const newResendKeyValidated = Boolean(
        !emailForm.apiKey.trim() || emailUi.keyTested?.valid,
    )
    const hasVerifiedDomain = Boolean(emailForm.verifiedDomain.trim())
    const hasFromEmail = Boolean(emailForm.fromEmail.trim())
    const hasGmailSender = Boolean(emailForm.defaultSender)
    const normalizedRateLimitGroupToken = emailForm.rateLimitGroupToken.trim()
    const rateLimitGroupTokenInvalid = Boolean(
        normalizedRateLimitGroupToken &&
        (normalizedRateLimitGroupToken.length < 32 ||
            normalizedRateLimitGroupToken.length > 256),
    )
    const rateLimitGroupReady = Boolean(
        emailForm.provider !== "resend" ||
        !emailForm.rateLimitGroupEnabled ||
        (emailForm.rateLimitGroupConfigured &&
            !emailForm.replaceRateLimitGroupToken &&
            !emailForm.clearRateLimitGroup) ||
        normalizedRateLimitGroupToken,
    )
    const normalizedVerifiedDomain = emailForm.verifiedDomain.trim().toLowerCase()
    const normalizedFromEmail = emailForm.fromEmail.trim().toLowerCase()
    const senderIdentityChanged = Boolean(
        emailForm.provider === "resend" &&
        (normalizedVerifiedDomain !==
            (settings?.verified_domain?.trim().toLowerCase() ?? "") ||
            normalizedFromEmail !==
            (settings?.from_email?.trim().toLowerCase() ?? "")),
    )
    const storedCredentialRetestRequired = Boolean(
        settings?.api_key_masked &&
        senderIdentityChanged &&
        !emailUi.keyTested?.valid,
    )
    const testedDomains = emailUi.keyTested?.verified_domains ?? []
    const testedDomainMismatch = Boolean(
        emailUi.keyTested?.valid &&
        !emailUi.keyTested.permission_limited &&
        !testedDomains.includes(normalizedVerifiedDomain),
    )
    const webhookTrackingReady = Boolean(
        emailForm.provider !== "resend" ||
        !emailForm.webhookTrackingEnabled ||
        (settings?.webhook_signing_secret_configured &&
            !emailForm.replaceWebhookSigningSecret) ||
        emailForm.webhookSigningSecret.trim(),
    )
    const resendReady =
        emailForm.provider !== "resend" ||
        (hasResendKey &&
            newResendKeyValidated &&
            hasVerifiedDomain &&
            hasFromEmail &&
            !storedCredentialRetestRequired &&
            !testedDomainMismatch)
    const gmailReady = emailForm.provider !== "gmail" || hasGmailSender
    const canSave =
        Boolean(emailForm.provider) &&
        resendReady &&
        gmailReady &&
        rateLimitGroupReady &&
        !rateLimitGroupTokenInvalid &&
        webhookTrackingReady
    const showMaskedKey = Boolean(settings?.api_key_masked) && !emailUi.isEditingKey && !emailForm.apiKey

    if (isLoading) {
        return <IntegrationDialogLoadingState />
    }

    return (
        <>
            <DialogBody>
                <EmailSettingsFields
                    form={emailForm}
                    ui={emailUi}
                    settings={settings}
                    eligibleSenders={eligibleSenders ?? []}
                    eligibleSendersLoading={eligibleSendersLoading}
                    showMaskedKey={showMaskedKey}
                    storedCredentialRetestRequired={storedCredentialRetestRequired}
                    rateLimitGroupTokenInvalid={rateLimitGroupTokenInvalid}
                    pendingState={{
                        keyTest: testKey.isPending,
                        webhookRotate: rotateWebhook.isPending,
                    }}
                    onProviderChange={handleProviderChange}
                    updateEmailForm={updateEmailForm}
                    onApiKeyChange={(apiKey) => {
                        updateEmailForm("apiKey", apiKey, true)
                        setEmailUi((current) => ({
                            ...current,
                            keyTested: null,
                            isEditingKey: true,
                        }))
                    }}
                    onEditKey={() => {
                        updateEmailForm("apiKey", "", true)
                        setEmailUi((current) => ({
                            ...current,
                            isEditingKey: true,
                            keyTested: null,
                        }))
                    }}
                    onCancelKeyEdit={() => {
                        updateEmailForm("apiKey", "")
                        setEmailUi((current) => ({
                            ...current,
                            isEditingKey: false,
                            keyTested: null,
                        }))
                    }}
                    onTestKey={handleTestKey}
                    onRotateWebhook={handleRotateWebhook}
                />
            </DialogBody>
            <DialogFooter
                start={(
                    <Button variant="ghost" render={<Link href="/settings/integrations/email" />}>
                        <ActivityIcon aria-hidden="true" />
                        View email operations
                    </Button>
                )}
            >
                <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
                <EmailSaveButton
                    pending={updateSettings.isPending}
                    saved={emailUi.saved}
                    disabled={!canSave}
                    onSave={() => {
                        void handleSave()
                    }}
                />
            </DialogFooter>
        </>
    )
}

type UpdateEmailConfigurationForm = <K extends keyof EmailConfigurationFormState>(
    field: K,
    value: EmailConfigurationFormState[K],
    markEdited?: boolean,
) => void

function EmailSettingsFields({
    form,
    ui,
    settings,
    eligibleSenders,
    eligibleSendersLoading,
    showMaskedKey,
    storedCredentialRetestRequired,
    rateLimitGroupTokenInvalid,
    pendingState,
    onProviderChange,
    updateEmailForm,
    onApiKeyChange,
    onEditKey,
    onCancelKeyEdit,
    onTestKey,
    onRotateWebhook,
}: {
    form: EmailConfigurationFormState
    ui: EmailConfigurationUiState
    settings: ResendSettings | undefined
    eligibleSenders: EligibleSender[]
    eligibleSendersLoading: boolean
    showMaskedKey: boolean
    storedCredentialRetestRequired: boolean
    rateLimitGroupTokenInvalid: boolean
    pendingState: {
        keyTest: boolean
        webhookRotate: boolean
    }
    onProviderChange: (provider: "resend" | "gmail" | "") => void
    updateEmailForm: UpdateEmailConfigurationForm
    onApiKeyChange: (apiKey: string) => void
    onEditKey: () => void
    onCancelKeyEdit: () => void
    onTestKey: () => void
    onRotateWebhook: () => Promise<void>
}) {
    return (
        <div className="space-y-6">
            <EmailProviderField
                provider={form.provider}
                onProviderChange={onProviderChange}
            />

            {form.provider === "resend" ? (
                <ResendConfigurationFields
                    form={form}
                    ui={ui}
                    settings={settings}
                    showMaskedKey={showMaskedKey}
                    storedCredentialRetestRequired={storedCredentialRetestRequired}
                    rateLimitGroupTokenInvalid={rateLimitGroupTokenInvalid}
                    pendingState={pendingState}
                    updateEmailForm={updateEmailForm}
                    onApiKeyChange={onApiKeyChange}
                    onEditKey={onEditKey}
                    onCancelKeyEdit={onCancelKeyEdit}
                    onTestKey={onTestKey}
                    onRotateWebhook={onRotateWebhook}
                />
            ) : null}

            {form.provider === "gmail" ? (
                <GmailConfigurationFields
                    defaultSender={form.defaultSender}
                    eligibleSenders={eligibleSenders}
                    eligibleSendersLoading={eligibleSendersLoading}
                    settings={settings}
                    onDefaultSenderChange={(defaultSender) =>
                        updateEmailForm("defaultSender", defaultSender, true)
                    }
                />
            ) : null}
        </div>
    )
}

function EmailProviderField({
    provider,
    onProviderChange,
}: {
    provider: EmailConfigurationFormState["provider"]
    onProviderChange: (provider: "resend" | "gmail" | "") => void
}) {
    return (
        <div className="space-y-3">
            <Label htmlFor="email-provider">Email Provider</Label>
            <RadioGroup
                value={provider}
                onValueChange={(value) => onProviderChange(value as "resend" | "gmail" | "")}
                className="flex flex-col gap-3"
                id="email-provider"
                aria-label="Email provider"
            >
                <div className="flex items-center gap-2">
                    <RadioGroupItem value="resend" id="provider-resend" />
                    <Label htmlFor="provider-resend" className="cursor-pointer">
                        <span className="font-medium">Resend</span>
                        <span className="ml-2 text-xs text-muted-foreground">(Recommended)</span>
                    </Label>
                </div>
                <div className="flex items-center gap-2">
                    <RadioGroupItem value="gmail" id="provider-gmail" />
                    <Label htmlFor="provider-gmail" className="cursor-pointer">
                        <span className="font-medium">Gmail</span>
                        <span className="ml-2 text-xs text-muted-foreground">(Org admin account)</span>
                    </Label>
                </div>
            </RadioGroup>
        </div>
    )
}

function ResendConfigurationFields({
    form,
    ui,
    settings,
    showMaskedKey,
    storedCredentialRetestRequired,
    rateLimitGroupTokenInvalid,
    pendingState,
    updateEmailForm,
    onApiKeyChange,
    onEditKey,
    onCancelKeyEdit,
    onTestKey,
    onRotateWebhook,
}: {
    form: EmailConfigurationFormState
    ui: EmailConfigurationUiState
    settings: ResendSettings | undefined
    showMaskedKey: boolean
    storedCredentialRetestRequired: boolean
    rateLimitGroupTokenInvalid: boolean
    pendingState: {
        keyTest: boolean
        webhookRotate: boolean
    }
    updateEmailForm: UpdateEmailConfigurationForm
    onApiKeyChange: (apiKey: string) => void
    onEditKey: () => void
    onCancelKeyEdit: () => void
    onTestKey: () => void
    onRotateWebhook: () => Promise<void>
}) {
    return (
        <div className="space-y-4 rounded-lg border p-4">
            <h3 className="text-sm font-medium">Resend Configuration</h3>

            <ResendApiKeyField
                apiKey={form.apiKey}
                apiKeyMasked={settings?.api_key_masked ?? null}
                keyTested={ui.keyTested}
                editingKey={ui.isEditingKey}
                showMaskedKey={showMaskedKey}
                pending={pendingState.keyTest}
                onApiKeyChange={onApiKeyChange}
                onEditKey={onEditKey}
                onCancelKeyEdit={onCancelKeyEdit}
                onTestKey={onTestKey}
            />

            {storedCredentialRetestRequired ? (
                <Alert
                    id="resend-sender-retest-alert"
                    variant="destructive"
                >
                    <AlertTriangleIcon aria-hidden="true" />
                    <AlertTitle>Re-test sender access</AlertTitle>
                    <AlertDescription>
                        These sender changes are not verified. Re-enter the
                        stored Resend credential with Change Key, then test it
                        before saving.
                    </AlertDescription>
                </Alert>
            ) : null}

            <ResendVerifiedDomainField
                value={form.verifiedDomain}
                keyTested={ui.keyTested}
                storedCredentialRetestRequired={storedCredentialRetestRequired}
                onChange={(verifiedDomain) =>
                    updateEmailForm("verifiedDomain", verifiedDomain, true)
                }
            />

            <div className="space-y-2">
                <Label htmlFor="from-email">From Email</Label>
                <Input
                    id="from-email"
                    type="email"
                    value={form.fromEmail}
                    onChange={(event) => updateEmailForm("fromEmail", event.target.value, true)}
                    aria-invalid={storedCredentialRetestRequired}
                    aria-describedby={
                        storedCredentialRetestRequired
                            ? "resend-sender-retest-alert"
                            : undefined
                    }
                    placeholder={
                        form.verifiedDomain
                            ? `no-reply@${form.verifiedDomain}`
                            : "no-reply@yourdomain.com"
                    }
                    name="from-email"
                    autoComplete="email"
                />
                <p className="text-xs text-muted-foreground">
                    Enter the complete sender address. Its domain must match the
                    verified domain above.
                </p>
            </div>

            <div className="space-y-2">
                <Label htmlFor="from-name">From Name (optional)</Label>
                <Input
                    id="from-name"
                    value={form.fromName}
                    onChange={(event) => updateEmailForm("fromName", event.target.value, true)}
                    placeholder="Your Company Name"
                    name="from-name"
                    autoComplete="organization"
                />
            </div>

            <div className="space-y-2">
                <Label htmlFor="reply-to">Reply-To Email (optional)</Label>
                <Input
                    id="reply-to"
                    type="email"
                    value={form.replyTo}
                    onChange={(event) => updateEmailForm("replyTo", event.target.value, true)}
                    placeholder="support@yourdomain.com"
                    name="reply-to"
                    autoComplete="email"
                />
            </div>

            <ResendWebhookTrackingField
                form={form}
                settings={settings}
                pending={pendingState.webhookRotate}
                updateEmailForm={updateEmailForm}
                onRotateWebhook={onRotateWebhook}
            />

            <ResendRateLimitGroupField
                form={form}
                invalid={rateLimitGroupTokenInvalid}
                updateEmailForm={updateEmailForm}
            />
        </div>
    )
}

function ResendWebhookTrackingField({
    form,
    settings,
    pending,
    updateEmailForm,
    onRotateWebhook,
}: {
    form: EmailConfigurationFormState
    settings: ResendSettings | undefined
    pending: boolean
    updateEmailForm: UpdateEmailConfigurationForm
    onRotateWebhook: () => Promise<void>
}) {
    const [disableTrackingDialogOpen, setDisableTrackingDialogOpen] =
        useState(false)
    const webhookTrackingConfigured =
        settings?.webhook_signing_secret_configured ?? false
    const status = form.clearWebhookTracking
        ? { label: "Pending disable", variant: "secondary" as const }
        : form.webhookTrackingEnabled && webhookTrackingConfigured
          ? { label: "Tracking enabled", variant: "default" as const }
          : form.webhookTrackingEnabled
            ? { label: "Setup required", variant: "secondary" as const }
            : { label: "Optional", variant: "outline" as const }

    const handleTrackingChange = (checked: boolean) => {
        if (!checked && webhookTrackingConfigured && !form.clearWebhookTracking) {
            setDisableTrackingDialogOpen(true)
            return
        }

        updateEmailForm("webhookTrackingEnabled", checked, true)
        if (checked) {
            updateEmailForm("clearWebhookTracking", false)
        } else {
            updateEmailForm("replaceWebhookSigningSecret", false)
            updateEmailForm("webhookSigningSecret", "")
        }
    }

    const confirmDisableTracking = () => {
        updateEmailForm("webhookTrackingEnabled", false, true)
        updateEmailForm("clearWebhookTracking", true)
        updateEmailForm("replaceWebhookSigningSecret", false)
        updateEmailForm("webhookSigningSecret", "")
        setDisableTrackingDialogOpen(false)
    }

    return (
        <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                    <Checkbox
                        id="resend-webhook-tracking"
                        checked={form.webhookTrackingEnabled}
                        onCheckedChange={(checked) =>
                            handleTrackingChange(checked === true)
                        }
                    />
                    <div className="space-y-1">
                        <Label
                            htmlFor="resend-webhook-tracking"
                            className="cursor-pointer"
                        >
                            Enable Resend webhook tracking (optional)
                        </Label>
                        <p className="text-xs text-muted-foreground">
                            Track delivery, opens, and clicks with verified Resend events.
                        </p>
                    </div>
                </div>
                <Badge variant={status.variant}>{status.label}</Badge>
            </div>

            {form.webhookTrackingEnabled ? (
                <div className="space-y-3">
                    {settings?.webhook_url ? (
                        <ResendWebhookUrlField
                            webhookUrl={settings.webhook_url}
                            pending={pending}
                            onRotateWebhook={onRotateWebhook}
                        />
                    ) : null}

                    {webhookTrackingConfigured &&
                    !form.replaceWebhookSigningSecret ? (
                        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-background p-3">
                            <p className="text-sm text-muted-foreground">
                                Signing secret is stored securely.
                            </p>
                            <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() =>
                                    updateEmailForm(
                                        "replaceWebhookSigningSecret",
                                        true,
                                        true,
                                    )
                                }
                            >
                                Replace secret
                            </Button>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            <Label htmlFor="resend-webhook-secret">
                                Webhook Signing Secret
                            </Label>
                            <Input
                                id="resend-webhook-secret"
                                type="password"
                                value={form.webhookSigningSecret}
                                onChange={(event) =>
                                    updateEmailForm(
                                        "webhookSigningSecret",
                                        event.target.value,
                                        true,
                                    )
                                }
                                placeholder="whsec_…"
                                name="resend-webhook-signing-secret"
                                autoComplete="off"
                            />
                            <p className="text-xs text-muted-foreground">
                                Paste the signing secret from Resend. It is encrypted
                                and never shown again.
                            </p>
                            {webhookTrackingConfigured ? (
                                <Button
                                    type="button"
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => {
                                        updateEmailForm("webhookSigningSecret", "")
                                        updateEmailForm(
                                            "replaceWebhookSigningSecret",
                                            false,
                                            true,
                                        )
                                    }}
                                >
                                    Cancel replacement
                                </Button>
                            ) : null}
                        </div>
                    )}
                </div>
            ) : form.clearWebhookTracking ? (
                <Alert>
                    <AlertTriangleIcon aria-hidden="true" />
                    <AlertTitle>Tracking pending disable</AlertTitle>
                    <AlertDescription>
                        Tracking will be disabled when you save. Sending email is
                        unaffected.
                    </AlertDescription>
                </Alert>
            ) : null}

            <AlertDialog
                open={disableTrackingDialogOpen}
                onOpenChange={setDisableTrackingDialogOpen}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Disable webhook tracking?</AlertDialogTitle>
                        <AlertDialogDescription>
                            Delivery, open, and click events will stop being verified
                            after you save. Sending email through Resend will continue.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Keep tracking</AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            onClick={confirmDisableTracking}
                        >
                            Disable tracking
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}

function ResendRateLimitGroupField({
    form,
    invalid,
    updateEmailForm,
}: {
    form: EmailConfigurationFormState
    invalid: boolean
    updateEmailForm: UpdateEmailConfigurationForm
}) {
    const [disableDialogOpen, setDisableDialogOpen] = useState(false)
    const status = form.clearRateLimitGroup
        ? { label: "Pending disable", variant: "secondary" as const }
        : form.rateLimitGroupEnabled && form.rateLimitGroupConfigured
          ? { label: "Group configured", variant: "default" as const }
          : form.rateLimitGroupEnabled
            ? { label: "Setup required", variant: "secondary" as const }
            : { label: "Optional", variant: "outline" as const }

    const handleEnabledChange = (checked: boolean) => {
        if (
            !checked &&
            form.rateLimitGroupConfigured &&
            !form.clearRateLimitGroup
        ) {
            setDisableDialogOpen(true)
            return
        }

        updateEmailForm("rateLimitGroupEnabled", checked, true)
        if (checked) {
            updateEmailForm("clearRateLimitGroup", false)
            return
        }

        updateEmailForm("replaceRateLimitGroupToken", false)
        updateEmailForm("rateLimitGroupToken", "")
    }

    const confirmDisable = () => {
        updateEmailForm("rateLimitGroupEnabled", false, true)
        updateEmailForm("clearRateLimitGroup", true)
        updateEmailForm("replaceRateLimitGroupToken", false)
        updateEmailForm("rateLimitGroupToken", "")
        setDisableDialogOpen(false)
    }

    return (
        <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                    <Checkbox
                        id="resend-rate-limit-group-enabled"
                        checked={form.rateLimitGroupEnabled}
                        onCheckedChange={(checked) =>
                            handleEnabledChange(checked === true)
                        }
                    />
                    <div className="space-y-1">
                        <Label
                            htmlFor="resend-rate-limit-group-enabled"
                            className="cursor-pointer"
                        >
                            Use shared Resend team rate-limit group (optional)
                        </Label>
                        <p className="text-xs text-muted-foreground">
                            Coordinate rate limiting across API keys in the same
                            Resend team.
                        </p>
                    </div>
                </div>
                <Badge variant={status.variant}>{status.label}</Badge>
            </div>

            {form.rateLimitGroupEnabled ? (
                <div className="space-y-3">
                    {form.rateLimitGroupConfigured &&
                    !form.replaceRateLimitGroupToken ? (
                        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-background p-3">
                            <p className="text-sm text-muted-foreground">
                                Shared group token is stored securely.
                            </p>
                            <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() =>
                                    updateEmailForm(
                                        "replaceRateLimitGroupToken",
                                        true,
                                        true,
                                    )
                                }
                            >
                                Replace token
                            </Button>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            <Label htmlFor="resend-rate-limit-group">
                                Resend team rate-limit group token
                            </Label>
                            <Input
                                id="resend-rate-limit-group"
                                name="resend-rate-limit-group"
                                type="password"
                                autoComplete="off"
                                value={form.rateLimitGroupToken}
                                onChange={(event) =>
                                    updateEmailForm(
                                        "rateLimitGroupToken",
                                        event.target.value,
                                        true,
                                    )
                                }
                                placeholder="Enter a shared token with at least 32 characters"
                                aria-invalid={invalid}
                                aria-describedby="resend-rate-limit-group-help"
                            />
                            {form.rateLimitGroupConfigured ? (
                                <Button
                                    type="button"
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => {
                                        updateEmailForm("rateLimitGroupToken", "")
                                        updateEmailForm(
                                            "replaceRateLimitGroupToken",
                                            false,
                                            true,
                                        )
                                    }}
                                >
                                    Cancel replacement
                                </Button>
                            ) : null}
                        </div>
                    )}

                    <div
                        id="resend-rate-limit-group-help"
                        className="space-y-1 text-xs"
                    >
                        <p className="text-muted-foreground">
                            Use the same token for every API key in the same Resend
                            team. The default limit is 5 requests per second shared
                            across the team.
                        </p>
                        {invalid ? (
                            <p className="text-destructive">
                                Token must be between 32 and 256 characters.
                            </p>
                        ) : null}
                    </div>
                </div>
            ) : null}

            {form.clearRateLimitGroup ? (
                <Alert>
                    <AlertTriangleIcon aria-hidden="true" />
                    <AlertTitle>Shared group pending disable</AlertTitle>
                    <AlertDescription>
                        The saved rate-limit group will be removed when you save.
                    </AlertDescription>
                </Alert>
            ) : null}

            <AlertDialog
                open={disableDialogOpen}
                onOpenChange={setDisableDialogOpen}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>
                            Disable the shared rate-limit group?
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            After you save, this organization will no longer share
                            one admission limit with other API keys in the same
                            Resend team. Email sending will remain available.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Keep shared group</AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            onClick={confirmDisable}
                        >
                            Disable shared group
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}

function ResendApiKeyField({
    apiKey,
    apiKeyMasked,
    keyTested,
    editingKey,
    showMaskedKey,
    pending,
    onApiKeyChange,
    onEditKey,
    onCancelKeyEdit,
    onTestKey,
}: {
    apiKey: string
    apiKeyMasked: string | null
    keyTested: EmailConfigurationUiState["keyTested"]
    editingKey: boolean
    showMaskedKey: boolean
    pending: boolean
    onApiKeyChange: (apiKey: string) => void
    onEditKey: () => void
    onCancelKeyEdit: () => void
    onTestKey: () => void
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor="resend-key">API Key</Label>
            <div className="flex gap-2">
                <Input
                    id="resend-key"
                    type="password"
                    value={showMaskedKey ? apiKeyMasked ?? "" : apiKey}
                    onChange={(event) => onApiKeyChange(event.target.value)}
                    placeholder="re_…"
                    disabled={showMaskedKey}
                    className="flex-1"
                    name="resend-api-key"
                    autoComplete="off"
                />
                {showMaskedKey ? (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onEditKey}
                        className="shrink-0"
                    >
                        Change Key
                    </Button>
                ) : (
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onTestKey}
                            disabled={!apiKey.trim() || pending}
                        >
                            {pending ? (
                                <Loader2Icon
                                    className="size-4 animate-spin motion-reduce:animate-none"
                                    aria-hidden="true"
                                />
                            ) : keyTested?.valid ? (
                                <CheckIcon className="size-4 text-green-600" aria-hidden="true" />
                            ) : keyTested !== null ? (
                                <XCircleIcon className="size-4 text-red-600" aria-hidden="true" />
                            ) : (
                                "Test"
                            )}
                        </Button>
                        {apiKeyMasked && editingKey ? (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={onCancelKeyEdit}
                            >
                                Cancel
                            </Button>
                        ) : null}
                    </div>
                )}
            </div>
            <ResendVerifiedDomainBanner keyTested={keyTested} />
            <p className="text-xs text-muted-foreground">
                Testing checks Resend domain access only and never sends an
                email. Full access keys can list verified domains; Sending
                access keys may require manual domain entry. Test a new key
                before saving. Get your key from{" "}
                <a
                    href="https://resend.com/api-keys"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                >
                    resend.com/api-keys
                </a>
                , or{" "}
                <a
                    href="https://resend.com/docs/dashboard/api-keys/introduction"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                >
                    review Resend key permissions
                </a>
                .
            </p>
        </div>
    )
}

function ResendVerifiedDomainBanner({
    keyTested,
}: {
    keyTested: EmailConfigurationUiState["keyTested"]
}) {
    if (keyTested?.valid && keyTested.permission_limited) {
        return (
            <Alert>
                <AlertTriangleIcon aria-hidden="true" />
                <AlertTitle>Domain access is permission-limited</AlertTitle>
                <AlertDescription className="space-y-1">
                    <p>{keyTested.warning}</p>
                    <p>
                        Enter a domain you have already verified in Resend. This
                        app cannot confirm domain verification with this key.
                    </p>
                </AlertDescription>
            </Alert>
        )
    }

    if (keyTested?.valid) {
        return (
            <Alert>
                <CheckCircleIcon aria-hidden="true" />
                <AlertTitle>API key accepted</AlertTitle>
                <AlertDescription className="space-y-1">
                    <p>
                        No domain was selected automatically. Enter one of the
                        verified domains in the field below.
                    </p>
                    <p>
                        {keyTested.verified_domains.length > 0
                            ? `Available verified domains: ${keyTested.verified_domains.join(", ")}`
                            : "No verified domains were returned for this account."}
                    </p>
                </AlertDescription>
            </Alert>
        )
    }

    if (keyTested && !keyTested.valid) {
        return (
            <Alert variant="destructive">
                <XCircleIcon aria-hidden="true" />
                <AlertTitle>API key is invalid</AlertTitle>
                <AlertDescription>
                    {keyTested.error || "Resend rejected this API key."}
                </AlertDescription>
            </Alert>
        )
    }

    return null
}

function ResendVerifiedDomainField({
    value,
    keyTested,
    storedCredentialRetestRequired,
    onChange,
}: {
    value: string
    keyTested: EmailConfigurationUiState["keyTested"]
    storedCredentialRetestRequired: boolean
    onChange: (verifiedDomain: string) => void
}) {
    const normalizedValue = value.trim().toLowerCase()
    const domainRejectedByFullAccessKey = Boolean(
        normalizedValue &&
        keyTested?.valid &&
        !keyTested.permission_limited &&
        !keyTested.verified_domains.includes(normalizedValue),
    )

    return (
        <div className="space-y-2">
            <Label htmlFor="resend-verified-domain">Verified domain</Label>
            <Input
                id="resend-verified-domain"
                value={value}
                onChange={(event) => onChange(event.target.value)}
                placeholder="example.com"
                name="resend-verified-domain"
                autoComplete="off"
                aria-invalid={
                    storedCredentialRetestRequired ||
                    domainRejectedByFullAccessKey
                }
                aria-describedby={
                    storedCredentialRetestRequired
                        ? "resend-verified-domain-help resend-sender-retest-alert"
                        : "resend-verified-domain-help"
                }
            />
            <p
                id="resend-verified-domain-help"
                className="text-xs text-muted-foreground"
            >
                Enter the domain exactly as it appears in Resend. This value is
                never selected automatically.
            </p>
            {domainRejectedByFullAccessKey ? (
                <p className="text-xs font-medium text-destructive" role="alert">
                    This domain is not in the verified domains returned for this
                    API key.
                </p>
            ) : null}
        </div>
    )
}

function ResendWebhookUrlField({
    webhookUrl,
    pending,
    onRotateWebhook,
}: {
    webhookUrl: string
    pending: boolean
    onRotateWebhook: () => Promise<void>
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor="resend-webhook-url">Webhook URL</Label>
            <div className="flex min-w-0 gap-2">
                <CopyField
                    id="resend-webhook-url"
                    value={webhookUrl}
                    copyLabel="Copy webhook URL"
                    className="flex-1"
                />
                <ConfirmDialog
                    trigger={(
                        <Button
                            variant="outline"
                            size="icon"
                            disabled={pending}
                            aria-label="Rotate webhook URL"
                        >
                            {pending ? (
                                <Loader2Icon
                                    className="animate-spin motion-reduce:animate-none"
                                    aria-hidden="true"
                                />
                            ) : (
                                <RotateCwIcon aria-hidden="true" />
                            )}
                        </Button>
                    )}
                    title="Rotate webhook URL?"
                    description="The current URL stops accepting Resend events. Update the endpoint in Resend after rotating."
                    confirmLabel="Rotate URL"
                    errorFallback="Couldn't rotate the webhook URL. Try again."
                    onConfirm={onRotateWebhook}
                />
            </div>
            <p className="text-xs text-muted-foreground">
                Create a webhook endpoint in Resend pointing to this URL and subscribe to: email.delivered, email.bounced, email.complained, email.opened, email.clicked.
            </p>
        </div>
    )
}

function GmailConfigurationFields({
    defaultSender,
    eligibleSenders,
    eligibleSendersLoading,
    settings,
    onDefaultSenderChange,
}: {
    defaultSender: string
    eligibleSenders: EligibleSender[]
    eligibleSendersLoading: boolean
    settings: ResendSettings | undefined
    onDefaultSenderChange: (defaultSender: string) => void
}) {
    return (
        <div className="space-y-4 rounded-lg border p-4">
            <h3 className="text-sm font-medium">Gmail Configuration</h3>

            <div className="space-y-2">
                <Label htmlFor="gmail-sender">Default Sender</Label>
                <Select
                    value={defaultSender}
                    onValueChange={(value) => onDefaultSenderChange(value ?? "")}
                >
                    <SelectTrigger id="gmail-sender">
                        <SelectValue placeholder={eligibleSendersLoading ? "Loading senders…" : "Select admin with Gmail connected"}>
                            {(value: string | null) => getEligibleSenderLabel(eligibleSenders, value)}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {eligibleSenders.map((sender) => (
                            <SelectItem key={sender.user_id} value={sender.user_id}>
                                {sender.display_name} ({sender.gmail_email})
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                {!eligibleSendersLoading && !eligibleSenders.length ? (
                    <p className="text-xs text-yellow-600">
                        No eligible senders found. Admin users must connect Gmail first.
                    </p>
                ) : null}
                <p className="text-xs text-muted-foreground">
                    Only admin users with Gmail connected can be selected as the default sender.
                </p>
            </div>

            {settings?.default_sender_name ? (
                <div className="flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm dark:bg-green-900/20">
                    <CheckCircleIcon className="size-4 text-green-600" aria-hidden="true" />
                    <span>
                        Current sender: <strong>{settings.default_sender_name}</strong> ({settings.default_sender_email})
                    </span>
                </div>
            ) : null}
        </div>
    )
}

function EmailSaveButton({
    pending,
    saved,
    disabled,
    onSave,
}: {
    pending: boolean
    saved: boolean
    disabled: boolean
    onSave: () => void
}) {
    return (
        <Button onClick={onSave} disabled={pending || disabled}>
            {pending ? (
                <>
                    <Loader2Icon
                        className="animate-spin motion-reduce:animate-none"
                        aria-hidden="true"
                    />
                    Saving…
                </>
            ) : saved ? (
                <>
                    <CheckIcon aria-hidden="true" />
                    Saved
                </>
            ) : (
                "Save Email Configuration"
            )}
        </Button>
    )
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
    const isDialog = variant === "dialog"

    const handleRetry = async (eventId: string) => {
        try {
            await retryOutboundEvent.mutateAsync({ eventId })
            toast.success("Retry queued")
        } catch {
            toast.error("Failed to retry outbound event")
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
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => handleRetry(event.id)}
                                                disabled={!event.can_retry || retryOutboundEvent.isPending}
                                                className={isDialog ? "" : "min-w-24"}
                                            >
                                                {retryOutboundEvent.isPending ? "Retrying…" : "Retry"}
                                            </Button>
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

/**
 * Stage → event bucket table shared by the Meta CRM dataset and the Zapier surrogate mapping.
 * A tracked bucket fixes the event name; "Not Tracked" rows take a custom event name.
 */
function StageEventMappingTable<T extends StageEventMappingLike>({
    items,
    namePrefix,
    getStageKeyLabel,
    getSendLabel,
    getUntrackedEnabled,
    onChange,
}: {
    items: T[]
    namePrefix: string
    getStageKeyLabel: (stageKey: string) => string
    getSendLabel: (stageLabel: string) => string
    /** Send state after a row is set to Not Tracked. */
    getUntrackedEnabled: (item: T) => boolean
    onChange: (next: T[]) => void
}) {
    const updateItem = (index: number, updater: (existing: T) => T) => {
        const existing = items[index]
        if (!existing) return
        const next = [...items]
        next[index] = updater(existing)
        onChange(next)
    }

    return (
        <div className="rounded-lg border">
            <Table className="min-w-[36rem]">
                <TableHeader>
                    <TableRow>
                        <TableHead>Stage</TableHead>
                        <TableHead className="w-48">Event bucket</TableHead>
                        <TableHead className="w-56">Event name</TableHead>
                        <TableHead className="w-16 text-center">Send</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {items.map((item, index) => {
                        const stageLabel = getStageKeyLabel(item.stage_key)
                        const tracked = isZapierStageBucket(item.bucket)
                        return (
                            <TableRow key={item.stage_key}>
                                <TableCell className="whitespace-normal font-medium">{stageLabel}</TableCell>
                                <TableCell>
                                    <Select
                                        value={tracked ? item.bucket : UNTRACKED_BUCKET_VALUE}
                                        onValueChange={(value) => {
                                            if (value === UNTRACKED_BUCKET_VALUE) {
                                                updateItem(index, (existing) => ({
                                                    ...existing,
                                                    bucket: null,
                                                    enabled: getUntrackedEnabled(existing),
                                                }))
                                            } else if (isZapierStageBucket(value)) {
                                                updateItem(index, (existing) => ({
                                                    ...existing,
                                                    bucket: value,
                                                    event_name: ZAPIER_BUCKET_EVENT_NAME[value],
                                                    enabled: true,
                                                }))
                                            }
                                        }}
                                    >
                                        <SelectTrigger
                                            size="sm"
                                            className="w-full"
                                            aria-label={`Event bucket for ${stageLabel}`}
                                        >
                                            <SelectValue placeholder="Bucket">
                                                {(value: string | null) => getBucketSelectLabel(value)}
                                            </SelectValue>
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value={UNTRACKED_BUCKET_VALUE}>
                                                {getBucketSelectLabel(UNTRACKED_BUCKET_VALUE)}
                                            </SelectItem>
                                            {ZAPIER_BUCKET_OPTIONS.map((option) => (
                                                <SelectItem key={option.value} value={option.value}>
                                                    {option.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </TableCell>
                                <TableCell>
                                    {tracked ? (
                                        <span className="text-muted-foreground">{item.event_name}</span>
                                    ) : (
                                        <Input
                                            value={item.event_name}
                                            onChange={(event) => {
                                                const eventName = event.target.value
                                                updateItem(index, (existing) => ({ ...existing, event_name: eventName }))
                                            }}
                                            placeholder="Event name"
                                            aria-label={`Event name for ${stageLabel}`}
                                            name={`${namePrefix}-event-${item.stage_key}`}
                                            autoComplete="off"
                                            className="h-8"
                                        />
                                    )}
                                </TableCell>
                                <TableCell>
                                    <div className="flex justify-center">
                                        <Checkbox
                                            checked={item.enabled}
                                            onCheckedChange={(checked) => {
                                                updateItem(index, (existing) => ({ ...existing, enabled: checked === true }))
                                            }}
                                            aria-label={getSendLabel(stageLabel)}
                                        />
                                    </div>
                                </TableCell>
                            </TableRow>
                        )
                    })}
                </TableBody>
            </Table>
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
function ZapierWebhookSection({
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

function MetaCrmDatasetMonitoringSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
    const { data: summary, isLoading: summaryLoading } = useMetaCrmDatasetEventsSummary()
    const { data: events, isLoading: eventsLoading } = useMetaCrmDatasetEvents({ limit: 20 })
    const retryEvent = useRetryMetaCrmDatasetEvent()
    const isDialog = variant === "dialog"

    const handleRetry = async (eventId: string) => {
        try {
            await retryEvent.mutateAsync({ eventId })
            toast.success("Retry queued")
        } catch {
            toast.error("Failed to retry Meta CRM dataset event")
        }
    }

    if (summaryLoading || eventsLoading) {
        return (
            <div className="flex items-center justify-center py-8">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground motion-reduce:animate-none" aria-hidden="true" />
            </div>
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
                    <CardTitle className="text-base">Recent direct Meta CRM dataset events</CardTitle>
                    <CardDescription className="text-xs">
                        Review delivery outcomes, skip reasons, Graph API errors, and replay failed jobs.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {!events?.items?.length ? (
                        <p className="text-sm text-muted-foreground">
                            No direct Meta CRM dataset events recorded yet.
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
                                {events.items.map((event) => (
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
                                                {event.stage_label || event.stage_key || "No stage"}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={ZAPIER_OUTBOUND_STATUS_BADGE[event.status].variant}>
                                                {ZAPIER_OUTBOUND_STATUS_BADGE[event.status].label}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="max-w-xs">
                                            <div className="space-y-1 text-xs text-muted-foreground">
                                                <p>Lead: {event.lead_id || "—"}</p>
                                                <p>
                                                    {event.last_error
                                                        || (event.reason ? formatZapierReason(event.reason) : "No issues recorded")}
                                                </p>
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => handleRetry(event.id)}
                                                disabled={!event.can_retry || retryEvent.isPending}
                                                className={isDialog ? "" : "min-w-24"}
                                            >
                                                {retryEvent.isPending ? "Retrying…" : "Retry"}
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}

/**
 * Tabs, DialogBody and DialogFooter of the Meta dialog. The CRM dataset form owns the footer
 * Save, so the legacy setup (which saves each action on its own) is passed in as a slot.
 */
function MetaCrmDatasetSection({ legacySetup }: { legacySetup: ReactNode }) {
    const { data: pipelines } = usePipelines()
    const { data: settings, isLoading } = useMetaCrmDatasetSettings()

    return (
        <MetaCrmDatasetSectionContent
            key={settings && pipelines ? "loaded" : "loading"}
            pipelines={pipelines}
            settings={settings}
            isLoading={isLoading}
            legacySetup={legacySetup}
        />
    )
}

function MetaCrmDatasetSectionContent({
    pipelines,
    settings,
    isLoading,
    legacySetup,
}: {
    pipelines: ReturnType<typeof usePipelines>["data"]
    settings: ReturnType<typeof useMetaCrmDatasetSettings>["data"]
    isLoading: boolean
    legacySetup: ReactNode
}) {
    const recommendedBucketByStage = buildRecommendedBucketByStage(pipelines)
    const stageLabelByKey = buildStageLabelByKey(pipelines)
    const getStageKeyLabel = (stageKey: string) => stageLabelByKey[stageKey] ?? "Unknown stage"
    const updateSettings = useUpdateMetaCrmDatasetSettings()
    const sendOutboundTest = useMetaCrmDatasetOutboundTest()
    const [activeTab, setActiveTab] = useState<"configuration" | "monitoring">("configuration")
    // Both tabs share one scroll body, so it returns to the top on each tab change.
    const bodyRef = useRef<HTMLDivElement | null>(null)
    const initialEventMapping = mergeEventMappingWithPipelineStages(
        settings?.event_mapping || [],
        pipelines,
    )
    const [metaForm, setMetaForm] = useState<MetaCrmDatasetFormState>(() => ({
        datasetId: settings?.dataset_id || "",
        accessToken: "",
        enabled: Boolean(settings?.enabled),
        crmName: settings?.crm_name || "Surrogacy Force CRM",
        sendHashedPii: Boolean(settings?.send_hashed_pii),
        eventMapping: initialEventMapping,
        testEventCode: settings?.test_event_code || "",
        selectedStage: initialEventMapping[0]?.stage_key || "",
        outboundTestLeadId: "",
        outboundTestFbc: "",
    }))

    const updateMetaForm = <K extends keyof MetaCrmDatasetFormState>(field: K, value: MetaCrmDatasetFormState[K]) => {
        setMetaForm((current) => ({ ...current, [field]: value }))
    }

    const updateEventMapping = (
        updater: (current: MetaCrmDatasetEventMappingItem[]) => MetaCrmDatasetEventMappingItem[],
    ) => {
        setMetaForm((current) => ({
            ...current,
            eventMapping: updater(current.eventMapping),
        }))
    }

    const handleSave = async () => {
        try {
            const payload: {
                dataset_id: string | null
                access_token?: string | null
                enabled: boolean
                crm_name: string
                send_hashed_pii: boolean
                event_mapping: MetaCrmDatasetEventMappingItem[]
                test_event_code: string | null
            } = {
                dataset_id: metaForm.datasetId.trim() || null,
                enabled: metaForm.enabled,
                crm_name: metaForm.crmName.trim() || "Surrogacy Force CRM",
                send_hashed_pii: metaForm.sendHashedPii,
                event_mapping: metaForm.eventMapping,
                test_event_code: metaForm.testEventCode.trim() || null,
            }
            const nextAccessToken = metaForm.accessToken.trim()
            if (nextAccessToken) {
                payload.access_token = nextAccessToken
            }
            await updateSettings.mutateAsync(payload)
            setMetaForm((current) => ({ ...current, accessToken: "" }))
            toast.success("CRM dataset settings saved")
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't save CRM dataset settings")
            if (message) toast.error(message)
        }
    }

    const handleOutboundTest = async () => {
        try {
            const payload: {
                stage_key?: string
                lead_id?: string
                fbc?: string | null
                test_event_code?: string | null
            } = {}
            if (metaForm.selectedStage) {
                payload.stage_key = metaForm.selectedStage
            }
            const leadId = metaForm.outboundTestLeadId.trim()
            if (leadId) {
                payload.lead_id = leadId
            }
            const clickId = metaForm.outboundTestFbc.trim()
            if (clickId) {
                payload.fbc = clickId
            }
            payload.test_event_code = metaForm.testEventCode.trim() || null
            const result = await sendOutboundTest.mutateAsync(payload)
            toast.success(`Test event queued: ${result.event_name} for ${result.lead_id}`)
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't send the Meta CRM dataset test event")
            if (message) toast.error(message)
        }
    }

    const applyRecommendedBucketMapping = () => {
        updateEventMapping((current) =>
            current.map((item) => {
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
            })
        )
        toast.success("Applied recommended Meta CRM dataset stage mapping")
    }

    return (
        <>
            <Tabs
                value={activeTab}
                onValueChange={(value) => {
                    if (value === "configuration" || value === "monitoring") setActiveTab(value)
                }}
                resetScrollRef={bodyRef}
                className="min-h-0 flex-1 gap-0"
            >
                <div className="shrink-0 overflow-x-auto border-b px-6">
                    <TabsList variant="line" aria-label="Meta configuration sections">
                        <TabsTrigger value="configuration">Configuration</TabsTrigger>
                        <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
                    </TabsList>
                </div>
                <DialogBody ref={bodyRef} className="overflow-x-hidden">
                    <TabsContent value="configuration" className="space-y-6">
                        <section className="space-y-6" aria-labelledby="meta-crm-dataset-heading">
                            <h3 id="meta-crm-dataset-heading" className="text-base font-semibold">CRM dataset</h3>
                            {isLoading ? (
                                <div role="status" className="flex items-center justify-center py-8">
                                    <Loader2Icon className="size-6 animate-spin text-muted-foreground motion-reduce:animate-none" aria-hidden="true" />
                                    <span className="sr-only">Loading</span>
                                </div>
                            ) : (
                                <>
                                    <MetaCrmDatasetSettingsFields
                                        metaForm={metaForm}
                                        accessTokenConfigured={Boolean(settings?.access_token_configured)}
                                        updateMetaForm={updateMetaForm}
                                    />
                                    <MetaCrmDatasetStageMapping
                                        eventMapping={metaForm.eventMapping}
                                        updateEventMapping={updateEventMapping}
                                        getStageKeyLabel={getStageKeyLabel}
                                        applyRecommendedBucketMapping={applyRecommendedBucketMapping}
                                    />
                                    <MetaCrmDatasetTestControls
                                        metaForm={metaForm}
                                        updateMetaForm={updateMetaForm}
                                        getStageKeyLabel={getStageKeyLabel}
                                        isSendingTest={sendOutboundTest.isPending}
                                        handleOutboundTest={handleOutboundTest}
                                    />
                                </>
                            )}
                        </section>
                        {legacySetup}
                    </TabsContent>

                    <TabsContent value="monitoring" keepMounted>
                        <MetaCrmDatasetMonitoringSection variant="dialog" />
                    </TabsContent>
                </DialogBody>
            </Tabs>
            {/* Save applies to the CRM dataset form only; legacy actions save on their own. */}
            <DialogFooter>
                {activeTab === "configuration" ? (
                    <>
                        <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
                        <Button
                            onClick={() => {
                                void handleSave()
                            }}
                            disabled={isLoading || updateSettings.isPending}
                        >
                            {updateSettings.isPending ? (
                                <>
                                    <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                    Saving…
                                </>
                            ) : (
                                "Save CRM Dataset Settings"
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

function MetaCrmDatasetSettingsFields({
    metaForm,
    accessTokenConfigured,
    updateMetaForm,
}: {
    metaForm: MetaCrmDatasetFormState
    accessTokenConfigured: boolean
    updateMetaForm: UpdateMetaCrmDatasetForm
}) {
    return (
        <>
            <Alert>
                <AlertTitle>No Meta app required</AlertTitle>
                <AlertDescription>
                    Use this direct CRM dataset path when you want Meta CRM conversion reporting without the legacy app-based OAuth flow.
                </AlertDescription>
            </Alert>

            <div className="flex items-center justify-between rounded-md border p-3">
                <div>
                    <p className="text-sm font-medium">Enable direct CRM dataset delivery</p>
                    <p className="text-xs text-muted-foreground">
                        Send Meta lead stage changes directly to your dataset endpoint.
                    </p>
                </div>
                <Switch
                    checked={metaForm.enabled}
                    onCheckedChange={(checked) => updateMetaForm("enabled", checked)}
                    aria-label="Enable direct CRM dataset delivery"
                />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                    <Label htmlFor="meta-crm-dataset-id">Dataset ID</Label>
                    <Input
                        id="meta-crm-dataset-id"
                        value={metaForm.datasetId}
                        onChange={(event) => updateMetaForm("datasetId", event.target.value)}
                        placeholder="1428122951556949"
                        autoComplete="off"
                    />
                </div>
                <div className="space-y-2">
                    <Label htmlFor="meta-crm-dataset-access-token">Meta CRM Dataset Access Token</Label>
                    <Input
                        id="meta-crm-dataset-access-token"
                        type="password"
                        value={metaForm.accessToken}
                        onChange={(event) => updateMetaForm("accessToken", event.target.value)}
                        placeholder={accessTokenConfigured ? "•••••••• (set)" : "Enter access token"}
                        autoComplete="off"
                    />
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                    <Label htmlFor="meta-crm-dataset-crm-name">CRM Name</Label>
                    <Input
                        id="meta-crm-dataset-crm-name"
                        value={metaForm.crmName}
                        onChange={(event) => updateMetaForm("crmName", event.target.value)}
                        placeholder="Surrogacy Force CRM"
                        autoComplete="off"
                    />
                </div>
                <div className="space-y-2">
                    <Label htmlFor="meta-crm-dataset-test-event-code">Test Event Code</Label>
                    <Input
                        id="meta-crm-dataset-test-event-code"
                        value={metaForm.testEventCode}
                        onChange={(event) => updateMetaForm("testEventCode", event.target.value)}
                        placeholder="Optional Meta test event code"
                        autoComplete="off"
                    />
                </div>
            </div>

            <div className="flex items-center justify-between rounded-md border p-3">
                <div>
                    <p className="text-sm font-medium">Include hashed PII for Meta CRM dataset</p>
                    <p className="text-xs text-muted-foreground">
                        Send hashed email and phone when available to improve match quality.
                    </p>
                </div>
                <Switch
                    checked={metaForm.sendHashedPii}
                    onCheckedChange={(checked) => updateMetaForm("sendHashedPii", checked)}
                    aria-label="Include hashed PII for Meta CRM dataset"
                />
            </div>
        </>
    )
}

function MetaCrmDatasetStageMapping({
    eventMapping,
    updateEventMapping,
    getStageKeyLabel,
    applyRecommendedBucketMapping,
}: {
    eventMapping: MetaCrmDatasetEventMappingItem[]
    updateEventMapping: UpdateMetaCrmDatasetEventMapping
    getStageKeyLabel: (stageKey: string) => string
    applyRecommendedBucketMapping: () => void
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
                    onClick={applyRecommendedBucketMapping}
                >
                    Apply Recommended Mapping
                </Button>
            </div>
            <StageEventMappingTable
                items={eventMapping}
                namePrefix="meta-crm-dataset"
                getStageKeyLabel={getStageKeyLabel}
                getSendLabel={(stageLabel) => `Send ${stageLabel} to Meta CRM dataset`}
                getUntrackedEnabled={() => false}
                onChange={(next) => updateEventMapping(() => next)}
            />
        </div>
    )
}

function MetaCrmDatasetTestControls({
    metaForm,
    updateMetaForm,
    getStageKeyLabel,
    isSendingTest,
    handleOutboundTest,
}: {
    metaForm: MetaCrmDatasetFormState
    updateMetaForm: UpdateMetaCrmDatasetForm
    getStageKeyLabel: (stageKey: string) => string
    isSendingTest: boolean
    handleOutboundTest: () => Promise<void>
}) {
    return (
        <div className="flex flex-col gap-2">
            <div className="flex flex-col gap-2">
                <div className="space-y-2">
                    <Label htmlFor="meta-crm-dataset-test-lead-id">Real Meta Lead ID</Label>
                    <Input
                        id="meta-crm-dataset-test-lead-id"
                        value={metaForm.outboundTestLeadId}
                        onChange={(event) => updateMetaForm("outboundTestLeadId", event.target.value)}
                        placeholder="Use a real Meta lead ID for testing"
                        autoComplete="off"
                    />
                    <p className="text-xs text-muted-foreground">
                        Meta CRM funnel updates generally only work for leads created within 90 days.
                    </p>
                </div>
                <div className="space-y-2">
                    <Label htmlFor="meta-crm-dataset-test-fbc">Click ID (fbc)</Label>
                    <Input
                        id="meta-crm-dataset-test-fbc"
                        value={metaForm.outboundTestFbc}
                        onChange={(event) => updateMetaForm("outboundTestFbc", event.target.value)}
                        placeholder="Optional Meta click ID for better matching"
                        autoComplete="off"
                    />
                    <p className="text-xs text-muted-foreground">
                        Send Meta click ID when you have it. This maps to <code>user_data.fbc</code>.
                    </p>
                </div>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                    <Select
                        value={metaForm.selectedStage}
                        onValueChange={(value) => updateMetaForm("selectedStage", value ?? "")}
                    >
                        <SelectTrigger className="w-full sm:flex-1" aria-label="Select Meta CRM dataset stage">
                            <SelectValue placeholder="Select stage">
                                {(value: string | null) => (value ? getStageKeyLabel(value) : "")}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {metaForm.eventMapping.map((item) => (
                                <SelectItem key={item.stage_key} value={item.stage_key}>
                                    {getStageKeyLabel(item.stage_key)}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Button
                        variant="outline"
                        onClick={() => { void handleOutboundTest() }}
                        disabled={isSendingTest}
                        className="w-full sm:w-auto"
                    >
                        {isSendingTest ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                Sending…
                            </>
                        ) : (
                            <>
                                <ActivityIcon className="mr-2 size-4" aria-hidden="true" />
                                Send Meta CRM Test Event
                            </>
                        )}
                    </Button>
                </div>
            </div>
        </div>
    )
}

// Connection health badge component for Meta dialog
function ConnectionHealthBadge({ connection }: { connection: MetaOAuthConnection }) {
    const status = getConnectionHealthStatus(connection)

    if (status === "healthy") {
        return (
            <Badge variant="default" className="gap-1 bg-green-500/10 text-green-600 border-green-500/20">
                <CheckCircleIcon className="size-3" aria-hidden="true" />
                Healthy
            </Badge>
        )
    }

    if (status === "needs_reauth") {
        return (
            <Tooltip>
                <TooltipTrigger>
                    <Badge variant="destructive" className="gap-1">
                        <AlertTriangleIcon className="size-3" aria-hidden="true" />
                        Needs Reauth
                    </Badge>
                </TooltipTrigger>
                <TooltipContent>
                    Token expired or revoked. Click Connect with Facebook to fix.
                </TooltipContent>
            </Tooltip>
        )
    }

    if (status === "rate_limited") {
        return (
            <Tooltip>
                <TooltipTrigger>
                    <Badge variant="secondary" className="gap-1 bg-yellow-500/10 text-yellow-600 border-yellow-500/20">
                        <AlertTriangleIcon className="size-3" aria-hidden="true" />
                        Rate Limited
                    </Badge>
                </TooltipTrigger>
                <TooltipContent>
                    Temporarily rate limited. Will retry automatically.
                </TooltipContent>
            </Tooltip>
        )
    }

    if (status === "permission_error") {
        return (
            <Tooltip>
                <TooltipTrigger>
                    <Badge variant="destructive" className="gap-1">
                        <AlertTriangleIcon className="size-3" aria-hidden="true" />
                        Permission Error
                    </Badge>
                </TooltipTrigger>
                <TooltipContent>
                    Check Lead Access Manager in Meta Business Settings.
                </TooltipContent>
            </Tooltip>
        )
    }

    return (
        <Tooltip>
            <TooltipTrigger>
                <Badge variant="secondary" className="gap-1 bg-yellow-500/10 text-yellow-600 border-yellow-500/20">
                    <AlertTriangleIcon className="size-3" aria-hidden="true" />
                    Error
                </Badge>
            </TooltipTrigger>
            <TooltipContent>{parseMetaError(connection.last_error)}</TooltipContent>
        </Tooltip>
    )
}

function LegacyMetaSetupSection({
    connections,
    adAccounts,
    connectionActions,
    adAccountActions,
}: {
    connections: MetaOAuthConnection[]
    adAccounts: MetaAdAccount[]
    connectionActions: {
        isConnecting: boolean
        onConnect: () => void
        onDisconnectRequest: (connectionId: string) => void
    }
    adAccountActions: {
        isDeleting: boolean
        onEdit: (account: MetaAdAccount) => void
        onDelete: (accountId: string) => Promise<unknown>
    }
}) {
    return (
        <div className="space-y-4 border-t pt-4">
            <div className="space-y-2">
                <h3 className="text-base font-semibold">Legacy app-based Meta setup</h3>
                <p className="text-sm text-muted-foreground">
                    These OAuth connections and ad-account CAPI settings are the legacy app-based integration path.
                </p>
            </div>

            <LegacyMetaConnectionsCard
                connections={connections}
                actions={connectionActions}
            />
            <LegacyMetaAdAccountsCard
                adAccounts={adAccounts}
                actions={adAccountActions}
            />

            <div className="flex justify-end">
                <Button render={<Link href="/settings/integrations/meta/forms" />} variant="outline" size="sm">
                    Manage lead forms
                </Button>
            </div>
        </div>
    )
}

function LegacyMetaConnectionsCard({
    connections,
    actions,
}: {
    connections: MetaOAuthConnection[]
    actions: {
        isConnecting: boolean
        onConnect: () => void
        onDisconnectRequest: (connectionId: string) => void
    }
}) {
    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-y-0 pb-3">
                <div>
                    <CardTitle className="text-base">Legacy Connections</CardTitle>
                    <CardDescription className="text-xs">
                        Connect Meta accounts and manage assets for lead ads through the legacy app-based flow.
                    </CardDescription>
                </div>
                <Button size="sm" onClick={actions.onConnect} disabled={actions.isConnecting}>
                    {actions.isConnecting ? (
                        <Loader2Icon
                            className="mr-2 size-4 animate-spin motion-reduce:animate-none"
                            aria-hidden="true"
                        />
                    ) : (
                        <MegaphoneIcon className="mr-2 size-4" aria-hidden="true" />
                    )}
                    Connect with Facebook
                </Button>
            </CardHeader>
            <CardContent>
                {connections.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                        No legacy Meta connections yet. Connect with Facebook to get started.
                    </p>
                ) : (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Account</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Last validated</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {connections.map((connection) => (
                                <TableRow key={connection.id}>
                                    <TableCell>
                                        <div className="font-medium">
                                            {connection.meta_user_name || "Meta user"}
                                        </div>
                                        <div className="text-xs text-muted-foreground">
                                            {connection.meta_user_id}
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <ConnectionHealthBadge connection={connection} />
                                    </TableCell>
                                    <TableCell className="text-sm text-muted-foreground">
                                        {connection.last_validated_at
                                            ? formatRelativeTime(connection.last_validated_at, "—")
                                            : "—"}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => actions.onDisconnectRequest(connection.id)}
                                            aria-label="Disconnect connection"
                                        >
                                            <UnlinkIcon className="size-4" aria-hidden="true" />
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                )}
            </CardContent>
        </Card>
    )
}

function LegacyMetaAdAccountsCard({
    adAccounts,
    actions,
}: {
    adAccounts: MetaAdAccount[]
    actions: {
        isDeleting: boolean
        onEdit: (account: MetaAdAccount) => void
        onDelete: (accountId: string) => Promise<unknown>
    }
}) {
    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base">Legacy Ad Accounts + CAPI</CardTitle>
                <CardDescription className="text-xs">
                    Configure legacy pixel-based CAPI settings and sync visibility.
                </CardDescription>
            </CardHeader>
            <CardContent>
                {adAccounts.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No legacy ad accounts connected yet.</p>
                ) : (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Ad Account</TableHead>
                                <TableHead>Name</TableHead>
                                <TableHead>CAPI</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {adAccounts.map((account) => (
                                <TableRow key={account.id}>
                                    <TableCell className="font-mono text-xs">
                                        {account.ad_account_external_id}
                                    </TableCell>
                                    <TableCell>{account.ad_account_name || "—"}</TableCell>
                                    <TableCell>
                                        <Badge variant={account.capi_enabled ? "default" : "secondary"}>
                                            {account.capi_enabled ? "Enabled" : "Disabled"}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant={account.is_active ? "default" : "secondary"} className="gap-1">
                                            {account.is_active ? (
                                                <CheckCircleIcon className="size-3" aria-hidden="true" />
                                            ) : (
                                                <AlertTriangleIcon className="size-3" aria-hidden="true" />
                                            )}
                                            {account.is_active ? "Active" : "Inactive"}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => actions.onEdit(account)}
                                            aria-label="Edit ad account"
                                        >
                                            <PencilIcon className="size-4" aria-hidden="true" />
                                        </Button>
                                        <ConfirmDialog
                                            trigger={
                                                <Button
                                                    variant="destructive-ghost"
                                                    size="sm"
                                                    disabled={actions.isDeleting}
                                                    aria-label="Delete ad account"
                                                >
                                                    <TrashIcon className="size-4" aria-hidden="true" />
                                                </Button>
                                            }
                                            title={`Delete ${account.ad_account_name || account.ad_account_external_id}?`}
                                            description="Lead sync and CAPI stop for this ad account."
                                            confirmLabel="Delete"
                                            errorFallback="Couldn't delete the ad account. Try again."
                                            onConfirm={() => actions.onDelete(account.id)}
                                        />
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                )}
            </CardContent>
        </Card>
    )
}

function MetaAdAccountEditDialog({
    editState,
    isSaving,
    onSubmit,
    onClose,
    onEditChange,
}: {
    editState: MetaAccountEditState
    isSaving: boolean
    onSubmit: (event: React.FormEvent) => void
    onClose: () => void
    onEditChange: (action: MetaAccountEditAction) => void
}) {
    return (
        <Dialog open={!!editState.account} onOpenChange={(open) => !open && onClose()}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Edit Ad Account</DialogTitle>
                    <DialogDescription>Update CAPI and account settings.</DialogDescription>
                </DialogHeader>
                <form onSubmit={onSubmit}>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="adAccountName">Ad account name</Label>
                            <Input
                                id="adAccountName"
                                value={editState.adAccountName}
                                onChange={(e) =>
                                    onEditChange({
                                        type: "changeAdAccountName",
                                        value: e.target.value,
                                    })
                                }
                                name="ad-account-name"
                                autoComplete="off"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="pixelId">Pixel ID</Label>
                            <Input
                                id="pixelId"
                                value={editState.pixelId}
                                onChange={(e) =>
                                    onEditChange({
                                        type: "changePixelId",
                                        value: e.target.value,
                                    })
                                }
                                name="pixel-id"
                                autoComplete="off"
                            />
                        </div>
                        <div className="flex items-center justify-between">
                            <div>
                                <Label htmlFor="capiEnabled">Enable CAPI</Label>
                                <p className="text-xs text-muted-foreground">
                                    Send lead status updates to Meta.
                                </p>
                            </div>
                            <Checkbox
                                checked={editState.capiEnabled}
                                onCheckedChange={(checked) =>
                                    onEditChange({
                                        type: "toggleCapiEnabled",
                                        value: !!checked,
                                    })
                                }
                                id="capiEnabled"
                            />
                        </div>
                        <div className="flex items-center justify-between">
                            <div>
                                <Label htmlFor="accountActive">Active</Label>
                                <p className="text-xs text-muted-foreground">
                                    Disable to pause sync and CAPI for this account.
                                </p>
                            </div>
                            <Checkbox
                                checked={editState.accountActive}
                                onCheckedChange={(checked) =>
                                    onEditChange({
                                        type: "toggleAccountActive",
                                        value: !!checked,
                                    })
                                }
                                id="accountActive"
                            />
                        </div>
                        {editState.error && (
                            <p className="text-sm text-destructive">{editState.error}</p>
                        )}
                    </div>
                    <div className="flex justify-end gap-2">
                        <Button
                            variant="outline"
                            onClick={onClose}
                            type="button"
                        >
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isSaving}>
                            {isSaving ? (
                                <>
                                    <Loader2Icon
                                        className="mr-2 size-4 animate-spin motion-reduce:animate-none"
                                        aria-hidden="true"
                                    />
                                    Saving…
                                </>
                            ) : (
                                "Save changes"
                            )}
                        </Button>
                    </div>
                </form>
            </DialogContent>
        </Dialog>
    )
}

function MetaDisconnectDialog({
    connectionId,
    onClose,
    onConfirm,
}: {
    connectionId: string | null
    onClose: () => void
    onConfirm: (connectionId: string) => Promise<void>
}) {
    return (
        <ConfirmDialog
            open={!!connectionId}
            onOpenChange={(open) => {
                if (!open) onClose()
            }}
            title="Disconnect Meta account?"
            description="This will unlink all ad accounts and pages connected through this Facebook account."
            confirmLabel="Disconnect"
            errorFallback="Couldn't disconnect the Meta account. Try again."
            onConfirm={() => (connectionId ? onConfirm(connectionId) : undefined)}
        />
    )
}

function MetaConfigurationSection() {
    const { data: connections = [], isLoading: connectionsLoading } = useMetaConnections()
    const connectUrlMutation = useMetaConnectUrl()
    const disconnectMutation = useDisconnectMetaConnection()

    const { data: adAccounts = [], isLoading: adAccountsLoading } = useAdminMetaAdAccounts()
    const updateAccountMutation = useUpdateMetaAdAccount()
    const deleteAccountMutation = useDeleteMetaAdAccount()

    const [accountEditState, dispatchAccountEdit] = useReducer(
        metaAccountEditReducer,
        initialMetaAccountEditState,
    )
    const [disconnectConnectionId, setDisconnectConnectionId] = useState<string | null>(null)
    const {
        account: editAccount,
        adAccountName,
        pixelId,
        capiEnabled,
        accountActive,
    } = accountEditState

    const handleConnectWithFacebook = async () => {
        try {
            const result = await connectUrlMutation.mutateAsync()
            window.location.href = result.auth_url
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't start the Meta connection. Try again.")
            if (message) toast.error(message)
        }
    }

    // Errors propagate so the confirm dialog stays open and shows them inline.
    const handleDisconnect = async (connectionId: string) => {
        await disconnectMutation.mutateAsync(connectionId)
        setDisconnectConnectionId(null)
        toast.success("Meta account disconnected")
    }

    const openEditAccount = (account: MetaAdAccount) => {
        dispatchAccountEdit({ type: "open", account })
    }

    const handleUpdateAdAccount = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!editAccount) return
        dispatchAccountEdit({ type: "clearError" })

        const payload: MetaAdAccountUpdate = {
            capi_enabled: capiEnabled,
            is_active: accountActive,
        }
        if (adAccountName.trim() !== (editAccount.ad_account_name || "")) {
            payload.ad_account_name = adAccountName.trim()
        }
        if (pixelId.trim() !== (editAccount.pixel_id || "")) {
            payload.pixel_id = pixelId.trim()
        }

        try {
            await updateAccountMutation.mutateAsync({
                accountId: editAccount.id,
                data: payload,
            })
            dispatchAccountEdit({ type: "close" })
        } catch (error: unknown) {
            const message = getActionErrorMessage(error, "Couldn't update the ad account. Try again.")
            if (message) dispatchAccountEdit({ type: "setError", error: message })
        }
    }

    const handleDeleteAdAccount = async (accountId: string) => {
        await deleteAccountMutation.mutateAsync(accountId)
        toast.success("Ad account deleted")
    }

    if (connectionsLoading || adAccountsLoading) {
        return <IntegrationDialogLoadingState />
    }

    return (
        <>
            <MetaCrmDatasetSection
                legacySetup={
                    <LegacyMetaSetupSection
                        connections={connections}
                        adAccounts={adAccounts}
                        connectionActions={{
                            isConnecting: connectUrlMutation.isPending,
                            onConnect: () => {
                                void handleConnectWithFacebook()
                            },
                            onDisconnectRequest: setDisconnectConnectionId,
                        }}
                        adAccountActions={{
                            isDeleting: deleteAccountMutation.isPending,
                            onEdit: openEditAccount,
                            onDelete: handleDeleteAdAccount,
                        }}
                    />
                }
            />
            <MetaAdAccountEditDialog
                editState={accountEditState}
                isSaving={updateAccountMutation.isPending}
                onSubmit={handleUpdateAdAccount}
                onClose={() => dispatchAccountEdit({ type: "close" })}
                onEditChange={dispatchAccountEdit}
            />
            <MetaDisconnectDialog
                connectionId={disconnectConnectionId}
                onClose={() => setDisconnectConnectionId(null)}
                onConfirm={handleDisconnect}
            />
        </>
    )
}

type IntegrationScope = "personal" | "organization"

export default function IntegrationsPage() {
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"
    const { data: effectivePermissions } = useEffectivePermissions(user?.user_id ?? null)
    const canManageOrganizationIntegrations =
        isDeveloper || (effectivePermissions?.permissions ?? []).includes("manage_integrations")
    const [selectedScope, setSelectedScope] = useState<IntegrationScope | null>(null)
    const requestedScope = selectedScope
        ?? (canManageOrganizationIntegrations ? "organization" : "personal")
    const activeScope = requestedScope === "organization" && !canManageOrganizationIntegrations
        ? "personal"
        : requestedScope
    const organizationIntegrationsEnabled =
        canManageOrganizationIntegrations && activeScope === "organization"
    const { data: healthData, refetch, isFetching } = useIntegrationHealth(
        organizationIntegrationsEnabled
    )
    const personalIntegrationsEnabled = activeScope === "personal"
    const { data: userIntegrations } = useUserIntegrations(personalIntegrationsEnabled)
    const { data: googleCalendarStatus } = useGoogleCalendarStatus(personalIntegrationsEnabled)
    const { data: aiSettings, isLoading: aiSettingsLoading } = useAISettings(
        organizationIntegrationsEnabled
    )
    const { data: resendSettings, isLoading: resendSettingsLoading } = useResendSettings(
        organizationIntegrationsEnabled
    )
    const { data: twilioSettings, isLoading: twilioSettingsLoading } = useTwilioSettings(
        organizationIntegrationsEnabled
    )
    const { data: twilioReadiness, isLoading: twilioReadinessLoading } = useTwilioReadiness(
        organizationIntegrationsEnabled
    )
    const { data: zapierSettings, isLoading: zapierSettingsLoading } = useZapierSettings(
        organizationIntegrationsEnabled
    )
    const { data: pipelines } = usePipelines("surrogate", organizationIntegrationsEnabled)
    const { data: metaFormsData } = useMetaForms(organizationIntegrationsEnabled)
    const { data: metaConnectionsData } = useMetaConnections(organizationIntegrationsEnabled)
    const { data: metaAdAccountsData } = useAdminMetaAdAccounts(organizationIntegrationsEnabled)
    const {
        data: metaCrmDatasetSettings,
        isLoading: metaCrmDatasetSettingsLoading,
    } = useMetaCrmDatasetSettings(organizationIntegrationsEnabled)
    const metaForms = metaFormsData ?? []
    const metaConnections = metaConnectionsData ?? []
    const metaAdAccounts = metaAdAccountsData ?? []
    const connectZoom = useConnectZoom()
    const connectGmail = useConnectGmail()
    const connectGoogleCalendar = useConnectGoogleCalendar()
    const syncGoogleCalendarNow = useSyncGoogleCalendarNow()
    const disconnectIntegration = useDisconnectIntegration()
    const [aiDialogOpen, setAiDialogOpen] = useState(false)
    const [emailDialogOpen, setEmailDialogOpen] = useState(false)
    const [zapierDialogOpen, setZapierDialogOpen] = useState(false)
    const [metaDialogOpen, setMetaDialogOpen] = useState(false)

    const zoomIntegration = userIntegrations?.find(i => i.integration_type === 'zoom')
    const gmailIntegration = userIntegrations?.find(i => i.integration_type === 'gmail')
    const googleCalendarIntegration = userIntegrations?.find(i => i.integration_type === 'google_calendar')
    const googleLastSyncAt = googleCalendarStatus === undefined
        ? googleCalendarIntegration?.last_sync_at ?? null
        : googleCalendarStatus.last_sync_at
    const googleLastSyncLabel = googleLastSyncAt
        ? `${formatRelativeTime(googleLastSyncAt)}`
        : "Not synced yet"
    const googleLastSyncAbsoluteLabel = formatDateTime(googleLastSyncAt)
    const aiProviderLabel = aiSettings?.provider
        ? AI_PROVIDERS.find((providerOption) => providerOption.value === aiSettings.provider)?.label
            ?? aiSettings.provider
        : "Not configured"
    const aiStatusLabel = aiSettings?.is_enabled ? "Enabled" : "Disabled"
    const aiStatusVariant = aiSettings?.is_enabled ? "default" : "secondary"
    const aiStatusIcon = aiSettings?.is_enabled ? CheckCircleIcon : AlertTriangleIcon
    const emailProviderLabel = resendSettings?.email_provider === "resend"
        ? "Resend"
        : resendSettings?.email_provider === "gmail"
            ? "Gmail"
            : "Not configured"
    const emailConfigured = Boolean(resendSettings?.email_provider)
    const emailStatusLabel = emailConfigured ? "Configured" : "Not configured"
    const emailStatusVariant = emailConfigured ? "default" : "secondary"
    const emailStatusIcon = emailConfigured ? CheckCircleIcon : AlertTriangleIcon
    const emailDetail = emailConfigured
        ? resendSettings?.email_provider === "resend"
            ? resendSettings?.from_email ?? "Resend configured"
            : resendSettings?.default_sender_email ?? "Gmail sender selected"
        : "Choose a provider"
    const messagingReadinessStatus = twilioReadiness?.overall_status
        ?? (twilioSettings?.enabled ? "unknown" : "not_configured")
    const messagingStatus = MESSAGING_STATUS_PRESENTATION[messagingReadinessStatus]
    const messagingSetupStepCount = twilioReadiness?.issues?.length ?? 0
    const messagingDetail = twilioSettings?.enabled
        ? "Twilio delivery enabled for configured routes"
        : messagingSetupStepCount > 0
            ? `${messagingSetupStepCount} setup step${messagingSetupStepCount === 1 ? "" : "s"} remaining`
            : "SMS and MMS"
    const inboundWebhooks = zapierSettings?.inbound_webhooks ?? []
    const zapierInboundConfigured =
        inboundWebhooks.some((hook) => hook.secret_configured)
        || Boolean(zapierSettings?.secret_configured)
    const zapierReportingConfigured = Boolean(
        zapierSettings?.outbound_webhook_url || zapierSettings?.outbound_secret_configured,
    )
    const zapierConfigured = zapierInboundConfigured || zapierReportingConfigured
    const zapierActive =
        inboundWebhooks.some((hook) => hook.is_active)
        || Boolean(zapierSettings?.is_active)
        || Boolean(zapierSettings?.outbound_enabled)
        || Boolean(zapierSettings?.donor_outbound_enabled)
    const zapierMappingPresentation = useZapierMappingPresentation(
        zapierSettings,
        pipelines,
        organizationIntegrationsEnabled,
    )
    const zapierMappingBadgeLabel = zapierMappingPresentation.label
    const zapierMappingBadgeVariant = zapierMappingPresentation.variant
    const zapierMappingDetail = zapierMappingPresentation.detail
    const zapierStatusLabel = zapierConfigured
        ? (zapierActive ? "Active" : "Configured")
        : "Not configured"
    const zapierStatusVariant = zapierConfigured ? "default" : "secondary"
    const zapierStatusIcon = zapierConfigured
        ? (zapierActive ? CheckCircleIcon : AlertTriangleIcon)
        : XCircleIcon
    const inboundSummary = inboundWebhooks.length
        ? `${inboundWebhooks.length} inbound webhook${inboundWebhooks.length === 1 ? "" : "s"}`
        : "Inbound webhook ready"
    const zapierDetail = [
        inboundSummary,
        `Surrogate reporting ${zapierSettings?.outbound_enabled ? "enabled" : "disabled"}`,
        Object.prototype.hasOwnProperty.call(zapierSettings ?? {}, "donor_outbound_enabled")
            ? `Donor reporting ${zapierSettings?.donor_outbound_enabled ? "enabled" : "disabled"}`
            : "Donor reporting unavailable",
    ].join(" · ")
    // Meta Lead Ads status
    const metaConnectionsCount = metaConnections.length
    const metaFormsCount = metaForms.length
    const metaMappedFormsCount = metaForms.filter(f => f.mapping_status === "mapped").length
    const metaCrmDatasetConfigured = Boolean(
        metaCrmDatasetSettings?.dataset_id && metaCrmDatasetSettings.access_token_configured
    )
    const metaCrmDatasetActive = metaCrmDatasetConfigured && Boolean(metaCrmDatasetSettings?.enabled)
    const metaConfigured = metaConnectionsCount > 0 || metaCrmDatasetConfigured
    const metaStatusLabel = metaCrmDatasetActive
        ? "Active"
        : metaConfigured
            ? "Configured"
            : "Not configured"
    const metaStatusVariant = metaConfigured ? "default" : "secondary"
    const metaStatusIcon = metaConfigured ? CheckCircleIcon : AlertTriangleIcon
    const metaDetailParts: string[] = []
    if (metaCrmDatasetConfigured) {
        metaDetailParts.push(metaCrmDatasetActive ? "CRM dataset enabled" : "CRM dataset configured")
    }
    metaDetailParts.push(
        `${metaFormsCount} lead form${metaFormsCount === 1 ? "" : "s"} · ${metaConnectionsCount} connection${metaConnectionsCount === 1 ? "" : "s"}`
    )
    const metaDetail = metaDetailParts.join(" · ")
    const AiStatusIcon = aiStatusIcon
    const EmailStatusIcon = emailStatusIcon
    const MessagingStatusIcon = messagingStatus.Icon
    const ZapierStatusIcon = zapierStatusIcon
    const MetaStatusIcon = metaStatusIcon

    return (
        <div className="flex min-h-dvh flex-col">
            <IntegrationsPageHeader
                activeScope={activeScope}
                canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                isFetching={isFetching}
                onScopeChange={setSelectedScope}
                onRefresh={() => {
                    if (organizationIntegrationsEnabled) void refetch()
                }}
            />

            {/* Main Content */}
            <div className="flex-1 space-y-6 p-6">
                {activeScope === "personal" ? (
                    <PersonalIntegrationsSection
                        zoomIntegration={zoomIntegration}
                        gmailIntegration={gmailIntegration}
                        googleCalendarIntegration={googleCalendarIntegration}
                        googleCalendarStatus={googleCalendarStatus}
                        googleHasSynced={Boolean(googleLastSyncAt)}
                        googleLastSyncLabel={googleLastSyncLabel}
                        googleLastSyncAbsoluteLabel={googleLastSyncAbsoluteLabel}
                        pendingState={{
                            zoomConnect: connectZoom.isPending,
                            gmailConnect: connectGmail.isPending,
                            googleCalendarConnect: connectGoogleCalendar.isPending,
                            googleCalendarSync: syncGoogleCalendarNow.isPending,
                            disconnect: disconnectIntegration.isPending,
                        }}
                        onConnectZoom={() => connectZoom.mutate()}
                        onConnectGmail={() => connectGmail.mutate()}
                        onConnectGoogleCalendar={() => connectGoogleCalendar.mutate()}
                        onSyncGoogleCalendar={() => syncGoogleCalendarNow.mutate()}
                        onDisconnect={(integrationType) => disconnectIntegration.mutateAsync(integrationType)}
                    />
                ) : (
                    <>
                        <OrganizationIntegrationsSection
                            canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                            aiSettingsLoading={aiSettingsLoading}
                            aiSettingsProvider={aiSettings?.provider ?? null}
                            aiProviderLabel={aiProviderLabel}
                            aiStatusLabel={aiStatusLabel}
                            aiStatusVariant={aiStatusVariant}
                            AiStatusIcon={AiStatusIcon}
                            resendSettingsLoading={resendSettingsLoading}
                            emailConfigured={emailConfigured}
                            emailProviderLabel={emailProviderLabel}
                            emailDetail={emailDetail}
                            emailStatusLabel={emailStatusLabel}
                            emailStatusVariant={emailStatusVariant}
                            EmailStatusIcon={EmailStatusIcon}
                            messagingSettingsLoading={twilioSettingsLoading || twilioReadinessLoading}
                            messagingStatusLabel={messagingStatus.label}
                            messagingStatusVariant={messagingStatus.variant}
                            MessagingStatusIcon={MessagingStatusIcon}
                            messagingDetail={messagingDetail}
                            zapierSettingsLoading={zapierSettingsLoading}
                            zapierStatusLabel={zapierStatusLabel}
                            zapierStatusVariant={zapierStatusVariant}
                            ZapierStatusIcon={ZapierStatusIcon}
                            zapierMappingBadgeLabel={zapierMappingBadgeLabel}
                            zapierMappingBadgeVariant={zapierMappingBadgeVariant}
                            zapierDetail={zapierDetail}
                            zapierMappingDetail={zapierMappingDetail}
                            metaCrmDatasetSettingsLoading={metaCrmDatasetSettingsLoading}
                            metaStatusLabel={metaStatusLabel}
                            metaStatusVariant={metaStatusVariant}
                            MetaStatusIcon={MetaStatusIcon}
                            metaDetail={metaDetail}
                            onConfigureAI={() => setAiDialogOpen(true)}
                            onConfigureEmail={() => setEmailDialogOpen(true)}
                            onConfigureZapier={() => setZapierDialogOpen(true)}
                            onConfigureMeta={() => setMetaDialogOpen(true)}
                        />

                        <IntegrationConfigurationDialogs
                            canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                            aiDialogOpen={aiDialogOpen}
                            emailDialogOpen={emailDialogOpen}
                            zapierDialogOpen={zapierDialogOpen}
                            metaDialogOpen={metaDialogOpen}
                            aiStatusLabel={aiStatusLabel}
                            aiStatusVariant={aiStatusVariant}
                            AiStatusIcon={AiStatusIcon}
                            emailStatusLabel={emailStatusLabel}
                            emailStatusVariant={emailStatusVariant}
                            EmailStatusIcon={EmailStatusIcon}
                            zapierStatusLabel={zapierStatusLabel}
                            zapierStatusVariant={zapierStatusVariant}
                            ZapierStatusIcon={ZapierStatusIcon}
                            zapierMappingBadgeLabel={zapierMappingBadgeLabel}
                            zapierMappingBadgeVariant={zapierMappingBadgeVariant}
                            metaStatusLabel={metaStatusLabel}
                            metaStatusVariant={metaStatusVariant}
                            MetaStatusIcon={MetaStatusIcon}
                            onAiDialogOpenChange={setAiDialogOpen}
                            onEmailDialogOpenChange={setEmailDialogOpen}
                            onZapierDialogOpenChange={setZapierDialogOpen}
                            onMetaDialogOpenChange={setMetaDialogOpen}
                        />

                        {healthData?.length ? (
                            <SystemIntegrationsSection
                                healthData={healthData}
                                canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                                metaFormsCount={metaFormsCount}
                                metaMappedFormsCount={metaMappedFormsCount}
                                metaAdAccounts={metaAdAccounts}
                                inboundWebhooksCount={inboundWebhooks.length}
                                zapierOutboundEnabled={Boolean(zapierSettings?.outbound_enabled)}
                                zapierDonorOutboundEnabled={
                                    Object.prototype.hasOwnProperty.call(
                                        zapierSettings ?? {},
                                        "donor_outbound_enabled",
                                    )
                                        ? Boolean(zapierSettings?.donor_outbound_enabled)
                                        : null
                                }
                            />
                        ) : null}
                    </>
                )}
            </div>
        </div>
    )
}

type BadgeVariant = "default" | "secondary" | "destructive"
type IconComponent = typeof CheckCircleIcon

const MESSAGING_STATUS_PRESENTATION: Record<
    TwilioReadinessStatus,
    { label: string; variant: BadgeVariant; Icon: IconComponent }
> = {
    ready: { label: "Ready", variant: "default", Icon: CheckCircleIcon },
    degraded: { label: "Needs attention", variant: "secondary", Icon: AlertTriangleIcon },
    blocked: { label: "Blocked", variant: "destructive", Icon: XCircleIcon },
    not_configured: { label: "Not configured", variant: "secondary", Icon: AlertTriangleIcon },
    action_required: { label: "Action required", variant: "destructive", Icon: AlertTriangleIcon },
    unknown: { label: "Verification pending", variant: "secondary", Icon: AlertTriangleIcon },
}

function IntegrationsPageHeader({
    activeScope,
    canManageOrganizationIntegrations,
    isFetching,
    onScopeChange,
    onRefresh,
}: {
    activeScope: IntegrationScope
    canManageOrganizationIntegrations: boolean
    isFetching: boolean
    onScopeChange: (scope: IntegrationScope) => void
    onRefresh: () => void
}) {
    const hasActions = canManageOrganizationIntegrations || activeScope === "organization"
    return (
        <PageHeader
            title="Integrations"
            actions={
                hasActions ? (
                    <>
                        {canManageOrganizationIntegrations ? (
                            <ToggleGroup
                                aria-label="Integration scope"
                                multiple={false}
                                value={[activeScope]}
                                onValueChange={(value) => {
                                    const nextScope = value[0]
                                    if (nextScope === "personal" || nextScope === "organization") {
                                        onScopeChange(nextScope)
                                    }
                                }}
                                variant="outline"
                                size="sm"
                            >
                                <ToggleGroupItem value="personal">Personal</ToggleGroupItem>
                                <ToggleGroupItem value="organization">Organization</ToggleGroupItem>
                            </ToggleGroup>
                        ) : null}
                        {activeScope === "organization" ? (
                            <Button variant="outline" size="sm" onClick={onRefresh} disabled={isFetching}>
                                <RefreshCwIcon
                                    className={`mr-2 size-4 ${isFetching ? "animate-spin" : ""} motion-reduce:animate-none`}
                                    aria-hidden="true"
                                />
                                Refresh
                            </Button>
                        ) : null}
                    </>
                ) : null
            }
        />
    )
}

function PersonalIntegrationsSection({
    zoomIntegration,
    gmailIntegration,
    googleCalendarIntegration,
    googleCalendarStatus,
    googleHasSynced,
    googleLastSyncLabel,
    googleLastSyncAbsoluteLabel,
    pendingState,
    onConnectZoom,
    onConnectGmail,
    onConnectGoogleCalendar,
    onSyncGoogleCalendar,
    onDisconnect,
}: {
    zoomIntegration: IntegrationStatus | undefined
    gmailIntegration: IntegrationStatus | undefined
    googleCalendarIntegration: IntegrationStatus | undefined
    googleCalendarStatus: GoogleCalendarStatusResponse | undefined
    googleHasSynced: boolean
    googleLastSyncLabel: string
    googleLastSyncAbsoluteLabel: string
    pendingState: {
        zoomConnect: boolean
        gmailConnect: boolean
        googleCalendarConnect: boolean
        googleCalendarSync: boolean
        disconnect: boolean
    }
    onConnectZoom: () => void
    onConnectGmail: () => void
    onConnectGoogleCalendar: () => void
    onSyncGoogleCalendar: () => void
    onDisconnect: (integrationType: PersonalIntegrationType) => Promise<unknown>
}) {
    const [googleCalendarDialogOpen, setGoogleCalendarDialogOpen] = useState(false)
    // The calendar settings load after the dialog opens, so the default first-tabbable focus would
    // land on the Appointment types link. Focus the dialog itself; Tab then starts at Sync now.
    const googleCalendarDialogRef = useRef<HTMLDivElement>(null)
    const googleCalendarConnected = Boolean(googleCalendarIntegration?.connected)
    const disconnect = async (integrationType: PersonalIntegrationType) => {
        await onDisconnect(integrationType)
        toast.success(`${PERSONAL_INTEGRATION_LABELS[integrationType]} disconnected`)
    }
    const googleDetail = googleCalendarIntegration
        ? [
            googleCalendarIntegration.account_email,
            googleHasSynced ? `Last sync ${googleLastSyncLabel}` : googleLastSyncLabel,
        ]
            .filter(Boolean)
            .join(" · ")
        : "Calendar sync and Meet links"

    return (
        <>
            <IntegrationList title="Your accounts" testId="personal-integrations-list">
                <IntegrationRow
                    Icon={VideoIcon}
                    iconContainerClassName="bg-blue-100 dark:bg-blue-900"
                    iconClassName="text-blue-600 dark:text-blue-400"
                    title="Zoom"
                    detail={zoomIntegration?.account_email ?? "Video appointments"}
                    status={<ConnectionStatusBadge connected={Boolean(zoomIntegration)} />}
                    action={zoomIntegration ? (
                        <Button
                            variant="outline"
                            size="sm"
                            aria-label="Manage Zoom"
                            render={<Link href="/settings/integrations/zoom" />}
                        >
                            Manage
                        </Button>
                    ) : (
                        <IntegrationConnectButton
                            label="Connect Zoom"
                            pending={pendingState.zoomConnect}
                            onConnect={onConnectZoom}
                        />
                    )}
                />

                <IntegrationRow
                    Icon={MailIcon}
                    iconContainerClassName="bg-red-100 dark:bg-red-900"
                    iconClassName="text-red-600 dark:text-red-400"
                    title="Gmail"
                    detail={gmailIntegration?.account_email ?? "Email sending"}
                    status={<ConnectionStatusBadge connected={Boolean(gmailIntegration)} />}
                    action={gmailIntegration ? (
                        <ConfirmDialog
                            trigger={(
                                <Button
                                    variant="outline"
                                    size="sm"
                                    aria-label="Disconnect Gmail"
                                    disabled={pendingState.disconnect}
                                >
                                    Disconnect…
                                </Button>
                            )}
                            title="Disconnect Gmail?"
                            description="Emails can no longer be sent from this Gmail account."
                            confirmLabel="Disconnect"
                            errorFallback="Couldn't disconnect Gmail. Try again."
                            onConfirm={() => disconnect("gmail")}
                        />
                    ) : (
                        <IntegrationConnectButton
                            label="Connect Gmail"
                            pending={pendingState.gmailConnect}
                            onConnect={onConnectGmail}
                        />
                    )}
                />

                <IntegrationRow
                    Icon={CalendarIcon}
                    iconContainerClassName="bg-emerald-100 dark:bg-emerald-900"
                    iconClassName="text-emerald-600 dark:text-emerald-400"
                    title="Google Calendar & Meet"
                    detail={googleDetail}
                    status={<ConnectionStatusBadge connected={Boolean(googleCalendarIntegration)} />}
                    action={googleCalendarIntegration ? (
                        <Button
                            variant="outline"
                            size="sm"
                            aria-label="Manage Google Calendar & Meet"
                            onClick={() => setGoogleCalendarDialogOpen(true)}
                            disabled={!googleCalendarConnected}
                        >
                            Manage
                        </Button>
                    ) : (
                        <IntegrationConnectButton
                            label="Connect Google Calendar"
                            pending={pendingState.googleCalendarConnect}
                            onConnect={onConnectGoogleCalendar}
                        />
                    )}
                />
            </IntegrationList>

            <Dialog
                open={googleCalendarDialogOpen && googleCalendarConnected}
                onOpenChange={setGoogleCalendarDialogOpen}
            >
                <DialogContent
                    ref={googleCalendarDialogRef}
                    initialFocus={googleCalendarDialogRef}
                    layout="sectioned"
                    size="2xl"
                >
                    <DialogHeader
                        icon={<CalendarIcon />}
                        status={<ConnectionStatusBadge connected />}
                    >
                        <DialogTitle>Google Calendar &amp; Meet</DialogTitle>
                        {googleCalendarIntegration?.account_email ? (
                            <DialogDescription className="truncate">
                                {googleCalendarIntegration.account_email}
                            </DialogDescription>
                        ) : null}
                    </DialogHeader>
                    {googleCalendarDialogOpen ? (
                        <GoogleCalendarBindingSettings
                            enabled={googleCalendarConnected}
                            lastSyncLabel={googleLastSyncLabel}
                            lastSyncTitle={googleLastSyncAbsoluteLabel || undefined}
                            onLegacySync={onSyncGoogleCalendar}
                            legacySyncPending={pendingState.googleCalendarSync}
                            onSaved={() => setGoogleCalendarDialogOpen(false)}
                            notice={googleCalendarStatus && !googleCalendarStatus.tasks_accessible ? (
                                // tasks_error holds raw provider codes and messages, so it is never shown.
                                <Alert role="status" className="border-warning/40 bg-warning/10">
                                    <AlertTriangleIcon className="text-warning" aria-hidden="true" />
                                    <AlertTitle>Google Tasks sync unavailable</AlertTitle>
                                    <AlertDescription>Tasks are not added to Google Tasks.</AlertDescription>
                                </Alert>
                            ) : null}
                            footerStart={(
                                <ConfirmDialog
                                    trigger={(
                                        <Button variant="destructive-ghost" disabled={pendingState.disconnect}>
                                            Disconnect…
                                        </Button>
                                    )}
                                    title="Disconnect Google Calendar?"
                                    description="Calendar sync stops and new Google Meet links are no longer created."
                                    confirmLabel="Disconnect"
                                    errorFallback="Couldn't disconnect Google Calendar. Try again."
                                    onConfirm={async () => {
                                        await disconnect("google_calendar")
                                        setGoogleCalendarDialogOpen(false)
                                    }}
                                />
                            )}
                        />
                    ) : null}
                </DialogContent>
            </Dialog>
        </>
    )
}

type PersonalIntegrationType = "zoom" | "gmail" | "google_calendar"

const PERSONAL_INTEGRATION_LABELS: Record<PersonalIntegrationType, string> = {
    zoom: "Zoom",
    gmail: "Gmail",
    google_calendar: "Google Calendar",
}

// Token colors keep the connected state readable in both themes; the Badge has no success variant.
function ConnectionStatusBadge({ connected }: { connected: boolean }) {
    return connected ? (
        <Badge variant="outline" className="border-success/30 bg-success/10 text-success">
            <CheckCircleIcon aria-hidden="true" />
            Connected
        </Badge>
    ) : (
        <Badge variant="secondary">Not connected</Badge>
    )
}

function IntegrationConnectButton({
    label,
    pending,
    onConnect,
}: {
    label: string
    pending: boolean
    onConnect: () => void
}) {
    return (
        <Button size="sm" onClick={onConnect} disabled={pending} aria-label={label}>
            {pending ? (
                <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
            ) : (
                <LinkIcon aria-hidden="true" />
            )}
            Connect
        </Button>
    )
}

function IntegrationList({
    title,
    testId,
    children,
}: {
    title: string
    testId: string
    children: ReactNode
}) {
    const headingId = `${testId}-heading`
    return (
        <section aria-labelledby={headingId}>
            <h2 id={headingId} className="mb-3 text-lg font-semibold">{title}</h2>
            <ul data-testid={testId} className="divide-y rounded-xl border bg-card">
                {children}
            </ul>
        </section>
    )
}

function IntegrationRow({
    Icon,
    iconContainerClassName,
    iconClassName,
    title,
    detail,
    status,
    action,
}: {
    Icon: IconComponent
    iconContainerClassName: string
    iconClassName: string
    title: string
    detail: ReactNode
    status: ReactNode
    action: ReactNode
}) {
    return (
        <li
            data-slot="integration-row"
            className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:gap-4"
        >
            <div className="flex min-w-0 flex-1 items-center gap-3">
                <div className={`flex size-10 shrink-0 items-center justify-center rounded-lg ${iconContainerClassName}`}>
                    <Icon className={`size-5 ${iconClassName}`} aria-hidden="true" />
                </div>
                <div className="min-w-0 space-y-0.5">
                    <h3 className="text-sm font-medium">{title}</h3>
                    <div className="text-xs break-words text-muted-foreground">{detail}</div>
                </div>
            </div>
            <div className="flex items-center justify-between gap-3 pl-13 sm:shrink-0 sm:justify-end sm:pl-0">
                <div className="flex flex-wrap items-center gap-2">{status}</div>
                {action}
            </div>
        </li>
    )
}

function OrganizationIntegrationsSection({
    canManageOrganizationIntegrations,
    aiSettingsLoading,
    aiSettingsProvider,
    aiProviderLabel,
    aiStatusLabel,
    aiStatusVariant,
    AiStatusIcon,
    resendSettingsLoading,
    emailConfigured,
    emailProviderLabel,
    emailDetail,
    emailStatusLabel,
    emailStatusVariant,
    EmailStatusIcon,
    messagingSettingsLoading,
    messagingStatusLabel,
    messagingStatusVariant,
    MessagingStatusIcon,
    messagingDetail,
    zapierSettingsLoading,
    zapierStatusLabel,
    zapierStatusVariant,
    ZapierStatusIcon,
    zapierMappingBadgeLabel,
    zapierMappingBadgeVariant,
    zapierDetail,
    zapierMappingDetail,
    metaCrmDatasetSettingsLoading,
    metaStatusLabel,
    metaStatusVariant,
    MetaStatusIcon,
    metaDetail,
    onConfigureAI,
    onConfigureEmail,
    onConfigureZapier,
    onConfigureMeta,
}: {
    canManageOrganizationIntegrations: boolean
    aiSettingsLoading: boolean
    aiSettingsProvider: string | null
    aiProviderLabel: string
    aiStatusLabel: string
    aiStatusVariant: BadgeVariant
    AiStatusIcon: IconComponent
    resendSettingsLoading: boolean
    emailConfigured: boolean
    emailProviderLabel: string
    emailDetail: string
    emailStatusLabel: string
    emailStatusVariant: BadgeVariant
    EmailStatusIcon: IconComponent
    messagingSettingsLoading: boolean
    messagingStatusLabel: string
    messagingStatusVariant: BadgeVariant
    MessagingStatusIcon: IconComponent
    messagingDetail: string
    zapierSettingsLoading: boolean
    zapierStatusLabel: string
    zapierStatusVariant: BadgeVariant
    ZapierStatusIcon: IconComponent
    zapierMappingBadgeLabel: string
    zapierMappingBadgeVariant: BadgeVariant
    zapierDetail: string
    zapierMappingDetail: string
    metaCrmDatasetSettingsLoading: boolean
    metaStatusLabel: string
    metaStatusVariant: BadgeVariant
    MetaStatusIcon: IconComponent
    metaDetail: string
    onConfigureAI: () => void
    onConfigureEmail: () => void
    onConfigureZapier: () => void
    onConfigureMeta: () => void
}) {
    const statusBadge = (
        isLoading: boolean,
        label: string,
        variant: BadgeVariant,
        StatusIcon: IconComponent,
    ) => isLoading ? (
        <span role="status">
            <Loader2Icon
                className="size-4 animate-spin text-muted-foreground motion-reduce:animate-none"
                aria-hidden="true"
            />
            <span className="sr-only">Loading status</span>
        </span>
    ) : (
        <Badge variant={variant}>
            <StatusIcon aria-hidden="true" />
            {label}
        </Badge>
    )

    return (
        <IntegrationList title="Organization" testId="organization-integrations-list">
            <IntegrationRow
                Icon={SparklesIcon}
                iconContainerClassName="bg-purple-100 dark:bg-purple-900"
                iconClassName="text-purple-600 dark:text-purple-400"
                title="AI Assistant"
                detail={aiSettingsProvider ? aiProviderLabel : "No provider configured"}
                status={statusBadge(aiSettingsLoading, aiStatusLabel, aiStatusVariant, AiStatusIcon)}
                action={(
                    <OrganizationIntegrationAction
                        title="AI Assistant"
                        canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                        onConfigure={onConfigureAI}
                    />
                )}
            />
            <IntegrationRow
                Icon={SendIcon}
                iconContainerClassName="bg-teal-100 dark:bg-teal-900"
                iconClassName="text-teal-600 dark:text-teal-400"
                title="Email delivery"
                detail={emailConfigured ? `${emailProviderLabel} · ${emailDetail}` : "No provider"}
                status={statusBadge(resendSettingsLoading, emailStatusLabel, emailStatusVariant, EmailStatusIcon)}
                action={(
                    <OrganizationIntegrationAction
                        title="Email delivery"
                        canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                        onConfigure={onConfigureEmail}
                    />
                )}
            />
            <IntegrationRow
                Icon={MessageSquareTextIcon}
                iconContainerClassName="bg-cyan-100 dark:bg-cyan-900"
                iconClassName="text-cyan-700 dark:text-cyan-300"
                title="Messaging (Twilio)"
                detail={messagingDetail}
                status={statusBadge(
                    messagingSettingsLoading,
                    messagingStatusLabel,
                    messagingStatusVariant,
                    MessagingStatusIcon,
                )}
                action={(
                    <OrganizationIntegrationAction
                        title="Messaging"
                        canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                        href="/settings/integrations/messaging"
                    />
                )}
            />
            <IntegrationRow
                Icon={LinkIcon}
                iconContainerClassName="bg-primary/10 dark:bg-primary/20"
                iconClassName="text-primary"
                title="Zapier"
                detail={(
                    <>
                        <p>{zapierDetail}</p>
                        {zapierMappingDetail ? <p>{zapierMappingDetail}</p> : null}
                    </>
                )}
                status={(
                    <>
                        {statusBadge(zapierSettingsLoading, zapierStatusLabel, zapierStatusVariant, ZapierStatusIcon)}
                        {zapierSettingsLoading ? null : (
                            <Badge
                                data-testid="zapier-mapping-health-card-badge"
                                variant={zapierMappingBadgeVariant}
                            >
                                {zapierMappingBadgeLabel}
                            </Badge>
                        )}
                    </>
                )}
                action={(
                    <OrganizationIntegrationAction
                        title="Zapier"
                        canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                        onConfigure={onConfigureZapier}
                    />
                )}
            />
            <IntegrationRow
                Icon={MegaphoneIcon}
                iconContainerClassName="bg-blue-100 dark:bg-blue-900"
                iconClassName="text-blue-600 dark:text-blue-400"
                title="Meta Lead Ads"
                detail={metaDetail}
                status={statusBadge(metaCrmDatasetSettingsLoading, metaStatusLabel, metaStatusVariant, MetaStatusIcon)}
                action={(
                    <OrganizationIntegrationAction
                        title="Meta Lead Ads"
                        canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                        onConfigure={onConfigureMeta}
                    />
                )}
            />
        </IntegrationList>
    )
}

function OrganizationIntegrationAction({
    title,
    canManageOrganizationIntegrations,
    href,
    onConfigure,
}: {
    title: string
    canManageOrganizationIntegrations: boolean
    href?: string
    onConfigure?: () => void
}) {
    if (!canManageOrganizationIntegrations) {
        return (
            <Button variant="outline" size="sm" disabled>
                Admin access required
            </Button>
        )
    }
    if (href) {
        return (
            <Button
                variant="outline"
                size="sm"
                aria-label={`Configure ${title}`}
                render={<Link href={href} />}
            >
                Configure
            </Button>
        )
    }
    return (
        <Button variant="outline" size="sm" aria-label={`Configure ${title}`} onClick={onConfigure}>
            Configure
        </Button>
    )
}

function IntegrationConfigurationDialogs({
    canManageOrganizationIntegrations,
    aiDialogOpen,
    emailDialogOpen,
    zapierDialogOpen,
    metaDialogOpen,
    aiStatusLabel,
    aiStatusVariant,
    AiStatusIcon,
    emailStatusLabel,
    emailStatusVariant,
    EmailStatusIcon,
    zapierStatusLabel,
    zapierStatusVariant,
    ZapierStatusIcon,
    zapierMappingBadgeLabel,
    zapierMappingBadgeVariant,
    metaStatusLabel,
    metaStatusVariant,
    MetaStatusIcon,
    onAiDialogOpenChange,
    onEmailDialogOpenChange,
    onZapierDialogOpenChange,
    onMetaDialogOpenChange,
}: {
    canManageOrganizationIntegrations: boolean
    aiDialogOpen: boolean
    emailDialogOpen: boolean
    zapierDialogOpen: boolean
    metaDialogOpen: boolean
    aiStatusLabel: string
    aiStatusVariant: BadgeVariant
    AiStatusIcon: IconComponent
    emailStatusLabel: string
    emailStatusVariant: BadgeVariant
    EmailStatusIcon: IconComponent
    zapierStatusLabel: string
    zapierStatusVariant: BadgeVariant
    ZapierStatusIcon: IconComponent
    zapierMappingBadgeLabel: string
    zapierMappingBadgeVariant: BadgeVariant
    metaStatusLabel: string
    metaStatusVariant: BadgeVariant
    MetaStatusIcon: IconComponent
    onAiDialogOpenChange: (open: boolean) => void
    onEmailDialogOpenChange: (open: boolean) => void
    onZapierDialogOpenChange: (open: boolean) => void
    onMetaDialogOpenChange: (open: boolean) => void
}) {
    return (
        <>
            <Dialog
                open={canManageOrganizationIntegrations && aiDialogOpen}
                onOpenChange={(open) => {
                    if (!canManageOrganizationIntegrations) return
                    onAiDialogOpenChange(open)
                }}
            >
                <DialogContent layout="sectioned" size="4xl">
                    <DialogHeader
                        icon={<SparklesIcon />}
                        status={(
                            <Badge variant={aiStatusVariant}>
                                <AiStatusIcon aria-hidden="true" />
                                {aiStatusLabel}
                            </Badge>
                        )}
                    >
                        <DialogTitle>AI Configuration</DialogTitle>
                    </DialogHeader>
                    {aiDialogOpen ? <AIConfigurationSection /> : null}
                </DialogContent>
            </Dialog>

            <Dialog
                open={canManageOrganizationIntegrations && emailDialogOpen}
                onOpenChange={(open) => {
                    if (!canManageOrganizationIntegrations) return
                    onEmailDialogOpenChange(open)
                }}
            >
                <DialogContent layout="sectioned" size="4xl">
                    <DialogHeader
                        icon={<SendIcon />}
                        status={(
                            <Badge variant={emailStatusVariant}>
                                <EmailStatusIcon aria-hidden="true" />
                                {emailStatusLabel}
                            </Badge>
                        )}
                    >
                        <DialogTitle>Email Configuration</DialogTitle>
                    </DialogHeader>
                    {emailDialogOpen ? <EmailConfigurationSection /> : null}
                </DialogContent>
            </Dialog>

            <Dialog
                open={canManageOrganizationIntegrations && zapierDialogOpen}
                onOpenChange={(open) => {
                    if (!canManageOrganizationIntegrations) return
                    onZapierDialogOpenChange(open)
                }}
            >
                {/* Wider than size="5xl" so the Activity tables fit; a fixed height stops tab switches from resizing it. */}
                <DialogContent
                    layout="sectioned"
                    size="5xl"
                    className="h-[min(calc(100dvh-2rem),55rem)] max-w-[1240px]"
                >
                    {zapierDialogOpen ? (
                        <ZapierWebhookSection
                            statusLabel={zapierStatusLabel}
                            statusVariant={zapierStatusVariant}
                            StatusIcon={ZapierStatusIcon}
                            mappingBadgeLabel={zapierMappingBadgeLabel}
                            mappingBadgeVariant={zapierMappingBadgeVariant}
                        />
                    ) : null}
                </DialogContent>
            </Dialog>

            <Dialog
                open={canManageOrganizationIntegrations && metaDialogOpen}
                onOpenChange={(open) => {
                    if (!canManageOrganizationIntegrations) return
                    onMetaDialogOpenChange(open)
                }}
            >
                <DialogContent layout="sectioned" size="4xl">
                    <DialogHeader
                        icon={<MegaphoneIcon />}
                        status={(
                            <Badge variant={metaStatusVariant}>
                                <MetaStatusIcon aria-hidden="true" />
                                {metaStatusLabel}
                            </Badge>
                        )}
                    >
                        <DialogTitle>Meta Lead Ads + CRM Dataset</DialogTitle>
                    </DialogHeader>
                    {metaDialogOpen ? <MetaConfigurationSection /> : null}
                </DialogContent>
            </Dialog>
        </>
    )
}

// Rendered only when the health endpoint returns rows; the organization list above already
// covers the empty case, so no empty state is shown here.
function SystemIntegrationsSection({
    healthData,
    canManageOrganizationIntegrations,
    metaFormsCount,
    metaMappedFormsCount,
    metaAdAccounts,
    inboundWebhooksCount,
    zapierOutboundEnabled,
    zapierDonorOutboundEnabled,
}: {
    healthData: IntegrationHealth[]
    canManageOrganizationIntegrations: boolean
    metaFormsCount: number
    metaMappedFormsCount: number
    metaAdAccounts: MetaAdAccount[]
    inboundWebhooksCount: number
    zapierOutboundEnabled: boolean
    zapierDonorOutboundEnabled: boolean | null
}) {
    return (
        <section aria-labelledby="system-integrations-heading">
            <h2 id="system-integrations-heading" className="mb-3 text-lg font-semibold">System health</h2>
            <div
                data-testid="system-integrations-grid"
                className="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
            >
                {healthData.map((integration) => (
                    <SystemIntegrationCard
                        key={integration.id}
                        integration={integration}
                        canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                        metaFormsCount={metaFormsCount}
                        metaMappedFormsCount={metaMappedFormsCount}
                        metaAdAccounts={metaAdAccounts}
                        inboundWebhooksCount={inboundWebhooksCount}
                        zapierOutboundEnabled={zapierOutboundEnabled}
                        zapierDonorOutboundEnabled={zapierDonorOutboundEnabled}
                    />
                ))}
            </div>
        </section>
    )
}

function SystemIntegrationCard({
    integration,
    canManageOrganizationIntegrations,
    metaFormsCount,
    metaMappedFormsCount,
    metaAdAccounts,
    inboundWebhooksCount,
    zapierOutboundEnabled,
    zapierDonorOutboundEnabled,
}: {
    integration: IntegrationHealth
    canManageOrganizationIntegrations: boolean
    metaFormsCount: number
    metaMappedFormsCount: number
    metaAdAccounts: MetaAdAccount[]
    inboundWebhooksCount: number
    zapierOutboundEnabled: boolean
    zapierDonorOutboundEnabled: boolean | null
}) {
    const typeConfig = integrationTypeConfig[integration.integration_type] || {
        icon: ServerIcon,
        label: integration.integration_type.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase()),
        description: "Custom integration",
    }
    const status = statusConfig[integration.status] || statusConfig.error
    const configStatus = configStatusLabels[integration.config_status]
        ?? configStatusLabels.configured
        ?? { label: "Configured", variant: "default" as const }
    const Icon = typeConfig.icon
    const StatusIcon = status.icon
    const metricsLabel = getSystemIntegrationMetricsLabel({
        integrationType: integration.integration_type,
        metaFormsCount,
        metaMappedFormsCount,
        metaAdAccounts,
        inboundWebhooksCount,
        zapierOutboundEnabled,
        zapierDonorOutboundEnabled,
    })

    return (
        <Card className="relative overflow-hidden">
            <div className={`absolute left-0 top-0 h-full w-1 ${getIntegrationStatusBarClass(integration.status)}`} />

            <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                        <div className="flex size-10 items-center justify-center rounded-lg bg-muted">
                            <Icon className="size-5" aria-hidden="true" />
                        </div>
                        <div>
                            <CardTitle className="text-base">{typeConfig.label}</CardTitle>
                            {integration.integration_key ? (
                                <p className="text-xs text-muted-foreground">
                                    Page: {integration.integration_key}
                                </p>
                            ) : null}
                        </div>
                    </div>
                    <Badge variant={status.badge} className="flex items-center gap-1">
                        <StatusIcon className="size-3" aria-hidden="true" />
                        {status.label}
                    </Badge>
                </div>
                <CardDescription className="mt-2 text-xs">{typeConfig.description}</CardDescription>
            </CardHeader>

            <CardContent className="space-y-3">
                {metricsLabel ? (
                    <div className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
                        <ActivityIcon className="size-3.5 shrink-0" aria-hidden="true" />
                        {metricsLabel}
                    </div>
                ) : null}

                <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Configuration</span>
                    <Badge variant={configStatus.variant} className="text-xs">
                        <KeyIcon className="mr-1 size-3" aria-hidden="true" />
                        {configStatus.label}
                    </Badge>
                </div>

                <SystemIntegrationTimestamps integration={integration} />
                <SystemIntegrationErrorDetails integration={integration} />
                <SystemIntegrationAction
                    integration={integration}
                    canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                />
            </CardContent>
        </Card>
    )
}

function SystemIntegrationTimestamps({ integration }: { integration: IntegrationHealth }) {
    return (
        <div className="space-y-1 text-xs">
            {integration.last_success_at ? (
                <div className="flex items-center justify-between text-muted-foreground">
                    <span>Last success</span>
                    <span className="text-green-600">
                        {formatRelativeTime(integration.last_success_at, "Never")}
                    </span>
                </div>
            ) : null}
            {integration.last_error_at ? (
                <div className="flex items-center justify-between text-muted-foreground">
                    <span>Last error</span>
                    <span className="text-red-600">
                        {formatRelativeTime(integration.last_error_at, "Never")}
                    </span>
                </div>
            ) : null}
        </div>
    )
}

function SystemIntegrationErrorDetails({ integration }: { integration: IntegrationHealth }) {
    return (
        <>
            {integration.error_count_24h > 0 ? (
                <div className="flex items-center justify-between rounded-md bg-red-100 px-3 py-2 text-sm dark:bg-red-900/30">
                    <span className="text-red-700 dark:text-red-300">Errors (24h)</span>
                    <span className="font-semibold text-red-700 dark:text-red-300">
                        {integration.error_count_24h}
                    </span>
                </div>
            ) : null}
            {integration.last_error ? (
                <div className="rounded-md bg-muted p-2">
                    <p className="text-xs text-muted-foreground line-clamp-2">
                        {integration.last_error}
                    </p>
                </div>
            ) : null}
        </>
    )
}

function SystemIntegrationAction({
    integration,
    canManageOrganizationIntegrations,
}: {
    integration: IntegrationHealth
    canManageOrganizationIntegrations: boolean
}) {
    if (integration.config_status === "configured") {
        return null
    }

    if (!canManageOrganizationIntegrations) {
        return (
            <p className="text-xs text-muted-foreground text-center">
                Admin access required to configure
            </p>
        )
    }

    if (integration.integration_type === "meta_leads" || integration.integration_type === "meta_capi") {
        return (
            <Button
                render={<Link href="/settings/integrations/meta" />}
                variant="outline"
                size="sm"
                className="w-full"
            >
                <KeyIcon className="mr-2 size-3" aria-hidden="true" />
                {integration.config_status === "expired_token" ? "Refresh Token" : "Configure"}
            </Button>
        )
    }

    return (
        <p className="text-xs text-muted-foreground text-center">
            Configure via CLI
        </p>
    )
}

function getSystemIntegrationMetricsLabel({
    integrationType,
    metaFormsCount,
    metaMappedFormsCount,
    metaAdAccounts,
    inboundWebhooksCount,
    zapierOutboundEnabled,
    zapierDonorOutboundEnabled,
}: {
    integrationType: string
    metaFormsCount: number
    metaMappedFormsCount: number
    metaAdAccounts: MetaAdAccount[]
    inboundWebhooksCount: number
    zapierOutboundEnabled: boolean
    zapierDonorOutboundEnabled: boolean | null
}): string | null {
    if (integrationType === "meta_leads") {
        return `${metaFormsCount} form${metaFormsCount === 1 ? "" : "s"} synced · ${metaMappedFormsCount} mapped`
    }
    if (integrationType === "meta_capi") {
        const capiEnabledCount = metaAdAccounts.filter((account) => account.capi_enabled).length
        return `${capiEnabledCount} ad account${capiEnabledCount === 1 ? "" : "s"} with CAPI enabled`
    }
    if (integrationType === "zapier") {
        const donorStatus = zapierDonorOutboundEnabled === null
            ? "unavailable"
            : zapierDonorOutboundEnabled
                ? "enabled"
                : "disabled"
        return `${inboundWebhooksCount} inbound webhook${inboundWebhooksCount === 1 ? "" : "s"} · Surrogate reporting ${zapierOutboundEnabled ? "enabled" : "disabled"} · Donor reporting ${donorStatus}`
    }
    return null
}

function getIntegrationStatusBarClass(status: IntegrationHealth["status"]): string {
    if (status === "healthy") return "bg-green-500"
    if (status === "degraded") return "bg-yellow-500"
    return "bg-red-500"
}
