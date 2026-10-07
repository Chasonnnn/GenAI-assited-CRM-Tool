"use client"

import { useId, useState, type FormEvent, type ReactNode } from "react"
import {
    AlertTriangleIcon,
    CheckCircle2Icon,
    ChevronRightIcon,
    CircleDashedIcon,
    CircleMinusIcon,
    CircleXIcon,
    Loader2Icon,
    ShieldCheckIcon,
} from "lucide-react"

import { PermissionDeniedState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { CopyField } from "@/components/ui/copy-field"
import { EmptyValue } from "@/components/ui/empty-value"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SaveBar } from "@/components/ui/save-bar"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "@/components/ui/toast"
import { useAuth } from "@/lib/auth-context"
import { getErrorMessage } from "@/lib/error-utils"
import type {
    TwilioCredentialTestRequest,
    TwilioMessagingPurpose,
    TwilioReadiness,
    TwilioReadinessGate,
    TwilioReadinessGateStatus,
    TwilioReadinessStatus,
    TwilioRouteReadiness,
    TwilioRouteSettings,
    TwilioRouteSettingsUpdate,
    TwilioSettings,
    TwilioSettingsUpdate,
} from "@/lib/api/twilio"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import {
    readinessPollInterval,
    useQueueTwilioReadinessCheck,
    useTestTwilioCredentials,
    useTwilioReadiness,
    useTwilioSettings,
    useUpdateTwilioSettings,
} from "@/lib/hooks/use-twilio"
import { cn } from "@/lib/utils"

const ROUTE_LABELS: Record<TwilioMessagingPurpose, string> = {
    operational: "Operational route",
    promotional: "Promotional route",
}

const ROUTE_PREFIX: Record<TwilioMessagingPurpose, string> = {
    operational: "Operational",
    promotional: "Promotional",
}

const READINESS_LABELS: Record<TwilioReadinessStatus, string> = {
    ready: "Ready",
    degraded: "Needs attention",
    blocked: "Blocked",
    not_configured: "Not configured",
    action_required: "Action required",
    unknown: "Unknown",
}

const GATE_LABELS: Record<TwilioReadinessGateStatus, string> = {
    pass: "Ready",
    fail: "Blocked",
    pending: "Check required",
    skipped: "Not required",
}

const SENDER_TYPE_LABELS: Record<string, string> = {
    toll_free: "Toll-free",
    "10dlc": "10DLC",
}

type ClearableCredential =
    | "account_sid"
    | "api_key_sid"
    | "api_secret"
    | "auth_token"

interface CredentialDraft {
    accountSid: string
    apiKeySid: string
    apiSecret: string
    authToken: string
}

interface RouteDraft {
    messagingServiceSid: string
    senderPhoneE164: string
    clearMessagingServiceSid: boolean
    clearSenderPhone: boolean
    enabled: boolean
}

interface SettingsDraft {
    enabled: boolean
    legalMessagingBrand: string
    operationalDisclosure: string
    promotionalDisclosure: string
    smsTermsUrl: string
    privacyPolicyUrl: string
    supportContact: string
    expectedFrequency: string
    complianceToolkitEnabled: boolean
    phiEnabled: boolean
    credentials: CredentialDraft
    clearCredentials: Record<ClearableCredential, boolean>
    routes: Record<TwilioMessagingPurpose, RouteDraft>
}

type EditableSection = "credentials" | "operational" | "promotional" | "consent"

const NO_SECTIONS_EDITING: Record<EditableSection, boolean> = {
    credentials: false,
    operational: false,
    promotional: false,
    consent: false,
}

function valueOrNull(value: string) {
    const trimmed = value.trim()
    return trimmed.length > 0 ? trimmed : null
}

function initialRouteDraft(settings: TwilioRouteSettings): RouteDraft {
    return {
        messagingServiceSid: "",
        senderPhoneE164: "",
        clearMessagingServiceSid: false,
        clearSenderPhone: false,
        enabled: settings.enabled,
    }
}

function initialCredentialDraft(): CredentialDraft {
    return { accountSid: "", apiKeySid: "", apiSecret: "", authToken: "" }
}

function initialDraft(settings: TwilioSettings): SettingsDraft {
    return {
        enabled: settings.enabled,
        legalMessagingBrand: settings.legal_messaging_brand ?? "",
        operationalDisclosure: settings.operational_disclosure ?? "",
        promotionalDisclosure: settings.promotional_disclosure ?? "",
        smsTermsUrl: settings.sms_terms_url ?? "",
        privacyPolicyUrl: settings.privacy_policy_url ?? "",
        supportContact: settings.support_contact ?? "",
        expectedFrequency: settings.expected_frequency ?? "",
        complianceToolkitEnabled: settings.compliance_toolkit_enabled,
        phiEnabled: settings.phi_enabled,
        credentials: initialCredentialDraft(),
        clearCredentials: {
            account_sid: false,
            api_key_sid: false,
            api_secret: false,
            auth_token: false,
        },
        routes: {
            operational: initialRouteDraft(settings.routes.operational),
            promotional: initialRouteDraft(settings.routes.promotional),
        },
    }
}

/** Both objects are built by the same constructors, so key order is stable. */
function isDraftDirty(draft: SettingsDraft, settings: TwilioSettings) {
    return JSON.stringify(draft) !== JSON.stringify(initialDraft(settings))
}

function friendlyStatus(value: string | null | undefined) {
    const normalized = value?.trim().toLowerCase()
    const labels: Record<string, string> = {
        active: "Active",
        approved: "Approved",
        available: "Available",
        disabled: "Disabled",
        enabled: "Enabled",
        enforced: "Enforced",
        failed: "Failed",
        inactive: "Inactive",
        pending: "Pending",
        rejected: "Rejected",
        standard: "Standard",
        hipaa: "HIPAA",
        hipaa_eligible: "HIPAA eligible",
        unconfigured: "Not configured",
        unavailable: "Unavailable",
        unknown: "Unknown",
        verified: "Verified",
    }
    return normalized ? labels[normalized] ?? "Needs review" : "Not configured"
}

function statusClasses(status: string | null | undefined) {
    const normalized = status?.toLowerCase() ?? ""
    if (["ready", "active", "approved", "enabled", "enforced", "verified", "available", "pass"].includes(normalized)) {
        return "border-success/30 bg-success/10 text-success"
    }
    if (["blocked", "failed", "rejected", "action_required", "fail"].includes(normalized)) {
        return "border-destructive/30 bg-destructive/10 text-destructive"
    }
    if (["skipped", "not_configured", "unconfigured"].includes(normalized)) {
        return "border-border bg-muted text-muted-foreground"
    }
    return "border-warning/30 bg-warning/10 text-warning"
}

function StatusBadge({ status, label }: { status: string; label?: string }) {
    return (
        <Badge variant="outline" className={cn("font-medium", statusClasses(status))}>
            {label ?? friendlyStatus(status)}
        </Badge>
    )
}

function formatEvidenceDate(value: string | null) {
    if (!value) return "Not verified"
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return "Recorded"
    return `${date.toISOString().slice(0, 16).replace("T", " ")} UTC`
}

function formatDateOnly(value: string | null) {
    if (!value) return null
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return "Recorded"
    return date.toISOString().slice(0, 10)
}

function LoadingState() {
    return (
        <div className="mx-auto max-w-7xl space-y-6 p-6" aria-label="Loading messaging settings">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-40 w-full" />
            <div className="grid gap-4 lg:grid-cols-2">
                <Skeleton className="h-64" />
                <Skeleton className="h-64" />
            </div>
        </div>
    )
}

function SummaryItem({
    label,
    children,
    mono = false,
    className,
}: {
    label: string
    children: ReactNode
    mono?: boolean
    className?: string
}) {
    return (
        <div className={cn("min-w-0 space-y-0.5", className)}>
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className={cn("flex flex-wrap items-center gap-2 text-sm font-medium break-words", mono && "font-mono text-xs")}>
                {children}
            </dd>
        </div>
    )
}

function GateIcon({ status }: { status: TwilioReadinessGateStatus }) {
    if (status === "pass") return <CheckCircle2Icon className="size-4 text-success" aria-hidden="true" />
    if (status === "fail") return <CircleXIcon className="size-4 text-destructive" aria-hidden="true" />
    if (status === "pending") return <CircleDashedIcon className="size-4 text-warning" aria-hidden="true" />
    return <CircleMinusIcon className="size-4 text-muted-foreground" aria-hidden="true" />
}

function CapabilityLine({ label, available }: { label: string; available: boolean }) {
    return (
        <div className="flex items-center justify-between gap-2 rounded-lg border bg-muted/20 px-3 py-2">
            <span className="text-sm font-medium">{label}</span>
            <StatusBadge status={available ? "ready" : "blocked"} label={available ? "Available" : "Unavailable"} />
        </div>
    )
}

function ReadinessCard({ readiness, checking }: { readiness: TwilioReadiness; checking: boolean }) {
    const gateDetails = new Set(readiness.gates.map((gate) => gate.detail).filter(Boolean))
    const remainingIssues = readiness.issues.filter(
        (issue) => issue.severity !== "info" && !gateDetails.has(issue.message),
    )
    const checkedLine = checking
        ? "Checking with Twilio"
        : readiness.provider.checked_at
          ? `Checked ${formatEvidenceDate(readiness.provider.checked_at)}`
          : "Settings changed since the last check"

    return (
        <Card role="region" aria-label="Readiness" className="gap-0 py-0">
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 border-b py-4 [.border-b]:pb-4">
                <CardTitle className="text-lg">Readiness</CardTitle>
                <p className="text-sm text-muted-foreground" role="status" aria-label="Last readiness check">
                    {checking ? <Loader2Icon className="mr-1.5 inline size-3.5 animate-spin motion-reduce:animate-none" aria-hidden="true" /> : null}
                    {checkedLine}
                </p>
            </CardHeader>
            <CardContent className="grid gap-0 p-0 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
                <ul className="divide-y px-6 py-4" aria-label="Launch gates">
                    {readiness.gates.map((gate) => (
                        <li key={gate.key} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 py-2.5 first:pt-0 last:pb-0">
                            <GateIcon status={gate.status} />
                            <div className="min-w-0">
                                <p className="text-sm font-medium">{gate.label}</p>
                                {gate.detail ? <p className="text-xs text-muted-foreground break-words">{gate.detail}</p> : null}
                            </div>
                            <StatusBadge status={gate.status} label={GATE_LABELS[gate.status]} />
                        </li>
                    ))}
                </ul>
                <div className="space-y-5 border-t px-6 py-4 lg:border-t-0 lg:border-l">
                    <section aria-label="Capabilities" className="space-y-2">
                        <h3 className="text-xs font-medium text-muted-foreground">Capabilities</h3>
                        <div className="grid gap-2 sm:grid-cols-2">
                            <CapabilityLine label="SMS sending" available={readiness.provider.capabilities.send_sms} />
                            <CapabilityLine label="SMS receiving" available={readiness.provider.capabilities.receive_sms} />
                            <CapabilityLine label="MMS sending" available={readiness.provider.capabilities.send_mms} />
                            <CapabilityLine label="MMS receiving" available={readiness.provider.capabilities.receive_mms} />
                        </div>
                    </section>
                    <section aria-label="Local delivery operations" className="space-y-2">
                        <h3 className="text-xs font-medium text-muted-foreground">Local operations</h3>
                        <div className="grid gap-2 sm:grid-cols-2">
                            <div className="rounded-lg border p-3">
                                <p className="text-xl font-semibold tabular-nums">{readiness.local.queue.queued_count} queued</p>
                                <p className="text-xs text-muted-foreground">
                                    {readiness.local.queue.processing_count} processing · {readiness.local.queue.failed_count} failed
                                </p>
                            </div>
                            <div className="rounded-lg border p-3">
                                <p className="text-xl font-semibold tabular-nums">
                                    {readiness.local.reconciliation.action_required_count} action required
                                </p>
                                <p className="text-xs text-muted-foreground">
                                    {readiness.local.reconciliation.unresolved_event_count} unresolved provider events
                                </p>
                            </div>
                        </div>
                    </section>
                    {remainingIssues.length > 0 ? (
                        <ul className="list-disc space-y-1 pl-5 text-xs text-destructive" aria-label="Other issues">
                            {remainingIssues.map((issue) => (
                                <li key={`${issue.code}-${issue.route ?? "organization"}`}>{issue.message}</li>
                            ))}
                        </ul>
                    ) : null}
                </div>
            </CardContent>
        </Card>
    )
}

function ClearStoredValue({
    label,
    checked,
    onCheckedChange,
}: {
    label: string
    checked: boolean
    onCheckedChange: (checked: boolean) => void
}) {
    return (
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <Checkbox checked={checked} onCheckedChange={(value) => onCheckedChange(Boolean(value))} />
            {label}
        </label>
    )
}

function CredentialField({
    id,
    label,
    value,
    maskedValue,
    configured,
    secret = false,
    clearLabel,
    clearChecked,
    onChange,
    onClearChange,
}: {
    id: string
    label: string
    value: string
    maskedValue?: string | null
    configured?: boolean
    secret?: boolean
    clearLabel: string
    clearChecked: boolean
    onChange: (value: string) => void
    onClearChange: (checked: boolean) => void
}) {
    const stored = Boolean(maskedValue || configured)
    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
                <Label htmlFor={id}>{label}</Label>
                {stored ? (
                    <span className="font-mono text-xs text-muted-foreground">{maskedValue ?? "Stored"}</span>
                ) : null}
            </div>
            <Input
                id={id}
                type={secret ? "password" : "text"}
                autoComplete="new-password"
                value={value}
                disabled={clearChecked}
                placeholder={stored ? "Leave blank to keep saved value" : undefined}
                onChange={(event) => onChange(event.target.value)}
            />
            {stored ? (
                <ClearStoredValue label={clearLabel} checked={clearChecked} onCheckedChange={onClearChange} />
            ) : null}
        </div>
    )
}

function WebhookValue({ label, value }: { label: string; value: string }) {
    const id = useId()

    return (
        <div className="space-y-1.5">
            <Label htmlFor={id}>{label}</Label>
            <CopyField id={id} value={value} copyLabel={`Copy ${label}`} />
        </div>
    )
}

function SectionActions({ children }: { children: ReactNode }) {
    return <div className="ml-auto flex flex-wrap items-center gap-2">{children}</div>
}

function ConnectionCard({
    settings,
    draft,
    gate,
    editing,
    credentialResult,
    isTesting,
    onEditingChange,
    onEnabledChange,
    onCredentialChange,
    onCredentialClear,
    onTest,
}: {
    settings: TwilioSettings
    draft: SettingsDraft
    gate: TwilioReadinessGate | null
    editing: boolean
    credentialResult: { valid: boolean; message: string } | null
    isTesting: boolean
    onEditingChange: (editing: boolean) => void
    onEnabledChange: (enabled: boolean) => void
    onCredentialChange: (field: keyof CredentialDraft, value: string) => void
    onCredentialClear: (field: ClearableCredential, checked: boolean) => void
    onTest: () => void
}) {
    const configured = Boolean(
        settings.account_sid_masked ||
            settings.api_key_sid_masked ||
            settings.api_secret_configured ||
            settings.auth_token_configured,
    )
    const showForm = editing || !configured

    return (
        <Card>
            <CardHeader className="flex flex-row flex-wrap items-center gap-3">
                <CardTitle className="text-lg">Connection</CardTitle>
                {gate ? <StatusBadge status={gate.status} label={GATE_LABELS[gate.status]} /> : null}
                <SectionActions>
                    <Button type="button" variant="outline" size="sm" onClick={onTest} disabled={isTesting}>
                        {isTesting ? <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <ShieldCheckIcon aria-hidden="true" />}
                        Test connection
                    </Button>
                    {configured ? (
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            aria-label={editing ? "Cancel replacing credentials" : "Replace credentials"}
                            onClick={() => onEditingChange(!editing)}
                        >
                            {editing ? "Cancel" : "Replace credentials"}
                        </Button>
                    ) : null}
                </SectionActions>
            </CardHeader>
            <CardContent className="space-y-5">
                <div className="flex items-center justify-between gap-4">
                    <Label htmlFor="messaging-enabled">Organization messaging</Label>
                    <Switch id="messaging-enabled" checked={draft.enabled} onCheckedChange={onEnabledChange} />
                </div>
                {showForm ? (
                    <div className="grid gap-4 md:grid-cols-2">
                        <CredentialField
                            id="twilio-account-sid"
                            label="Account SID"
                            value={draft.credentials.accountSid}
                            maskedValue={settings.account_sid_masked}
                            clearLabel="Clear saved Account SID"
                            clearChecked={draft.clearCredentials.account_sid}
                            onChange={(value) => onCredentialChange("accountSid", value)}
                            onClearChange={(checked) => onCredentialClear("account_sid", checked)}
                        />
                        <CredentialField
                            id="twilio-api-key-sid"
                            label="API Key SID"
                            value={draft.credentials.apiKeySid}
                            maskedValue={settings.api_key_sid_masked}
                            clearLabel="Clear saved API Key SID"
                            clearChecked={draft.clearCredentials.api_key_sid}
                            onChange={(value) => onCredentialChange("apiKeySid", value)}
                            onClearChange={(checked) => onCredentialClear("api_key_sid", checked)}
                        />
                        <CredentialField
                            id="twilio-api-secret"
                            label="API Secret"
                            value={draft.credentials.apiSecret}
                            configured={settings.api_secret_configured}
                            secret
                            clearLabel="Clear saved API Secret"
                            clearChecked={draft.clearCredentials.api_secret}
                            onChange={(value) => onCredentialChange("apiSecret", value)}
                            onClearChange={(checked) => onCredentialClear("api_secret", checked)}
                        />
                        <CredentialField
                            id="twilio-auth-token"
                            label="Auth Token"
                            value={draft.credentials.authToken}
                            configured={settings.auth_token_configured}
                            secret
                            clearLabel="Clear saved Auth Token"
                            clearChecked={draft.clearCredentials.auth_token}
                            onChange={(value) => onCredentialChange("authToken", value)}
                            onClearChange={(checked) => onCredentialClear("auth_token", checked)}
                        />
                    </div>
                ) : (
                    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Saved credentials">
                        <SummaryItem label="Account SID" mono>{settings.account_sid_masked ?? <EmptyValue label="Not configured" />}</SummaryItem>
                        <SummaryItem label="API Key SID" mono>{settings.api_key_sid_masked ?? <EmptyValue label="Not configured" />}</SummaryItem>
                        <SummaryItem label="API Secret">{settings.api_secret_configured ? "Stored" : <EmptyValue label="Not configured" />}</SummaryItem>
                        <SummaryItem label="Auth Token">{settings.auth_token_configured ? "Stored" : <EmptyValue label="Not configured" />}</SummaryItem>
                    </dl>
                )}
                {credentialResult ? (
                    <Alert variant={credentialResult.valid ? "default" : "destructive"}>
                        {credentialResult.valid ? <CheckCircle2Icon aria-hidden="true" /> : <AlertTriangleIcon aria-hidden="true" />}
                        <AlertTitle>{credentialResult.valid ? "Connection verified" : "Connection failed"}</AlertTitle>
                        <AlertDescription>{credentialResult.message}</AlertDescription>
                    </Alert>
                ) : null}
            </CardContent>
        </Card>
    )
}

function RouteCard({
    purpose,
    settings,
    draft,
    readiness,
    gates,
    editing,
    onEditingChange,
    onChange,
}: {
    purpose: TwilioMessagingPurpose
    settings: TwilioRouteSettings
    draft: RouteDraft
    readiness: TwilioRouteReadiness | null
    gates: TwilioReadinessGate[]
    editing: boolean
    onEditingChange: (editing: boolean) => void
    onChange: (draft: RouteDraft) => void
}) {
    const prefix = ROUTE_PREFIX[purpose]
    const configured = Boolean(settings.messaging_service_sid_masked && settings.sender_phone_masked)
    const gateFor = (suffix: string) => gates.find((gate) => gate.key === `${purpose}_${suffix}`) ?? null
    const registration = gateFor("sender_registration")
    const inbound = gateFor("inbound_webhook")
    const providerEvidence = (settings.capability_evidence?.provider ?? {}) as Record<string, unknown>
    const senderTypeLabel = readiness?.sender_type ? SENDER_TYPE_LABELS[readiness.sender_type] : undefined

    return (
        <Card>
            <CardHeader className="flex flex-row flex-wrap items-center gap-3">
                <CardTitle className="text-lg">{ROUTE_LABELS[purpose]}</CardTitle>
                {readiness ? (
                    <StatusBadge status={readiness.status} label={READINESS_LABELS[readiness.status]} />
                ) : null}
                {configured ? (
                    <SectionActions>
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            aria-label={`${editing ? "Cancel editing" : "Edit"} ${ROUTE_LABELS[purpose].toLowerCase()}`}
                            onClick={() => onEditingChange(!editing)}
                        >
                            {editing ? "Cancel" : "Edit"}
                        </Button>
                    </SectionActions>
                ) : null}
            </CardHeader>
            <CardContent className="space-y-5">
                <div className="flex items-center justify-between gap-4">
                    <Label htmlFor={`${purpose}-route-enabled`}>Route enabled</Label>
                    <Switch
                        id={`${purpose}-route-enabled`}
                        aria-label={`${prefix} route enabled`}
                        checked={draft.enabled}
                        onCheckedChange={(enabled) => onChange({ ...draft, enabled })}
                    />
                </div>

                {editing ? (
                    <div className="grid gap-4">
                        <CredentialField
                            id={`${purpose}-messaging-service-sid`}
                            label={`${prefix} Messaging Service SID`}
                            value={draft.messagingServiceSid}
                            maskedValue={settings.messaging_service_sid_masked}
                            clearLabel={`Clear saved ${prefix} Messaging Service SID`}
                            clearChecked={draft.clearMessagingServiceSid}
                            onChange={(messagingServiceSid) => onChange({ ...draft, messagingServiceSid })}
                            onClearChange={(clearMessagingServiceSid) => onChange({ ...draft, clearMessagingServiceSid, messagingServiceSid: "" })}
                        />
                        <CredentialField
                            id={`${purpose}-sender-phone`}
                            label={`${prefix} sender number`}
                            value={draft.senderPhoneE164}
                            maskedValue={settings.sender_phone_masked}
                            clearLabel={`Clear saved ${prefix} sender number`}
                            clearChecked={draft.clearSenderPhone}
                            onChange={(senderPhoneE164) => onChange({ ...draft, senderPhoneE164 })}
                            onClearChange={(clearSenderPhone) => onChange({ ...draft, clearSenderPhone, senderPhoneE164: "" })}
                        />
                    </div>
                ) : configured ? (
                    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2" aria-label={`${prefix} route summary`}>
                        <SummaryItem label="Sender">
                            {settings.sender_phone_masked}
                            {senderTypeLabel ? <Badge variant="secondary">{senderTypeLabel}</Badge> : null}
                        </SummaryItem>
                        <SummaryItem label="Messaging Service" mono>{settings.messaging_service_sid_masked}</SummaryItem>
                        <SummaryItem label={registration?.label ?? "Sender registration"}>
                            {registration ? (
                                <StatusBadge status={registration.status} label={GATE_LABELS[registration.status]} />
                            ) : (
                                friendlyStatus(settings.a2p_status)
                            )}
                        </SummaryItem>
                        {inbound ? (
                            <SummaryItem label={inbound.label}>
                                <StatusBadge status={inbound.status} label={GATE_LABELS[inbound.status]} />
                            </SummaryItem>
                        ) : null}
                        <SummaryItem label="Evidence">
                            <Badge variant="secondary">SMS {providerEvidence.sms === true ? "evidenced" : "not evidenced"}</Badge>
                            <Badge variant="secondary">MMS {providerEvidence.mms === true ? "evidenced" : "not evidenced"}</Badge>
                            <Badge variant="secondary">Sender pool {providerEvidence.sender_in_pool === true ? "verified" : "not verified"}</Badge>
                        </SummaryItem>
                    </dl>
                ) : (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                        <span>No sender or Messaging Service saved.</span>
                        <Button type="button" variant="outline" size="sm" onClick={() => onEditingChange(true)}>
                            Set up route
                        </Button>
                    </div>
                )}

                <Collapsible>
                    <CollapsibleTrigger className="group/webhooks flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground">
                        <ChevronRightIcon className="size-4 transition-transform group-data-panel-open/webhooks:rotate-90" aria-hidden="true" />
                        Webhooks
                    </CollapsibleTrigger>
                    <CollapsibleContent className="space-y-3 pt-3">
                        <WebhookValue label={`${prefix} inbound webhook URL`} value={settings.inbound_webhook_url} />
                        <WebhookValue label={`${prefix} status callback URL`} value={settings.status_callback_url} />
                        <p className="text-xs text-muted-foreground">Webhook route ID: <code>{settings.webhook_id}</code></p>
                    </CollapsibleContent>
                </Collapsible>
            </CardContent>
        </Card>
    )
}

type DisclosureField =
    | "legalMessagingBrand"
    | "supportContact"
    | "smsTermsUrl"
    | "privacyPolicyUrl"
    | "expectedFrequency"
    | "operationalDisclosure"
    | "promotionalDisclosure"

function LinkOrEmpty({ href }: { href: string | null }) {
    if (!href) return <EmptyValue label="Not set" />
    return (
        <a href={href} target="_blank" rel="noreferrer" className="break-all underline underline-offset-4">
            {href.replace(/^https?:\/\//, "")}
        </a>
    )
}

function ConsentDisclosureCard({
    settings,
    draft,
    editing,
    onEditingChange,
    onChange,
}: {
    settings: TwilioSettings
    draft: SettingsDraft
    editing: boolean
    onEditingChange: (editing: boolean) => void
    onChange: (field: DisclosureField, value: string) => void
}) {
    return (
        <Card>
            <CardHeader className="flex flex-row flex-wrap items-center gap-3">
                <CardTitle className="text-lg">Consent and disclosure</CardTitle>
                <SectionActions>
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        aria-label={editing ? "Cancel editing consent and disclosure" : "Edit consent and disclosure"}
                        onClick={() => onEditingChange(!editing)}
                    >
                        {editing ? "Cancel" : "Edit"}
                    </Button>
                </SectionActions>
            </CardHeader>
            <CardContent>
                {editing ? (
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                            <Label htmlFor="legal-messaging-brand">Legal messaging brand</Label>
                            <Input id="legal-messaging-brand" value={draft.legalMessagingBrand} onChange={(event) => onChange("legalMessagingBrand", event.target.value)} />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="support-contact">Support contact</Label>
                            <Input id="support-contact" value={draft.supportContact} onChange={(event) => onChange("supportContact", event.target.value)} />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="sms-terms-url">SMS terms URL</Label>
                            <Input id="sms-terms-url" type="url" value={draft.smsTermsUrl} onChange={(event) => onChange("smsTermsUrl", event.target.value)} />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="privacy-policy-url">Privacy policy URL</Label>
                            <Input id="privacy-policy-url" type="url" value={draft.privacyPolicyUrl} onChange={(event) => onChange("privacyPolicyUrl", event.target.value)} />
                        </div>
                        <div className="space-y-2 md:col-span-2">
                            <Label htmlFor="expected-frequency">Expected message frequency</Label>
                            <Input id="expected-frequency" value={draft.expectedFrequency} onChange={(event) => onChange("expectedFrequency", event.target.value)} />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="operational-disclosure">Operational disclosure</Label>
                            <Textarea id="operational-disclosure" rows={5} value={draft.operationalDisclosure} onChange={(event) => onChange("operationalDisclosure", event.target.value)} />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="promotional-disclosure">Promotional disclosure</Label>
                            <Textarea id="promotional-disclosure" rows={5} value={draft.promotionalDisclosure} onChange={(event) => onChange("promotionalDisclosure", event.target.value)} />
                        </div>
                    </div>
                ) : (
                    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2" aria-label="Consent record">
                        <SummaryItem label="Legal messaging brand">{settings.legal_messaging_brand || <EmptyValue label="Not set" />}</SummaryItem>
                        <SummaryItem label="Support contact">{settings.support_contact || <EmptyValue label="Not set" />}</SummaryItem>
                        <SummaryItem label="SMS terms"><LinkOrEmpty href={settings.sms_terms_url} /></SummaryItem>
                        <SummaryItem label="Privacy policy"><LinkOrEmpty href={settings.privacy_policy_url} /></SummaryItem>
                        <SummaryItem label="Expected message frequency" className="sm:col-span-2">{settings.expected_frequency || <EmptyValue label="Not set" />}</SummaryItem>
                        <SummaryItem label="Operational disclosure" className="sm:col-span-2 [&>dd]:font-normal">{settings.operational_disclosure || <EmptyValue label="Not set" />}</SummaryItem>
                        <SummaryItem label="Promotional disclosure" className="sm:col-span-2 [&>dd]:font-normal">{settings.promotional_disclosure || <EmptyValue label="Not set" />}</SummaryItem>
                    </dl>
                )}
            </CardContent>
        </Card>
    )
}

function ComplianceControlsCard({
    settings,
    draft,
    onToolkitChange,
    onPhiChange,
}: {
    settings: TwilioSettings
    draft: SettingsDraft
    onToolkitChange: (enabled: boolean) => void
    onPhiChange: (enabled: boolean) => void
}) {
    const phiPrerequisitesMet =
        settings.twilio_edition?.toLowerCase() === "hipaa_eligible" &&
        Boolean(settings.baa_verified_at) &&
        Boolean(settings.compliance_approved_at)

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-lg">Compliance</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
                <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <SummaryItem label="Twilio edition" className="rounded-lg border p-3">{friendlyStatus(settings.twilio_edition)}</SummaryItem>
                    <SummaryItem label="Counsel approval" className="rounded-lg border p-3">{formatDateOnly(settings.counsel_approved_at) ?? <EmptyValue label="Not recorded" />}</SummaryItem>
                    <SummaryItem label="Compliance approval" className="rounded-lg border p-3">{formatDateOnly(settings.compliance_approved_at) ?? <EmptyValue label="Not recorded" />}</SummaryItem>
                    <SummaryItem label="BAA verification" className="rounded-lg border p-3">{formatDateOnly(settings.baa_verified_at) ?? <EmptyValue label="Not recorded" />}</SummaryItem>
                </dl>
                <div className="grid gap-3 md:grid-cols-2">
                    <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
                        <Label htmlFor="compliance-toolkit-enabled">Compliance toolkit</Label>
                        <Switch id="compliance-toolkit-enabled" checked={draft.complianceToolkitEnabled} onCheckedChange={onToolkitChange} />
                    </div>
                    <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
                        <div>
                            <Label htmlFor="phi-enabled">PHI messaging</Label>
                            {phiPrerequisitesMet ? null : (
                                <p className="text-xs text-muted-foreground">Requires a HIPAA-eligible edition, verified BAA, and compliance approval.</p>
                            )}
                        </div>
                        <Switch id="phi-enabled" checked={draft.phiEnabled} disabled={!phiPrerequisitesMet} onCheckedChange={onPhiChange} />
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}

function addCredentialValue(
    update: TwilioSettingsUpdate,
    key: ClearableCredential,
    value: string,
    clear: boolean,
) {
    if (clear) {
        update[key] = ""
    } else if (value.trim()) {
        update[key] = value.trim()
    }
}

function buildRouteUpdate(draft: RouteDraft): TwilioRouteSettingsUpdate {
    const update: TwilioRouteSettingsUpdate = {
        enabled: draft.enabled,
    }
    if (draft.clearMessagingServiceSid) {
        update.messaging_service_sid = ""
    } else if (draft.messagingServiceSid.trim()) {
        update.messaging_service_sid = draft.messagingServiceSid.trim()
    }
    if (draft.clearSenderPhone) {
        update.sender_phone_e164 = ""
    } else if (draft.senderPhoneE164.trim()) {
        update.sender_phone_e164 = draft.senderPhoneE164.trim()
    }
    return update
}

function validateDraft(draft: SettingsDraft) {
    for (const purpose of ["operational", "promotional"] as const) {
        const route = draft.routes[purpose]
        if (route.senderPhoneE164.trim() && !/^\+1\d{10}$/.test(route.senderPhoneE164.trim())) {
            return "Use an exact +1 E.164 sender, for example +14155550101."
        }
        if (route.messagingServiceSid.trim() && !/^MG[a-fA-F0-9]{32}$/.test(route.messagingServiceSid.trim())) {
            return `${ROUTE_LABELS[purpose]} needs a valid Twilio Messaging Service SID.`
        }
    }
    if (draft.credentials.accountSid.trim() && !/^AC[a-fA-F0-9]{32}$/.test(draft.credentials.accountSid.trim())) {
        return "Enter a valid Twilio Account SID."
    }
    if (draft.credentials.apiKeySid.trim() && !/^SK[a-fA-F0-9]{32}$/.test(draft.credentials.apiKeySid.trim())) {
        return "Enter a valid Twilio API Key SID."
    }
    return null
}

function buildCredentialTestRequest(draft: SettingsDraft): TwilioCredentialTestRequest {
    const request: TwilioCredentialTestRequest = {}
    if (draft.credentials.accountSid.trim()) request.account_sid = draft.credentials.accountSid.trim()
    if (draft.credentials.apiKeySid.trim()) request.api_key_sid = draft.credentials.apiKeySid.trim()
    if (draft.credentials.apiSecret) request.api_secret = draft.credentials.apiSecret
    if (draft.credentials.authToken) request.auth_token = draft.credentials.authToken
    const routes: NonNullable<TwilioCredentialTestRequest["routes"]> = {}
    for (const purpose of ["operational", "promotional"] as const) {
        const serviceSid = draft.routes[purpose].messagingServiceSid.trim()
        const sender = draft.routes[purpose].senderPhoneE164.trim()
        if (serviceSid || sender) {
            routes[purpose] = {
                ...(serviceSid ? { messaging_service_sid: serviceSid } : {}),
                ...(sender ? { sender_phone_e164: sender } : {}),
            }
        }
    }
    if (Object.keys(routes).length > 0) request.routes = routes
    return request
}

function SettingsForm({
    settings,
    readiness,
    onSaved,
}: {
    settings: TwilioSettings
    readiness: TwilioReadiness | null
    onSaved: () => void
}) {
    const [draft, setDraft] = useState(() => initialDraft(settings))
    const [editing, setEditing] = useState(NO_SECTIONS_EDITING)
    const [formError, setFormError] = useState<string | null>(null)
    const [credentialResult, setCredentialResult] = useState<{ valid: boolean; message: string } | null>(null)
    const updateSettings = useUpdateTwilioSettings()
    const testCredentials = useTestTwilioCredentials()
    const gates = readiness?.gates ?? []
    const dirty = isDraftDirty(draft, settings)

    const setSectionEditing = (section: EditableSection, value: boolean) => {
        setEditing((current) => ({ ...current, [section]: value }))
        if (value) return
        // Leaving edit mode drops unsaved edits for that section only.
        setDraft((current) => {
            if (section === "credentials") {
                return {
                    ...current,
                    credentials: initialCredentialDraft(),
                    clearCredentials: { account_sid: false, api_key_sid: false, api_secret: false, auth_token: false },
                }
            }
            if (section === "consent") {
                const fresh = initialDraft(settings)
                return {
                    ...current,
                    legalMessagingBrand: fresh.legalMessagingBrand,
                    supportContact: fresh.supportContact,
                    smsTermsUrl: fresh.smsTermsUrl,
                    privacyPolicyUrl: fresh.privacyPolicyUrl,
                    expectedFrequency: fresh.expectedFrequency,
                    operationalDisclosure: fresh.operationalDisclosure,
                    promotionalDisclosure: fresh.promotionalDisclosure,
                }
            }
            return {
                ...current,
                routes: {
                    ...current.routes,
                    [section]: { ...initialRouteDraft(settings.routes[section]), enabled: current.routes[section].enabled },
                },
            }
        })
    }

    const changeCredential = (field: keyof CredentialDraft, value: string) => {
        setCredentialResult(null)
        setDraft((current) => ({
            ...current,
            credentials: { ...current.credentials, [field]: value },
        }))
    }

    const changeCredentialClear = (field: ClearableCredential, checked: boolean) => {
        const draftField: Record<ClearableCredential, keyof CredentialDraft> = {
            account_sid: "accountSid",
            api_key_sid: "apiKeySid",
            api_secret: "apiSecret",
            auth_token: "authToken",
        }
        setCredentialResult(null)
        setDraft((current) => ({
            ...current,
            credentials: checked
                ? { ...current.credentials, [draftField[field]]: "" }
                : current.credentials,
            clearCredentials: { ...current.clearCredentials, [field]: checked },
        }))
    }

    const handleTestCredentials = async () => {
        setFormError(null)
        setCredentialResult(null)
        const validationError = validateDraft(draft)
        if (validationError) {
            setFormError(validationError)
            return
        }
        try {
            const result = await testCredentials.mutateAsync(buildCredentialTestRequest(draft))
            if (result.valid) {
                setCredentialResult({ valid: true, message: "Connection verified. No message was sent." })
                toast.success("Twilio connection verified")
            } else {
                setCredentialResult({
                    valid: false,
                    message: result.error ?? "Twilio rejected this configuration.",
                })
            }
        } catch (error) {
            setCredentialResult({ valid: false, message: getErrorMessage(error, "Could not verify the Twilio connection.") })
        }
    }

    const discard = () => {
        setDraft(initialDraft(settings))
        setEditing(NO_SECTIONS_EDITING)
        setFormError(null)
        setCredentialResult(null)
    }

    const handleSubmit = async () => {
        if (updateSettings.isPending) return
        setFormError(null)
        const validationError = validateDraft(draft)
        if (validationError) {
            setFormError(validationError)
            return
        }

        const update: TwilioSettingsUpdate = {
            enabled: draft.enabled,
            legal_messaging_brand: valueOrNull(draft.legalMessagingBrand),
            operational_disclosure: valueOrNull(draft.operationalDisclosure),
            promotional_disclosure: valueOrNull(draft.promotionalDisclosure),
            sms_terms_url: valueOrNull(draft.smsTermsUrl),
            privacy_policy_url: valueOrNull(draft.privacyPolicyUrl),
            support_contact: valueOrNull(draft.supportContact),
            expected_frequency: valueOrNull(draft.expectedFrequency),
            compliance_toolkit_enabled: draft.complianceToolkitEnabled,
            phi_enabled: draft.phiEnabled,
            routes: {
                operational: buildRouteUpdate(draft.routes.operational),
                promotional: buildRouteUpdate(draft.routes.promotional),
            },
            expected_version: settings.current_version,
        }
        addCredentialValue(update, "account_sid", draft.credentials.accountSid, draft.clearCredentials.account_sid)
        addCredentialValue(update, "api_key_sid", draft.credentials.apiKeySid, draft.clearCredentials.api_key_sid)
        addCredentialValue(update, "api_secret", draft.credentials.apiSecret, draft.clearCredentials.api_secret)
        addCredentialValue(update, "auth_token", draft.credentials.authToken, draft.clearCredentials.auth_token)

        try {
            const saved = await updateSettings.mutateAsync(update)
            setDraft(initialDraft(saved))
            setEditing(NO_SECTIONS_EDITING)
            setCredentialResult(null)
            toast.success("Messaging settings saved")
            onSaved()
        } catch (error) {
            setFormError(getErrorMessage(error, "Could not save messaging settings."))
        }
    }

    const onSubmit = (event: FormEvent) => {
        event.preventDefault()
        void handleSubmit()
    }

    return (
        <form className="space-y-6" onSubmit={onSubmit}>
            {formError ? (
                <Alert variant="destructive">
                    <AlertTriangleIcon aria-hidden="true" />
                    <AlertTitle>Settings were not saved</AlertTitle>
                    <AlertDescription>{formError}</AlertDescription>
                </Alert>
            ) : null}

            <ConnectionCard
                settings={settings}
                draft={draft}
                gate={gates.find((gate) => gate.key === "connection") ?? null}
                editing={editing.credentials}
                credentialResult={credentialResult}
                isTesting={testCredentials.isPending}
                onEditingChange={(value) => setSectionEditing("credentials", value)}
                onEnabledChange={(enabled) => setDraft((current) => ({ ...current, enabled }))}
                onCredentialChange={changeCredential}
                onCredentialClear={changeCredentialClear}
                onTest={() => void handleTestCredentials()}
            />

            <div className="grid gap-6 xl:grid-cols-2">
                {(["operational", "promotional"] as const).map((purpose) => (
                    <RouteCard
                        key={purpose}
                        purpose={purpose}
                        settings={settings.routes[purpose]}
                        draft={draft.routes[purpose]}
                        readiness={readiness?.provider.routes[purpose] ?? null}
                        gates={gates}
                        editing={editing[purpose]}
                        onEditingChange={(value) => setSectionEditing(purpose, value)}
                        onChange={(route) => setDraft((current) => ({ ...current, routes: { ...current.routes, [purpose]: route } }))}
                    />
                ))}
            </div>

            <ConsentDisclosureCard
                settings={settings}
                draft={draft}
                editing={editing.consent}
                onEditingChange={(value) => setSectionEditing("consent", value)}
                onChange={(field, value) => setDraft((current) => ({ ...current, [field]: value }))}
            />

            <ComplianceControlsCard
                settings={settings}
                draft={draft}
                onToolkitChange={(complianceToolkitEnabled) => setDraft((current) => ({ ...current, complianceToolkitEnabled }))}
                onPhiChange={(phiEnabled) => setDraft((current) => ({ ...current, phiEnabled }))}
            />

            <SaveBar
                dirty={dirty}
                saving={updateSettings.isPending}
                onSave={() => void handleSubmit()}
                onDiscard={discard}
                saveLabel="Save messaging settings"
            />
        </form>
    )
}

export default function MessagingIntegrationPageClient() {
    const { user, isLoading: authLoading } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const isDeveloper = user?.role === "developer"
    const canManageIntegrations =
        isDeveloper ||
        (permissionsQuery.data?.permissions ?? []).includes("manage_integrations")
    const [awaitingCheckSince, setAwaitingCheckSince] = useState<string | null>(null)
    const settingsQuery = useTwilioSettings(Boolean(user && canManageIntegrations))
    const readinessQuery = useTwilioReadiness(Boolean(user && canManageIntegrations), awaitingCheckSince)
    const queueCheck = useQueueTwilioReadinessCheck()
    const permissionsLoading = Boolean(user && !isDeveloper && permissionsQuery.isLoading)
    const checking =
        queueCheck.isPending || readinessPollInterval(readinessQuery.data, awaitingCheckSince) !== false

    const runReadinessCheck = async () => {
        try {
            const response = await queueCheck.mutateAsync()
            setAwaitingCheckSince(response.queued_at)
        } catch (error) {
            toast.error(getErrorMessage(error, "Could not start the readiness check."))
        }
    }

    if (authLoading || permissionsLoading || !user || !canManageIntegrations) {
        // Same shell as SettingsPageGate: the header stays while access is checked or denied.
        return (
            <div className="flex min-h-dvh flex-col bg-muted/10">
                <PageHeader
                    title="Messaging delivery"
                    back={{ href: "/settings/integrations", label: "Back to integrations" }}
                />
                {authLoading || permissionsLoading ? (
                    <LoadingState />
                ) : (
                    <PermissionDeniedState
                        title="Messaging settings are restricted"
                        description="Only organization administrators and developers can manage Twilio credentials, routes, and compliance settings."
                        secondaryHref="/settings/integrations"
                        secondaryLabel="Back to integrations"
                        headingLevel={2}
                    />
                )}
            </div>
        )
    }

    return (
        <div className="min-h-dvh bg-muted/10">
            <PageHeader
                title="Messaging delivery"
                back={{ href: "/settings/integrations", label: "Back to integrations" }}
                meta={
                    readinessQuery.data ? (
                        <StatusBadge status={readinessQuery.data.overall_status} label={READINESS_LABELS[readinessQuery.data.overall_status]} />
                    ) : null
                }
                actions={
                    <Button
                        type="button"
                        variant={readinessQuery.data?.overall_status === "ready" ? "outline" : "default"}
                        size="sm"
                        onClick={() => void runReadinessCheck()}
                        disabled={checking || !settingsQuery.data}
                    >
                        {checking ? (
                            <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                        ) : (
                            <ShieldCheckIcon aria-hidden="true" />
                        )}
                        {checking ? "Checking" : "Run readiness check"}
                    </Button>
                }
            />

            <main className="mx-auto max-w-7xl space-y-6 p-6">
                {settingsQuery.isLoading && !settingsQuery.data ? <LoadingState /> : null}

                {settingsQuery.isError && !settingsQuery.data ? (
                    <Alert variant="destructive">
                        <AlertTriangleIcon aria-hidden="true" />
                        <AlertTitle>Messaging settings are unavailable</AlertTitle>
                        <AlertDescription className="flex flex-wrap items-center gap-3">
                            {getErrorMessage(settingsQuery.error, "The organization configuration could not be loaded.")}
                            <Button type="button" size="sm" variant="outline" onClick={() => void settingsQuery.refetch()}>Try again</Button>
                        </AlertDescription>
                    </Alert>
                ) : null}

                {readinessQuery.data ? (
                    <ReadinessCard readiness={readinessQuery.data} checking={checking} />
                ) : readinessQuery.isError ? (
                    <Alert>
                        <AlertTriangleIcon aria-hidden="true" />
                        <AlertTitle>Readiness evidence is temporarily unavailable</AlertTitle>
                        <AlertDescription>Settings remain editable. Run a readiness check before enabling delivery.</AlertDescription>
                    </Alert>
                ) : null}

                {settingsQuery.data ? (
                    <SettingsForm
                        key={`twilio-settings-${settingsQuery.data.current_version}`}
                        settings={settingsQuery.data}
                        readiness={readinessQuery.data ?? null}
                        onSaved={() => setAwaitingCheckSince(null)}
                    />
                ) : null}
            </main>
        </div>
    )
}
