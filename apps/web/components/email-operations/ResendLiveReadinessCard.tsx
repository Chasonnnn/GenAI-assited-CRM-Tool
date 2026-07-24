"use client"

import {
    AlertCircleIcon,
    CheckCircle2Icon,
    CircleHelpIcon,
    Clock3Icon,
    Loader2Icon,
    RadarIcon,
    RefreshCwIcon,
    ShieldAlertIcon,
} from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime, formatRelativeTime } from "@/lib/formatters"
import type {
    ResendReadinessCapabilityStatus,
    ResendReadinessEnvelope,
    ResendReadinessIssueCode,
    ResendReadinessSnapshot,
} from "@/lib/types/resend-readiness"

type BadgeVariant = "default" | "secondary" | "destructive" | "outline"

const CAPABILITY_LABELS: Record<ResendReadinessCapabilityStatus, string> = {
    ready: "Ready",
    needs_attention: "Needs attention",
    limited: "Limited visibility",
    unknown: "Unknown",
    not_configured: "Not configured",
}

const CAPABILITY_VARIANTS: Record<
    ResendReadinessCapabilityStatus,
    BadgeVariant
> = {
    ready: "default",
    needs_attention: "destructive",
    limited: "secondary",
    unknown: "secondary",
    not_configured: "outline",
}

const ISSUE_LABELS: Record<ResendReadinessIssueCode, string> = {
    admission_unavailable: "Readiness checks are temporarily busy",
    credential_rejected: "Resend rejected the stored credential",
    credential_unavailable: "No usable Resend credential is available",
    delivery_events_missing: "Delivery events are not enabled",
    domain_not_verified: "Sending domain is not fully verified",
    engagement_events_missing: "Open and click events are not enabled",
    invalid_provider_response: "Resend returned an unexpected response",
    limited_visibility: "API key has restricted visibility",
    provider_unavailable: "Resend is temporarily unavailable",
    sending_disabled: "Sending is disabled for the configured domain",
    snapshot_stale: "Readiness result is out of date",
    timeout: "Resend did not respond in time",
    webhook_disabled: "The matching webhook is disabled",
    webhook_missing: "No matching webhook was found",
}

type ResendLiveReadinessCardProps = {
    envelope?: ResendReadinessEnvelope | undefined
    isLoading?: boolean
    isError?: boolean
    canCheck: boolean
    isCheckPending?: boolean
    isCheckError?: boolean
    onCheck: () => void
}

type ResendCompactReadinessSummaryProps = {
    envelope: ResendReadinessEnvelope | null
    isLoading: boolean
    isError: boolean
    isCheckPending: boolean
    isCheckError: boolean
    onCheck: () => void
}

type ResendOperationsReadinessSummaryProps = {
    envelope: ResendReadinessEnvelope | undefined
    isLoading: boolean
    isError: boolean
    canCheck: boolean
    isCheckPending: boolean
    isCheckError: boolean
    onCheck: () => void
}

function getIssueLabel(code: string): string {
    return ISSUE_LABELS[code as ResendReadinessIssueCode] ??
        "Resend readiness needs review"
}

function getOverallLabel(snapshot: ResendReadinessSnapshot): string {
    if (snapshot.freshness === "never_checked") return "Not checked"
    if (snapshot.freshness === "stale") return "Stale"
    return CAPABILITY_LABELS[snapshot.overall_status]
}

function getOverallVariant(snapshot: ResendReadinessSnapshot): BadgeVariant {
    if (snapshot.freshness === "stale") return "secondary"
    return CAPABILITY_VARIANTS[snapshot.overall_status]
}

function CapabilityStatus({
    testId,
    label,
    status,
}: {
    testId: string
    label: string
    status: ResendReadinessCapabilityStatus
}) {
    const Icon =
        status === "ready"
            ? CheckCircle2Icon
            : status === "needs_attention"
              ? AlertCircleIcon
              : status === "unknown"
                ? CircleHelpIcon
                : ShieldAlertIcon

    return (
        <div
            data-testid={testId}
            className="flex min-w-0 items-center justify-between gap-3 rounded-lg border bg-background px-3 py-3"
        >
            <div className="flex min-w-0 items-center gap-2">
                <Icon
                    className={
                        status === "ready"
                            ? "size-4 shrink-0 text-primary"
                            : status === "needs_attention"
                              ? "size-4 shrink-0 text-destructive"
                              : "size-4 shrink-0 text-muted-foreground"
                    }
                    aria-hidden="true"
                />
                <span className="truncate text-sm font-medium">{label}</span>
            </div>
            <Badge
                className="shrink-0"
                variant={CAPABILITY_VARIANTS[status]}
            >
                {CAPABILITY_LABELS[status]}
            </Badge>
        </div>
    )
}

function ReadinessStateAlert({
    envelope,
}: {
    envelope: ResendReadinessEnvelope
}) {
    const snapshot = envelope.last_snapshot

    if (envelope.check_status === "queued") {
        return (
            <Alert>
                <Clock3Icon aria-hidden="true" />
                <AlertTitle>Check queued</AlertTitle>
                <AlertDescription>
                    The previous saved result remains visible while this read-only check
                    waits to run.
                </AlertDescription>
            </Alert>
        )
    }

    if (envelope.check_status === "running") {
        return (
            <Alert>
                <Loader2Icon
                    className="animate-spin motion-reduce:animate-none"
                    aria-hidden="true"
                />
                <AlertTitle>Checking Resend</AlertTitle>
                <AlertDescription>
                    The previous saved result remains visible until the check finishes.
                </AlertDescription>
            </Alert>
        )
    }

    if (snapshot.freshness === "never_checked") {
        return (
            <Alert>
                <CircleHelpIcon aria-hidden="true" />
                <AlertTitle>No live check yet</AlertTitle>
                <AlertDescription>
                    Run a read-only check to verify the domain and webhook settings in
                    Resend.
                </AlertDescription>
            </Alert>
        )
    }

    if (snapshot.freshness === "stale") {
        return (
            <Alert>
                <Clock3Icon aria-hidden="true" />
                <AlertTitle>Saved result is stale</AlertTitle>
                <AlertDescription>
                    Run another check before relying on this provider configuration.
                </AlertDescription>
            </Alert>
        )
    }

    if (snapshot.probe_status === "limited") {
        return (
            <Alert>
                <ShieldAlertIcon aria-hidden="true" />
                <AlertTitle>Limited provider visibility</AlertTitle>
                <AlertDescription>
                    The API key can send email but cannot inspect every domain or webhook
                    setting.
                </AlertDescription>
            </Alert>
        )
    }

    if (snapshot.probe_status === "failed") {
        return (
            <Alert variant="destructive">
                <AlertCircleIcon aria-hidden="true" />
                <AlertTitle>Live check failed</AlertTitle>
                <AlertDescription>
                    Review the controlled issues below, then run the check again.
                </AlertDescription>
            </Alert>
        )
    }

    return null
}

function CheckButtonLabel({
    envelope,
    isPending,
}: {
    envelope: ResendReadinessEnvelope
    isPending: boolean
}) {
    if (isPending) return "Starting check…"
    if (envelope.check_status === "queued") return "Check queued"
    if (envelope.check_status === "running") return "Checking Resend…"
    return "Check Resend now"
}

function getCompactStateTitle(
    snapshot: ResendReadinessSnapshot,
    subject = "Shared sender",
): string | null {
    if (snapshot.freshness === "never_checked") {
        return `${subject} has not been checked`
    }
    if (snapshot.freshness === "stale") {
        return `${subject} result is stale`
    }
    if (snapshot.probe_status === "limited") {
        return `${subject} visibility is limited`
    }
    if (
        snapshot.probe_status === "failed" ||
        snapshot.overall_status === "needs_attention"
    ) {
        return `${subject} needs attention`
    }
    return null
}

function getCompactCapabilityLabel(
    label: string,
    status: ResendReadinessCapabilityStatus,
): string {
    return `${label} ${CAPABILITY_LABELS[status].toLowerCase()}`
}

function ReadinessCardSkeleton() {
    return (
        <Card aria-label="Loading live Resend readiness">
            <CardHeader className="border-b">
                <div className="space-y-2">
                    <Skeleton className="h-5 w-48" />
                    <Skeleton className="h-4 w-80 max-w-full" />
                </div>
            </CardHeader>
            <CardContent className="space-y-4 pt-6">
                <Skeleton className="h-16 w-full" />
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                    {[0, 1, 2, 3, 4].map((item) => (
                        <Skeleton key={item} className="h-12 w-full" />
                    ))}
                </div>
            </CardContent>
        </Card>
    )
}

export function ResendLiveReadinessCard({
    envelope,
    isLoading = false,
    isError = false,
    canCheck,
    isCheckPending = false,
    isCheckError = false,
    onCheck,
}: ResendLiveReadinessCardProps) {
    if (isLoading && !envelope) {
        return <ReadinessCardSkeleton />
    }

    if (!envelope) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>
                        <h2 className="flex items-center gap-2">
                            <RadarIcon
                                className="size-5 text-primary"
                                aria-hidden="true"
                            />
                            Live Resend readiness
                        </h2>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <Alert variant={isError ? "destructive" : "default"}>
                        <AlertCircleIcon aria-hidden="true" />
                        <AlertTitle>Live readiness is unavailable</AlertTitle>
                        <AlertDescription>
                            Refresh the saved operations data and try again.
                        </AlertDescription>
                    </Alert>
                </CardContent>
            </Card>
        )
    }

    const snapshot = envelope.last_snapshot
    const isCheckActive =
        envelope.check_status === "queued" ||
        envelope.check_status === "running" ||
        isCheckPending
    const issueLabels = Array.from(
        new Set(snapshot.issue_codes.map((code) => getIssueLabel(code))),
    )

    return (
        <Card>
            <CardHeader className="border-b">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                        <CardTitle>
                            <h2 className="flex items-center gap-2">
                                <RadarIcon
                                    className="size-5 text-primary"
                                    aria-hidden="true"
                                />
                                Live Resend readiness
                            </h2>
                        </CardTitle>
                        <CardDescription className="mt-1 max-w-3xl">
                            Checks the configured domain and webhook directly in Resend.
                            The check is read-only and sends no email.
                        </CardDescription>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={getOverallVariant(snapshot)}>
                            {getOverallLabel(snapshot)}
                        </Badge>
                        {canCheck ? (
                            <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                disabled={isCheckActive}
                                onClick={onCheck}
                            >
                                {isCheckActive ? (
                                    <RefreshCwIcon
                                        className="animate-spin motion-reduce:animate-none"
                                        aria-hidden="true"
                                    />
                                ) : (
                                    <RadarIcon aria-hidden="true" />
                                )}
                                <CheckButtonLabel
                                    envelope={envelope}
                                    isPending={isCheckPending}
                                />
                            </Button>
                        ) : null}
                    </div>
                </div>
            </CardHeader>
            <CardContent className="space-y-5 pt-6">
                <ReadinessStateAlert envelope={envelope} />

                {isCheckError ? (
                    <Alert variant="destructive">
                        <AlertCircleIcon aria-hidden="true" />
                        <AlertTitle>Couldn’t start the live check</AlertTitle>
                        <AlertDescription>
                            The saved result is unchanged. Try again in a moment.
                        </AlertDescription>
                    </Alert>
                ) : null}

                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                    <CapabilityStatus
                        testId="live-readiness-domain"
                        label="Domain"
                        status={snapshot.domain_status}
                    />
                    <CapabilityStatus
                        testId="live-readiness-sending"
                        label="Sending"
                        status={snapshot.sending_status}
                    />
                    <CapabilityStatus
                        testId="live-readiness-webhook"
                        label="Webhook"
                        status={snapshot.webhook_status}
                    />
                    <CapabilityStatus
                        testId="live-readiness-delivery"
                        label="Delivery events"
                        status={snapshot.delivery_tracking_status}
                    />
                    <CapabilityStatus
                        testId="live-readiness-engagement"
                        label="Open and click events"
                        status={snapshot.engagement_tracking_status}
                    />
                </div>

                <div className="grid gap-4 rounded-xl border bg-muted/30 p-4 sm:grid-cols-2 lg:grid-cols-4">
                    <div>
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            Domains
                        </p>
                        <p className="mt-1 text-sm font-medium">
                            {snapshot.verified_domain_count} verified{" "}
                            {snapshot.verified_domain_count === 1 ? "domain" : "domains"}
                        </p>
                    </div>
                    <div>
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            Webhooks
                        </p>
                        <p className="mt-1 text-sm font-medium">
                            {snapshot.enabled_webhook_count} enabled{" "}
                            {snapshot.enabled_webhook_count === 1
                                ? "webhook"
                                : "webhooks"}
                        </p>
                    </div>
                    <div>
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            Last checked
                        </p>
                        <p className="mt-1 text-sm font-medium">
                            {snapshot.checked_at
                                ? formatDateTime(snapshot.checked_at, "Unknown")
                                : "Not checked"}
                        </p>
                        {snapshot.checked_at ? (
                            <p className="text-xs text-muted-foreground">
                                {formatRelativeTime(snapshot.checked_at, "Recently")}
                            </p>
                        ) : null}
                    </div>
                    <div>
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            Last successful check
                        </p>
                        <p className="mt-1 text-sm font-medium">
                            {snapshot.last_success_at
                                ? formatDateTime(snapshot.last_success_at, "Unknown")
                                : "No successful check"}
                        </p>
                    </div>
                </div>

                {issueLabels.length > 0 ? (
                    <div>
                        <h3 className="text-sm font-semibold">What needs attention</h3>
                        <ul className="mt-2 flex flex-wrap gap-2">
                            {issueLabels.map((label) => (
                                <li key={label}>
                                    <Badge variant="outline">{label}</Badge>
                                </li>
                            ))}
                        </ul>
                    </div>
                ) : null}

                <p className="text-xs text-muted-foreground">
                    Refresh reloads this saved result without contacting Resend.
                </p>
            </CardContent>
        </Card>
    )
}

export function ResendOperationsReadinessSummary({
    envelope,
    isLoading,
    isError,
    canCheck,
    isCheckPending,
    isCheckError,
    onCheck,
}: ResendOperationsReadinessSummaryProps) {
    if (isLoading && !envelope) {
        return (
            <section
                aria-label="Email readiness"
                className="rounded-xl border bg-card p-5"
            >
                <div className="space-y-3" aria-label="Loading email readiness">
                    <Skeleton className="h-5 w-52" />
                    <Skeleton className="h-8 w-full" />
                    <Skeleton className="h-4 w-44" />
                </div>
            </section>
        )
    }

    if (!envelope) {
        return (
            <section aria-label="Email readiness">
                <Alert variant={isError ? "destructive" : "default"}>
                    <AlertCircleIcon aria-hidden="true" />
                    <AlertTitle>Email readiness is unavailable</AlertTitle>
                    <AlertDescription>
                        Refresh the saved operations data and try again.
                    </AlertDescription>
                </Alert>
            </section>
        )
    }

    const snapshot = envelope.last_snapshot
    const stateTitle = getCompactStateTitle(snapshot, "Email delivery")
    const isCheckActive =
        envelope.check_status === "queued" ||
        envelope.check_status === "running" ||
        isCheckPending
    const issueLabels = Array.from(
        new Set(snapshot.issue_codes.map((code) => getIssueLabel(code))),
    )

    return (
        <section
            aria-label="Email readiness"
            className="rounded-xl border bg-card p-5 shadow-sm"
        >
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                        <RadarIcon className="size-4 text-primary" aria-hidden="true" />
                        <h2 className="font-semibold">
                            Email delivery readiness
                        </h2>
                        <Badge variant={getOverallVariant(snapshot)}>
                            {getOverallLabel(snapshot)}
                        </Badge>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Live provider status with locally saved evidence.
                    </p>
                </div>
                {canCheck ? (
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={isCheckActive}
                        onClick={onCheck}
                    >
                        {isCheckActive ? (
                            <RefreshCwIcon
                                className="animate-spin motion-reduce:animate-none"
                                aria-hidden="true"
                            />
                        ) : (
                            <RadarIcon aria-hidden="true" />
                        )}
                        <CheckButtonLabel
                            envelope={envelope}
                            isPending={isCheckPending}
                        />
                    </Button>
                ) : null}
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
                <Badge variant="outline">
                    {getCompactCapabilityLabel("Domain", snapshot.domain_status)}
                </Badge>
                <Badge variant="outline">
                    {getCompactCapabilityLabel("Sending", snapshot.sending_status)}
                </Badge>
                <Badge variant="outline">
                    {getCompactCapabilityLabel("Webhook", snapshot.webhook_status)}
                </Badge>
                <Badge variant="outline">
                    {getCompactCapabilityLabel(
                        "Delivery",
                        snapshot.delivery_tracking_status,
                    )}
                </Badge>
                <Badge variant="outline">
                    {getCompactCapabilityLabel(
                        "Engagement",
                        snapshot.engagement_tracking_status,
                    )}
                </Badge>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <p>
                    Last checked{" "}
                    {snapshot.checked_at ? (
                        <time dateTime={snapshot.checked_at}>
                            {formatDateTime(snapshot.checked_at, "Unknown")}
                        </time>
                    ) : (
                        "Not checked"
                    )}
                </p>
                <p>The check is read-only and sends no email.</p>
            </div>

            {stateTitle ? (
                <Alert
                    className="mt-4"
                    variant={
                        snapshot.probe_status === "failed" ||
                        snapshot.overall_status === "needs_attention"
                            ? "destructive"
                            : "default"
                    }
                >
                    <ShieldAlertIcon aria-hidden="true" />
                    <AlertTitle>{stateTitle}</AlertTitle>
                    {issueLabels.length > 0 ? (
                        <AlertDescription>
                            {issueLabels.join(". ")}. Open Diagnostics for the saved
                            provider evidence.
                        </AlertDescription>
                    ) : null}
                </Alert>
            ) : null}

            {isCheckError ? (
                <Alert className="mt-4" variant="destructive">
                    <AlertCircleIcon aria-hidden="true" />
                    <AlertTitle>Couldn’t start the live check</AlertTitle>
                    <AlertDescription>
                        The saved readiness is unchanged. Try again in a moment.
                    </AlertDescription>
                </Alert>
            ) : null}
        </section>
    )
}

export function ResendCompactReadinessSummary({
    envelope,
    isLoading,
    isError,
    isCheckPending,
    isCheckError,
    onCheck,
}: ResendCompactReadinessSummaryProps) {
    if (isLoading && !envelope) {
        return (
            <div
                data-testid="platform-email-readiness"
                aria-label="Loading shared sender readiness"
                className="space-y-3 rounded-lg border bg-muted/30 p-4"
            >
                <Skeleton className="h-5 w-48" />
                <Skeleton className="h-8 w-full" />
            </div>
        )
    }

    if (!envelope) {
        return (
            <Alert
                data-testid="platform-email-readiness"
                variant={isError ? "destructive" : "default"}
            >
                <AlertCircleIcon aria-hidden="true" />
                <AlertTitle>Shared sender status unavailable</AlertTitle>
                <AlertDescription>
                    Invitation creation remains available. Refresh this page to reload
                    the saved status.
                </AlertDescription>
            </Alert>
        )
    }

    const snapshot = envelope.last_snapshot
    const stateTitle = getCompactStateTitle(snapshot)
    const isCheckActive =
        envelope.check_status === "queued" ||
        envelope.check_status === "running" ||
        isCheckPending
    const issueLabels = Array.from(
        new Set(snapshot.issue_codes.map((code) => getIssueLabel(code))),
    )

    return (
        <div
            data-testid="platform-email-readiness"
            className="space-y-3 rounded-lg border bg-muted/30 p-4"
        >
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                    <div className="flex items-center gap-2">
                        <RadarIcon className="size-4 text-primary" aria-hidden="true" />
                        <p className="text-sm font-semibold">Shared sender readiness</p>
                        <Badge variant={getOverallVariant(snapshot)}>
                            {getOverallLabel(snapshot)}
                        </Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                        The provider check is read-only and sends no email.
                    </p>
                </div>
                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={isCheckActive}
                    onClick={onCheck}
                >
                    {isCheckActive ? (
                        <RefreshCwIcon
                            className="animate-spin motion-reduce:animate-none"
                            aria-hidden="true"
                        />
                    ) : (
                        <RadarIcon aria-hidden="true" />
                    )}
                    <CheckButtonLabel
                        envelope={envelope}
                        isPending={isCheckPending}
                    />
                </Button>
            </div>

            <div className="flex flex-wrap gap-2">
                <Badge variant="outline">
                    {getCompactCapabilityLabel("Domain", snapshot.domain_status)}
                </Badge>
                <Badge variant="outline">
                    {getCompactCapabilityLabel("Sending", snapshot.sending_status)}
                </Badge>
                <Badge variant="outline">
                    {getCompactCapabilityLabel("Webhook", snapshot.webhook_status)}
                </Badge>
            </div>

            {stateTitle ? (
                <Alert
                    variant={
                        snapshot.probe_status === "failed" ||
                        snapshot.overall_status === "needs_attention"
                            ? "destructive"
                            : "default"
                    }
                >
                    <ShieldAlertIcon aria-hidden="true" />
                    <AlertTitle>{stateTitle}</AlertTitle>
                    {issueLabels.length > 0 ? (
                        <AlertDescription>
                            <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
                                {issueLabels.map((label) => (
                                    <li key={label}>{label}</li>
                                ))}
                            </ul>
                        </AlertDescription>
                    ) : null}
                </Alert>
            ) : null}

            {isCheckError ? (
                <Alert variant="destructive">
                    <AlertCircleIcon aria-hidden="true" />
                    <AlertTitle>Couldn’t start the sender check</AlertTitle>
                    <AlertDescription>
                        The saved status is unchanged. Try again in a moment.
                    </AlertDescription>
                </Alert>
            ) : null}

            <p className="text-xs text-muted-foreground">
                This status is advisory; invitation creation remains available.
            </p>
        </div>
    )
}
