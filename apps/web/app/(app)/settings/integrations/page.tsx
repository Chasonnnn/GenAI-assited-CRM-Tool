"use client"

import { useReducer, useState, type ReactNode } from "react"
import Link from "@/components/app-link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
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
} from "lucide-react"
import { useIntegrationHealth } from "@/lib/hooks/use-ops"
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
import {
    useZapierSettings,
    useZapierTestLead,
    useUpdateZapierOutboundSettings,
    useZapierOutboundTest,
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
import { CopyIcon, SendIcon, RotateCwIcon, ActivityIcon, PlusIcon } from "lucide-react"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { toast } from "@/components/ui/toast"
import type { IntegrationStatus, GoogleCalendarStatusResponse } from "@/lib/api/integrations"
import type { IntegrationHealth } from "@/lib/api/ops"
import type { EligibleSender, ResendSettings } from "@/lib/api/resend"
import type { Pipeline, StageSemantics } from "@/lib/api/pipelines"
import type {
    MetaCrmDatasetEventMappingItem,
} from "@/lib/api/meta-crm-dataset"
import type {
    ZapierEventMappingItem,
    ZapierFieldPasteResponse,
    ZapierOutboundEvent,
    ZapierStageBucket,
} from "@/lib/api/zapier"
import { getStageSemantics } from "@/lib/surrogate-stage-context"

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

const UNTRACKED_BUCKET_VALUE = "__none__"

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

function formatZapierSource(source: string): string {
    if (source === "automatic") return "Automatic"
    if (source === "workflow") return "Workflow"
    if (source === "test") return "Test"
    return source.replace(/_/g, " ")
}

function formatZapierReason(reason: string | null | undefined): string {
    if (!reason) return "—"
    return reason.replace(/_/g, " ")
}

function getErrorMessage(error: unknown, fallback: string) {
    if (error instanceof Error && error.message) return error.message
    return fallback
}

function copyToClipboard(text: string) {
    navigator.clipboard
        .writeText(text)
        .then(() => toast.success("Copied to clipboard"))
        .catch(() => toast.error("Failed to copy"))
}

// AI provider options
const AI_PROVIDERS = [
    {
        value: "gemini",
        label: "Google Gemini",
        models: ["gemini-3-flash-preview", "gemini-3-pro-preview"],
    },
    {
        value: "vertex_api_key",
        label: "Vertex AI (API Key)",
        models: ["gemini-3-flash-preview", "gemini-3-pro-preview"],
    },
    {
        value: "vertex_wif",
        label: "Vertex AI (WIF)",
        models: ["gemini-3-flash-preview", "gemini-3-pro-preview"],
    },
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
    fromEmail: string
    fromName: string
    replyTo: string
    webhookSigningSecret: string
    defaultSender: string
}

type EmailConfigurationUiState = {
    keyTested: { valid: boolean; error?: string | null; verified_domains?: string[] } | null
    saved: boolean
    isEditingKey: boolean
    hasUserEdited: boolean
}

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
    sendHashedPii: boolean
    eventMapping: ZapierEventMappingItem[]
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

function getSingleZapierFormId(
    forms: Array<{
        is_active?: boolean
        page_id?: string | null
        form_external_id?: string | null
    }>,
) {
    const activeZapierForms = forms.filter(
        (form) =>
            form.is_active &&
            (form.page_id === "zapier" || form.form_external_id?.startsWith("zapier-"))
    )
    if (activeZapierForms.length !== 1) return ""
    return activeZapierForms[0]?.form_external_id?.trim() ?? ""
}

function createZapierOutboundDraftKey(
    settings:
        | {
            outbound_webhook_url?: string | null
            outbound_enabled?: boolean | null
            send_hashed_pii?: boolean | null
            event_mapping?: ZapierEventMappingItem[] | null
        }
        | null
        | undefined,
    pipelines: Pipeline[] | null | undefined,
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
        stageKey,
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
        }
        | null
        | undefined,
    pipelines: Pipeline[] | null | undefined,
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
            sendHashedPii: Boolean(settings?.send_hashed_pii),
            eventMapping,
            selectedOutboundStage,
        },
    }
}

function AIConfigurationSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
    const { data: aiSettings, isLoading } = useAISettings()

    return (
        <AIConfigurationSectionContent
            key={aiSettings ? "loaded" : "loading"}
            variant={variant}
            aiSettings={aiSettings}
            isLoading={isLoading}
        />
    )
}

function AIConfigurationSectionContent({
    variant,
    aiSettings,
    isLoading,
}: {
    variant: "page" | "dialog"
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
            "us-central1",
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
    const showHeading = variant === "page"
    const containerClass = showHeading ? "border-t pt-6" : "space-y-4"

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
        await updateSettings.mutateAsync(update)
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
            toast.error(error instanceof Error ? error.message : "Failed to accept consent")
        }
    }

    if (isLoading) {
        return (
            <AIConfigurationLoadingState
                containerClass={containerClass}
                showHeading={showHeading}
            />
        )
    }

    return (
        <div className={containerClass}>
            {showHeading && <AIConfigurationHeading />}

            {!consentAccepted && consentInfo ? (
                <AIConsentCard
                    consentText={consentInfo.consent_text}
                    pending={acceptConsent.isPending}
                    onAccept={handleAcceptConsent}
                />
            ) : null}

            <AISettingsCard
                aiForm={aiForm}
                aiUi={aiUi}
                apiKeyMasked={aiSettings?.api_key_masked ?? null}
                consentAccepted={consentAccepted}
                selectedProviderModels={selectedProviderModels}
                gcpIntegration={gcpIntegration}
                vertexReady={vertexReady}
                pendingState={{
                    keyTest: testKey.isPending,
                    settingsUpdate: updateSettings.isPending,
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
                onDisconnectGcp={() => disconnectIntegration.mutate("gcp")}
                onSave={handleSave}
            />
        </div>
    )
}

type UpdateAiConfigurationForm = <K extends keyof AiConfigurationFormState>(
    field: K,
    value: AiConfigurationFormState[K],
) => void

function AIConfigurationLoadingState({
    containerClass,
    showHeading,
}: {
    containerClass: string
    showHeading: boolean
}) {
    return (
        <div className={containerClass}>
            {showHeading ? <h2 className="mb-4 text-lg font-semibold">AI Configuration</h2> : null}
            <div className="flex items-center justify-center py-8">
                <Loader2Icon
                    className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground"
                    aria-hidden="true"
                />
            </div>
        </div>
    )
}

function AIConfigurationHeading() {
    return (
        <>
            <h2 className="mb-4 text-lg font-semibold">AI Configuration</h2>
            <p className="mb-4 text-sm text-muted-foreground">
                Configure AI assistant settings for your organization. Use BYOK (OpenAI/Gemini), Vertex API key (express mode), or Vertex AI via Workload Identity Federation.
            </p>
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

function AISettingsCard({
    aiForm,
    aiUi,
    apiKeyMasked,
    consentAccepted,
    selectedProviderModels,
    gcpIntegration,
    vertexReady,
    pendingState,
    updateAiForm,
    onProviderChange,
    onApiKeyChange,
    onEditKey,
    onTestKey,
    onConnectGcp,
    onDisconnectGcp,
    onSave,
}: {
    aiForm: AiConfigurationFormState
    aiUi: AiConfigurationUiState
    apiKeyMasked: string | null
    consentAccepted: boolean
    selectedProviderModels: ReadonlyArray<string>
    gcpIntegration: IntegrationStatus | undefined
    vertexReady: boolean
    pendingState: {
        keyTest: boolean
        settingsUpdate: boolean
        gcpConnect: boolean
        gcpDisconnect: boolean
    }
    updateAiForm: UpdateAiConfigurationForm
    onProviderChange: (provider: AiProvider) => void
    onApiKeyChange: (apiKey: string) => void
    onEditKey: () => void
    onTestKey: () => void
    onConnectGcp: () => void
    onDisconnectGcp: () => void
    onSave: () => void
}) {
    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="flex size-10 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900">
                            <SparklesIcon className="size-5 text-purple-600 dark:text-purple-400" aria-hidden="true" />
                        </div>
                        <div>
                            <CardTitle className="text-base">AI Assistant</CardTitle>
                            <CardDescription className="text-xs">
                                Enable AI-powered features
                            </CardDescription>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Label htmlFor="ai-enabled" className="text-sm">
                            {aiForm.isEnabled ? "Enabled" : "Disabled"}
                        </Label>
                        <Switch
                            id="ai-enabled"
                            checked={aiForm.isEnabled}
                            onCheckedChange={(checked) => updateAiForm("isEnabled", checked)}
                            disabled={!consentAccepted && !aiForm.isEnabled}
                        />
                    </div>
                </div>
            </CardHeader>

            <CardContent className="space-y-4">
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

                <AISaveButton
                    pending={pendingState.settingsUpdate}
                    saved={aiUi.saved}
                    disabled={!vertexReady}
                    onSave={onSave}
                />
            </CardContent>
        </Card>
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
                        <Input
                            id="vertex-location-key"
                            value={form.vertexLocation}
                            onChange={(event) => updateAiForm("vertexLocation", event.target.value)}
                            placeholder="us-central1"
                            name="vertex-location-key"
                            autoComplete="off"
                        />
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
    onDisconnectGcp: () => void
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
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onDisconnectGcp}
                        disabled={pendingState.gcpDisconnect}
                    >
                        Disconnect
                    </Button>
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
                <Input
                    id="vertex-location"
                    value={form.vertexLocation}
                    onChange={(event) => updateAiForm("vertexLocation", event.target.value)}
                    placeholder="us-central1"
                    name="vertex-location"
                    autoComplete="off"
                />
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
        <Button onClick={onSave} disabled={pending || disabled} className="w-full">
            {pending ? (
                <>
                    <Loader2Icon
                        className="mr-2 size-4 animate-spin motion-reduce:animate-none"
                        aria-hidden="true"
                    />
                    Saving…
                </>
            ) : saved ? (
                <>
                    <CheckIcon className="mr-2 size-4" aria-hidden="true" />
                    Saved!
                </>
            ) : (
                "Save AI Configuration"
            )}
        </Button>
    )
}

function EmailConfigurationSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
    const { data: settings, isLoading } = useResendSettings()

    return (
        <EmailConfigurationSectionContent
            key={settings ? "loaded" : "loading"}
            variant={variant}
            settings={settings}
            isLoading={isLoading}
        />
    )
}

function EmailConfigurationSectionContent({
    variant,
    settings,
    isLoading,
}: {
    variant: "page" | "dialog"
    settings: ReturnType<typeof useResendSettings>["data"]
    isLoading: boolean
}) {
    const updateSettings = useUpdateResendSettings()
    const testKey = useTestResendKey()
    const rotateWebhook = useRotateWebhook()
    const [emailForm, setEmailForm] = useState<EmailConfigurationFormState>(() => ({
        provider: settings?.email_provider || "resend",
        apiKey: "",
        fromEmail: settings?.from_email || "",
        fromName: settings?.from_name || "",
        replyTo: settings?.reply_to_email || "",
        webhookSigningSecret: "",
        defaultSender: settings?.default_sender_user_id || "",
    }))
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
        setEmailForm((current) => ({
            ...current,
            provider: value,
            apiKey: value !== "resend" ? "" : current.apiKey,
            webhookSigningSecret: value !== "resend" ? "" : current.webhookSigningSecret,
        }))
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
            if (result.valid && result.verified_domains.length > 0) {
                const domain = result.verified_domains[0]
                if (!emailForm.fromEmail) {
                    setEmailForm((current) => ({ ...current, fromEmail: `no-reply@${domain}` }))
                    setEmailUi((current) => ({ ...current, hasUserEdited: true }))
                }
            }
        } catch (error) {
            const message = getErrorMessage(error, "Failed to test key")
            setEmailUi((current) => ({ ...current, keyTested: { valid: false, error: message } }))
            toast.error(message)
        }
    }

    const handleSave = async () => {
        const update: {
            email_provider?: "resend" | "gmail" | "";
            api_key?: string;
            from_email?: string;
            from_name?: string;
            reply_to_email?: string;
            webhook_signing_secret?: string;
            default_sender_user_id?: string | null;
            expected_version?: number;
        } = {
            email_provider: emailForm.provider,
        }

        if (settings?.current_version !== undefined) {
            update.expected_version = settings.current_version
        }

        if (emailForm.provider === "resend") {
            if (emailForm.apiKey.trim()) {
                update.api_key = emailForm.apiKey
            }
            update.from_email = emailForm.fromEmail
            update.from_name = emailForm.fromName
            update.reply_to_email = emailForm.replyTo
            if (emailForm.webhookSigningSecret.trim()) {
                update.webhook_signing_secret = emailForm.webhookSigningSecret.trim()
            }
        } else if (emailForm.provider === "gmail") {
            update.default_sender_user_id = emailForm.defaultSender || null
        }

        try {
            await updateSettings.mutateAsync(update)
            setEmailForm((current) => ({
                ...current,
                apiKey: "",
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
            const message = getErrorMessage(error, "Failed to save email configuration")
            toast.error(message)
        }
    }

    const handleRotateWebhook = async () => {
        try {
            const result = await rotateWebhook.mutateAsync()
            toast.success("Webhook URL rotated. Update Resend to use the new URL.")
            // Optional convenience: copy the new URL
            if (result?.webhook_url) {
                const write = navigator.clipboard?.writeText(result.webhook_url)
                write?.catch(() => {})
            }
        } catch (error) {
            toast.error(getErrorMessage(error, "Failed to rotate webhook URL"))
        }
    }

    const hasResendKey = Boolean(emailForm.apiKey.trim() || settings?.api_key_masked)
    const hasFromEmail = Boolean(emailForm.fromEmail.trim())
    const hasGmailSender = Boolean(emailForm.defaultSender)
    const resendReady = emailForm.provider !== "resend" || (hasResendKey && hasFromEmail)
    const gmailReady = emailForm.provider !== "gmail" || hasGmailSender
    const canSave = Boolean(emailForm.provider) && resendReady && gmailReady
    const showMaskedKey = Boolean(settings?.api_key_masked) && !emailUi.isEditingKey && !emailForm.apiKey
    const showHeading = variant === "page"
    const containerClass = showHeading ? "border-t pt-6" : "space-y-4"

    if (isLoading) {
        return (
            <EmailConfigurationLoadingState
                containerClass={containerClass}
                showHeading={showHeading}
            />
        )
    }

    return (
        <div className={containerClass}>
            {showHeading && <EmailConfigurationHeading />}

            <EmailSettingsCard
                form={emailForm}
                ui={emailUi}
                settings={settings}
                eligibleSenders={eligibleSenders ?? []}
                eligibleSendersLoading={eligibleSendersLoading}
                showMaskedKey={showMaskedKey}
                canSave={canSave}
                pendingState={{
                    keyTest: testKey.isPending,
                    settingsUpdate: updateSettings.isPending,
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
                onCopyWebhookUrl={copyToClipboard}
                onRotateWebhook={handleRotateWebhook}
                onSave={handleSave}
            />
        </div>
    )
}

type UpdateEmailConfigurationForm = <K extends keyof EmailConfigurationFormState>(
    field: K,
    value: EmailConfigurationFormState[K],
    markEdited?: boolean,
) => void

function EmailConfigurationLoadingState({
    containerClass,
    showHeading,
}: {
    containerClass: string
    showHeading: boolean
}) {
    return (
        <div className={containerClass}>
            {showHeading ? <h2 className="mb-4 text-lg font-semibold">Email Configuration</h2> : null}
            <div className="flex items-center justify-center py-8">
                <Loader2Icon
                    className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground"
                    aria-hidden="true"
                />
            </div>
        </div>
    )
}

function EmailConfigurationHeading() {
    return (
        <>
            <h2 className="mb-4 text-lg font-semibold">Email Configuration</h2>
            <p className="mb-4 text-sm text-muted-foreground">
                Configure the email provider for campaigns. Choose between Resend (recommended for deliverability) or Gmail.
            </p>
        </>
    )
}

function EmailSettingsCard({
    form,
    ui,
    settings,
    eligibleSenders,
    eligibleSendersLoading,
    showMaskedKey,
    canSave,
    pendingState,
    onProviderChange,
    updateEmailForm,
    onApiKeyChange,
    onEditKey,
    onCancelKeyEdit,
    onTestKey,
    onCopyWebhookUrl,
    onRotateWebhook,
    onSave,
}: {
    form: EmailConfigurationFormState
    ui: EmailConfigurationUiState
    settings: ResendSettings | undefined
    eligibleSenders: EligibleSender[]
    eligibleSendersLoading: boolean
    showMaskedKey: boolean
    canSave: boolean
    pendingState: {
        keyTest: boolean
        settingsUpdate: boolean
        webhookRotate: boolean
    }
    onProviderChange: (provider: "resend" | "gmail" | "") => void
    updateEmailForm: UpdateEmailConfigurationForm
    onApiKeyChange: (apiKey: string) => void
    onEditKey: () => void
    onCancelKeyEdit: () => void
    onTestKey: () => void
    onCopyWebhookUrl: (webhookUrl: string) => void
    onRotateWebhook: () => void
    onSave: () => void
}) {
    const statusLabel =
        settings?.email_provider === "resend"
            ? "Resend"
            : settings?.email_provider === "gmail"
                ? "Gmail"
                : "Not configured"

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                    <div className="flex size-10 items-center justify-center rounded-lg bg-teal-100 dark:bg-teal-900">
                        <SendIcon className="size-5 text-teal-600 dark:text-teal-400" aria-hidden="true" />
                    </div>
                    <div>
                        <CardTitle className="text-base">Campaign Email Provider</CardTitle>
                        <CardDescription className="text-xs">{statusLabel}</CardDescription>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="space-y-6">
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
                        pendingState={pendingState}
                        updateEmailForm={updateEmailForm}
                        onApiKeyChange={onApiKeyChange}
                        onEditKey={onEditKey}
                        onCancelKeyEdit={onCancelKeyEdit}
                        onTestKey={onTestKey}
                        onCopyWebhookUrl={onCopyWebhookUrl}
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

                <EmailSaveButton
                    pending={pendingState.settingsUpdate}
                    saved={ui.saved}
                    disabled={!canSave}
                    onSave={onSave}
                />
            </CardContent>
        </Card>
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
    pendingState,
    updateEmailForm,
    onApiKeyChange,
    onEditKey,
    onCancelKeyEdit,
    onTestKey,
    onCopyWebhookUrl,
    onRotateWebhook,
}: {
    form: EmailConfigurationFormState
    ui: EmailConfigurationUiState
    settings: ResendSettings | undefined
    showMaskedKey: boolean
    pendingState: {
        keyTest: boolean
        webhookRotate: boolean
    }
    updateEmailForm: UpdateEmailConfigurationForm
    onApiKeyChange: (apiKey: string) => void
    onEditKey: () => void
    onCancelKeyEdit: () => void
    onTestKey: () => void
    onCopyWebhookUrl: (webhookUrl: string) => void
    onRotateWebhook: () => void
}) {
    return (
        <div className="space-y-4 rounded-lg border p-4">
            <h3 className="text-sm font-medium">Resend Configuration</h3>

            <ResendApiKeyField
                apiKey={form.apiKey}
                apiKeyMasked={settings?.api_key_masked ?? null}
                verifiedDomain={settings?.verified_domain ?? null}
                keyTested={ui.keyTested}
                editingKey={ui.isEditingKey}
                showMaskedKey={showMaskedKey}
                pending={pendingState.keyTest}
                onApiKeyChange={onApiKeyChange}
                onEditKey={onEditKey}
                onCancelKeyEdit={onCancelKeyEdit}
                onTestKey={onTestKey}
            />

            <ResendVerifiedDomainBanner verifiedDomain={settings?.verified_domain ?? null} />

            <div className="space-y-2">
                <Label htmlFor="from-email">From Email</Label>
                <Input
                    id="from-email"
                    type="email"
                    value={form.fromEmail}
                    onChange={(event) => updateEmailForm("fromEmail", event.target.value, true)}
                    placeholder={settings?.verified_domain ? `no-reply@${settings.verified_domain}` : "no-reply@yourdomain.com"}
                    name="from-email"
                    autoComplete="email"
                />
                {settings?.verified_domain ? (
                    <p className="text-xs text-muted-foreground">
                        Must use your verified domain: @{settings.verified_domain}
                    </p>
                ) : null}
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

            {settings?.webhook_url ? (
                <ResendWebhookUrlField
                    webhookUrl={settings.webhook_url}
                    pending={pendingState.webhookRotate}
                    onCopyWebhookUrl={onCopyWebhookUrl}
                    onRotateWebhook={onRotateWebhook}
                />
            ) : null}

            <div className="space-y-2">
                <Label htmlFor="resend-webhook-secret">Webhook Signing Secret</Label>
                <Input
                    id="resend-webhook-secret"
                    type="password"
                    value={form.webhookSigningSecret}
                    onChange={(event) => updateEmailForm("webhookSigningSecret", event.target.value, true)}
                    placeholder="whsec_…"
                    name="resend-webhook-signing-secret"
                    autoComplete="off"
                />
                {settings?.webhook_signing_secret_configured ? (
                    <p className="text-xs text-muted-foreground">
                        Signing secret is configured. Paste a new one here only if you rotated it in Resend.
                    </p>
                ) : (
                    <p className="text-xs text-muted-foreground">
                        Paste the signing secret from Resend to enable signature verification.
                    </p>
                )}
            </div>
        </div>
    )
}

function ResendApiKeyField({
    apiKey,
    apiKeyMasked,
    verifiedDomain,
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
    verifiedDomain: string | null
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
            {keyTested?.valid ? (
                <p className="text-xs text-green-600">
                    API key is valid! Verified domain: {keyTested.verified_domains?.[0] || verifiedDomain}
                </p>
            ) : null}
            {keyTested && !keyTested.valid ? (
                <p className="text-xs text-red-600">{keyTested.error || "API key is invalid"}</p>
            ) : null}
            <p className="text-xs text-muted-foreground">
                Get your key from <a href="https://resend.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">resend.com/api-keys</a>
            </p>
        </div>
    )
}

function ResendVerifiedDomainBanner({ verifiedDomain }: { verifiedDomain: string | null }) {
    if (!verifiedDomain) return null

    return (
        <div className="flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm dark:bg-green-900/20">
            <CheckCircleIcon className="size-4 text-green-600" aria-hidden="true" />
            <span>Verified domain: <strong>{verifiedDomain}</strong></span>
        </div>
    )
}

function ResendWebhookUrlField({
    webhookUrl,
    pending,
    onCopyWebhookUrl,
    onRotateWebhook,
}: {
    webhookUrl: string
    pending: boolean
    onCopyWebhookUrl: (webhookUrl: string) => void
    onRotateWebhook: () => void
}) {
    return (
        <div className="space-y-2">
            <Label>Webhook URL</Label>
            <div className="flex gap-2">
                <Input
                    value={webhookUrl}
                    readOnly
                    className="flex-1 text-xs font-mono"
                />
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onCopyWebhookUrl(webhookUrl)}
                    aria-label="Copy webhook URL"
                >
                    <CopyIcon className="size-4" aria-hidden="true" />
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={onRotateWebhook}
                    disabled={pending}
                    aria-label="Rotate webhook URL"
                >
                    {pending ? (
                        <Loader2Icon
                            className="size-4 animate-spin motion-reduce:animate-none"
                            aria-hidden="true"
                        />
                    ) : (
                        <RotateCwIcon className="size-4" aria-hidden="true" />
                    )}
                </Button>
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
        <Button onClick={onSave} disabled={pending || disabled} className="w-full">
            {pending ? (
                <>
                    <Loader2Icon
                        className="mr-2 size-4 animate-spin motion-reduce:animate-none"
                        aria-hidden="true"
                    />
                    Saving…
                </>
            ) : saved ? (
                <>
                    <CheckIcon className="mr-2 size-4" aria-hidden="true" />
                    Saved!
                </>
            ) : (
                "Save Email Configuration"
            )}
        </Button>
    )
}

function ZapierMonitoringSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
    const { data: summary, isLoading: summaryLoading } = useZapierOutboundEventsSummary()
    const { data: events, isLoading: eventsLoading } = useZapierOutboundEvents({ limit: 20 })
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
                                                disabled={!event.can_retry || retryOutboundEvent.isPending}
                                                className={isDialog ? "" : "min-w-24"}
                                            >
                                                {retryOutboundEvent.isPending ? "Retrying…" : "Retry"}
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
    form_external_id?: string | null
}

type UpdateZapierWebhookDraft = (
    updater: (draft: ZapierWebhookDraftState) => ZapierWebhookDraftState,
) => void

type UpdateZapierOutboundForm = <K extends keyof ZapierOutboundFormState>(
    field: K,
    value: ZapierOutboundFormState[K],
) => void

function ZapierDetectedFormsAlert({
    formCount,
    mappingHref,
}: {
    formCount: number
    mappingHref: string
}) {
    return (
        <Alert>
            <AlertTitle>Zapier form detected</AlertTitle>
            <AlertDescription>
                We detected {formCount} Zapier form
                {formCount === 1 ? "" : "s"}. Map fields so inbound Zapier leads can
                convert automatically.{" "}
                <Link href={mappingHref} className="text-primary underline">
                    Manage mapping
                </Link>
            </AlertDescription>
        </Alert>
    )
}

function ZapierInboundWebhooksCard({
    isDialog,
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
    children,
}: {
    isDialog: boolean
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
    children: ReactNode
}) {
    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                    <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 dark:bg-primary/20">
                        <LinkIcon className="size-5 text-primary" aria-hidden="true" />
                    </div>
                    <div>
                        <CardTitle className="text-base">Lead Intake Webhook</CardTitle>
                        <CardDescription className="text-xs">
                            Send a POST request with lead data when a new lead arrives.
                        </CardDescription>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="space-y-6">
                <div className="space-y-4">
                    <div
                        className={`flex flex-col gap-3 ${isDialog ? "" : "md:flex-row md:items-center md:justify-between"}`}
                        data-testid="zapier-inbound-header"
                    >
                        <div>
                            <Label>Inbound Webhooks</Label>
                            <p className="text-xs text-muted-foreground">
                                Create a webhook per Zapier flow or lead source.
                            </p>
                        </div>
                        <Button
                            variant="outline"
                            onClick={onCreateInbound}
                            disabled={createPending}
                        >
                            {createPending ? (
                                <>
                                    <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                    Creating…
                                </>
                            ) : (
                                <>
                                    <PlusIcon className="mr-2 size-4" aria-hidden="true" />
                                    Add webhook
                                </>
                            )}
                        </Button>
                    </div>

                    {!inboundWebhooks.length ? (
                        <p className="text-xs text-muted-foreground">No inbound webhooks configured yet.</p>
                    ) : (
                        <div className="space-y-4">
                            {inboundWebhooks.map((webhook) => (
                                <ZapierInboundWebhookItem
                                    key={webhook.webhook_id}
                                    webhook={webhook}
                                    labelValue={labelDrafts[webhook.webhook_id] ?? ""}
                                    secret={webhookSecrets[webhook.webhook_id]}
                                    canDelete={inboundWebhooks.length > 1}
                                    isDialog={isDialog}
                                    rotatePending={rotatePending}
                                    rotatingWebhookId={rotatingWebhookId}
                                    deletingWebhookId={deletingWebhookId}
                                    onUpdateWebhookDraft={onUpdateWebhookDraft}
                                    onLabelBlur={onLabelBlur}
                                    onToggleInbound={onToggleInbound}
                                    onRotateInbound={onRotateInbound}
                                    onDeleteInbound={onDeleteInbound}
                                />
                            ))}
                        </div>
                    )}
                </div>

                {children}
            </CardContent>
        </Card>
    )
}

function ZapierInboundWebhookItem({
    webhook,
    labelValue,
    secret,
    canDelete,
    isDialog,
    rotatePending,
    rotatingWebhookId,
    deletingWebhookId,
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
    isDialog: boolean
    rotatePending: boolean
    rotatingWebhookId: string | null
    deletingWebhookId: string | null
    onUpdateWebhookDraft: UpdateZapierWebhookDraft
    onLabelBlur: (webhookId: string) => Promise<void>
    onToggleInbound: (webhookId: string, enabled: boolean) => Promise<void>
    onRotateInbound: (webhookId: string) => Promise<void>
    onDeleteInbound: (webhookId: string) => Promise<void>
}) {
    const isRotating = rotatePending && rotatingWebhookId === webhook.webhook_id
    const isDeleting = deletingWebhookId === webhook.webhook_id

    return (
        <div className="space-y-3 rounded-md border p-4">
            <div className={`flex flex-col gap-3 ${isDialog ? "" : "md:flex-row md:items-start md:justify-between"}`}>
                <div className="flex-1 space-y-2">
                    <Label>Label</Label>
                    <Input
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
                <div className="flex items-center gap-2">
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
                <Label>Webhook URL</Label>
                <div className="flex min-w-0 gap-2">
                    <div
                        className="flex h-9 min-w-0 flex-1 items-center rounded-md border border-input bg-transparent px-3 py-1 text-xs font-mono shadow-xs dark:bg-input/30"
                        title={webhook.webhook_url}
                    >
                        <span className="min-w-0 flex-1 truncate">
                            {webhook.webhook_url}
                        </span>
                    </div>
                    <Button
                        variant="outline"
                        size="icon"
                        onClick={() => copyToClipboard(webhook.webhook_url)}
                        aria-label="Copy webhook URL"
                    >
                        <CopyIcon className="size-4" aria-hidden="true" />
                    </Button>
                </div>
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
                    <Button
                        variant="outline"
                        onClick={() => {
                            void onRotateInbound(webhook.webhook_id)
                        }}
                        disabled={isRotating}
                    >
                        {isRotating ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                Rotating…
                            </>
                        ) : (
                            <>
                                <RotateCwIcon className="mr-2 size-4" aria-hidden="true" />
                                Rotate Webhook Secret
                            </>
                        )}
                    </Button>

                    <AlertDialog>
                        <AlertDialogTrigger
                            disabled={!canDelete || isDeleting}
                            render={
                                <Button
                                    variant="ghost"
                                    className="text-destructive hover:text-destructive"
                                    disabled={!canDelete || isDeleting}
                                >
                                    <TrashIcon className="mr-2 size-4" aria-hidden="true" />
                                    Delete Webhook
                                </Button>
                            }
                        />
                        <AlertDialogContent>
                            <AlertDialogHeader>
                                <AlertDialogTitle>Delete webhook?</AlertDialogTitle>
                                <AlertDialogDescription>
                                    This will disable the incoming URL immediately. Any Zapier
                                    flows using it will fail until updated.
                                </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction
                                    onClick={() => {
                                        void onDeleteInbound(webhook.webhook_id)
                                    }}
                                    disabled={!canDelete || isDeleting}
                                >
                                    {isDeleting ? "Deleting…" : "Delete"}
                                </AlertDialogAction>
                            </AlertDialogFooter>
                        </AlertDialogContent>
                    </AlertDialog>
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
                            <code className="flex-1 break-all">
                                {secret}
                            </code>
                            <Button
                                variant="outline"
                                size="icon"
                                onClick={() => copyToClipboard(secret)}
                                aria-label="Copy webhook secret"
                            >
                                <CopyIcon className="size-4" aria-hidden="true" />
                            </Button>
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
    fieldPaste,
    fieldPasteResult,
    parsePending,
    onWebhookChange,
    onFieldPasteChange,
    onParse,
    onClear,
}: {
    isDialog: boolean
    inboundWebhooks: ZapierInboundWebhookView[]
    activeWebhookId: string
    fieldPaste: string
    fieldPasteResult: ZapierFieldPasteResponse | null
    parsePending: boolean
    onWebhookChange: (webhookId: string) => void
    onFieldPasteChange: (value: string) => void
    onParse: () => void
    onClear: () => void
}) {
    return (
        <div className="space-y-4 border-t pt-4">
            <div className="space-y-2">
                <Label>Paste Zapier Field List</Label>
                <p className="text-xs text-muted-foreground">
                    Paste the field list from Zapier (either the token lines or the sample field/value list).
                    We’ll extract keys, build a form schema, and open the mapping suggestions.
                </p>
            </div>

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

            <Textarea
                value={fieldPaste}
                onChange={(event) => onFieldPasteChange(event.target.value)}
                placeholder={'Paste lines like {{=gives["312067957"]["full_name"]}} or "Full Name: Jane Doe"'}
                rows={6}
                name="zapier-field-paste"
            />
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
                        {fieldPasteResult.form_name || fieldPasteResult.form_id}.{" "}
                        <Link href={fieldPasteResult.mapping_url} className="text-primary underline">
                            Open mapping
                        </Link>
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
        <div className="space-y-3 border-t pt-4">
            <div className="space-y-2">
                <Label>Test Lead</Label>
                <Input
                    placeholder="Zapier Form ID (optional if only one active Zapier form exists)"
                    value={activeTestFormId}
                    onChange={(event) => onTestFormIdChange(event.target.value)}
                    name="zapier-test-form-id"
                    autoComplete="off"
                />
                <p className="text-xs text-muted-foreground">
                    Sends a dummy lead through the same inbound mapping pipeline as Zapier leads.
                </p>
                {zapierForms.length === 1 ? (
                    <p className="text-xs text-muted-foreground">
                        Defaulting to {zapierForms[0]?.form_name || zapierForms[0]?.form_external_id}.
                    </p>
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
                disabled={sendPending}
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

function ZapierOutboundSettingsCard({
    isDialog,
    outboundForm,
    outboundSecret,
    outboundSecretConfigured,
    outboundTestLeadId,
    savePending,
    testPending,
    recommendedBucketByStage,
    getStageKeyLabel,
    onOutboundFormChange,
    onOutboundSecretChange,
    onOutboundTestLeadIdChange,
    onSaveOutbound,
    onSendOutboundTest,
    onApplyRecommendedMapping,
}: {
    isDialog: boolean
    outboundForm: ZapierOutboundFormState
    outboundSecret: string
    outboundSecretConfigured: boolean
    outboundTestLeadId: string
    savePending: boolean
    testPending: boolean
    recommendedBucketByStage: Record<string, ZapierStageBucket>
    getStageKeyLabel: (stageKey: string) => string
    onOutboundFormChange: UpdateZapierOutboundForm
    onOutboundSecretChange: (value: string) => void
    onOutboundTestLeadIdChange: (value: string) => void
    onSaveOutbound: () => void
    onSendOutboundTest: () => void
    onApplyRecommendedMapping: () => void
}) {
    return (
        <div className="space-y-4 border-t pt-4">
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-sm font-medium">Outbound Stage Events</p>
                    <p className="text-xs text-muted-foreground">
                        Send surrogate stage changes to Zapier for Meta Conversions.
                    </p>
                </div>
                <Switch
                    checked={outboundForm.outboundEnabled}
                    onCheckedChange={(checked) => onOutboundFormChange("outboundEnabled", checked)}
                    aria-label="Enable outbound stage events"
                />
            </div>

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
                    If provided, we send it as X-Webhook-Token header.
                </p>
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

            <ZapierStageMappingRows
                eventMapping={outboundForm.eventMapping}
                isDialog={isDialog}
                recommendedBucketByStage={recommendedBucketByStage}
                getStageKeyLabel={getStageKeyLabel}
                onOutboundFormChange={onOutboundFormChange}
                onApplyRecommendedMapping={onApplyRecommendedMapping}
            />

            <ZapierOutboundTestControls
                isDialog={isDialog}
                outboundForm={outboundForm}
                outboundTestLeadId={outboundTestLeadId}
                savePending={savePending}
                testPending={testPending}
                getStageKeyLabel={getStageKeyLabel}
                onOutboundFormChange={onOutboundFormChange}
                onOutboundTestLeadIdChange={onOutboundTestLeadIdChange}
                onSaveOutbound={onSaveOutbound}
                onSendOutboundTest={onSendOutboundTest}
            />
        </div>
    )
}

function ZapierStageMappingRows({
    eventMapping,
    isDialog,
    recommendedBucketByStage,
    getStageKeyLabel,
    onOutboundFormChange,
    onApplyRecommendedMapping,
}: {
    eventMapping: ZapierEventMappingItem[]
    isDialog: boolean
    recommendedBucketByStage: Record<string, ZapierStageBucket>
    getStageKeyLabel: (stageKey: string) => string
    onOutboundFormChange: UpdateZapierOutboundForm
    onApplyRecommendedMapping: () => void
}) {
    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <Label>Stage → Event Mapping</Label>
                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={onApplyRecommendedMapping}
                >
                    Apply Recommended Mapping
                </Button>
            </div>
            <p className="text-xs text-muted-foreground">
                Set each stage bucket for Meta conversion status mapping. Dedupe runs once per lead per bucket.
            </p>
            <div className="space-y-2">
                {eventMapping.map((item, index) => (
                    <ZapierStageMappingRow
                        key={item.stage_key}
                        item={item}
                        index={index}
                        eventMapping={eventMapping}
                        isDialog={isDialog}
                        recommendedBucketByStage={recommendedBucketByStage}
                        getStageKeyLabel={getStageKeyLabel}
                        onOutboundFormChange={onOutboundFormChange}
                    />
                ))}
            </div>
        </div>
    )
}

function ZapierStageMappingRow({
    item,
    index,
    eventMapping,
    isDialog,
    recommendedBucketByStage,
    getStageKeyLabel,
    onOutboundFormChange,
}: {
    item: ZapierEventMappingItem
    index: number
    eventMapping: ZapierEventMappingItem[]
    isDialog: boolean
    recommendedBucketByStage: Record<string, ZapierStageBucket>
    getStageKeyLabel: (stageKey: string) => string
    onOutboundFormChange: UpdateZapierOutboundForm
}) {
    const updateItem = (updater: (existing: ZapierEventMappingItem) => ZapierEventMappingItem) => {
        const next = [...eventMapping]
        const existing = next[index]
        if (!existing) return
        next[index] = updater(existing)
        onOutboundFormChange("eventMapping", next)
    }

    return (
        <div className={`flex flex-col gap-2 rounded-md border p-3 ${isDialog ? "" : "md:flex-row md:items-center"}`}>
            <div className="w-32 text-sm font-medium">
                {getStageKeyLabel(item.stage_key)}
            </div>
            <Select
                value={isZapierStageBucket(item.bucket) ? item.bucket : UNTRACKED_BUCKET_VALUE}
                onValueChange={(value) => {
                    if (value === UNTRACKED_BUCKET_VALUE) {
                        updateItem((existing) => ({
                            ...existing,
                            bucket: null,
                            enabled: recommendedBucketByStage[existing.stage_key]
                                ? false
                                : existing.enabled,
                        }))
                    } else if (isZapierStageBucket(value)) {
                        updateItem((existing) => ({
                            ...existing,
                            bucket: value,
                            event_name: ZAPIER_BUCKET_EVENT_NAME[value],
                            enabled: true,
                        }))
                    }
                }}
            >
                <SelectTrigger className={isDialog ? "w-full" : "w-full md:w-44"}>
                    <SelectValue placeholder="Bucket">
                        {(value: string | null) => getBucketSelectLabel(value)}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value={UNTRACKED_BUCKET_VALUE}>Not Tracked</SelectItem>
                    {ZAPIER_BUCKET_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                            {option.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
            {!isZapierStageBucket(item.bucket) ? (
                <Input
                    value={item.event_name}
                    onChange={(event) => {
                        updateItem((existing) => ({ ...existing, event_name: event.target.value }))
                    }}
                    placeholder="Event name"
                    name={`zapier-event-${item.stage_key}`}
                    autoComplete="off"
                />
            ) : null}
            <div className="flex items-center gap-2">
                <Switch
                    checked={item.enabled}
                    onCheckedChange={(checked) => {
                        updateItem((existing) => ({ ...existing, enabled: checked }))
                    }}
                    aria-label={`Enable ${item.stage_key} event`}
                />
                <span className="text-xs text-muted-foreground">Enabled</span>
            </div>
        </div>
    )
}

function ZapierOutboundTestControls({
    isDialog,
    outboundForm,
    outboundTestLeadId,
    savePending,
    testPending,
    getStageKeyLabel,
    onOutboundFormChange,
    onOutboundTestLeadIdChange,
    onSaveOutbound,
    onSendOutboundTest,
}: {
    isDialog: boolean
    outboundForm: ZapierOutboundFormState
    outboundTestLeadId: string
    savePending: boolean
    testPending: boolean
    getStageKeyLabel: (stageKey: string) => string
    onOutboundFormChange: UpdateZapierOutboundForm
    onOutboundTestLeadIdChange: (value: string) => void
    onSaveOutbound: () => void
    onSendOutboundTest: () => void
}) {
    return (
        <div className={`flex flex-col gap-2 ${isDialog ? "" : "md:flex-row md:items-center"}`}>
            <Button onClick={onSaveOutbound} disabled={savePending}>
                {savePending ? (
                    <>
                        <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                        Saving…
                    </>
                ) : (
                    "Save Outbound Settings"
                )}
            </Button>
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

function useZapierWebhookController(variant: "page" | "dialog") {
    const { data: pipelines } = usePipelines()
    const recommendedBucketByStage = buildRecommendedBucketByStage(pipelines)
    const stageLabelByKey = buildStageLabelByKey(pipelines)
    const getStageKeyLabel = (stageKey: string) => stageLabelByKey[stageKey] ?? "Unknown stage"
    const { data: settings, isLoading } = useZapierSettings()
    const { data: metaForms = [], isLoading: metaFormsLoading } = useMetaForms()
    const createInboundWebhook = useCreateZapierInboundWebhook()
    const rotateInboundWebhook = useRotateZapierInboundWebhook()
    const updateInboundWebhook = useUpdateZapierInboundWebhook()
    const parseFieldPaste = useZapierFieldPaste()
    const deleteInboundWebhook = useDeleteZapierInboundWebhook()
    const updateOutbound = useUpdateZapierOutboundSettings()
    const [rotatingWebhookId, setRotatingWebhookId] = useState<string | null>(null)
    const [deletingWebhookId, setDeletingWebhookId] = useState<string | null>(null)
    const [testFormId, setTestFormId] = useState('')
    const [fieldPaste, setFieldPaste] = useState('')
    const [fieldPasteWebhookId, setFieldPasteWebhookId] = useState('')
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
    const activeWebhookDraft = webhookDraft.webhookKey === activeWebhookKey
        ? webhookDraft
        : createZapierWebhookDraftState(activeWebhookKey, inboundWebhooks, webhookDraft.webhookSecrets)
    const { labelDrafts, webhookSecrets } = activeWebhookDraft
    const activeFieldPasteWebhookId = getActiveFieldPasteWebhookId(fieldPasteWebhookId, inboundWebhooks)
    const singleZapierFormId = getSingleZapierFormId(metaForms)
    const activeTestFormId = testFormId.trim() || singleZapierFormId
    const activeOutboundKey = createZapierOutboundDraftKey(settings, pipelines)
    const [outboundDraft, setOutboundDraft] = useState<ZapierOutboundDraftState>(() =>
        createZapierOutboundDraftState(activeOutboundKey, settings, pipelines)
    )
    const activeOutboundDraft = outboundDraft.outboundKey === activeOutboundKey
        ? outboundDraft
        : createZapierOutboundDraftState(
            activeOutboundKey,
            settings,
            pipelines,
            outboundDraft.form.selectedOutboundStage,
        )
    const outboundForm = activeOutboundDraft.form

    const updateWebhookDraft = (
        updater: (draft: ZapierWebhookDraftState) => ZapierWebhookDraftState,
    ) => {
        setWebhookDraft((current) => {
            const activeDraft = current.webhookKey === activeWebhookKey
                ? current
                : createZapierWebhookDraftState(activeWebhookKey, inboundWebhooks, current.webhookSecrets)
            return updater(activeDraft)
        })
    }

    const updateOutboundForm = <K extends keyof ZapierOutboundFormState>(
        field: K,
        value: ZapierOutboundFormState[K],
    ) => {
        setOutboundDraft((current) => {
            const activeDraft = current.outboundKey === activeOutboundKey
                ? current
                : createZapierOutboundDraftState(
                    activeOutboundKey,
                    settings,
                    pipelines,
                    current.form.selectedOutboundStage,
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

    const handleRotateInbound = async (webhookId: string) => {
        try {
            setRotatingWebhookId(webhookId)
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
        } catch {
            toast.error("Failed to rotate webhook secret")
        }
        setRotatingWebhookId(null)
    }

    const handleDeleteInbound = async (webhookId: string) => {
        try {
            setDeletingWebhookId(webhookId)
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
        } catch (error) {
            const message = error instanceof Error ? error.message : null
            toast.error(message || "Failed to delete webhook")
        }
        setDeletingWebhookId(null)
    }

    const handleLabelBlur = async (webhookId: string) => {
        const draft = (labelDrafts[webhookId] || "").trim()
        const current = settings?.inbound_webhooks?.find((item) => item.webhook_id === webhookId)?.label || ""
        if (draft === (current || "")) {
            return
        }
        try {
            await updateInboundWebhook.mutateAsync({
                webhookId,
                payload: { label: draft || null },
            })
            toast.success("Webhook updated")
        } catch {
            toast.error("Failed to update webhook")
        }
    }

    const handleToggleInbound = async (webhookId: string, enabled: boolean) => {
        try {
            await updateInboundWebhook.mutateAsync({
                webhookId,
                payload: { is_active: enabled },
            })
            toast.success(enabled ? "Webhook enabled" : "Webhook disabled")
        } catch {
            toast.error("Failed to update webhook")
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
            const message = error instanceof Error ? error.message : null
            toast.error(message || "Failed to send test lead")
        }
    }

    const handleFieldPaste = async () => {
        const paste = fieldPaste.trim()
        if (!paste) {
            toast.error("Paste the Zapier field list first.")
            return
        }
        try {
            const payload: { paste: string; webhook_id?: string } = { paste }
            if (activeFieldPasteWebhookId) {
                payload.webhook_id = activeFieldPasteWebhookId
            }
            const result = await parseFieldPaste.mutateAsync(payload)
            setFieldPasteResult(result)
            if (result.form_id) {
                setTestFormId(result.form_id)
            }
            toast.success(`Detected ${result.field_count} fields`)
        } catch {
            toast.error("Unable to parse fields. Check the pasted data and try again.")
        }
    }

    const handleFieldPasteClear = () => {
        setFieldPaste('')
        setFieldPasteResult(null)
    }

    const handleSaveOutbound = async () => {
        try {
            const payload: {
                outbound_webhook_url: string | null
                outbound_webhook_secret?: string | null
                outbound_enabled: boolean
                send_hashed_pii: boolean
                event_mapping: ZapierEventMappingItem[]
            } = {
                outbound_webhook_url: outboundForm.outboundUrl.trim() || null,
                outbound_enabled: outboundForm.outboundEnabled,
                send_hashed_pii: outboundForm.sendHashedPii,
                event_mapping: outboundForm.eventMapping,
            }
            const secret = outboundSecret.trim()
            if (secret) {
                payload.outbound_webhook_secret = secret
            }
            await updateOutbound.mutateAsync(payload)
            setOutboundSecret('')
            toast.success("Outbound webhook settings saved")
        } catch {
            toast.error("Failed to save outbound settings")
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
    const zapierForms = metaForms.filter(
        (form) =>
            form.is_active &&
            (form.page_id === "zapier" || form.form_external_id?.startsWith("zapier-"))
    )
    const singleZapierForm = zapierForms.length === 1 ? zapierForms[0] : null
    const mappingHref = singleZapierForm
        ? `/settings/integrations/meta/forms/${singleZapierForm.id}`
        : "/settings/integrations/meta/forms"

    return {
        activeFieldPasteWebhookId,
        activeTestFormId,
        applyRecommendedBucketMapping,
        containerClass,
        createInboundPending: createInboundWebhook.isPending,
        deletingWebhookId,
        fieldPaste,
        fieldPasteResult,
        getStageKeyLabel,
        handleCreateInbound,
        handleDeleteInbound,
        handleFieldPaste,
        handleFieldPasteClear,
        handleLabelBlur,
        handleOutboundTest,
        handleRotateInbound,
        handleSaveOutbound,
        handleTestLead,
        handleToggleInbound,
        inboundWebhooks,
        isDialog,
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

function ZapierWebhookSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
    const controller = useZapierWebhookController(variant)

    if (controller.isLoading) {
        return (
            <div className={controller.containerClass}>
                {controller.showHeading && (
                    <h2 className="mb-4 text-lg font-semibold">Zapier Webhook</h2>
                )}
                <div className="flex items-center justify-center py-8">
                    <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                </div>
            </div>
        )
    }

    return (
        <div className={controller.containerClass}>
            {controller.showHeading && (
                <>
                    <h2 className="mb-4 text-lg font-semibold">Zapier Webhook</h2>
                    <p className="mb-4 text-sm text-muted-foreground">
                        Use this webhook to push leads from Zapier into Surrogacy Force.
                    </p>
                </>
            )}
            <Tabs defaultValue="configuration" className="space-y-4">
                <TabsList variant="line">
                    <TabsTrigger value="configuration">Configuration</TabsTrigger>
                    <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
                </TabsList>
                <TabsContent value="configuration" className="space-y-4">
                    {!controller.metaFormsLoading && controller.zapierForms.length > 0 ? (
                        <ZapierDetectedFormsAlert
                            formCount={controller.zapierForms.length}
                            mappingHref={controller.mappingHref}
                        />
                    ) : null}

                    <ZapierInboundWebhooksCard
                        isDialog={controller.isDialog}
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
                    >
                        <ZapierFieldPasteCard
                            isDialog={controller.isDialog}
                            inboundWebhooks={controller.inboundWebhooks}
                            activeWebhookId={controller.activeFieldPasteWebhookId}
                            fieldPaste={controller.fieldPaste}
                            fieldPasteResult={controller.fieldPasteResult}
                            parsePending={controller.parseFieldPastePending}
                            onWebhookChange={controller.setFieldPasteWebhookId}
                            onFieldPasteChange={controller.setFieldPaste}
                            onParse={() => {
                                void controller.handleFieldPaste()
                            }}
                            onClear={controller.handleFieldPasteClear}
                        />
                        <ZapierTestLeadControls
                            activeTestFormId={controller.activeTestFormId}
                            zapierForms={controller.zapierForms}
                            sendPending={controller.sendTestLeadPending}
                            onTestFormIdChange={controller.setTestFormId}
                            onSendTestLead={() => {
                                void controller.handleTestLead()
                            }}
                        />
                        <ZapierOutboundSettingsCard
                            isDialog={controller.isDialog}
                            outboundForm={controller.outboundForm}
                            outboundSecret={controller.outboundSecret}
                            outboundSecretConfigured={controller.outboundSecretConfigured}
                            outboundTestLeadId={controller.outboundTestLeadId}
                            savePending={controller.updateOutboundPending}
                            testPending={controller.sendOutboundTestPending}
                            recommendedBucketByStage={controller.recommendedBucketByStage}
                            getStageKeyLabel={controller.getStageKeyLabel}
                            onOutboundFormChange={controller.updateOutboundForm}
                            onOutboundSecretChange={controller.setOutboundSecret}
                            onOutboundTestLeadIdChange={controller.setOutboundTestLeadId}
                            onSaveOutbound={() => {
                                void controller.handleSaveOutbound()
                            }}
                            onSendOutboundTest={() => {
                                void controller.handleOutboundTest()
                            }}
                            onApplyRecommendedMapping={controller.applyRecommendedBucketMapping}
                        />
                    </ZapierInboundWebhooksCard>
                </TabsContent>
                <TabsContent value="monitoring" keepMounted>
                    <ZapierMonitoringSection variant={controller.variant} />
                </TabsContent>
            </Tabs>
        </div>
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

function MetaCrmDatasetSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
    const { data: pipelines } = usePipelines()
    const { data: settings, isLoading } = useMetaCrmDatasetSettings()

    return (
        <MetaCrmDatasetSectionContent
            key={settings && pipelines ? "loaded" : "loading"}
            variant={variant}
            pipelines={pipelines}
            settings={settings}
            isLoading={isLoading}
        />
    )
}

function MetaCrmDatasetSectionContent({
    variant,
    pipelines,
    settings,
    isLoading,
}: {
    variant: "page" | "dialog"
    pipelines: ReturnType<typeof usePipelines>["data"]
    settings: ReturnType<typeof useMetaCrmDatasetSettings>["data"]
    isLoading: boolean
}) {
    const recommendedBucketByStage = buildRecommendedBucketByStage(pipelines)
    const stageLabelByKey = buildStageLabelByKey(pipelines)
    const getStageKeyLabel = (stageKey: string) => stageLabelByKey[stageKey] ?? "Unknown stage"
    const updateSettings = useUpdateMetaCrmDatasetSettings()
    const sendOutboundTest = useMetaCrmDatasetOutboundTest()
    const isDialog = variant === "dialog"
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
            const message = error instanceof Error ? error.message : null
            toast.error(message || "Failed to save CRM dataset settings")
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
            const message = error instanceof Error ? error.message : null
            toast.error(message || "Failed to send Meta CRM dataset test event")
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

    if (isLoading) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-8">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground motion-reduce:animate-none" aria-hidden="true" />
                </CardContent>
            </Card>
        )
    }

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                    <div className="flex size-10 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900">
                        <ServerIcon className="size-5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
                    </div>
                    <div>
                        <CardTitle className="text-base">CRM Dataset</CardTitle>
                        <CardDescription className="text-xs">
                            Direct Meta Conversions API delivery using a dataset ID and access token.
                        </CardDescription>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="space-y-6">
                <MetaCrmDatasetSettingsFields
                    metaForm={metaForm}
                    accessTokenConfigured={Boolean(settings?.access_token_configured)}
                    updateMetaForm={updateMetaForm}
                />
                <MetaCrmDatasetStageMapping
                    eventMapping={metaForm.eventMapping}
                    isDialog={isDialog}
                    updateEventMapping={updateEventMapping}
                    getStageKeyLabel={getStageKeyLabel}
                    applyRecommendedBucketMapping={applyRecommendedBucketMapping}
                />
                <MetaCrmDatasetTestControls
                    metaForm={metaForm}
                    isDialog={isDialog}
                    updateMetaForm={updateMetaForm}
                    getStageKeyLabel={getStageKeyLabel}
                    isSaving={updateSettings.isPending}
                    isSendingTest={sendOutboundTest.isPending}
                    handleSave={handleSave}
                    handleOutboundTest={handleOutboundTest}
                />
            </CardContent>
        </Card>
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
    isDialog,
    updateEventMapping,
    getStageKeyLabel,
    applyRecommendedBucketMapping,
}: {
    eventMapping: MetaCrmDatasetEventMappingItem[]
    isDialog: boolean
    updateEventMapping: UpdateMetaCrmDatasetEventMapping
    getStageKeyLabel: (stageKey: string) => string
    applyRecommendedBucketMapping: () => void
}) {
    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <Label>Stage → Event Mapping</Label>
                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={applyRecommendedBucketMapping}
                >
                    Apply Recommended Mapping
                </Button>
            </div>
            <p className="text-xs text-muted-foreground">
                Map each internal surrogate stage to the Meta CRM event bucket you want to report.
            </p>
            <div className="space-y-2">
                {eventMapping.map((item, index) => (
                    <MetaCrmDatasetStageMappingRow
                        key={item.stage_key}
                        item={item}
                        index={index}
                        isDialog={isDialog}
                        updateEventMapping={updateEventMapping}
                        getStageKeyLabel={getStageKeyLabel}
                    />
                ))}
            </div>
        </div>
    )
}

function MetaCrmDatasetStageMappingRow({
    item,
    index,
    isDialog,
    updateEventMapping,
    getStageKeyLabel,
}: {
    item: MetaCrmDatasetEventMappingItem
    index: number
    isDialog: boolean
    updateEventMapping: UpdateMetaCrmDatasetEventMapping
    getStageKeyLabel: (stageKey: string) => string
}) {
    return (
        <div className={`flex flex-col gap-2 rounded-md border p-3 ${isDialog ? "" : "md:flex-row md:items-center"}`}>
            <div className="w-32 text-sm font-medium">
                {getStageKeyLabel(item.stage_key)}
            </div>
            <Select
                value={isZapierStageBucket(item.bucket) ? item.bucket : UNTRACKED_BUCKET_VALUE}
                onValueChange={(value) => {
                    updateEventMapping((current) => {
                        const next = [...current]
                        const existing = next[index]
                        if (!existing) return current
                        if (value === UNTRACKED_BUCKET_VALUE) {
                            next[index] = {
                                ...existing,
                                bucket: null,
                                enabled: false,
                            }
                        } else if (isZapierStageBucket(value)) {
                            next[index] = {
                                ...existing,
                                bucket: value,
                                event_name: ZAPIER_BUCKET_EVENT_NAME[value],
                                enabled: true,
                            }
                        }
                        return next
                    })
                }}
            >
                <SelectTrigger className={isDialog ? "w-full" : "w-full md:w-44"}>
                    <SelectValue placeholder="Bucket">
                        {(value: string | null) => getBucketSelectLabel(value)}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value={UNTRACKED_BUCKET_VALUE}>Not Tracked</SelectItem>
                    {ZAPIER_BUCKET_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                            {option.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
            {!isZapierStageBucket(item.bucket) ? (
                <Input
                    value={item.event_name}
                    onChange={(event) => {
                        updateEventMapping((current) => {
                            const next = [...current]
                            const existing = next[index]
                            if (!existing) return current
                            next[index] = { ...existing, event_name: event.target.value }
                            return next
                        })
                    }}
                    placeholder="Event name"
                    name={`meta-crm-dataset-event-${item.stage_key}`}
                    autoComplete="off"
                />
            ) : null}
            <div className="flex items-center gap-2">
                <Switch
                    checked={item.enabled}
                    onCheckedChange={(checked) => {
                        updateEventMapping((current) => {
                            const next = [...current]
                            const existing = next[index]
                            if (!existing) return current
                            next[index] = { ...existing, enabled: checked }
                            return next
                        })
                    }}
                    aria-label={`Enable ${item.stage_key} Meta CRM dataset event`}
                />
                <span className="text-xs text-muted-foreground">Enabled</span>
            </div>
        </div>
    )
}

function MetaCrmDatasetTestControls({
    metaForm,
    isDialog,
    updateMetaForm,
    getStageKeyLabel,
    isSaving,
    isSendingTest,
    handleSave,
    handleOutboundTest,
}: {
    metaForm: MetaCrmDatasetFormState
    isDialog: boolean
    updateMetaForm: UpdateMetaCrmDatasetForm
    getStageKeyLabel: (stageKey: string) => string
    isSaving: boolean
    isSendingTest: boolean
    handleSave: () => Promise<void>
    handleOutboundTest: () => Promise<void>
}) {
    return (
        <div className={`flex flex-col gap-2 ${isDialog ? "" : "md:flex-row md:items-start"}`}>
            <Button onClick={() => { void handleSave() }} disabled={isSaving}>
                {isSaving ? (
                    <>
                        <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                        Saving…
                    </>
                ) : (
                    "Save CRM Dataset Settings"
                )}
            </Button>
            <div className={isDialog ? "flex flex-col gap-2" : "flex flex-1 flex-col gap-2"}>
                <div className={isDialog ? "space-y-2" : "flex flex-col gap-2 md:max-w-sm"}>
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
                <div className={isDialog ? "space-y-2" : "flex flex-col gap-2 md:max-w-sm"}>
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
                <div className={isDialog ? "flex flex-col gap-2" : "flex flex-1 items-center gap-2"}>
                    <Select
                        value={metaForm.selectedStage}
                        onValueChange={(value) => updateMetaForm("selectedStage", value ?? "")}
                    >
                        <SelectTrigger className={isDialog ? "w-full" : "w-full md:w-56"} aria-label="Select Meta CRM dataset stage">
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
                        className={isDialog ? "w-full" : undefined}
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

function MetaConfigurationLoadingState({
    containerClass,
    showHeading,
}: {
    containerClass: string
    showHeading: boolean
}) {
    return (
        <div className={containerClass}>
            {showHeading && (
                <h2 className="mb-4 text-lg font-semibold">Meta Integration</h2>
            )}
            <div className="flex items-center justify-center py-8">
                <Loader2Icon
                    className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground"
                    aria-hidden="true"
                />
            </div>
        </div>
    )
}

function MetaConfigurationHeading() {
    return (
        <>
            <h2 className="mb-4 text-lg font-semibold">Meta Integration</h2>
            <p className="mb-4 text-sm text-muted-foreground">
                Connect Meta accounts to sync lead forms, and configure direct CRM dataset delivery for Meta conversion reporting.
            </p>
        </>
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
        onDelete: (accountId: string) => void
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
        onDelete: (accountId: string) => void
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
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => actions.onDelete(account.id)}
                                            disabled={actions.isDeleting}
                                            aria-label="Delete ad account"
                                        >
                                            <TrashIcon className="size-4" aria-hidden="true" />
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
    onConfirm: (connectionId: string) => void
}) {
    return (
        <AlertDialog open={!!connectionId} onOpenChange={(open) => !open && onClose()}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>Disconnect Meta account?</AlertDialogTitle>
                    <AlertDialogDescription>
                        This will unlink all ad accounts and pages connected through this Facebook account.
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                        onClick={() => connectionId && onConfirm(connectionId)}
                    >
                        Disconnect
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    )
}

function MetaConfigurationSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
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
        } catch {
            // Error handled by mutation
        }
    }

    const handleDisconnect = async (connectionId: string) => {
        try {
            await disconnectMutation.mutateAsync(connectionId)
            setDisconnectConnectionId(null)
        } catch {
            // Error handled by mutation
        }
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
            const message = error instanceof Error ? error.message : "Failed to update ad account"
            dispatchAccountEdit({ type: "setError", error: message })
        }
    }

    const handleDeleteAdAccount = async (accountId: string) => {
        try {
            await deleteAccountMutation.mutateAsync(accountId)
        } catch (error) {
            console.error("Failed to delete ad account:", error)
        }
    }

    const showHeading = variant === "page"
    const containerClass = showHeading ? "border-t pt-6" : "space-y-6"

    const isLoading = connectionsLoading || adAccountsLoading

    if (isLoading) {
        return (
            <MetaConfigurationLoadingState
                containerClass={containerClass}
                showHeading={showHeading}
            />
        )
    }

    return (
        <div className={containerClass}>
            {showHeading && <MetaConfigurationHeading />}
            <Tabs defaultValue="configuration" className="space-y-4">
                <TabsList variant="line">
                    <TabsTrigger value="configuration">Configuration</TabsTrigger>
                    <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
                </TabsList>

                <TabsContent value="configuration" className="space-y-4">
                    <MetaCrmDatasetSection variant={variant} />

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
                            onDelete: (accountId) => {
                                void handleDeleteAdAccount(accountId)
                            },
                        }}
                    />
                </TabsContent>

                <TabsContent value="monitoring" keepMounted>
                    <MetaCrmDatasetMonitoringSection variant={variant} />
                </TabsContent>
            </Tabs>

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
        </div>
    )
}

export default function IntegrationsPage() {
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"
    const { data: effectivePermissions } = useEffectivePermissions(user?.user_id ?? null)
    const canManageOrganizationIntegrations =
        isDeveloper || (effectivePermissions?.permissions ?? []).includes("manage_integrations")
    const organizationIntegrationsEnabled = canManageOrganizationIntegrations
    const { data: healthData, isLoading, refetch, isFetching } = useIntegrationHealth(
        organizationIntegrationsEnabled
    )
    const { data: userIntegrations } = useUserIntegrations()
    const { data: googleCalendarStatus } = useGoogleCalendarStatus(true)
    const { data: aiSettings, isLoading: aiSettingsLoading } = useAISettings(
        organizationIntegrationsEnabled
    )
    const { data: resendSettings, isLoading: resendSettingsLoading } = useResendSettings(
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
    const googleLastSyncAt = googleCalendarStatus?.last_sync_at ?? googleCalendarIntegration?.last_sync_at ?? null
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
    const inboundWebhooks = zapierSettings?.inbound_webhooks ?? []
    const zapierConfigured = inboundWebhooks.some((hook) => hook.secret_configured) || Boolean(zapierSettings?.secret_configured)
    const zapierActive = inboundWebhooks.some((hook) => hook.is_active) || Boolean(zapierSettings?.is_active)
    const recommendedBucketByStage = buildRecommendedBucketByStage(pipelines)
    const mergedZapierEventMapping = mergeEventMappingWithPipelineStages(zapierSettings?.event_mapping, pipelines)
    const zapierMappingHealth = getZapierMappingHealth(
        mergedZapierEventMapping,
        recommendedBucketByStage,
    )
    const zapierMappingBadgeLabel = zapierMappingHealth.isHealthy
        ? "Mapping Healthy"
        : "Mapping Needs Review"
    const zapierMappingBadgeVariant = zapierMappingHealth.isHealthy ? "default" : "secondary"
    const zapierMappingDetail = `${zapierMappingHealth.matched}/${zapierMappingHealth.total} recommended stages`
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
    const zapierDetail = zapierConfigured
        ? (zapierSettings?.outbound_enabled ? `${inboundSummary} + outbound enabled` : inboundSummary)
        : "Configure webhook secret"
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
    if (metaConnectionsCount > 0 || metaFormsCount > 0) {
        metaDetailParts.push(
            `${metaFormsCount} form${metaFormsCount === 1 ? "" : "s"} · ${metaConnectionsCount} connection${metaConnectionsCount === 1 ? "" : "s"}`
        )
    }
    const metaDetail = metaDetailParts.length > 0
        ? metaDetailParts.join(" · ")
        : "Connect Facebook or add a CRM dataset to get started"
    const AiStatusIcon = aiStatusIcon
    const EmailStatusIcon = emailStatusIcon
    const ZapierStatusIcon = zapierStatusIcon
    const MetaStatusIcon = metaStatusIcon

    return (
        <div className="flex min-h-screen flex-col">
            <IntegrationsPageHeader
                canRefresh={organizationIntegrationsEnabled}
                isFetching={isFetching}
                onRefresh={() => {
                    if (organizationIntegrationsEnabled) void refetch()
                }}
            />

            {/* Main Content */}
            <div className="flex-1 space-y-6 p-6">
                <PersonalIntegrationsSection
                    zoomIntegration={zoomIntegration}
                    gmailIntegration={gmailIntegration}
                    googleCalendarIntegration={googleCalendarIntegration}
                    googleCalendarStatus={googleCalendarStatus}
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
                    onDisconnect={(integrationType) => disconnectIntegration.mutate(integrationType)}
                />

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

                <SystemIntegrationsSection
                    isLoading={isLoading}
                    healthData={healthData ?? []}
                    canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                    metaFormsCount={metaFormsCount}
                    metaMappedFormsCount={metaMappedFormsCount}
                    metaAdAccounts={metaAdAccounts}
                    inboundWebhooksCount={inboundWebhooks.length}
                    zapierOutboundEnabled={Boolean(zapierSettings?.outbound_enabled)}
                />

                <IntegrationsHelpCard />
            </div>
        </div>
    )
}

type BadgeVariant = "default" | "secondary" | "destructive"
type IconComponent = typeof CheckCircleIcon

function IntegrationsPageHeader({
    canRefresh,
    isFetching,
    onRefresh,
}: {
    canRefresh: boolean
    isFetching: boolean
    onRefresh: () => void
}) {
    return (
        <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex h-16 items-center justify-between px-6">
                <h1 className="text-2xl font-semibold">Integrations</h1>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={onRefresh}
                    disabled={!canRefresh || isFetching}
                >
                    <RefreshCwIcon
                        className={`mr-2 size-4 ${isFetching ? "animate-spin" : ""} motion-reduce:animate-none`}
                        aria-hidden="true"
                    />
                    Refresh
                </Button>
            </div>
        </div>
    )
}

function PersonalIntegrationsSection({
    zoomIntegration,
    gmailIntegration,
    googleCalendarIntegration,
    googleCalendarStatus,
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
    onDisconnect: (integrationType: string) => void
}) {
    return (
        <div>
            <h2 className="mb-4 text-lg font-semibold">Personal Integrations</h2>
            <p className="mb-4 text-sm text-muted-foreground">
                Connect your personal accounts to enable features like Zoom appointments and email sending.
            </p>
            <div
                data-testid="personal-integrations-grid"
                className="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
            >
                <PersonalIntegrationCard
                    Icon={VideoIcon}
                    iconContainerClassName="bg-blue-100 dark:bg-blue-900"
                    iconClassName="text-blue-600 dark:text-blue-400"
                    title="Zoom"
                    description="Video appointments"
                    integration={zoomIntegration}
                    connectLabel="Connect Zoom"
                    isConnectPending={pendingState.zoomConnect}
                    isDisconnectPending={pendingState.disconnect}
                    onConnect={onConnectZoom}
                    onDisconnect={() => onDisconnect("zoom")}
                />

                <PersonalIntegrationCard
                    Icon={MailIcon}
                    iconContainerClassName="bg-red-100 dark:bg-red-900"
                    iconClassName="text-red-600 dark:text-red-400"
                    title="Gmail"
                    description="Email sending"
                    integration={gmailIntegration}
                    connectLabel="Connect Gmail"
                    isConnectPending={pendingState.gmailConnect}
                    isDisconnectPending={pendingState.disconnect}
                    onConnect={onConnectGmail}
                    onDisconnect={() => onDisconnect("gmail")}
                />

                <PersonalIntegrationCard
                    Icon={CalendarIcon}
                    iconContainerClassName="bg-emerald-100 dark:bg-emerald-900"
                    iconClassName="text-emerald-600 dark:text-emerald-400"
                    title="Google Calendar + Meeting"
                    description="Two-way calendar sync + meeting links"
                    integration={googleCalendarIntegration}
                    connectLabel="Connect Google Calendar"
                    isConnectPending={pendingState.googleCalendarConnect}
                    isDisconnectPending={pendingState.disconnect}
                    onConnect={onConnectGoogleCalendar}
                    onDisconnect={() => onDisconnect("google_calendar")}
                >
                    <div className="rounded-md border border-border/60 bg-muted/40 px-3 py-2">
                        <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                            Last Sync
                        </p>
                        <p className="text-xs font-medium">{googleLastSyncLabel}</p>
                        {googleLastSyncAbsoluteLabel ? (
                            <p className="text-[11px] text-muted-foreground">
                                {googleLastSyncAbsoluteLabel}
                            </p>
                        ) : null}
                    </div>
                    <Button
                        variant="secondary"
                        size="sm"
                        className="w-full"
                        onClick={onSyncGoogleCalendar}
                        disabled={pendingState.googleCalendarSync}
                    >
                        {pendingState.googleCalendarSync ? (
                            <Loader2Icon
                                className="mr-2 size-3 animate-spin motion-reduce:animate-none"
                                aria-hidden="true"
                            />
                        ) : (
                            <RefreshCwIcon className="mr-2 size-3" aria-hidden="true" />
                        )}
                        Sync now
                    </Button>
                    {googleCalendarStatus && !googleCalendarStatus.tasks_accessible ? (
                        <p className="text-xs text-amber-700">
                            Google Tasks sync is not accessible ({googleCalendarStatus.tasks_error ?? "unknown"}).
                        </p>
                    ) : null}
                </PersonalIntegrationCard>
            </div>
        </div>
    )
}

function PersonalIntegrationCard({
    Icon,
    iconContainerClassName,
    iconClassName,
    title,
    description,
    integration,
    connectLabel,
    isConnectPending,
    isDisconnectPending,
    onConnect,
    onDisconnect,
    children,
}: {
    Icon: IconComponent
    iconContainerClassName: string
    iconClassName: string
    title: string
    description: string
    integration: IntegrationStatus | undefined
    connectLabel: string
    isConnectPending: boolean
    isDisconnectPending: boolean
    onConnect: () => void
    onDisconnect: () => void
    children?: ReactNode
}) {
    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                    <div className={`flex size-10 items-center justify-center rounded-lg ${iconContainerClassName}`}>
                        <Icon className={`size-5 ${iconClassName}`} aria-hidden="true" />
                    </div>
                    <div>
                        <CardTitle className="text-base">{title}</CardTitle>
                        <CardDescription className="text-xs">{description}</CardDescription>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                {integration ? (
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                            <Badge variant="default" className="bg-green-600">
                                <CheckCircleIcon className="mr-1 size-3" aria-hidden="true" />
                                Connected
                            </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">{integration.account_email}</p>
                        {children}
                        <Button
                            variant="outline"
                            size="sm"
                            className="w-full"
                            onClick={onDisconnect}
                            disabled={isDisconnectPending}
                        >
                            <UnlinkIcon className="mr-2 size-3" aria-hidden="true" />
                            Disconnect
                        </Button>
                    </div>
                ) : (
                    <Button className="w-full" onClick={onConnect} disabled={isConnectPending}>
                        {isConnectPending ? (
                            <Loader2Icon
                                className="mr-2 size-4 animate-spin motion-reduce:animate-none"
                                aria-hidden="true"
                            />
                        ) : (
                            <LinkIcon className="mr-2 size-4" aria-hidden="true" />
                        )}
                        {connectLabel}
                    </Button>
                )}
            </CardContent>
        </Card>
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
    return (
        <div>
            <h2 className="mb-4 text-lg font-semibold">Organization Integrations</h2>
            <p className="mb-4 text-sm text-muted-foreground">
                Configure shared services like AI, email delivery, and Zapier for the organization.
            </p>
            {!canManageOrganizationIntegrations ? (
                <Alert className="mb-4">
                    <AlertTriangleIcon className="size-4" aria-hidden="true" />
                    <AlertTitle>Read-only access</AlertTitle>
                    <AlertDescription>
                        You can view organization integration status, but only administrators can configure these integrations.
                    </AlertDescription>
                </Alert>
            ) : null}
            <div
                data-testid="organization-integrations-grid"
                className="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
            >
                <OrganizationIntegrationCard
                    Icon={SparklesIcon}
                    iconContainerClassName="bg-purple-100 dark:bg-purple-900"
                    iconClassName="text-purple-600 dark:text-purple-400"
                    title="AI Assistant"
                    description="Copilot, summaries, and AI workflows"
                    isLoading={aiSettingsLoading}
                    statusLabel={aiStatusLabel}
                    statusVariant={aiStatusVariant}
                    StatusIcon={AiStatusIcon}
                    canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                    actionLabel="Configure AI"
                    onConfigure={onConfigureAI}
                >
                    <p className="text-xs text-muted-foreground">
                        {aiSettingsProvider ? `Provider: ${aiProviderLabel}` : "No provider configured"}
                    </p>
                </OrganizationIntegrationCard>

                <OrganizationIntegrationCard
                    Icon={SendIcon}
                    iconContainerClassName="bg-teal-100 dark:bg-teal-900"
                    iconClassName="text-teal-600 dark:text-teal-400"
                    title="Email Delivery"
                    description="Campaign + transactional sending"
                    isLoading={resendSettingsLoading}
                    statusLabel={emailStatusLabel}
                    statusVariant={emailStatusVariant}
                    StatusIcon={EmailStatusIcon}
                    canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                    actionLabel="Configure Email"
                    onConfigure={onConfigureEmail}
                >
                    <p className="text-xs text-muted-foreground">
                        {emailConfigured ? `${emailProviderLabel} · ${emailDetail}` : "Choose a provider to start sending"}
                    </p>
                </OrganizationIntegrationCard>

                <OrganizationIntegrationCard
                    Icon={LinkIcon}
                    iconContainerClassName="bg-primary/10 dark:bg-primary/20"
                    iconClassName="text-primary"
                    title="Zapier"
                    description="Inbound leads + stage event delivery"
                    isLoading={zapierSettingsLoading}
                    statusLabel={zapierStatusLabel}
                    statusVariant={zapierStatusVariant}
                    StatusIcon={ZapierStatusIcon}
                    canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                    actionLabel="Configure Zapier"
                    onConfigure={onConfigureZapier}
                >
                    <Badge
                        data-testid="zapier-mapping-health-card-badge"
                        variant={zapierMappingBadgeVariant}
                        className="w-fit"
                    >
                        {zapierMappingBadgeLabel}
                    </Badge>
                    <p className="text-xs text-muted-foreground">{zapierDetail}</p>
                    <p className="text-xs text-muted-foreground">{zapierMappingDetail}</p>
                </OrganizationIntegrationCard>

                <OrganizationIntegrationCard
                    Icon={MegaphoneIcon}
                    iconContainerClassName="bg-blue-100 dark:bg-blue-900"
                    iconClassName="text-blue-600 dark:text-blue-400"
                    title="Meta Lead Ads"
                    description="Facebook/Instagram lead capture + CAPI"
                    isLoading={metaCrmDatasetSettingsLoading}
                    statusLabel={metaStatusLabel}
                    statusVariant={metaStatusVariant}
                    StatusIcon={MetaStatusIcon}
                    canManageOrganizationIntegrations={canManageOrganizationIntegrations}
                    actionLabel="Configure Meta"
                    onConfigure={onConfigureMeta}
                >
                    <p className="text-xs text-muted-foreground">{metaDetail}</p>
                </OrganizationIntegrationCard>
            </div>
        </div>
    )
}

function OrganizationIntegrationCard({
    Icon,
    iconContainerClassName,
    iconClassName,
    title,
    description,
    isLoading,
    statusLabel,
    statusVariant,
    StatusIcon,
    canManageOrganizationIntegrations,
    actionLabel,
    onConfigure,
    children,
}: {
    Icon: IconComponent
    iconContainerClassName: string
    iconClassName: string
    title: string
    description: string
    isLoading: boolean
    statusLabel: string
    statusVariant: BadgeVariant
    StatusIcon: IconComponent
    canManageOrganizationIntegrations: boolean
    actionLabel: string
    onConfigure: () => void
    children: ReactNode
}) {
    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                    <div className={`flex size-10 items-center justify-center rounded-lg ${iconContainerClassName}`}>
                        <Icon className={`size-5 ${iconClassName}`} aria-hidden="true" />
                    </div>
                    <div>
                        <CardTitle className="text-base">{title}</CardTitle>
                        <CardDescription className="text-xs">{description}</CardDescription>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                {isLoading ? (
                    <div className="flex items-center justify-center py-6">
                        <Loader2Icon
                            className="size-5 animate-spin motion-reduce:animate-none text-muted-foreground"
                            aria-hidden="true"
                        />
                    </div>
                ) : (
                    <div className="space-y-3">
                        <Badge variant={statusVariant} className="w-fit flex items-center gap-1">
                            <StatusIcon className="size-3" aria-hidden="true" />
                            {statusLabel}
                        </Badge>
                        {children}
                        <Button
                            variant="outline"
                            className="w-full"
                            onClick={onConfigure}
                            disabled={!canManageOrganizationIntegrations}
                        >
                            {canManageOrganizationIntegrations ? actionLabel : "Admin access required"}
                        </Button>
                    </div>
                )}
            </CardContent>
        </Card>
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
                <DialogContent className="max-h-[85vh] w-[95vw] max-w-4xl overflow-y-auto overflow-x-hidden">
                    <DialogHeader>
                        <div className="flex items-start justify-between gap-4">
                            <div className="space-y-1">
                                <DialogTitle>AI Configuration</DialogTitle>
                                <DialogDescription>
                                    Configure the AI provider, model, and safety controls for your organization.
                                </DialogDescription>
                            </div>
                            <Badge variant={aiStatusVariant} className="mt-1 flex items-center gap-1">
                                <AiStatusIcon className="size-3" aria-hidden="true" />
                                {aiStatusLabel}
                            </Badge>
                        </div>
                    </DialogHeader>
                    {aiDialogOpen ? <AIConfigurationSection variant="dialog" /> : null}
                </DialogContent>
            </Dialog>

            <Dialog
                open={canManageOrganizationIntegrations && emailDialogOpen}
                onOpenChange={(open) => {
                    if (!canManageOrganizationIntegrations) return
                    onEmailDialogOpenChange(open)
                }}
            >
                <DialogContent className="max-h-[85vh] w-[95vw] max-w-4xl overflow-y-auto overflow-x-hidden">
                    <DialogHeader>
                        <div className="flex items-start justify-between gap-4">
                            <div className="space-y-1">
                                <DialogTitle>Email Configuration</DialogTitle>
                                <DialogDescription>
                                    Choose a provider and set sender defaults for campaigns and automation.
                                </DialogDescription>
                            </div>
                            <Badge variant={emailStatusVariant} className="mt-1 flex items-center gap-1">
                                <EmailStatusIcon className="size-3" aria-hidden="true" />
                                {emailStatusLabel}
                            </Badge>
                        </div>
                    </DialogHeader>
                    {emailDialogOpen ? <EmailConfigurationSection variant="dialog" /> : null}
                </DialogContent>
            </Dialog>

            <Dialog
                open={canManageOrganizationIntegrations && zapierDialogOpen}
                onOpenChange={(open) => {
                    if (!canManageOrganizationIntegrations) return
                    onZapierDialogOpenChange(open)
                }}
            >
                <DialogContent className="flex h-[85vh] w-[95vw] max-w-4xl flex-col gap-0 overflow-hidden p-0">
                    <DialogHeader className="shrink-0 px-6 pt-6 pb-4">
                        <div className="flex items-start justify-between gap-4">
                            <div className="space-y-1">
                                <DialogTitle>Zapier Configuration</DialogTitle>
                                <DialogDescription>
                                    Manage inbound lead webhooks and outbound stage event delivery.
                                </DialogDescription>
                            </div>
                            <div className="mt-1 flex items-center gap-2">
                                <Badge variant={zapierStatusVariant} className="flex items-center gap-1">
                                    <ZapierStatusIcon className="size-3" aria-hidden="true" />
                                    {zapierStatusLabel}
                                </Badge>
                                <Badge
                                    data-testid="zapier-mapping-health-dialog-badge"
                                    variant={zapierMappingBadgeVariant}
                                >
                                    {zapierMappingBadgeLabel}
                                </Badge>
                            </div>
                        </div>
                    </DialogHeader>
                    <div
                        className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-6 pb-6"
                        data-testid="zapier-dialog-body"
                    >
                        {zapierDialogOpen ? <ZapierWebhookSection variant="dialog" /> : null}
                    </div>
                </DialogContent>
            </Dialog>

            <Dialog
                open={canManageOrganizationIntegrations && metaDialogOpen}
                onOpenChange={(open) => {
                    if (!canManageOrganizationIntegrations) return
                    onMetaDialogOpenChange(open)
                }}
            >
                <DialogContent className="max-h-[85vh] w-[95vw] max-w-4xl overflow-y-auto overflow-x-hidden">
                    <DialogHeader>
                        <div className="flex items-start justify-between gap-4">
                            <div className="space-y-1">
                                <DialogTitle>Meta Lead Ads + CRM Dataset</DialogTitle>
                                <DialogDescription>
                                    Configure direct CRM dataset delivery and manage the legacy app-based Meta setup.
                                </DialogDescription>
                            </div>
                            <Badge variant={metaStatusVariant} className="mt-1 flex items-center gap-1">
                                <MetaStatusIcon className="size-3" aria-hidden="true" />
                                {metaStatusLabel}
                            </Badge>
                        </div>
                    </DialogHeader>
                    {metaDialogOpen ? <MetaConfigurationSection variant="dialog" /> : null}
                </DialogContent>
            </Dialog>
        </>
    )
}

function SystemIntegrationsSection({
    isLoading,
    healthData,
    canManageOrganizationIntegrations,
    metaFormsCount,
    metaMappedFormsCount,
    metaAdAccounts,
    inboundWebhooksCount,
    zapierOutboundEnabled,
}: {
    isLoading: boolean
    healthData: IntegrationHealth[]
    canManageOrganizationIntegrations: boolean
    metaFormsCount: number
    metaMappedFormsCount: number
    metaAdAccounts: MetaAdAccount[]
    inboundWebhooksCount: number
    zapierOutboundEnabled: boolean
}) {
    return (
        <>
            <div className="border-t pt-6">
                <h2 className="mb-4 text-lg font-semibold">System Integrations</h2>
                <p className="mb-4 text-sm text-muted-foreground">
                    Organization-level integrations managed by administrators.
                </p>
            </div>
            {isLoading ? (
                <div className="flex items-center justify-center py-12">
                    <Loader2Icon
                        className="size-8 animate-spin motion-reduce:animate-none text-muted-foreground"
                        aria-hidden="true"
                    />
                </div>
            ) : healthData.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <ServerIcon className="mb-4 size-12" aria-hidden="true" />
                        <p className="text-lg font-medium">No integrations configured</p>
                        <p className="text-sm">Add integrations to see their health status here</p>
                    </CardContent>
                </Card>
            ) : (
                <div
                    data-testid="system-integrations-grid"
                    className="grid gap-6 md:grid-cols-2 xl:grid-cols-3"
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
                        />
                    ))}
                </div>
            )}
        </>
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
}: {
    integration: IntegrationHealth
    canManageOrganizationIntegrations: boolean
    metaFormsCount: number
    metaMappedFormsCount: number
    metaAdAccounts: MetaAdAccount[]
    inboundWebhooksCount: number
    zapierOutboundEnabled: boolean
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
}: {
    integrationType: string
    metaFormsCount: number
    metaMappedFormsCount: number
    metaAdAccounts: MetaAdAccount[]
    inboundWebhooksCount: number
    zapierOutboundEnabled: boolean
}): string | null {
    if (integrationType === "meta_leads") {
        return `${metaFormsCount} form${metaFormsCount === 1 ? "" : "s"} synced · ${metaMappedFormsCount} mapped`
    }
    if (integrationType === "meta_capi") {
        const capiEnabledCount = metaAdAccounts.filter((account) => account.capi_enabled).length
        return `${capiEnabledCount} ad account${capiEnabledCount === 1 ? "" : "s"} with CAPI enabled`
    }
    if (integrationType === "zapier") {
        const outboundStatus = zapierOutboundEnabled ? "enabled" : "disabled"
        return `${inboundWebhooksCount} inbound webhook${inboundWebhooksCount === 1 ? "" : "s"} · Outbound ${outboundStatus}`
    }
    return null
}

function getIntegrationStatusBarClass(status: IntegrationHealth["status"]): string {
    if (status === "healthy") return "bg-green-500"
    if (status === "degraded") return "bg-yellow-500"
    return "bg-red-500"
}

function IntegrationsHelpCard() {
    return (
        <Card className="bg-muted/50">
            <CardHeader>
                <CardTitle className="text-base">Need help?</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
                <p>
                    Integration tokens are managed via CLI commands. To update a Meta page token:
                </p>
                <pre className="mt-2 overflow-x-auto rounded-md bg-muted p-3 text-xs">
                    python -m app.cli update-meta-page-token --page-id YOUR_PAGE_ID
                </pre>
                <p className="mt-3">
                    Contact your administrator if you need to add or reconfigure integrations.
                </p>
            </CardContent>
        </Card>
    )
}
