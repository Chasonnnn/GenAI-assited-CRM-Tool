"use client"

import { useState, type FormEvent } from "react"
import {
    AlertTriangleIcon,
    ArrowLeftIcon,
    CheckCircle2Icon,
    ClipboardIcon,
    Loader2Icon,
    MessageSquareTextIcon,
    RefreshCwIcon,
    ShieldCheckIcon,
} from "lucide-react"

import Link from "@/components/app-link"
import { PermissionDeniedState } from "@/components/error-state"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
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
    TwilioReadinessStatus,
    TwilioRouteSettings,
    TwilioRouteSettingsUpdate,
    TwilioSettings,
    TwilioSettingsUpdate,
} from "@/lib/api/twilio"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import {
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

const READINESS_LABELS: Record<TwilioReadinessStatus, string> = {
    ready: "Ready",
    degraded: "Needs attention",
    blocked: "Blocked",
    not_configured: "Not configured",
    action_required: "Action required",
    unknown: "Unknown",
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
        credentials: {
            accountSid: "",
            apiKeySid: "",
            apiSecret: "",
            authToken: "",
        },
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
    }
    return normalized ? labels[normalized] ?? "Needs review" : "Not configured"
}

function statusClasses(status: string | null | undefined) {
    const normalized = status?.toLowerCase()
    if (["ready", "active", "approved", "enabled", "enforced"].includes(normalized ?? "")) {
        return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700"
    }
    if (["blocked", "failed", "rejected", "action_required"].includes(normalized ?? "")) {
        return "border-destructive/30 bg-destructive/10 text-destructive"
    }
    return "border-amber-500/30 bg-amber-500/10 text-amber-700"
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

function LoadingState() {
    return (
        <div className="mx-auto max-w-7xl space-y-6 p-6" aria-label="Loading messaging settings">
            <Skeleton className="h-12 w-full max-w-lg" />
            <div className="grid gap-4 lg:grid-cols-2">
                <Skeleton className="h-64" />
                <Skeleton className="h-64" />
            </div>
            <Skeleton className="h-96" />
        </div>
    )
}

function CapabilityLine({ label, available }: { label: string; available: boolean }) {
    return (
        <div className="flex items-center justify-between gap-3 rounded-lg border bg-muted/20 px-3 py-2">
            <span className="text-sm font-medium">{label}</span>
            <StatusBadge status={available ? "ready" : "blocked"} label={available ? "Available" : "Unavailable"} />
        </div>
    )
}

function ReadinessSummary({ readiness }: { readiness: TwilioReadiness }) {
    return (
        <div className="grid gap-4 lg:grid-cols-2">
            <Card role="region" aria-label="Provider readiness">
                <CardHeader className="pb-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                            <CardTitle className="text-lg">Provider readiness</CardTitle>
                            <CardDescription>
                                Live Twilio account and carrier capability evidence.
                            </CardDescription>
                        </div>
                        <StatusBadge
                            status={readiness.provider.status}
                            label={READINESS_LABELS[readiness.provider.status]}
                        />
                    </div>
                </CardHeader>
                <CardContent className="space-y-3">
                    <div className="grid gap-2 sm:grid-cols-2">
                        <CapabilityLine label="SMS sending" available={readiness.provider.capabilities.send_sms} />
                        <CapabilityLine label="MMS sending" available={readiness.provider.capabilities.send_mms} />
                        <CapabilityLine label="SMS receiving" available={readiness.provider.capabilities.receive_sms} />
                        <CapabilityLine label="MMS receiving" available={readiness.provider.capabilities.receive_mms} />
                    </div>
                    <p className="text-xs text-muted-foreground">
                        Account {friendlyStatus(readiness.provider.account_status).toLowerCase()} · checked {formatEvidenceDate(readiness.provider.checked_at)}
                    </p>
                </CardContent>
            </Card>

            <Card role="region" aria-label="Local delivery operations">
                <CardHeader className="pb-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                            <CardTitle className="text-lg">Local delivery operations</CardTitle>
                            <CardDescription>
                                Application queue and reconciliation state, independent of Twilio.
                            </CardDescription>
                        </div>
                        <StatusBadge
                            status={readiness.local.queue.status}
                            label={READINESS_LABELS[readiness.local.queue.status]}
                        />
                    </div>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-lg border p-4">
                        <p className="text-sm text-muted-foreground">Delivery queue</p>
                        <p className="mt-1 text-2xl font-semibold">{readiness.local.queue.queued_count} queued</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                            {readiness.local.queue.processing_count} processing · {readiness.local.queue.failed_count} failed
                        </p>
                    </div>
                    <div className="rounded-lg border p-4">
                        <p className="text-sm text-muted-foreground">Reconciliation</p>
                        <p className="mt-1 text-2xl font-semibold">
                            {readiness.local.reconciliation.action_required_count} action required
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                            {readiness.local.reconciliation.unresolved_event_count} unresolved provider events
                        </p>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}

function ReadinessIssues({ readiness }: { readiness: TwilioReadiness }) {
    if (readiness.issues.length === 0) return null
    return (
        <Alert variant={readiness.issues.some((issue) => issue.severity === "error") ? "destructive" : "default"}>
            <AlertTriangleIcon aria-hidden="true" />
            <AlertTitle>Messaging readiness needs attention</AlertTitle>
            <AlertDescription>
                <ul className="list-disc space-y-1 pl-5">
                    {readiness.issues.map((issue) => (
                        <li key={`${issue.code}-${issue.route ?? "organization"}`}>{issue.message}</li>
                    ))}
                </ul>
            </AlertDescription>
        </Alert>
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
    const storedLabel = maskedValue ?? (configured ? "Stored securely" : "Not configured")
    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
                <Label htmlFor={id}>{label}</Label>
                <span className="font-mono text-xs text-muted-foreground">{storedLabel}</span>
            </div>
            <Input
                id={id}
                type={secret ? "password" : "text"}
                autoComplete="new-password"
                value={value}
                disabled={clearChecked}
                placeholder={maskedValue || configured ? "Leave blank to keep saved value" : `Enter ${label}`}
                onChange={(event) => onChange(event.target.value)}
            />
            {(maskedValue || configured) ? (
                <ClearStoredValue
                    label={clearLabel}
                    checked={clearChecked}
                    onCheckedChange={onClearChange}
                />
            ) : null}
        </div>
    )
}

function WebhookValue({ label, value }: { label: string; value: string }) {
    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(value)
            toast.success(`${label} copied`)
        } catch {
            toast.error(`Could not copy ${label.toLowerCase()}`)
        }
    }

    return (
        <div className="space-y-1.5">
            <Label>{label}</Label>
            <div className="flex min-w-0 items-center gap-2 rounded-md border bg-muted/30 px-3 py-2">
                <code className="min-w-0 flex-1 truncate text-xs">{value}</code>
                <Button type="button" variant="ghost" size="icon-sm" onClick={handleCopy} aria-label={`Copy ${label}`}>
                    <ClipboardIcon aria-hidden="true" />
                </Button>
            </div>
        </div>
    )
}

function RouteConfiguration({
    purpose,
    settings,
    draft,
    readiness,
    onChange,
}: {
    purpose: TwilioMessagingPurpose
    settings: TwilioRouteSettings
    draft: RouteDraft
    readiness: TwilioReadiness["provider"]["routes"][TwilioMessagingPurpose] | null
    onChange: (draft: RouteDraft) => void
}) {
    const titlePrefix = purpose === "operational" ? "Operational" : "Promotional"
    const providerEvidence = (
        settings.capability_evidence?.provider ?? {}
    ) as Record<string, unknown>
    const smsCapable = providerEvidence.sms === true
    const mmsCapable = providerEvidence.mms === true

    return (
        <Card>
            <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                        <CardTitle className="text-lg">{ROUTE_LABELS[purpose]}</CardTitle>
                        <CardDescription>
                            {purpose === "operational"
                                ? "Service, care-coordination, and one-to-one operational messages."
                                : "Consent-gated promotional messaging with an independent sender route."}
                        </CardDescription>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <StatusBadge status={settings.a2p_status} label={`A2P ${friendlyStatus(settings.a2p_status).toLowerCase()}`} />
                        <StatusBadge status={settings.advanced_opt_out_status} label={`Opt-out ${friendlyStatus(settings.advanced_opt_out_status).toLowerCase()}`} />
                    </div>
                </div>
            </CardHeader>
            <CardContent className="space-y-5">
                <div className="flex items-center justify-between gap-4 rounded-lg border bg-muted/20 p-3">
                    <div>
                        <Label htmlFor={`${purpose}-route-enabled`} className="text-sm font-medium">Enable {purpose} route</Label>
                        <p className="text-xs text-muted-foreground">Sending remains server-gated by consent and readiness.</p>
                    </div>
                    <Switch
                        id={`${purpose}-route-enabled`}
                        checked={draft.enabled}
                        onCheckedChange={(enabled) => onChange({ ...draft, enabled })}
                    />
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                    <CredentialField
                        id={`${purpose}-messaging-service-sid`}
                        label={`${titlePrefix} Messaging Service SID`}
                        value={draft.messagingServiceSid}
                        maskedValue={settings.messaging_service_sid_masked}
                        clearLabel={`Clear saved ${titlePrefix} Messaging Service SID`}
                        clearChecked={draft.clearMessagingServiceSid}
                        onChange={(messagingServiceSid) => onChange({ ...draft, messagingServiceSid })}
                        onClearChange={(clearMessagingServiceSid) => onChange({ ...draft, clearMessagingServiceSid, messagingServiceSid: "" })}
                    />
                    <CredentialField
                        id={`${purpose}-sender-phone`}
                        label={`${titlePrefix} sender number`}
                        value={draft.senderPhoneE164}
                        maskedValue={settings.sender_phone_masked}
                        clearLabel={`Clear saved ${titlePrefix} sender number`}
                        clearChecked={draft.clearSenderPhone}
                        onChange={(senderPhoneE164) => onChange({ ...draft, senderPhoneE164 })}
                        onClearChange={(clearSenderPhone) => onChange({ ...draft, clearSenderPhone, senderPhoneE164: "" })}
                    />
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">A2P campaign</p><p className="mt-1 font-medium">{friendlyStatus(settings.a2p_status)}</p></div>
                    <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Advanced Opt-Out</p><p className="mt-1 font-medium">{friendlyStatus(settings.advanced_opt_out_status)}</p></div>
                    <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Consent API</p><p className="mt-1 font-medium">{friendlyStatus(settings.consent_management_status)}</p></div>
                </div>

                <div className="flex flex-wrap items-center gap-2 text-xs">
                    <Badge variant="secondary">SMS {smsCapable ? "evidenced" : "not evidenced"}</Badge>
                    <Badge variant="secondary">MMS {mmsCapable ? "evidenced" : "not evidenced"}</Badge>
                    <Badge variant="secondary">Sender pool {providerEvidence.sender_in_pool === true ? "verified" : "not verified"}</Badge>
                    {readiness ? <StatusBadge status={readiness.status} label={`Route ${READINESS_LABELS[readiness.status].toLowerCase()}`} /> : null}
                </div>

                <Separator />
                <div className="grid gap-4 xl:grid-cols-2">
                    <WebhookValue label={`${titlePrefix} inbound webhook URL`} value={settings.inbound_webhook_url} />
                    <WebhookValue label={`${titlePrefix} status callback URL`} value={settings.status_callback_url} />
                </div>
                <p className="text-xs text-muted-foreground">Webhook route ID: <code>{settings.webhook_id}</code></p>
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

function OrganizationConnectionCard({
    settings,
    draft,
    credentialResult,
    isTesting,
    onEnabledChange,
    onCredentialChange,
    onCredentialClear,
    onTest,
}: {
    settings: TwilioSettings
    draft: SettingsDraft
    credentialResult: { valid: boolean; message: string } | null
    isTesting: boolean
    onEnabledChange: (enabled: boolean) => void
    onCredentialChange: (field: keyof CredentialDraft, value: string) => void
    onCredentialClear: (field: ClearableCredential, checked: boolean) => void
    onTest: () => void
}) {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                    <MessageSquareTextIcon className="size-5 text-primary" aria-hidden="true" />
                    Organization connection
                </CardTitle>
                <CardDescription>
                    Credentials are write-only. Blank fields preserve saved values; clearing requires an explicit choice.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
                <div className="flex items-center justify-between gap-4 rounded-lg border bg-muted/20 p-3">
                    <div>
                        <Label htmlFor="messaging-enabled" className="text-sm font-medium">Enable organization messaging</Label>
                        <p className="text-xs text-muted-foreground">Delivery remains blocked unless route, consent, and compliance gates pass.</p>
                    </div>
                    <Switch id="messaging-enabled" checked={draft.enabled} onCheckedChange={onEnabledChange} />
                </div>
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
                <div className="flex flex-wrap items-center gap-3">
                    <Button type="button" variant="outline" onClick={onTest} disabled={isTesting}>
                        {isTesting ? <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <ShieldCheckIcon aria-hidden="true" />}
                        Test connection
                    </Button>
                    <p className="text-xs text-muted-foreground">Read-only account verification; this never sends SMS or MMS.</p>
                </div>
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

type DisclosureField =
    | "legalMessagingBrand"
    | "supportContact"
    | "smsTermsUrl"
    | "privacyPolicyUrl"
    | "expectedFrequency"
    | "operationalDisclosure"
    | "promotionalDisclosure"

function ConsentDisclosureCard({
    draft,
    onChange,
}: {
    draft: SettingsDraft
    onChange: (field: DisclosureField, value: string) => void
}) {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-lg">Consent and disclosure record</CardTitle>
                <CardDescription>
                    Organization-level language shown wherever SMS consent is collected. Provider opt-out state does not replace local consent evidence.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
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
                <CardTitle className="text-lg">Compliance controls</CardTitle>
                <CardDescription>
                    Product flags remain subordinate to recorded counsel, compliance, and Twilio account evidence.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Twilio edition</p><p className="mt-1 font-medium">{friendlyStatus(settings.twilio_edition)}</p></div>
                    <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Counsel approval</p><p className="mt-1 text-sm font-medium">{formatEvidenceDate(settings.counsel_approved_at)}</p></div>
                    <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Compliance approval</p><p className="mt-1 text-sm font-medium">{formatEvidenceDate(settings.compliance_approved_at)}</p></div>
                    <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">BAA verification</p><p className="mt-1 text-sm font-medium">{formatEvidenceDate(settings.baa_verified_at)}</p></div>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                    <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
                        <div><Label htmlFor="compliance-toolkit-enabled">Compliance toolkit</Label><p className="text-xs text-muted-foreground">Require consent and suppression checks before dispatch.</p></div>
                        <Switch id="compliance-toolkit-enabled" checked={draft.complianceToolkitEnabled} onCheckedChange={onToolkitChange} />
                    </div>
                    <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
                        <div><Label htmlFor="phi-enabled">PHI messaging</Label><p className="text-xs text-muted-foreground">Requires HIPAA edition, verified BAA, and compliance approval.</p></div>
                        <Switch id="phi-enabled" checked={draft.phiEnabled} disabled={!phiPrerequisitesMet} onCheckedChange={onPhiChange} />
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}

function SettingsSaveBar({ version, isPending }: { version: number; isPending: boolean }) {
    return (
        <div className="sticky bottom-4 z-10 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-background/95 p-4 shadow-lg backdrop-blur supports-[backdrop-filter]:bg-background/85">
            <p className="text-xs text-muted-foreground">Configuration version {version}</p>
            <Button type="submit" disabled={isPending}>
                {isPending ? <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <ShieldCheckIcon aria-hidden="true" />}
                Save messaging settings
            </Button>
        </div>
    )
}

function SettingsForm({ settings, readiness }: { settings: TwilioSettings; readiness: TwilioReadiness | null }) {
    const [draft, setDraft] = useState(() => initialDraft(settings))
    const [formError, setFormError] = useState<string | null>(null)
    const [credentialResult, setCredentialResult] = useState<{ valid: boolean; message: string } | null>(null)
    const updateSettings = useUpdateTwilioSettings()
    const testCredentials = useTestTwilioCredentials()
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
        const request: TwilioCredentialTestRequest = {}
        if (draft.credentials.accountSid.trim()) request.account_sid = draft.credentials.accountSid.trim()
        if (draft.credentials.apiKeySid.trim()) request.api_key_sid = draft.credentials.apiKeySid.trim()
        if (draft.credentials.apiSecret) request.api_secret = draft.credentials.apiSecret
        if (draft.credentials.authToken) request.auth_token = draft.credentials.authToken
        const operationalServiceSid = draft.routes.operational.messagingServiceSid.trim()
        const promotionalServiceSid = draft.routes.promotional.messagingServiceSid.trim()
        const operationalSender = draft.routes.operational.senderPhoneE164.trim()
        const promotionalSender = draft.routes.promotional.senderPhoneE164.trim()
        if (operationalServiceSid || promotionalServiceSid || operationalSender || promotionalSender) {
            request.routes = {
                ...(operationalServiceSid || operationalSender
                    ? {
                          operational: {
                              ...(operationalServiceSid ? { messaging_service_sid: operationalServiceSid } : {}),
                              ...(operationalSender ? { sender_phone_e164: operationalSender } : {}),
                          },
                      }
                    : {}),
                ...(promotionalServiceSid || promotionalSender
                    ? {
                          promotional: {
                              ...(promotionalServiceSid ? { messaging_service_sid: promotionalServiceSid } : {}),
                              ...(promotionalSender ? { sender_phone_e164: promotionalSender } : {}),
                          },
                      }
                    : {}),
            }
        }

        try {
            const result = await testCredentials.mutateAsync(request)
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

    const handleSubmit = async (event: FormEvent) => {
        event.preventDefault()
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
            await updateSettings.mutateAsync(update)
            toast.success("Messaging settings saved")
        } catch (error) {
            setFormError(getErrorMessage(error, "Could not save messaging settings."))
        }
    }

    return (
        <form className="space-y-6" onSubmit={handleSubmit}>
            {formError ? (
                <Alert variant="destructive">
                    <AlertTriangleIcon aria-hidden="true" />
                    <AlertTitle>Settings were not saved</AlertTitle>
                    <AlertDescription>{formError}</AlertDescription>
                </Alert>
            ) : null}

            <OrganizationConnectionCard
                settings={settings}
                draft={draft}
                credentialResult={credentialResult}
                isTesting={testCredentials.isPending}
                onEnabledChange={(enabled) => setDraft((current) => ({ ...current, enabled }))}
                onCredentialChange={changeCredential}
                onCredentialClear={changeCredentialClear}
                onTest={() => void handleTestCredentials()}
            />

            <ConsentDisclosureCard
                draft={draft}
                onChange={(field, value) => setDraft((current) => ({ ...current, [field]: value }))}
            />

            <div className="grid gap-6 xl:grid-cols-2">
                <RouteConfiguration
                    purpose="operational"
                    settings={settings.routes.operational}
                    draft={draft.routes.operational}
                    readiness={readiness?.provider.routes.operational ?? null}
                    onChange={(operational) => setDraft((current) => ({ ...current, routes: { ...current.routes, operational } }))}
                />
                <RouteConfiguration
                    purpose="promotional"
                    settings={settings.routes.promotional}
                    draft={draft.routes.promotional}
                    readiness={readiness?.provider.routes.promotional ?? null}
                    onChange={(promotional) => setDraft((current) => ({ ...current, routes: { ...current.routes, promotional } }))}
                />
            </div>

            <ComplianceControlsCard
                settings={settings}
                draft={draft}
                onToolkitChange={(complianceToolkitEnabled) => setDraft((current) => ({ ...current, complianceToolkitEnabled }))}
                onPhiChange={(phiEnabled) => setDraft((current) => ({ ...current, phiEnabled }))}
            />

            <SettingsSaveBar version={settings.current_version} isPending={updateSettings.isPending} />
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
    const settingsQuery = useTwilioSettings(Boolean(user && canManageIntegrations))
    const readinessQuery = useTwilioReadiness(Boolean(user && canManageIntegrations))
    const permissionsLoading = Boolean(user && !isDeveloper && permissionsQuery.isLoading)
    const isRefreshing = settingsQuery.isFetching || readinessQuery.isFetching

    const refresh = () => {
        void Promise.all([settingsQuery.refetch(), readinessQuery.refetch()])
    }

    if (authLoading || permissionsLoading) return <LoadingState />

    if (!user || !canManageIntegrations) {
        return (
            <PermissionDeniedState
                title="Messaging settings are restricted"
                description="Only organization administrators and developers can manage Twilio credentials, routes, and compliance settings."
                secondaryHref="/settings/integrations"
                secondaryLabel="Back to integrations"
            />
        )
    }

    return (
        <div className="min-h-dvh bg-muted/10">
            <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
                <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
                    <div className="flex min-w-0 items-center gap-3">
                        <Button variant="ghost" size="icon" render={<Link href="/settings/integrations" />} aria-label="Back to integrations">
                            <ArrowLeftIcon aria-hidden="true" />
                        </Button>
                        <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                                <h1 className="text-2xl font-semibold">Messaging delivery</h1>
                                {readinessQuery.data ? (
                                    <StatusBadge status={readinessQuery.data.overall_status} label={READINESS_LABELS[readinessQuery.data.overall_status]} />
                                ) : null}
                            </div>
                            <p className="text-sm text-muted-foreground">
                                Twilio SMS/MMS routes, consent disclosures, and delivery readiness for {user.org_name}.
                            </p>
                        </div>
                    </div>
                    <Button type="button" variant="outline" size="sm" onClick={refresh} disabled={isRefreshing}>
                        <RefreshCwIcon className={isRefreshing ? "animate-spin motion-reduce:animate-none" : undefined} aria-hidden="true" />
                        Refresh
                    </Button>
                </div>
            </header>

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
                    <>
                        <ReadinessSummary readiness={readinessQuery.data} />
                        <ReadinessIssues readiness={readinessQuery.data} />
                    </>
                ) : readinessQuery.isError ? (
                    <Alert>
                        <AlertTriangleIcon aria-hidden="true" />
                        <AlertTitle>Readiness evidence is temporarily unavailable</AlertTitle>
                        <AlertDescription>Settings remain editable. Refresh before enabling delivery.</AlertDescription>
                    </Alert>
                ) : null}

                {settingsQuery.data ? (
                    <SettingsForm
                        key={`twilio-settings-${settingsQuery.data.current_version}`}
                        settings={settingsQuery.data}
                        readiness={readinessQuery.data ?? null}
                    />
                ) : null}
            </main>
        </div>
    )
}
