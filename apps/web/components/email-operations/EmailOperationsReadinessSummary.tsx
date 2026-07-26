"use client"

import {
    AlertCircleIcon,
    RadarIcon,
    RefreshCwIcon,
    ShieldAlertIcon,
} from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime } from "@/lib/formatters"
import type {
    ResendReadinessCapabilityStatus,
    ResendReadinessEnvelope,
    ResendReadinessSnapshot,
} from "@/lib/types/resend-readiness"

type BadgeVariant = "default" | "secondary" | "destructive" | "outline"

type EmailReadinessLoadState = "ready" | "loading" | "error"
type EmailReadinessCheckState = "idle" | "pending" | "error"

type EmailOperationsReadinessSummaryProps = {
    envelope: ResendReadinessEnvelope | undefined
    state: {
        load: EmailReadinessLoadState
        check: EmailReadinessCheckState
    }
    onCheck?: () => void
}

const CAPABILITY_LABELS: Record<ResendReadinessCapabilityStatus, string> = {
    ready: "Ready",
    needs_attention: "Needs attention",
    limited: "Limited visibility",
    unknown: "Unknown",
    not_configured: "Not configured",
}

const OVERALL_VARIANTS: Record<
    ResendReadinessCapabilityStatus,
    BadgeVariant
> = {
    ready: "default",
    needs_attention: "destructive",
    limited: "secondary",
    unknown: "secondary",
    not_configured: "outline",
}

function getOverallLabel(snapshot: ResendReadinessSnapshot): string {
    if (snapshot.freshness === "never_checked") return "Not checked"
    if (snapshot.freshness === "stale") return "Stale"
    return CAPABILITY_LABELS[snapshot.overall_status]
}

function getOverallVariant(snapshot: ResendReadinessSnapshot): BadgeVariant {
    if (snapshot.freshness === "stale") return "secondary"
    return OVERALL_VARIANTS[snapshot.overall_status]
}

function getStateTitle(snapshot: ResendReadinessSnapshot): string | null {
    if (snapshot.freshness === "never_checked") {
        return "Email delivery has not been checked"
    }
    if (snapshot.freshness === "stale") {
        return "Email delivery result is stale"
    }
    if (snapshot.probe_status === "limited") {
        return "Email delivery visibility is limited"
    }
    if (
        snapshot.probe_status === "failed" ||
        snapshot.overall_status === "needs_attention"
    ) {
        return "Email delivery needs attention"
    }
    return null
}

function getCheckLabel(
    envelope: ResendReadinessEnvelope,
    checkState: EmailReadinessCheckState,
): string {
    if (checkState === "pending") return "Starting check…"
    if (envelope.check_status === "queued") return "Check queued"
    if (envelope.check_status === "running") return "Checking Resend…"
    return "Check Resend now"
}

export function EmailOperationsReadinessSummary({
    envelope,
    state,
    onCheck,
}: EmailOperationsReadinessSummaryProps) {
    if (state.load === "loading" && !envelope) {
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
                <Alert variant={state.load === "error" ? "destructive" : "default"}>
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
    const stateTitle = getStateTitle(snapshot)
    const isCheckActive =
        envelope.check_status === "queued" ||
        envelope.check_status === "running" ||
        state.check === "pending"
    const capabilities = [
        { label: "Domain", status: snapshot.domain_status },
        { label: "Sending", status: snapshot.sending_status },
        { label: "Webhook", status: snapshot.webhook_status },
        { label: "Delivery", status: snapshot.delivery_tracking_status },
        { label: "Engagement", status: snapshot.engagement_tracking_status },
    ]

    return (
        <section
            aria-label="Email readiness"
            className="rounded-xl border bg-card p-5 shadow-sm"
        >
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                        <RadarIcon className="size-4 text-primary" aria-hidden="true" />
                        <h2 className="font-semibold">Email delivery readiness</h2>
                        <Badge variant={getOverallVariant(snapshot)}>
                            {getOverallLabel(snapshot)}
                        </Badge>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Live provider status with locally saved evidence.
                    </p>
                </div>
                {onCheck ? (
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
                        {getCheckLabel(envelope, state.check)}
                    </Button>
                ) : null}
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
                {capabilities.map(({ label, status }) => (
                    <Badge key={label} variant="outline">
                        {label} {CAPABILITY_LABELS[status].toLowerCase()}
                    </Badge>
                ))}
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
                    {snapshot.issue_codes.length > 0 ? (
                        <AlertDescription>
                            {snapshot.issue_codes.length} provider{" "}
                            {snapshot.issue_codes.length === 1
                                ? "check requires"
                                : "checks require"}{" "}
                            review. Open Diagnostics for the saved evidence.
                        </AlertDescription>
                    ) : null}
                </Alert>
            ) : null}

            {state.check === "error" ? (
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
