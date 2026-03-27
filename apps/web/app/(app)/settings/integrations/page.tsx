"use client"

import { useState, useEffect, useMemo } from "react"
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
    FacebookIcon,
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
import { formatRelativeTime } from "@/lib/formatters"
import { CopyIcon, SendIcon, RotateCwIcon, ActivityIcon, PlusIcon } from "lucide-react"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { toast } from "sonner"
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

const integrationTypeConfig: Record<string, { icon: typeof FacebookIcon; label: string; description: string }> = {
    meta_leads: {
        icon: FacebookIcon,
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

function AIConfigurationSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
    const { data: aiSettings, isLoading } = useAISettings()
    const { data: consentInfo } = useAIConsent()
    const acceptConsent = useAcceptConsent()
    const updateSettings = useUpdateAISettings()
    const testKey = useTestAPIKey()
    const { data: userIntegrations } = useUserIntegrations()
    const connectGcp = useConnectGcp()
    const disconnectIntegration = useDisconnectIntegration()
    const { refetch: refetchAuth } = useAuth()

    const [aiForm, setAiForm] = useState<AiConfigurationFormState>({
        isEnabled: false,
        provider: "gemini",
        apiKey: "",
        model: "",
        vertexProjectId: "",
        vertexLocation: "us-central1",
        vertexAudience: "",
        vertexServiceAccount: "",
        vertexUseExpress: true,
    })
    const [aiUi, setAiUi] = useState<AiConfigurationUiState>({
        keyTested: null,
        saved: false,
        editingKey: false,
    })

    useEffect(() => {
        if (!aiSettings) return
        setAiForm({
            isEnabled: aiSettings.is_enabled,
            provider: isAiProvider(aiSettings.provider) ? aiSettings.provider : "gemini",
            apiKey: "",
            model: aiSettings.model || "",
            vertexProjectId:
                aiSettings.vertex_wif?.project_id ||
                aiSettings.vertex_api_key?.project_id ||
                "",
            vertexLocation:
                aiSettings.vertex_wif?.location ||
                aiSettings.vertex_api_key?.location ||
                "us-central1",
            vertexAudience: aiSettings.vertex_wif?.audience || "",
            vertexServiceAccount: aiSettings.vertex_wif?.service_account_email || "",
            vertexUseExpress:
                aiSettings.provider === "vertex_api_key"
                && !aiSettings.vertex_api_key?.project_id
                && !aiSettings.vertex_api_key?.location,
        })
        setAiUi((current) => ({
            ...current,
            keyTested: null,
            editingKey: false,
        }))
    }, [aiSettings])

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
            <div className={containerClass}>
                {showHeading && (
                    <h2 className="mb-4 text-lg font-semibold">AI Configuration</h2>
                )}
                <div className="flex items-center justify-center py-8">
                    <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                </div>
            </div>
        )
    }

    return (
        <div className={containerClass}>
            {showHeading && (
                <>
                    <h2 className="mb-4 text-lg font-semibold">AI Configuration</h2>
                    <p className="mb-4 text-sm text-muted-foreground">
                        Configure AI assistant settings for your organization. Use BYOK (OpenAI/Gemini), Vertex API key (express mode), or Vertex AI via Workload Identity Federation.
                    </p>
                </>
            )}

            {!consentAccepted && consentInfo && (
                <Card className="mb-4 border-yellow-200 bg-yellow-50/60">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base">AI Consent Required</CardTitle>
                        <CardDescription className="text-xs text-muted-foreground">
                            An admin must accept the AI data processing consent before enabling AI features.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="max-h-40 overflow-auto rounded-md border border-yellow-200 bg-white p-3 text-xs leading-relaxed text-muted-foreground">
                            {consentInfo.consent_text}
                        </div>
                        <Button onClick={handleAcceptConsent} disabled={acceptConsent.isPending}>
                            {acceptConsent.isPending ? (
                                <>
                                    <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                    Accepting…
                                </>
                            ) : (
                                "Accept Consent"
                            )}
                        </Button>
                    </CardContent>
                </Card>
            )}

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
                    <div className="space-y-2">
                        <Label htmlFor="ai-provider">AI Provider</Label>
                        <Select
                            value={aiForm.provider}
                            onValueChange={(value) => {
                                if (!value || !isAiProvider(value)) return
                                setAiForm((current) => ({
                                    ...current,
                                    provider: value,
                                    model: "",
                                }))
                                setAiUi((current) => ({
                                    ...current,
                                    keyTested: null,
                                    editingKey: false,
                                }))
                            }}
                        >
                            <SelectTrigger id="ai-provider">
                                <SelectValue placeholder="Select provider" />
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

                    {aiForm.provider !== "vertex_wif" && (
                        <div className="space-y-2">
                            <Label htmlFor="ai-key">API Key</Label>
                            <div className="flex gap-2">
                                <Input
                                    id="ai-key"
                                    type="password"
                                    value={
                                        aiUi.editingKey
                                            ? aiForm.apiKey
                                            : aiForm.apiKey || (aiSettings?.api_key_masked ? aiSettings.api_key_masked : "")
                                    }
                                    onChange={(event) => {
                                        updateAiForm("apiKey", event.target.value)
                                        setAiUi((current) => ({ ...current, keyTested: null }))
                                    }}
                                    placeholder="Enter API key"
                                    disabled={!aiUi.editingKey && !aiForm.apiKey && !!aiSettings?.api_key_masked}
                                    className="flex-1"
                                    name="ai-api-key"
                                    autoComplete="off"
                                />
                                {aiSettings?.api_key_masked && !aiForm.apiKey && !aiUi.editingKey ? (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => {
                                            updateAiForm("apiKey", "")
                                            setAiUi((current) => ({ ...current, editingKey: true }))
                                        }}
                                        className="shrink-0"
                                    >
                                        Change Key
                                    </Button>
                                ) : (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleTestKey}
                                        disabled={!aiForm.apiKey.trim() || testKey.isPending}
                                    >
                                        {testKey.isPending ? (
                                            <Loader2Icon className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        ) : aiUi.keyTested === true ? (
                                            <CheckIcon className="size-4 text-green-600" aria-hidden="true" />
                                        ) : aiUi.keyTested === false ? (
                                            <XCircleIcon className="size-4 text-red-600" aria-hidden="true" />
                                        ) : (
                                            "Test"
                                        )}
                                    </Button>
                                )}
                            </div>
                            {aiUi.keyTested === true && (
                                <p className="text-xs text-green-600">API key is valid!</p>
                            )}
                            {aiUi.keyTested === false && (
                                <p className="text-xs text-red-600">API key is invalid. Please check and try again.</p>
                            )}
                            <p className="text-xs text-muted-foreground">
                                {aiForm.provider === "gemini"
                                    ? "Get your key from aistudio.google.com"
                                    : "Create a Vertex AI API key in Google Cloud"}
                            </p>
                        </div>
                    )}

                    {aiForm.provider === "vertex_api_key" && (
                        <div className="space-y-4 rounded-lg border p-4">
                            <div>
                                <h3 className="text-sm font-medium">Vertex AI (API Key)</h3>
                                <p className="text-xs text-muted-foreground">
                                    Express mode works without project or location. Add them to use project-scoped endpoints.
                                </p>
                            </div>
                            <div className="flex items-center justify-between rounded-md border p-3">
                                <div className="text-sm">
                                    {aiForm.vertexUseExpress ? "Express mode active" : "Project-scoped mode"}
                                </div>
                                <div className="flex items-center gap-2">
                                    <Label htmlFor="vertex-express" className="text-xs text-muted-foreground">
                                        Use express mode
                                    </Label>
                                    <Switch
                                        id="vertex-express"
                                        checked={aiForm.vertexUseExpress}
                                        onCheckedChange={(checked) => updateAiForm("vertexUseExpress", checked)}
                                    />
                                </div>
                            </div>
                            {!aiForm.vertexUseExpress && (
                                <div className="grid gap-3 md:grid-cols-2">
                                    <div className="space-y-2">
                                        <Label htmlFor="vertex-project-key">Project ID (optional)</Label>
                                        <Input
                                            id="vertex-project-key"
                                            value={aiForm.vertexProjectId}
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
                                            value={aiForm.vertexLocation}
                                            onChange={(event) => updateAiForm("vertexLocation", event.target.value)}
                                            placeholder="us-central1"
                                            name="vertex-location-key"
                                            autoComplete="off"
                                        />
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {aiForm.provider === "vertex_wif" && (
                        <div className="space-y-4 rounded-lg border p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <h3 className="text-sm font-medium">Vertex AI (WIF)</h3>
                                    <p className="text-xs text-muted-foreground">
                                        Uses Workload Identity Federation—no long-lived keys stored.
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
                                        onClick={() => disconnectIntegration.mutate("gcp")}
                                        disabled={disconnectIntegration.isPending}
                                    >
                                        Disconnect
                                    </Button>
                                ) : (
                                    <Button size="sm" onClick={() => connectGcp.mutate()} disabled={connectGcp.isPending}>
                                        {connectGcp.isPending ? (
                                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        ) : null}
                                        Connect GCP
                                    </Button>
                                )}
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="vertex-project">Project ID</Label>
                                <Input
                                    id="vertex-project"
                                    value={aiForm.vertexProjectId}
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
                                    value={aiForm.vertexLocation}
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
                                    value={aiForm.vertexServiceAccount}
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
                                    value={aiForm.vertexAudience}
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
                    )}

                    <div className="space-y-2">
                        <Label htmlFor="ai-model">Model</Label>
                        <Select value={aiForm.model} onValueChange={(value) => updateAiForm("model", value || "")}>
                            <SelectTrigger id="ai-model">
                                <SelectValue placeholder="Select model (optional)" />
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

                    <Button onClick={handleSave} disabled={updateSettings.isPending || !vertexReady} className="w-full">
                        {updateSettings.isPending ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                Saving…
                            </>
                        ) : aiUi.saved ? (
                            <>
                                <CheckIcon className="mr-2 size-4" aria-hidden="true" />
                                Saved!
                            </>
                        ) : (
                            "Save AI Configuration"
                        )}
                    </Button>
                </CardContent>
            </Card>
        </div>
    )
}

function EmailConfigurationSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
    const { data: settings, isLoading } = useResendSettings()
    const updateSettings = useUpdateResendSettings()
    const testKey = useTestResendKey()
    const rotateWebhook = useRotateWebhook()
    const [emailForm, setEmailForm] = useState<EmailConfigurationFormState>({
        provider: "",
        apiKey: "",
        fromEmail: "",
        fromName: "",
        replyTo: "",
        webhookSigningSecret: "",
        defaultSender: "",
    })
    const [emailUi, setEmailUi] = useState<EmailConfigurationUiState>({
        keyTested: null,
        saved: false,
        isEditingKey: false,
        hasUserEdited: false,
    })
    const { data: eligibleSenders, isLoading: eligibleSendersLoading } = useEligibleSenders(emailForm.provider === "gmail")

    useEffect(() => {
        if (!settings || emailUi.hasUserEdited) return
        setEmailForm({
            provider: settings.email_provider || "resend",
            apiKey: "",
            fromEmail: settings.from_email || "",
            fromName: settings.from_name || "",
            replyTo: settings.reply_to_email || "",
            webhookSigningSecret: "",
            defaultSender: settings.default_sender_user_id || "",
        })
        setEmailUi((current) => ({
            ...current,
            keyTested: null,
            isEditingKey: false,
        }))
    }, [settings, emailUi.hasUserEdited])

    const getErrorMessage = (error: unknown, fallback: string) => {
        if (error instanceof Error && error.message) return error.message
        return fallback
    }

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

    const copyToClipboard = (text: string) => {
        navigator.clipboard
            .writeText(text)
            .then(() => toast.success("Copied to clipboard"))
            .catch(() => toast.error("Failed to copy"))
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
            <div className={containerClass}>
                {showHeading && (
                    <h2 className="mb-4 text-lg font-semibold">Email Configuration</h2>
                )}
                <div className="flex items-center justify-center py-8">
                    <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                </div>
            </div>
        )
    }

    return (
        <div className={containerClass}>
            {showHeading && (
                <>
                    <h2 className="mb-4 text-lg font-semibold">Email Configuration</h2>
                    <p className="mb-4 text-sm text-muted-foreground">
                        Configure the email provider for campaigns. Choose between Resend (recommended for deliverability) or Gmail.
                    </p>
                </>
            )}

            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center gap-3">
                        <div className="flex size-10 items-center justify-center rounded-lg bg-teal-100 dark:bg-teal-900">
                            <SendIcon className="size-5 text-teal-600 dark:text-teal-400" aria-hidden="true" />
                        </div>
                        <div>
                            <CardTitle className="text-base">Campaign Email Provider</CardTitle>
                            <CardDescription className="text-xs">
                                {settings?.email_provider === "resend"
                                    ? "Resend"
                                    : settings?.email_provider === "gmail"
                                    ? "Gmail"
                                    : "Not configured"}
                            </CardDescription>
                        </div>
                    </div>
                </CardHeader>

                <CardContent className="space-y-6">
                    {/* Provider Selection */}
                    <div className="space-y-3">
                        <Label htmlFor="email-provider">Email Provider</Label>
                        <RadioGroup
                            value={emailForm.provider}
                            onValueChange={(v) => handleProviderChange(v as "resend" | "gmail" | "")}
                            className="flex flex-col gap-3"
                            id="email-provider"
                            aria-label="Email provider"
                        >
                            <div className="flex items-center space-x-2">
                                <RadioGroupItem value="resend" id="provider-resend" />
                                <Label htmlFor="provider-resend" className="cursor-pointer">
                                    <span className="font-medium">Resend</span>
                                    <span className="ml-2 text-xs text-muted-foreground">(Recommended)</span>
                                </Label>
                            </div>
                            <div className="flex items-center space-x-2">
                                <RadioGroupItem value="gmail" id="provider-gmail" />
                                <Label htmlFor="provider-gmail" className="cursor-pointer">
                                    <span className="font-medium">Gmail</span>
                                    <span className="ml-2 text-xs text-muted-foreground">(Org admin account)</span>
                                </Label>
                            </div>
                        </RadioGroup>
                    </div>

                    {emailForm.provider === "resend" && (
                        <div className="space-y-4 rounded-lg border p-4">
                            <h3 className="text-sm font-medium">Resend Configuration</h3>

                            <div className="space-y-2">
                                <Label htmlFor="resend-key">API Key</Label>
                                <div className="flex gap-2">
                                    <Input
                                        id="resend-key"
                                        type="password"
                                        value={showMaskedKey ? settings?.api_key_masked ?? "" : emailForm.apiKey}
                                        onChange={(e) => {
                                            updateEmailForm("apiKey", e.target.value, true)
                                            setEmailUi((current) => ({
                                                ...current,
                                                keyTested: null,
                                                isEditingKey: true,
                                            }))
                                        }}
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
                                            onClick={() => {
                                                updateEmailForm("apiKey", "", true)
                                                setEmailUi((current) => ({
                                                    ...current,
                                                    isEditingKey: true,
                                                    keyTested: null,
                                                }))
                                            }}
                                            className="shrink-0"
                                        >
                                            Change Key
                                        </Button>
                                    ) : (
                                        <div className="flex gap-2">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={handleTestKey}
                                                disabled={!emailForm.apiKey.trim() || testKey.isPending}
                                            >
                                                {testKey.isPending ? (
                                                    <Loader2Icon className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                                ) : emailUi.keyTested?.valid ? (
                                                    <CheckIcon className="size-4 text-green-600" aria-hidden="true" />
                                                ) : emailUi.keyTested !== null ? (
                                                    <XCircleIcon className="size-4 text-red-600" aria-hidden="true" />
                                                ) : (
                                                    "Test"
                                                )}
                                            </Button>
                                            {settings?.api_key_masked && emailUi.isEditingKey && (
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => {
                                                        updateEmailForm("apiKey", "")
                                                        setEmailUi((current) => ({
                                                            ...current,
                                                            isEditingKey: false,
                                                            keyTested: null,
                                                        }))
                                                    }}
                                                >
                                                    Cancel
                                                </Button>
                                            )}
                                        </div>
                                    )}
                                </div>
                                {emailUi.keyTested?.valid && (
                                    <p className="text-xs text-green-600">
                                        API key is valid! Verified domain: {emailUi.keyTested.verified_domains?.[0] || settings?.verified_domain}
                                    </p>
                                )}
                                {emailUi.keyTested && !emailUi.keyTested.valid && (
                                    <p className="text-xs text-red-600">{emailUi.keyTested.error || "API key is invalid"}</p>
                                )}
                                <p className="text-xs text-muted-foreground">
                                    Get your key from <a href="https://resend.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">resend.com/api-keys</a>
                                </p>
                            </div>

                            {settings?.verified_domain && (
                                <div className="flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm dark:bg-green-900/20">
                                    <CheckCircleIcon className="size-4 text-green-600" aria-hidden="true" />
                                    <span>Verified domain: <strong>{settings.verified_domain}</strong></span>
                                </div>
                            )}

                            <div className="space-y-2">
                                <Label htmlFor="from-email">From Email</Label>
                                <Input
                                    id="from-email"
                                    type="email"
                                    value={emailForm.fromEmail}
                                    onChange={(e) => updateEmailForm("fromEmail", e.target.value, true)}
                                    placeholder={settings?.verified_domain ? `no-reply@${settings.verified_domain}` : "no-reply@yourdomain.com"}
                                    name="from-email"
                                    autoComplete="email"
                                />
                                {settings?.verified_domain && (
                                    <p className="text-xs text-muted-foreground">
                                        Must use your verified domain: @{settings.verified_domain}
                                    </p>
                                )}
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="from-name">From Name (optional)</Label>
                                <Input
                                    id="from-name"
                                    value={emailForm.fromName}
                                    onChange={(e) => updateEmailForm("fromName", e.target.value, true)}
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
                                    value={emailForm.replyTo}
                                    onChange={(e) => updateEmailForm("replyTo", e.target.value, true)}
                                    placeholder="support@yourdomain.com"
                                    name="reply-to"
                                    autoComplete="email"
                                />
                            </div>

                            {settings?.webhook_url && (
                                <div className="space-y-2">
                                    <Label>Webhook URL</Label>
                                    <div className="flex gap-2">
                                        <Input
                                            value={settings.webhook_url}
                                            readOnly
                                            className="flex-1 text-xs font-mono"
                                        />
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => copyToClipboard(settings.webhook_url)}
                                            aria-label="Copy webhook URL"
                                        >
                                            <CopyIcon className="size-4" aria-hidden="true" />
                                        </Button>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={handleRotateWebhook}
                                            disabled={rotateWebhook.isPending}
                                            aria-label="Rotate webhook URL"
                                        >
                                            {rotateWebhook.isPending ? (
                                                <Loader2Icon className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                            ) : (
                                                <RotateCwIcon className="size-4" aria-hidden="true" />
                                            )}
                                        </Button>
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Create a webhook endpoint in Resend pointing to this URL and subscribe to: email.delivered, email.bounced, email.complained, email.opened, email.clicked.
                                    </p>
                                </div>
                            )}

                            <div className="space-y-2">
                                <Label htmlFor="resend-webhook-secret">Webhook Signing Secret</Label>
                                <Input
                                    id="resend-webhook-secret"
                                    type="password"
                                    value={emailForm.webhookSigningSecret}
                                    onChange={(e) => updateEmailForm("webhookSigningSecret", e.target.value, true)}
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
                    )}

                    {emailForm.provider === "gmail" && (
                        <div className="space-y-4 rounded-lg border p-4">
                            <h3 className="text-sm font-medium">Gmail Configuration</h3>

                            <div className="space-y-2">
                                <Label htmlFor="gmail-sender">Default Sender</Label>
                                <Select
                                    value={emailForm.defaultSender}
                                    onValueChange={(v) => updateEmailForm("defaultSender", v ?? "", true)}
                                >
                                    <SelectTrigger id="gmail-sender">
                                        <SelectValue placeholder={eligibleSendersLoading ? "Loading senders…" : "Select admin with Gmail connected"} />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {eligibleSenders?.map((sender) => (
                                            <SelectItem key={sender.user_id} value={sender.user_id}>
                                                {sender.display_name} ({sender.gmail_email})
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                {!eligibleSendersLoading && !eligibleSenders?.length && (
                                    <p className="text-xs text-yellow-600">
                                        No eligible senders found. Admin users must connect Gmail first.
                                    </p>
                                )}
                                <p className="text-xs text-muted-foreground">
                                    Only admin users with Gmail connected can be selected as the default sender.
                                </p>
                            </div>

                            {settings?.default_sender_name && (
                                <div className="flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm dark:bg-green-900/20">
                                    <CheckCircleIcon className="size-4 text-green-600" aria-hidden="true" />
                                    <span>
                                        Current sender: <strong>{settings.default_sender_name}</strong> ({settings.default_sender_email})
                                    </span>
                                </div>
                            )}
                        </div>
                    )}

                    <Button onClick={handleSave} disabled={updateSettings.isPending || !canSave} className="w-full">
                        {updateSettings.isPending ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                Saving…
                            </>
                        ) : emailUi.saved ? (
                            <>
                                <CheckIcon className="mr-2 size-4" aria-hidden="true" />
                                Saved!
                            </>
                        ) : (
                            "Save Email Configuration"
                        )}
                    </Button>
                </CardContent>
            </Card>
        </div>
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

function ZapierWebhookSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
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
    const [webhookSecrets, setWebhookSecrets] = useState<Record<string, string>>({})
    const [labelDrafts, setLabelDrafts] = useState<Record<string, string>>({})
    const [rotatingWebhookId, setRotatingWebhookId] = useState<string | null>(null)
    const [deletingWebhookId, setDeletingWebhookId] = useState<string | null>(null)
    const [testFormId, setTestFormId] = useState('')
    const [fieldPaste, setFieldPaste] = useState('')
    const [fieldPasteWebhookId, setFieldPasteWebhookId] = useState('')
    const [fieldPasteResult, setFieldPasteResult] = useState<ZapierFieldPasteResponse | null>(null)
    const sendTestLead = useZapierTestLead()
    const sendOutboundTest = useZapierOutboundTest()
    const [outboundUrl, setOutboundUrl] = useState('')
    const [outboundSecret, setOutboundSecret] = useState('')
    const [outboundEnabled, setOutboundEnabled] = useState(false)
    const [sendHashedPii, setSendHashedPii] = useState(false)
    const [eventMapping, setEventMapping] = useState<ZapierEventMappingItem[]>([])
    const [selectedOutboundStage, setSelectedOutboundStage] = useState<string>('')
    const [outboundTestLeadId, setOutboundTestLeadId] = useState('')

    useEffect(() => {
        if (!settings?.inbound_webhooks) return
        const drafts: Record<string, string> = {}
        settings.inbound_webhooks.forEach((webhook) => {
            drafts[webhook.webhook_id] = webhook.label || ""
        })
        setLabelDrafts(drafts)
        setWebhookSecrets((prev) => {
            const next: Record<string, string> = {}
            settings.inbound_webhooks.forEach((webhook) => {
                const existing = prev[webhook.webhook_id]
                if (existing) {
                    next[webhook.webhook_id] = existing
                }
            })
            return next
        })
    }, [settings?.inbound_webhooks])

    useEffect(() => {
        const inbound = settings?.inbound_webhooks ?? []
        if (!inbound.length) {
            if (fieldPasteWebhookId) {
                setFieldPasteWebhookId('')
            }
            return
        }
        const ids = inbound.map((webhook) => webhook.webhook_id)
        if (!fieldPasteWebhookId || !ids.includes(fieldPasteWebhookId)) {
            const [firstId] = ids
            if (firstId) {
                setFieldPasteWebhookId(firstId)
            }
        }
    }, [settings?.inbound_webhooks, fieldPasteWebhookId])

    useEffect(() => {
        if (!settings) return
        const mergedEventMapping = mergeEventMappingWithPipelineStages(
            settings.event_mapping || [],
            pipelines,
        )
        setOutboundUrl(settings.outbound_webhook_url || '')
        setOutboundEnabled(Boolean(settings.outbound_enabled))
        setSendHashedPii(Boolean(settings.send_hashed_pii))
        setEventMapping(mergedEventMapping)
        setSelectedOutboundStage((current) =>
            current && mergedEventMapping.some((item) => item.stage_key === current)
                ? current
                : mergedEventMapping[0]?.stage_key || ''
        )
    }, [settings, pipelines])

    useEffect(() => {
        const activeZapierForms = metaForms.filter(
            (form) =>
                form.is_active &&
                (form.page_id === "zapier" || form.form_external_id?.startsWith("zapier-"))
        )
        if (activeZapierForms.length !== 1) {
            return
        }
        const [onlyForm] = activeZapierForms
        const nextFormId = onlyForm?.form_external_id?.trim()
        if (!nextFormId || testFormId.trim() === nextFormId) {
            return
        }
        setTestFormId(nextFormId)
    }, [metaForms, testFormId])

    const copyToClipboard = (text: string) => {
        navigator.clipboard
            .writeText(text)
            .then(() => toast.success("Copied to clipboard"))
            .catch(() => toast.error("Failed to copy"))
    }

    const handleCreateInbound = async () => {
        try {
            const result = await createInboundWebhook.mutateAsync({ label: null })
            setWebhookSecrets((prev) => ({ ...prev, [result.webhook_id]: result.webhook_secret }))
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
            setWebhookSecrets((prev) => ({ ...prev, [secretId]: result.webhook_secret }))
            toast.success("Webhook secret rotated")
        } catch {
            toast.error("Failed to rotate webhook secret")
        } finally {
            setRotatingWebhookId(null)
        }
    }

    const handleDeleteInbound = async (webhookId: string) => {
        try {
            setDeletingWebhookId(webhookId)
            await deleteInboundWebhook.mutateAsync({ webhookId })
            setWebhookSecrets((prev) => {
                const next = { ...prev }
                delete next[webhookId]
                return next
            })
            setLabelDrafts((prev) => {
                const next = { ...prev }
                delete next[webhookId]
                return next
            })
            toast.success("Webhook deleted")
        } catch (error) {
            const message = error instanceof Error ? error.message : null
            toast.error(message || "Failed to delete webhook")
        } finally {
            setDeletingWebhookId(null)
        }
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
            const formId = testFormId.trim()
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
            if (fieldPasteWebhookId) {
                payload.webhook_id = fieldPasteWebhookId
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
                outbound_webhook_url: outboundUrl.trim() || null,
                outbound_enabled: outboundEnabled,
                send_hashed_pii: sendHashedPii,
                event_mapping: eventMapping,
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
            if (selectedOutboundStage) {
                payload.stage_key = selectedOutboundStage
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
        setEventMapping((current) =>
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

    if (isLoading) {
        return (
            <div className={containerClass}>
                {showHeading && (
                    <h2 className="mb-4 text-lg font-semibold">Zapier Webhook</h2>
                )}
                <div className="flex items-center justify-center py-8">
                    <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                </div>
            </div>
        )
    }

    return (
        <div className={containerClass}>
            {showHeading && (
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
                    {!metaFormsLoading && zapierForms.length > 0 && (
                        <Alert>
                            <AlertTitle>Zapier form detected</AlertTitle>
                            <AlertDescription>
                                We detected {zapierForms.length} Zapier form
                                {zapierForms.length === 1 ? "" : "s"}. Map fields so inbound Zapier leads can
                                convert automatically.{" "}
                                <Link href={mappingHref} className="text-primary underline">
                                    Manage mapping
                                </Link>
                            </AlertDescription>
                        </Alert>
                    )}

                    <Card>
                        <CardHeader className="pb-3">
                            <div className="flex items-center gap-3">
                                <div className="flex size-10 items-center justify-center rounded-lg bg-indigo-100 dark:bg-indigo-900">
                                    <LinkIcon className="size-5 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
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
                                        onClick={handleCreateInbound}
                                        disabled={createInboundWebhook.isPending}
                                    >
                                        {createInboundWebhook.isPending ? (
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

                                {!settings?.inbound_webhooks?.length ? (
                                    <p className="text-xs text-muted-foreground">No inbound webhooks configured yet.</p>
                                ) : (
                                    <div className="space-y-4">
                                        {settings.inbound_webhooks.map((webhook) => {
                                            const secret = webhookSecrets[webhook.webhook_id]
                                            const labelValue = labelDrafts[webhook.webhook_id] ?? ""
                                            const canDelete = settings.inbound_webhooks.length > 1
                                            return (
                                            <div key={webhook.webhook_id} className="space-y-3 rounded-md border p-4">
                                        <div className={`flex flex-col gap-3 ${isDialog ? "" : "md:flex-row md:items-start md:justify-between"}`}>
                                            <div className="flex-1 space-y-2">
                                                <Label>Label</Label>
                                                <Input
                                                    value={labelValue}
                                                    onChange={(event) =>
                                                        setLabelDrafts((prev) => ({
                                                            ...prev,
                                                            [webhook.webhook_id]: event.target.value,
                                                        }))
                                                    }
                                                    onBlur={() => handleLabelBlur(webhook.webhook_id)}
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
                                                    onCheckedChange={(checked) =>
                                                        handleToggleInbound(webhook.webhook_id, checked)
                                                    }
                                                    aria-label={`Toggle ${webhook.webhook_id}`}
                                                />
                                            </div>
                                        </div>

                                        <div className="space-y-2">
                                            <Label>Webhook URL</Label>
                                            <div className="flex min-w-0 gap-2">
                                                <div
                                                    className="flex h-9 min-w-0 flex-1 items-center rounded-md border border-input bg-transparent px-3 py-1 text-xs font-mono shadow-xs dark:bg-input/30"
                                                    role="textbox"
                                                    aria-readonly="true"
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
                                                    onClick={() => handleRotateInbound(webhook.webhook_id)}
                                                    disabled={
                                                        rotateInboundWebhook.isPending &&
                                                        rotatingWebhookId === webhook.webhook_id
                                                    }
                                                >
                                                    {rotateInboundWebhook.isPending &&
                                                    rotatingWebhookId === webhook.webhook_id ? (
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
                                                        disabled={!canDelete || deletingWebhookId === webhook.webhook_id}
                                                        render={
                                                            <Button
                                                                variant="ghost"
                                                                className="text-destructive hover:text-destructive"
                                                                disabled={!canDelete || deletingWebhookId === webhook.webhook_id}
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
                                                                onClick={() => handleDeleteInbound(webhook.webhook_id)}
                                                                disabled={!canDelete || deletingWebhookId === webhook.webhook_id}
                                                            >
                                                                {deletingWebhookId === webhook.webhook_id ? "Deleting…" : "Delete"}
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
                                                        New Webhook Secret (copy now — shown once):
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
                                        })}
                                    </div>
                                )}
                            </div>

                    <div className="space-y-4 border-t pt-4">
                        <div className="space-y-2">
                            <Label>Paste Zapier Field List</Label>
                            <p className="text-xs text-muted-foreground">
                                Paste the field list from Zapier (either the token lines or the sample field/value list).
                                We’ll extract keys, build a form schema, and open the mapping suggestions.
                            </p>
                        </div>

                        {settings?.inbound_webhooks?.length ? (
                            <div className="space-y-2">
                                <Label>Webhook</Label>
                                <Select value={fieldPasteWebhookId} onValueChange={(value) => setFieldPasteWebhookId(value ?? "")}>
                                    <SelectTrigger className={isDialog ? "w-full" : "w-full md:w-72"} aria-label="Select webhook">
                                        <SelectValue placeholder="Select webhook" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {settings.inbound_webhooks.map((webhook) => (
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
                            onChange={(event) => setFieldPaste(event.target.value)}
                            placeholder={'Paste lines like {{=gives["312067957"]["full_name"]}} or "Full Name: Jane Doe"'}
                            rows={6}
                            name="zapier-field-paste"
                        />
                        <div className="flex flex-wrap items-center gap-2">
                            <Button
                                variant="outline"
                                onClick={handleFieldPaste}
                                disabled={parseFieldPaste.isPending}
                            >
                                {parseFieldPaste.isPending ? (
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
                            <Button variant="ghost" onClick={handleFieldPasteClear}>
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

                    <div className="space-y-3 border-t pt-4">
                        <div className="space-y-2">
                            <Label>Test Lead</Label>
                            <Input
                                placeholder="Zapier Form ID (optional if only one active Zapier form exists)"
                                value={testFormId}
                                onChange={(event) => setTestFormId(event.target.value)}
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
                            onClick={handleTestLead}
                            disabled={sendTestLead.isPending}
                        >
                            {sendTestLead.isPending ? (
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

                    <div className="space-y-4 border-t pt-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium">Outbound Stage Events</p>
                                <p className="text-xs text-muted-foreground">
                                    Send surrogate stage changes to Zapier for Meta Conversions.
                                </p>
                            </div>
                            <Switch
                                checked={outboundEnabled}
                                onCheckedChange={setOutboundEnabled}
                                aria-label="Enable outbound stage events"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Outbound Webhook URL</Label>
                            <Input
                                value={outboundUrl}
                                onChange={(event) => setOutboundUrl(event.target.value)}
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
                                onChange={(event) => setOutboundSecret(event.target.value)}
                                placeholder={settings?.outbound_secret_configured ? "•••••••• (set)" : "Enter secret"}
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
                                checked={sendHashedPii}
                                onCheckedChange={setSendHashedPii}
                                aria-label="Include hashed PII"
                            />
                        </div>

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
                                Set each stage bucket for Meta conversion status mapping. Dedupe runs once per lead per bucket.
                            </p>
                            <div className="space-y-2">
                                {eventMapping.map((item, index) => (
                                    <div
                                        key={item.stage_key}
                                        className={`flex flex-col gap-2 rounded-md border p-3 ${isDialog ? "" : "md:flex-row md:items-center"}`}
                                    >
                                        <div className="w-32 text-sm font-medium">
                                            {getStageKeyLabel(item.stage_key)}
                                        </div>
                                        <Select
                                            value={isZapierStageBucket(item.bucket) ? item.bucket : "__none__"}
                                            onValueChange={(value) => {
                                                const next = [...eventMapping]
                                                const existing = next[index]
                                                if (!existing) return
                                                if (value === "__none__") {
                                                    next[index] = {
                                                        ...existing,
                                                        bucket: null,
                                                        enabled: recommendedBucketByStage[existing.stage_key]
                                                            ? false
                                                            : existing.enabled,
                                                    }
                                                } else if (isZapierStageBucket(value)) {
                                                    next[index] = {
                                                        ...existing,
                                                        bucket: value,
                                                        event_name: ZAPIER_BUCKET_EVENT_NAME[value],
                                                        enabled: true,
                                                    }
                                                }
                                                setEventMapping(next)
                                            }}
                                        >
                                            <SelectTrigger className={isDialog ? "w-full" : "w-full md:w-44"}>
                                                <SelectValue placeholder="Bucket" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="__none__">Not Tracked</SelectItem>
                                                {ZAPIER_BUCKET_OPTIONS.map((option) => (
                                                    <SelectItem key={option.value} value={option.value}>
                                                        {option.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                        <Input
                                            value={item.event_name}
                                            onChange={(event) => {
                                                const next = [...eventMapping]
                                                const existing = next[index]
                                                if (!existing) return
                                                next[index] = { ...existing, event_name: event.target.value }
                                                setEventMapping(next)
                                            }}
                                            placeholder="Event name"
                                            name={`zapier-event-${item.stage_key}`}
                                            autoComplete="off"
                                            disabled={isZapierStageBucket(item.bucket)}
                                        />
                                        <div className="flex items-center gap-2">
                                            <Switch
                                                checked={item.enabled}
                                                onCheckedChange={(checked) => {
                                                    const next = [...eventMapping]
                                                    const existing = next[index]
                                                    if (!existing) return
                                                    next[index] = { ...existing, enabled: checked }
                                                    setEventMapping(next)
                                                }}
                                                aria-label={`Enable ${item.stage_key} event`}
                                            />
                                            <span className="text-xs text-muted-foreground">Enabled</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className={`flex flex-col gap-2 ${isDialog ? "" : "md:flex-row md:items-center"}`}>
                            <Button onClick={handleSaveOutbound} disabled={updateOutbound.isPending}>
                                {updateOutbound.isPending ? (
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
                                        onChange={(event) => setOutboundTestLeadId(event.target.value)}
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
                                    value={selectedOutboundStage}
                                    onValueChange={(value) => setSelectedOutboundStage(value ?? '')}
                                >
                                    <SelectTrigger className={isDialog ? "w-full" : "w-full md:w-56"} aria-label="Select stage">
                                        <SelectValue placeholder="Select stage" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {eventMapping.map((item) => (
                                            <SelectItem key={item.stage_key} value={item.stage_key}>
                                                {getStageKeyLabel(item.stage_key)}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <Button
                                    variant="outline"
                                    onClick={handleOutboundTest}
                                    disabled={sendOutboundTest.isPending || !outboundEnabled}
                                    className={isDialog ? "w-full" : undefined}
                                >
                                    {sendOutboundTest.isPending ? (
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
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
                <TabsContent value="monitoring">
                    <ZapierMonitoringSection variant={variant} />
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
    const recommendedBucketByStage = buildRecommendedBucketByStage(pipelines)
    const stageLabelByKey = buildStageLabelByKey(pipelines)
    const getStageKeyLabel = (stageKey: string) => stageLabelByKey[stageKey] ?? "Unknown stage"
    const { data: settings, isLoading } = useMetaCrmDatasetSettings()
    const updateSettings = useUpdateMetaCrmDatasetSettings()
    const sendOutboundTest = useMetaCrmDatasetOutboundTest()
    const isDialog = variant === "dialog"
    const [metaForm, setMetaForm] = useState<MetaCrmDatasetFormState>({
        datasetId: "",
        accessToken: "",
        enabled: false,
        crmName: "Surrogacy Force CRM",
        sendHashedPii: false,
        eventMapping: [],
        testEventCode: "",
        selectedStage: "",
        outboundTestLeadId: "",
        outboundTestFbc: "",
    })

    useEffect(() => {
        if (!settings) return
        const mergedEventMapping = mergeEventMappingWithPipelineStages(
            settings.event_mapping || [],
            pipelines,
        )
        setMetaForm((current) => ({
            ...current,
            datasetId: settings.dataset_id || "",
            accessToken: "",
            enabled: Boolean(settings.enabled),
            crmName: settings.crm_name || "Surrogacy Force CRM",
            sendHashedPii: Boolean(settings.send_hashed_pii),
            eventMapping: mergedEventMapping,
            testEventCode: settings.test_event_code || "",
            selectedStage:
                current.selectedStage
                && mergedEventMapping.some((item) => item.stage_key === current.selectedStage)
                    ? current.selectedStage
                    : mergedEventMapping[0]?.stage_key || "",
        }))
    }, [settings, pipelines])

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
                            placeholder={settings?.access_token_configured ? "•••••••• (set)" : "Enter access token"}
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
                        {metaForm.eventMapping.map((item, index) => (
                            <div
                                key={item.stage_key}
                                className={`flex flex-col gap-2 rounded-md border p-3 ${isDialog ? "" : "md:flex-row md:items-center"}`}
                            >
                                <div className="w-32 text-sm font-medium">
                                    {getStageKeyLabel(item.stage_key)}
                                </div>
                                <Select
                                    value={isZapierStageBucket(item.bucket) ? item.bucket : "__none__"}
                                    onValueChange={(value) => {
                                        updateEventMapping((current) => {
                                            const next = [...current]
                                            const existing = next[index]
                                            if (!existing) return current
                                            if (value === "__none__") {
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
                                        <SelectValue placeholder="Bucket" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="__none__">Not Tracked</SelectItem>
                                        {ZAPIER_BUCKET_OPTIONS.map((option) => (
                                            <SelectItem key={option.value} value={option.value}>
                                                {option.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
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
                                    disabled={isZapierStageBucket(item.bucket)}
                                />
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
                        ))}
                    </div>
                </div>

                <div className={`flex flex-col gap-2 ${isDialog ? "" : "md:flex-row md:items-start"}`}>
                    <Button onClick={handleSave} disabled={updateSettings.isPending}>
                        {updateSettings.isPending ? (
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
                                    <SelectValue placeholder="Select stage" />
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
                                onClick={handleOutboundTest}
                                disabled={sendOutboundTest.isPending}
                                className={isDialog ? "w-full" : undefined}
                            >
                                {sendOutboundTest.isPending ? (
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
            </CardContent>
        </Card>
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

function MetaConfigurationSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
    const { data: connections = [], isLoading: connectionsLoading } = useMetaConnections()
    const connectUrlMutation = useMetaConnectUrl()
    const disconnectMutation = useDisconnectMetaConnection()

    const { data: adAccounts = [], isLoading: adAccountsLoading } = useAdminMetaAdAccounts()
    const updateAccountMutation = useUpdateMetaAdAccount()
    const deleteAccountMutation = useDeleteMetaAdAccount()

    const [editAccount, setEditAccount] = useState<MetaAdAccount | null>(null)
    const [disconnectConnectionId, setDisconnectConnectionId] = useState<string | null>(null)
    const [accountFormError, setAccountFormError] = useState("")
    const [adAccountName, setAdAccountName] = useState("")
    const [pixelId, setPixelId] = useState("")
    const [capiEnabled, setCapiEnabled] = useState(false)
    const [accountActive, setAccountActive] = useState(true)

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
        setEditAccount(account)
        setAdAccountName(account.ad_account_name || "")
        setPixelId(account.pixel_id || "")
        setCapiEnabled(account.capi_enabled)
        setAccountActive(account.is_active)
        setAccountFormError("")
    }

    const handleUpdateAdAccount = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!editAccount) return
        setAccountFormError("")

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
            setEditAccount(null)
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : "Failed to update ad account"
            setAccountFormError(message)
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
            <div className={containerClass}>
                {showHeading && (
                    <h2 className="mb-4 text-lg font-semibold">Meta Integration</h2>
                )}
                <div className="flex items-center justify-center py-8">
                    <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                </div>
            </div>
        )
    }

    return (
        <div className={containerClass}>
            {showHeading && (
                <>
                    <h2 className="mb-4 text-lg font-semibold">Meta Integration</h2>
                    <p className="mb-4 text-sm text-muted-foreground">
                        Connect Meta accounts to sync lead forms, and configure direct CRM dataset delivery for Meta conversion reporting.
                    </p>
                </>
            )}
            <Tabs defaultValue="configuration" className="space-y-4">
                <TabsList variant="line">
                    <TabsTrigger value="configuration">Configuration</TabsTrigger>
                    <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
                </TabsList>

                <TabsContent value="configuration" className="space-y-4">
                    <MetaCrmDatasetSection variant={variant} />

                    <div className="space-y-4 border-t pt-4">
                        <div className="space-y-2">
                            <h3 className="text-base font-semibold">Legacy app-based Meta setup</h3>
                            <p className="text-sm text-muted-foreground">
                                These OAuth connections and ad-account CAPI settings are the legacy app-based integration path.
                            </p>
                        </div>

                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
                                <div>
                                    <CardTitle className="text-base">Legacy Connections</CardTitle>
                                    <CardDescription className="text-xs">
                                        Connect Meta accounts and manage assets for lead ads through the legacy app-based flow.
                                    </CardDescription>
                                </div>
                                <Button size="sm" onClick={handleConnectWithFacebook} disabled={connectUrlMutation.isPending}>
                                    {connectUrlMutation.isPending ? (
                                        <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                    ) : (
                                        <FacebookIcon className="mr-2 size-4" aria-hidden="true" />
                                    )}
                                    Connect with Facebook
                                </Button>
                            </CardHeader>
                            <CardContent>
                                {connections.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">No legacy Meta connections yet. Connect with Facebook to get started.</p>
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
                                                            onClick={() => setDisconnectConnectionId(connection.id)}
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
                                                            onClick={() => openEditAccount(account)}
                                                            aria-label="Edit ad account"
                                                        >
                                                            <PencilIcon className="size-4" aria-hidden="true" />
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => handleDeleteAdAccount(account.id)}
                                                            disabled={deleteAccountMutation.isPending}
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

                        <div className="flex justify-end">
                            <Button render={<Link href="/settings/integrations/meta/forms" />} variant="outline" size="sm">
                                Manage lead forms
                            </Button>
                        </div>
                    </div>
                </TabsContent>

                <TabsContent value="monitoring">
                    <MetaCrmDatasetMonitoringSection variant={variant} />
                </TabsContent>
            </Tabs>

            {/* Edit Ad Account Dialog */}
            <Dialog open={!!editAccount} onOpenChange={(open) => !open && setEditAccount(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Edit Ad Account</DialogTitle>
                        <DialogDescription>Update CAPI and account settings.</DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleUpdateAdAccount}>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <Label htmlFor="adAccountName">Ad account name</Label>
                                <Input
                                    id="adAccountName"
                                    value={adAccountName}
                                    onChange={(e) => setAdAccountName(e.target.value)}
                                    name="ad-account-name"
                                    autoComplete="off"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="pixelId">Pixel ID</Label>
                                <Input
                                    id="pixelId"
                                    value={pixelId}
                                    onChange={(e) => setPixelId(e.target.value)}
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
                                    checked={capiEnabled}
                                    onCheckedChange={(checked) => setCapiEnabled(!!checked)}
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
                                    checked={accountActive}
                                    onCheckedChange={(checked) => setAccountActive(!!checked)}
                                    id="accountActive"
                                />
                            </div>
                            {accountFormError && (
                                <p className="text-sm text-destructive">{accountFormError}</p>
                            )}
                        </div>
                        <div className="flex justify-end gap-2">
                            <Button variant="outline" onClick={() => setEditAccount(null)} type="button">
                                Cancel
                            </Button>
                            <Button type="submit" disabled={updateAccountMutation.isPending}>
                                {updateAccountMutation.isPending ? (
                                    <>
                                        <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
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

            {/* Disconnect Confirmation Dialog */}
            <AlertDialog open={!!disconnectConnectionId} onOpenChange={(open) => !open && setDisconnectConnectionId(null)}>
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
                            onClick={() => disconnectConnectionId && handleDisconnect(disconnectConnectionId)}
                        >
                            Disconnect
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}

export default function IntegrationsPage() {
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"
    const { data: effectivePermissions } = useEffectivePermissions(user?.user_id ?? null)
    const canManageOrganizationIntegrations =
        isDeveloper || (effectivePermissions?.permissions ?? []).includes("manage_integrations")
    const { data: healthData, isLoading, refetch, isFetching } = useIntegrationHealth()
    const { data: userIntegrations } = useUserIntegrations()
    const { data: googleCalendarStatus } = useGoogleCalendarStatus(true)
    const { data: aiSettings, isLoading: aiSettingsLoading } = useAISettings()
    const { data: resendSettings, isLoading: resendSettingsLoading } = useResendSettings()
    const { data: zapierSettings, isLoading: zapierSettingsLoading } = useZapierSettings()
    const { data: pipelines } = usePipelines()
    const { data: metaFormsData } = useMetaForms()
    const { data: metaConnectionsData } = useMetaConnections()
    const { data: metaAdAccountsData } = useAdminMetaAdAccounts()
    const { data: metaCrmDatasetSettings, isLoading: metaCrmDatasetSettingsLoading } = useMetaCrmDatasetSettings()
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
    const mergedZapierEventMapping = useMemo(
        () => mergeEventMappingWithPipelineStages(zapierSettings?.event_mapping, pipelines),
        [zapierSettings?.event_mapping, pipelines],
    )
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
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Integrations</h1>
                    <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
                        <RefreshCwIcon className={`mr-2 size-4 ${isFetching ? "animate-spin" : ""} motion-reduce:animate-none`} aria-hidden="true" />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-6 p-6">

                {/* Personal Integrations */}
                <div>
                    <h2 className="mb-4 text-lg font-semibold">Personal Integrations</h2>
                    <p className="mb-4 text-sm text-muted-foreground">Connect your personal accounts to enable features like Zoom appointments and email sending.</p>
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                        {/* Zoom */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900">
                                        <VideoIcon className="size-5 text-blue-600 dark:text-blue-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Zoom</CardTitle>
                                        <CardDescription className="text-xs">Video appointments</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {zoomIntegration ? (
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="default" className="bg-green-600">
                                                <CheckCircleIcon className="mr-1 size-3" aria-hidden="true" />
                                                Connected
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-muted-foreground">{zoomIntegration.account_email}</p>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full"
                                            onClick={() => disconnectIntegration.mutate('zoom')}
                                            disabled={disconnectIntegration.isPending}
                                        >
                                            <UnlinkIcon className="mr-2 size-3" aria-hidden="true" />
                                            Disconnect
                                        </Button>
                                    </div>
                                ) : (
                                    <Button
                                        className="w-full"
                                        onClick={() => connectZoom.mutate()}
                                        disabled={connectZoom.isPending}
                                    >
                                        {connectZoom.isPending ? (
                                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        ) : (
                                            <LinkIcon className="mr-2 size-4" aria-hidden="true" />
                                        )}
                                        Connect Zoom
                                    </Button>
                                )}
                            </CardContent>
                        </Card>

                        {/* Gmail */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-red-100 dark:bg-red-900">
                                        <MailIcon className="size-5 text-red-600 dark:text-red-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Gmail</CardTitle>
                                        <CardDescription className="text-xs">Email sending</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {gmailIntegration ? (
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="default" className="bg-green-600">
                                                <CheckCircleIcon className="mr-1 size-3" aria-hidden="true" />
                                                Connected
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-muted-foreground">{gmailIntegration.account_email}</p>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full"
                                            onClick={() => disconnectIntegration.mutate('gmail')}
                                            disabled={disconnectIntegration.isPending}
                                        >
                                            <UnlinkIcon className="mr-2 size-3" aria-hidden="true" />
                                            Disconnect
                                        </Button>
                                    </div>
                                ) : (
                                    <Button
                                        className="w-full"
                                        onClick={() => connectGmail.mutate()}
                                        disabled={connectGmail.isPending}
                                    >
                                        {connectGmail.isPending ? (
                                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        ) : (
                                            <LinkIcon className="mr-2 size-4" aria-hidden="true" />
                                        )}
                                        Connect Gmail
                                    </Button>
                                )}
                            </CardContent>
                        </Card>

                        {/* Google Calendar + Meeting */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900">
                                        <CalendarIcon className="size-5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Google Calendar + Meeting</CardTitle>
                                        <CardDescription className="text-xs">Two-way calendar sync + meeting links</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {googleCalendarIntegration ? (
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="default" className="bg-green-600">
                                                <CheckCircleIcon className="mr-1 size-3" aria-hidden="true" />
                                                Connected
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-muted-foreground">{googleCalendarIntegration.account_email}</p>
                                        <div className="rounded-md border border-border/60 bg-muted/40 px-3 py-2">
                                            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                                                Last Sync
                                            </p>
                                            <p className="text-xs font-medium">
                                                {googleLastSyncLabel}
                                            </p>
                                            {googleLastSyncAt ? (
                                                <p className="text-[11px] text-muted-foreground">
                                                    {new Date(googleLastSyncAt).toLocaleString()}
                                                </p>
                                            ) : null}
                                        </div>
                                        <Button
                                            variant="secondary"
                                            size="sm"
                                            className="w-full"
                                            onClick={() => syncGoogleCalendarNow.mutate()}
                                            disabled={syncGoogleCalendarNow.isPending}
                                        >
                                            {syncGoogleCalendarNow.isPending ? (
                                                <Loader2Icon className="mr-2 size-3 animate-spin motion-reduce:animate-none" aria-hidden="true" />
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
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full"
                                            onClick={() => disconnectIntegration.mutate('google_calendar')}
                                            disabled={disconnectIntegration.isPending}
                                        >
                                            <UnlinkIcon className="mr-2 size-3" aria-hidden="true" />
                                            Disconnect
                                        </Button>
                                    </div>
                                ) : (
                                    <Button
                                        className="w-full"
                                        onClick={() => connectGoogleCalendar.mutate()}
                                        disabled={connectGoogleCalendar.isPending}
                                    >
                                        {connectGoogleCalendar.isPending ? (
                                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        ) : (
                                            <LinkIcon className="mr-2 size-4" aria-hidden="true" />
                                        )}
                                        Connect Google Calendar
                                    </Button>
                                )}
                            </CardContent>
                        </Card>

                    </div>
                </div>

                {/* Organization Integrations */}
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
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                        {/* AI */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900">
                                        <SparklesIcon className="size-5 text-purple-600 dark:text-purple-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">AI Assistant</CardTitle>
                                        <CardDescription className="text-xs">Copilot, summaries, and AI workflows</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {aiSettingsLoading ? (
                                    <div className="flex items-center justify-center py-6">
                                        <Loader2Icon className="size-5 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        <Badge variant={aiStatusVariant} className="w-fit flex items-center gap-1">
                                            <AiStatusIcon className="size-3" aria-hidden="true" />
                                            {aiStatusLabel}
                                        </Badge>
                                        <p className="text-xs text-muted-foreground">
                                            {aiSettings?.provider ? `Provider: ${aiProviderLabel}` : "No provider configured"}
                                        </p>
                                        <Button
                                            variant="outline"
                                            className="w-full"
                                            onClick={() => setAiDialogOpen(true)}
                                            disabled={!canManageOrganizationIntegrations}
                                        >
                                            {canManageOrganizationIntegrations ? "Configure AI" : "Admin access required"}
                                        </Button>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Email */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-teal-100 dark:bg-teal-900">
                                        <SendIcon className="size-5 text-teal-600 dark:text-teal-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Email Delivery</CardTitle>
                                        <CardDescription className="text-xs">Campaign + transactional sending</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {resendSettingsLoading ? (
                                    <div className="flex items-center justify-center py-6">
                                        <Loader2Icon className="size-5 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        <Badge variant={emailStatusVariant} className="w-fit flex items-center gap-1">
                                            <EmailStatusIcon className="size-3" aria-hidden="true" />
                                            {emailStatusLabel}
                                        </Badge>
                                        <p className="text-xs text-muted-foreground">
                                            {emailConfigured ? `${emailProviderLabel} · ${emailDetail}` : "Choose a provider to start sending"}
                                        </p>
                                        <Button
                                            variant="outline"
                                            className="w-full"
                                            onClick={() => setEmailDialogOpen(true)}
                                            disabled={!canManageOrganizationIntegrations}
                                        >
                                            {canManageOrganizationIntegrations ? "Configure Email" : "Admin access required"}
                                        </Button>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Zapier */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-indigo-100 dark:bg-indigo-900">
                                        <LinkIcon className="size-5 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Zapier</CardTitle>
                                        <CardDescription className="text-xs">Inbound leads + stage event delivery</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {zapierSettingsLoading ? (
                                    <div className="flex items-center justify-center py-6">
                                        <Loader2Icon className="size-5 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        <Badge variant={zapierStatusVariant} className="w-fit flex items-center gap-1">
                                            <ZapierStatusIcon className="size-3" aria-hidden="true" />
                                            {zapierStatusLabel}
                                        </Badge>
                                        <Badge
                                            data-testid="zapier-mapping-health-card-badge"
                                            variant={zapierMappingBadgeVariant}
                                            className="w-fit"
                                        >
                                            {zapierMappingBadgeLabel}
                                        </Badge>
                                        <p className="text-xs text-muted-foreground">
                                            {zapierDetail}
                                        </p>
                                        <p className="text-xs text-muted-foreground">{zapierMappingDetail}</p>
                                        <Button
                                            variant="outline"
                                            className="w-full"
                                            onClick={() => setZapierDialogOpen(true)}
                                            disabled={!canManageOrganizationIntegrations}
                                        >
                                            {canManageOrganizationIntegrations ? "Configure Zapier" : "Admin access required"}
                                        </Button>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Meta Lead Ads */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900">
                                        <FacebookIcon className="size-5 text-blue-600 dark:text-blue-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Meta Lead Ads</CardTitle>
                                        <CardDescription className="text-xs">Facebook/Instagram lead capture + CAPI</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {metaCrmDatasetSettingsLoading ? (
                                    <div className="flex items-center justify-center py-6">
                                        <Loader2Icon className="size-5 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        <Badge variant={metaStatusVariant} className="w-fit flex items-center gap-1">
                                            <MetaStatusIcon className="size-3" aria-hidden="true" />
                                            {metaStatusLabel}
                                        </Badge>
                                        <p className="text-xs text-muted-foreground">
                                            {metaDetail}
                                        </p>
                                        <Button
                                            variant="outline"
                                            className="w-full"
                                            onClick={() => setMetaDialogOpen(true)}
                                            disabled={!canManageOrganizationIntegrations}
                                        >
                                            {canManageOrganizationIntegrations ? "Configure Meta" : "Admin access required"}
                                        </Button>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>

                <Dialog
                    open={canManageOrganizationIntegrations && aiDialogOpen}
                    onOpenChange={(open) => {
                        if (!canManageOrganizationIntegrations) return
                        setAiDialogOpen(open)
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
                        setEmailDialogOpen(open)
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
                        setZapierDialogOpen(open)
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
                        setMetaDialogOpen(open)
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

                {/* System Integrations Section */}
                <div className="border-t pt-6">
                    <h2 className="mb-4 text-lg font-semibold">System Integrations</h2>
                    <p className="mb-4 text-sm text-muted-foreground">Organization-level integrations managed by administrators.</p>
                </div>
                {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2Icon className="size-8 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                    </div>
                ) : (healthData?.length ?? 0) === 0 ? (
                    <Card>
                        <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                            <ServerIcon className="mb-4 size-12" aria-hidden="true" />
                            <p className="text-lg font-medium">No integrations configured</p>
                            <p className="text-sm">Add integrations to see their health status here</p>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {healthData?.map((integration) => {
                            const typeConfig = integrationTypeConfig[integration.integration_type] || {
                                icon: ServerIcon,
                                label: integration.integration_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                                description: "Custom integration",
                            }
                            const status = statusConfig[integration.status] || statusConfig.error
                            const configStatus = configStatusLabels[integration.config_status]
                                ?? configStatusLabels.configured
                                ?? { label: "Configured", variant: "default" as const }
                            const Icon = typeConfig.icon
                            const StatusIcon = status.icon

                            // Compute integration-specific metrics
                            let metricsLabel: string | null = null
                            if (integration.integration_type === "meta_leads") {
                                metricsLabel = `${metaFormsCount} form${metaFormsCount === 1 ? "" : "s"} synced · ${metaMappedFormsCount} mapped`
                            } else if (integration.integration_type === "meta_capi") {
                                const capiEnabledCount = metaAdAccounts.filter(a => a.capi_enabled).length
                                metricsLabel = `${capiEnabledCount} ad account${capiEnabledCount === 1 ? "" : "s"} with CAPI enabled`
                            } else if (integration.integration_type === "zapier") {
                                const outboundStatus = zapierSettings?.outbound_enabled ? "enabled" : "disabled"
                                metricsLabel = `${inboundWebhooks.length} inbound webhook${inboundWebhooks.length === 1 ? "" : "s"} · Outbound ${outboundStatus}`
                            }

                            return (
                                <Card key={integration.id} className="relative overflow-hidden">
                                    {/* Status indicator bar */}
                                    <div className={`absolute left-0 top-0 h-full w-1 ${integration.status === 'healthy' ? 'bg-green-500' :
                                        integration.status === 'degraded' ? 'bg-yellow-500' :
                                            'bg-red-500'
                                        }`} />

                                    <CardHeader className="pb-3">
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className="flex size-10 items-center justify-center rounded-lg bg-muted">
                                                    <Icon className="size-5" aria-hidden="true" />
                                                </div>
                                                <div>
                                                    <CardTitle className="text-base">{typeConfig.label}</CardTitle>
                                                    {integration.integration_key && (
                                                        <p className="text-xs text-muted-foreground">
                                                            Page: {integration.integration_key}
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                            <Badge variant={status.badge} className="flex items-center gap-1">
                                                <StatusIcon className="size-3" aria-hidden="true" />
                                                {status.label}
                                            </Badge>
                                        </div>
                                        <CardDescription className="mt-2 text-xs">
                                            {typeConfig.description}
                                        </CardDescription>
                                    </CardHeader>

                                    <CardContent className="space-y-3">
                                        {/* Integration-specific metrics */}
                                        {metricsLabel && (
                                            <div className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
                                                <ActivityIcon className="size-3.5 shrink-0" aria-hidden="true" />
                                                {metricsLabel}
                                            </div>
                                        )}

                                        {/* Config Status */}
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-muted-foreground">Configuration</span>
                                            <Badge variant={configStatus.variant} className="text-xs">
                                                <KeyIcon className="mr-1 size-3" aria-hidden="true" />
                                                {configStatus.label}
                                            </Badge>
                                        </div>

                                        {/* Success/Error timestamps */}
                                        <div className="space-y-1 text-xs">
                                            {integration.last_success_at && (
                                                <div className="flex items-center justify-between text-muted-foreground">
                                                    <span>Last success</span>
                                                    <span className="text-green-600">
                                                        {formatRelativeTime(integration.last_success_at, "Never")}
                                                    </span>
                                                </div>
                                            )}
                                            {integration.last_error_at && (
                                                <div className="flex items-center justify-between text-muted-foreground">
                                                    <span>Last error</span>
                                                    <span className="text-red-600">
                                                        {formatRelativeTime(integration.last_error_at, "Never")}
                                                    </span>
                                                </div>
                                            )}
                                        </div>

                                        {/* Error count */}
                                        {integration.error_count_24h > 0 && (
                                            <div className="flex items-center justify-between rounded-md bg-red-100 px-3 py-2 text-sm dark:bg-red-900/30">
                                                <span className="text-red-700 dark:text-red-300">Errors (24h)</span>
                                                <span className="font-semibold text-red-700 dark:text-red-300">
                                                    {integration.error_count_24h}
                                                </span>
                                            </div>
                                        )}

                                        {/* Last error message */}
                                        {integration.last_error && (
                                            <div className="rounded-md bg-muted p-2">
                                                <p className="text-xs text-muted-foreground line-clamp-2">
                                                    {integration.last_error}
                                                </p>
                                            </div>
                                        )}

                                        {/* Action buttons */}
                                        {integration.config_status !== "configured" && (
                                            !canManageOrganizationIntegrations ? (
                                                <p className="text-xs text-muted-foreground text-center">
                                                    Admin access required to configure
                                                </p>
                                            ) : integration.integration_type === "meta_leads" || integration.integration_type === "meta_capi" ? (
                                                <Button
                                                    render={<Link href="/settings/integrations/meta" />}
                                                    variant="outline"
                                                    size="sm"
                                                    className="w-full"
                                                >
                                                    <KeyIcon className="mr-2 size-3" aria-hidden="true" />
                                                    {integration.config_status === "expired_token"
                                                        ? "Refresh Token"
                                                        : "Configure"
                                                    }
                                                </Button>
                                            ) : (
                                                <p className="text-xs text-muted-foreground text-center">
                                                    Configure via CLI
                                                </p>
                                            )
                                        )}
                                    </CardContent>
                                </Card>
                            )
                        })}
                    </div>
                )}

                {/* Help section */}
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
            </div>
        </div>
    )
}
