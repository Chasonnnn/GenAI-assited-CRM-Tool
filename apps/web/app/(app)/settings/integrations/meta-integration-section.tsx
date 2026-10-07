import { type ReactNode, useState, useRef, useReducer } from "react"
import Link from "@/components/app-link"
import { Card, CardHeader, CardDescription, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DialogBody, DialogFooter, DialogClose, Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Loader2Icon, AlertTriangleIcon, ActivityIcon, CheckCircleIcon, MegaphoneIcon, UnlinkIcon, PencilIcon, TrashIcon } from "lucide-react"
import { usePipelines } from "@/lib/hooks/use-pipelines"
import { useMetaConnections, useMetaConnectUrl, useDisconnectMetaConnection } from "@/lib/hooks/use-meta-oauth"
import { useAdminMetaAdAccounts, useUpdateMetaAdAccount, useDeleteMetaAdAccount } from "@/lib/hooks/use-admin-meta"
import { useMetaCrmDatasetEventsSummary, useMetaCrmDatasetEvents, useRetryMetaCrmDatasetEvent, useMetaCrmDatasetSettings, useUpdateMetaCrmDatasetSettings, useMetaCrmDatasetOutboundTest } from "@/lib/hooks/use-meta-crm-dataset"
import type { MetaAdAccount, MetaAdAccountUpdate } from "@/lib/api/admin-meta"
import { type MetaOAuthConnection, getConnectionHealthStatus, parseMetaError } from "@/lib/api/meta-oauth"
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table"
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip"
import { Checkbox } from "@/components/ui/checkbox"
import { formatRelativeTime } from "@/lib/formatters"
import { toast } from "@/components/ui/toast"
import type { MetaCrmDatasetEventMappingItem } from "@/lib/api/meta-crm-dataset"
import { IntegrationDialogLoadingState, StageEventMappingTable, ZAPIER_BUCKET_EVENT_NAME, ZAPIER_OUTBOUND_STATUS_BADGE, buildRecommendedBucketByStage, buildStageLabelByKey, formatZapierRate, formatZapierReason, formatZapierSource, mergeEventMappingWithPipelineStages } from "./integration-shared"

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

export function MetaConfigurationSection() {
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
