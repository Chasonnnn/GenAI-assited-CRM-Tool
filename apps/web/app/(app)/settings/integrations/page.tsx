"use client"

import { useState, useRef, type ReactNode } from "react"
import Link from "@/components/app-link"
import { PageHeader } from "@/components/page-header"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { CheckCircleIcon, AlertTriangleIcon, XCircleIcon, MegaphoneIcon, ZapIcon, ServerIcon, LinkIcon, RefreshCwIcon, VideoIcon, MailIcon, CalendarIcon, Loader2Icon, SparklesIcon, SendIcon, MessageSquareTextIcon, ActivityIcon, KeyIcon } from "lucide-react"
import { useIntegrationHealth } from "@/lib/hooks/use-ops"
import { GoogleCalendarBindingSettings } from "@/components/appointments/GoogleCalendarBindingSettings"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { usePipelines } from "@/lib/hooks/use-pipelines"
import { useUserIntegrations, useGoogleCalendarStatus, useConnectZoom, useConnectGmail, useConnectGoogleCalendar, useSyncGoogleCalendarNow, useDisconnectIntegration } from "@/lib/hooks/use-user-integrations"
import { useAISettings } from "@/lib/hooks/use-ai"
import { useResendSettings } from "@/lib/hooks/use-resend"
import { useTwilioSettings, useTwilioReadiness } from "@/lib/hooks/use-twilio"
import { useZapierSettings } from "@/lib/hooks/use-zapier"
import { useMetaForms } from "@/lib/hooks/use-meta-forms"
import { useMetaConnections } from "@/lib/hooks/use-meta-oauth"
import { useAdminMetaAdAccounts } from "@/lib/hooks/use-admin-meta"
import { useMetaCrmDatasetSettings } from "@/lib/hooks/use-meta-crm-dataset"
import type { MetaAdAccount } from "@/lib/api/admin-meta"
import { formatRelativeTime, formatDateTime } from "@/lib/formatters"
import { toast } from "@/components/ui/toast"
import type { IntegrationStatus, GoogleCalendarStatusResponse } from "@/lib/api/integrations"
import type { IntegrationHealth } from "@/lib/api/ops"
import type { TwilioReadinessStatus } from "@/lib/api/twilio"
import type { Pipeline } from "@/lib/api/pipelines"
import type { ZapierEventMappingItem, ZapierStageBucket, ZapierDonorEventMappingItem } from "@/lib/api/zapier"
import { buildRecommendedBucketByStage, isZapierStageBucket, mergeEventMappingWithPipelineStages, type BadgeVariant, type IconComponent } from "./integration-shared"
import { AIConfigurationSection, AI_PROVIDERS } from "./ai-configuration-section"
import { EmailConfigurationSection } from "./email-configuration-section"
import { ZapierWebhookSection, getZapierDonorSettingsState, hasUnresolvedDonorMappings, type ZapierDonorType } from "./zapier-webhook-section"
import { MetaConfigurationSection } from "./meta-integration-section"

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
