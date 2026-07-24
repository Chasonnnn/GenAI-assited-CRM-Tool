"use client"

import { useState } from "react"
import {
    ActivityIcon,
    AlertCircleIcon,
    AlertTriangleIcon,
    ArrowLeftIcon,
    CheckCircle2Icon,
    CircleHelpIcon,
    InfoIcon,
    MailCheckIcon,
    RefreshCwIcon,
    SendIcon,
    ShieldCheckIcon,
    XCircleIcon,
} from "lucide-react"

import Link from "@/components/app-link"
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "@/components/ui/accordion"
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
import {
    Empty,
    EmptyDescription,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { formatDateTime, formatRelativeTime } from "@/lib/formatters"
import type {
    EmailOperationMessage,
    EmailOperationsCheckStatus,
    EmailOperationsReadiness,
    EmailOperationsReadinessCheck,
    EmailOperationsSummary24h,
} from "@/lib/api/email-operations"
import {
    useEmailOperationsMessages,
    useEmailOperationsLiveReadiness,
    useEmailOperationsReadiness,
    useEmailReconciliationCases,
    useRequestEmailOperationsReadinessCheck,
} from "@/lib/hooks/use-email-operations"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { EmailOperationDetailSheet } from "./EmailOperationDetailSheet"
import { EmailReconciliationQueue } from "./EmailReconciliationQueue"
import {
    ResendLiveReadinessCard,
    ResendOperationsReadinessSummary,
} from "./ResendLiveReadinessCard"
import {
    getCheckStatusLabel,
    getMessageStatusLabel,
    getOverallLabel,
    getProviderLabel,
    getProviderScopeLabel,
    getReadinessCheckLabel,
    getWebhookActivityLabel,
} from "./email-operation-labels"

type BadgeVariant = "default" | "secondary" | "destructive" | "outline"

const OVERALL_VARIANTS: Record<
    EmailOperationsReadiness["overall"],
    BadgeVariant
> = {
    ready: "default",
    needs_attention: "destructive",
    not_configured: "secondary",
}

const CHECK_VARIANTS: Record<EmailOperationsCheckStatus, BadgeVariant> = {
    pass: "default",
    fail: "destructive",
    unknown: "secondary",
    not_applicable: "outline",
}

const ACTION_NEEDED_MESSAGE_STATUSES = new Set([
    "failed",
    "bounced",
    "complained",
    "suppressed",
    "reconciliation_required",
])

function CheckStatusIcon({ status }: { status: EmailOperationsCheckStatus }) {
    if (status === "pass") {
        return <CheckCircle2Icon className="size-4 text-primary" aria-hidden="true" />
    }
    if (status === "fail") {
        return <XCircleIcon className="size-4 text-destructive" aria-hidden="true" />
    }
    if (status === "unknown") {
        return <CircleHelpIcon className="size-4 text-muted-foreground" aria-hidden="true" />
    }
    return <InfoIcon className="size-4 text-muted-foreground" aria-hidden="true" />
}

function CapabilityCard({
    testId,
    title,
    available,
    availableDetail,
    unavailableDetail,
    Icon,
}: {
    testId: string
    title: string
    available: boolean
    availableDetail: string
    unavailableDetail: string
    Icon: typeof SendIcon
}) {
    return (
        <div
            data-testid={testId}
            className="rounded-xl border bg-background p-4 shadow-xs"
        >
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                    <div className="flex size-9 items-center justify-center rounded-lg bg-muted">
                        <Icon className="size-4" aria-hidden="true" />
                    </div>
                    <div>
                        <p className="font-medium">{title}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                            {available ? availableDetail : unavailableDetail}
                        </p>
                    </div>
                </div>
                <Badge variant={available ? "default" : "destructive"}>
                    {available ? "Available" : "Unavailable"}
                </Badge>
            </div>
        </div>
    )
}

function WebhookActivityCard({
    readiness,
}: {
    readiness: EmailOperationsReadiness
}) {
    return (
        <div className="rounded-xl border bg-background p-4 shadow-xs">
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                    <div className="flex size-9 items-center justify-center rounded-lg bg-muted">
                        <ActivityIcon className="size-4" aria-hidden="true" />
                    </div>
                    <div>
                        <p className="font-medium">Recent webhook activity</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                            {readiness.last_webhook_received_at
                                ? `Last received ${formatRelativeTime(
                                      readiness.last_webhook_received_at,
                                      "recently",
                                  )}`
                                : "No provider event has been observed in this window."}
                        </p>
                    </div>
                </div>
                <Badge
                    variant={
                        readiness.recent_webhook_activity === "fail"
                            ? "destructive"
                            : "secondary"
                    }
                >
                    {getWebhookActivityLabel(readiness.recent_webhook_activity)}
                </Badge>
            </div>
        </div>
    )
}

function ReadinessCheckRow({
    check,
}: {
    check: EmailOperationsReadinessCheck
}) {
    return (
        <li className="flex items-start gap-3 rounded-lg border bg-background p-3">
            <CheckStatusIcon status={check.status} />
            <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-medium">
                        {getReadinessCheckLabel(check.key)}
                    </p>
                    <Badge variant={CHECK_VARIANTS[check.status]}>
                        {getCheckStatusLabel(check.status)}
                    </Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{check.detail}</p>
                {check.observed_at ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                        Evidence recorded {formatDateTime(check.observed_at, "Unknown")}
                    </p>
                ) : null}
            </div>
        </li>
    )
}

function ReadinessSection({
    readiness,
}: {
    readiness: EmailOperationsReadiness
}) {
    return (
        <Card>
            <CardHeader className="border-b">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                        <CardTitle>
                            <h2 className="flex items-center gap-2">
                                <ShieldCheckIcon
                                    className="size-5 text-primary"
                                    aria-hidden="true"
                                />
                                Stored configuration and route activity
                            </h2>
                        </CardTitle>
                        <CardDescription className="mt-1">
                            Send capability, tracking capability, and observed provider evidence
                            are evaluated independently.
                        </CardDescription>
                    </div>
                    <Badge variant={OVERALL_VARIANTS[readiness.overall]}>
                        {getOverallLabel(readiness.overall)}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="space-y-5 pt-6">
                <div className="grid gap-3 lg:grid-cols-3">
                    <CapabilityCard
                        testId="sending-readiness"
                        title="Sending"
                        available={readiness.can_send}
                        availableDetail="Persisted sender and credential evidence is complete."
                        unavailableDetail="Sender or credential evidence needs attention."
                        Icon={SendIcon}
                    />
                    <CapabilityCard
                        testId="tracking-readiness"
                        title="Tracking"
                        available={readiness.can_track}
                        availableDetail="Domain and webhook signing evidence is complete."
                        unavailableDetail="Domain or webhook signing evidence needs attention."
                        Icon={ShieldCheckIcon}
                    />
                    <WebhookActivityCard readiness={readiness} />
                </div>

                <div className="grid gap-4 rounded-xl border bg-muted/30 p-4 md:grid-cols-3">
                    <div>
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            Provider
                        </p>
                        <p className="mt-1 font-medium">
                            {getProviderLabel(readiness.provider)}
                        </p>
                    </div>
                    <div>
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            Credential scope
                        </p>
                        <p className="mt-1 font-medium">
                            {getProviderScopeLabel(readiness.provider_scope)}
                        </p>
                    </div>
                    <div>
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            Stored provider account
                        </p>
                        <p className="mt-1 break-all font-mono text-sm">
                            {readiness.provider_account_id ?? "Not recorded"}
                        </p>
                    </div>
                </div>

                <div>
                    <h3 className="text-sm font-semibold">Readiness checks</h3>
                    <ul className="mt-3 grid gap-3 lg:grid-cols-2">
                        {readiness.checks.map((check) => (
                            <ReadinessCheckRow key={check.key} check={check} />
                        ))}
                    </ul>
                </div>
            </CardContent>
        </Card>
    )
}

function MetricCard({
    testId,
    label,
    value,
    detail,
}: {
    testId: string
    label: string
    value: number
    detail: string
}) {
    return (
        <Card data-testid={testId} className="gap-3 py-4">
            <CardHeader className="px-4">
                <CardDescription>{label}</CardDescription>
                <CardTitle className="text-2xl tabular-nums">{value}</CardTitle>
            </CardHeader>
            <CardContent className="px-4">
                <p className="text-xs text-muted-foreground">{detail}</p>
            </CardContent>
        </Card>
    )
}

function MetricsSection({ summary }: { summary: EmailOperationsSummary24h }) {
    return (
        <section aria-labelledby="metrics-heading" className="space-y-3">
            <div>
                <h2 id="metrics-heading" className="text-lg font-semibold">
                    Last 24 hours
                </h2>
                <p className="text-sm text-muted-foreground">
                    Organization-scoped message and provider activity.
                </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                <MetricCard
                    testId="metric-messages"
                    label="Messages"
                    value={summary.messages}
                    detail={`${summary.pending} pending`}
                />
                <MetricCard
                    testId="metric-sent"
                    label="Sent"
                    value={summary.sent}
                    detail={`${summary.delivery_attempts} attempts`}
                />
                <MetricCard
                    testId="metric-delivered"
                    label="Delivered"
                    value={summary.delivered}
                    detail={`${summary.webhook_events} provider events`}
                />
                <MetricCard
                    testId="metric-failed"
                    label="Failed"
                    value={summary.failed}
                    detail={`${summary.bounced} bounced`}
                />
                <MetricCard
                    testId="metric-opens"
                    label="Estimated opens"
                    value={summary.estimated_opens}
                    detail="Approximate engagement"
                />
                <MetricCard
                    testId="metric-clicks"
                    label="Clicks"
                    value={summary.clicks}
                    detail={`${summary.complained} complaints`}
                />
            </div>
        </section>
    )
}

function MessageStatusBadge({ message }: { message: EmailOperationMessage }) {
    const status = message.provider_status ?? message.delivery_status ?? message.status
    const destructive = ACTION_NEEDED_MESSAGE_STATUSES.has(status)
    return (
        <Badge variant={destructive ? "destructive" : "secondary"}>
            {getMessageStatusLabel(status)}
        </Badge>
    )
}

function MessagesSection({
    messages,
    isLoading,
    isError,
    hasNextPage,
    isFetchingNextPage,
    onLoadMore,
    onRetry,
    onSelectMessage,
}: {
    messages: EmailOperationMessage[]
    isLoading: boolean
    isError: boolean
    hasNextPage: boolean
    isFetchingNextPage: boolean
    onLoadMore: () => void
    onRetry: () => void
    onSelectMessage: (messageId: string) => void
}) {
    return (
        <Card>
            <CardHeader className="border-b">
                <div className="flex items-center gap-3">
                    <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        <MailCheckIcon className="size-5" aria-hidden="true" />
                    </div>
                    <div>
                        <CardTitle>Message log</CardTitle>
                        <CardDescription>
                            Sanitized delivery diagnostics. Message content and raw provider
                            payloads are never shown here.
                        </CardDescription>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="p-0">
                {isLoading ? (
                    <div className="space-y-3 p-6" aria-label="Loading email messages">
                        <span className="sr-only">Loading email messages…</span>
                        {[0, 1, 2].map((item) => (
                            <Skeleton key={item} className="h-16 w-full" />
                        ))}
                    </div>
                ) : isError ? (
                    <div className="p-6">
                        <Alert variant="destructive">
                            <AlertCircleIcon aria-hidden="true" />
                            <AlertTitle>Couldn’t load the message log</AlertTitle>
                            <AlertDescription>
                                <p>Check your connection and try loading messages again.</p>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    className="mt-3"
                                    onClick={onRetry}
                                >
                                    Try again
                                </Button>
                            </AlertDescription>
                        </Alert>
                    </div>
                ) : messages.length === 0 ? (
                    <Empty>
                        <EmptyHeader>
                            <EmptyMedia variant="icon">
                                <MailCheckIcon aria-hidden="true" />
                            </EmptyMedia>
                            <EmptyTitle>No messages recorded</EmptyTitle>
                            <EmptyDescription>
                                Messages will appear after this organization queues its first
                                supported email.
                            </EmptyDescription>
                        </EmptyHeader>
                    </Empty>
                ) : (
                    <>
                        <div className="overflow-x-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Message</TableHead>
                                        <TableHead>Provider route</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Engagement</TableHead>
                                        <TableHead>Created</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {messages.map((message) => (
                                        <TableRow key={message.id}>
                                            <TableCell className="min-w-64">
                                                <Button
                                                    type="button"
                                                    variant="ghost"
                                                    className="h-auto max-w-sm flex-col items-start gap-0.5 px-0 py-1 text-left hover:bg-transparent"
                                                    aria-label={`View message ${message.subject} to ${message.recipient_email}`}
                                                    onClick={() =>
                                                        onSelectMessage(message.id)
                                                    }
                                                >
                                                    <span className="max-w-full truncate font-medium">
                                                        {message.subject}
                                                    </span>
                                                    <span className="max-w-full truncate text-xs font-normal text-muted-foreground">
                                                        {message.recipient_email}
                                                    </span>
                                                </Button>
                                            </TableCell>
                                            <TableCell className="min-w-52">
                                                <p className="text-sm font-medium">
                                                    {getProviderLabel(message.provider)}
                                                </p>
                                                <p className="text-xs text-muted-foreground">
                                                    {getProviderScopeLabel(
                                                        message.provider_scope,
                                                    )}
                                                </p>
                                            </TableCell>
                                            <TableCell>
                                                <MessageStatusBadge message={message} />
                                            </TableCell>
                                            <TableCell className="min-w-40">
                                                <p className="text-sm">
                                                    {message.estimated_open_count} estimated{" "}
                                                    {message.estimated_open_count === 1
                                                        ? "open"
                                                        : "opens"}
                                                </p>
                                                <p className="text-xs text-muted-foreground">
                                                    {message.click_count}{" "}
                                                    {message.click_count === 1
                                                        ? "click"
                                                        : "clicks"}
                                                </p>
                                            </TableCell>
                                            <TableCell className="min-w-44 text-sm text-muted-foreground">
                                                {formatDateTime(
                                                    message.created_at,
                                                    "Unknown",
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                        {hasNextPage ? (
                            <div className="flex justify-center border-t p-4">
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={onLoadMore}
                                    disabled={isFetchingNextPage}
                                >
                                    {isFetchingNextPage ? (
                                        <RefreshCwIcon
                                            className="animate-spin motion-reduce:animate-none"
                                            aria-hidden="true"
                                        />
                                    ) : null}
                                    {isFetchingNextPage
                                        ? "Loading more…"
                                        : "Load more messages"}
                                </Button>
                            </div>
                        ) : null}
                    </>
                )}
            </CardContent>
        </Card>
    )
}

function DashboardSkeleton() {
    return (
        <div className="space-y-6" aria-label="Loading email operations">
            <span className="sr-only">Loading email operations…</span>
            <Skeleton className="h-72 w-full" />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                {[0, 1, 2, 3, 4, 5].map((item) => (
                    <Skeleton key={item} className="h-28 w-full" />
                ))}
            </div>
            <Skeleton className="h-80 w-full" />
        </div>
    )
}

export function EmailOperationsDashboard() {
    const { user } = useAuth()
    const effectivePermissionsQuery = useEffectivePermissions(
        user?.user_id ?? null,
    )
    const readinessQuery = useEmailOperationsReadiness()
    const liveReadinessQuery = useEmailOperationsLiveReadiness({ enabled: true })
    const requestReadinessCheck = useRequestEmailOperationsReadinessCheck()
    const messagesQuery = useEmailOperationsMessages()
    const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)

    const permissionSet = new Set(
        effectivePermissionsQuery.data?.permissions ?? [],
    )
    const canManageReconciliation =
        user?.role === "developer" || permissionSet.has("manage_ops")
    const canCheckLiveReadiness =
        user?.role === "developer" || permissionSet.has("manage_integrations")
    const reconciliationQuery = useEmailReconciliationCases({
        enabled: canManageReconciliation,
        status: "action_required",
    })
    const messages =
        messagesQuery.data?.pages.flatMap((page) => page.items) ?? []
    const isInitialLoading =
        (readinessQuery.isLoading && !readinessQuery.data) ||
        (messagesQuery.isLoading && !messagesQuery.data)
    const isFullError =
        readinessQuery.isError &&
        !readinessQuery.data &&
        messagesQuery.isError &&
        !messagesQuery.data
    const isRefreshing =
        readinessQuery.isFetching ||
        liveReadinessQuery.isFetching ||
        messagesQuery.isFetching ||
        (canManageReconciliation && reconciliationQuery.isFetching)

    const refresh = () => {
        void Promise.all([
            readinessQuery.refetch(),
            liveReadinessQuery.refetch(),
            messagesQuery.refetch(),
            ...(canManageReconciliation ? [reconciliationQuery.refetch()] : []),
        ])
    }

    return (
        <div className="min-h-dvh bg-muted/10">
            <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
                <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
                    <div className="flex min-w-0 items-center gap-3">
                        <Button
                            variant="ghost"
                            size="icon"
                            render={<Link href="/settings/integrations" />}
                            aria-label="Back to integrations"
                        >
                            <ArrowLeftIcon aria-hidden="true" />
                        </Button>
                        <div className="min-w-0">
                            <h1 className="text-2xl font-semibold">Email Operations</h1>
                            <p className="text-sm text-muted-foreground">
                                Delivery readiness, recent activity, and sanitized provider
                                diagnostics.
                            </p>
                        </div>
                    </div>
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={refresh}
                        disabled={isRefreshing}
                    >
                        <RefreshCwIcon
                            className={
                                isRefreshing
                                    ? "animate-spin motion-reduce:animate-none"
                                    : undefined
                            }
                            aria-hidden="true"
                        />
                        Refresh
                    </Button>
                </div>
            </header>

            <main className="mx-auto max-w-7xl space-y-6 p-6">
                {isInitialLoading ? (
                    <DashboardSkeleton />
                ) : (
                    <>
                        <ResendOperationsReadinessSummary
                            envelope={liveReadinessQuery.data}
                            isLoading={liveReadinessQuery.isLoading}
                            isError={liveReadinessQuery.isError}
                            canCheck={canCheckLiveReadiness}
                            isCheckPending={requestReadinessCheck.isPending}
                            isCheckError={requestReadinessCheck.isError}
                            onCheck={() => requestReadinessCheck.mutate()}
                        />

                        <Accordion
                            defaultValue={[]}
                            className="rounded-xl bg-background"
                        >
                            <AccordionItem value="provider-diagnostics">
                                <AccordionTrigger className="items-center px-5 py-4 hover:no-underline">
                                    <span className="flex flex-col gap-1 text-left">
                                        <span className="font-semibold">Diagnostics</span>
                                        <span className="text-xs font-normal text-muted-foreground">
                                            Provider configuration, live counts, and stored
                                            evidence.
                                        </span>
                                    </span>
                                </AccordionTrigger>
                                <AccordionContent className="space-y-4 pt-2">
                                    <section
                                        aria-label="Provider diagnostics"
                                        className="space-y-4"
                                    >
                                        <ResendLiveReadinessCard
                                            envelope={liveReadinessQuery.data}
                                            isLoading={liveReadinessQuery.isLoading}
                                            isError={liveReadinessQuery.isError}
                                            canCheck={false}
                                            onCheck={() =>
                                                requestReadinessCheck.mutate()
                                            }
                                        />
                                        {readinessQuery.data ? (
                                            <ReadinessSection
                                                readiness={readinessQuery.data}
                                            />
                                        ) : (
                                            <Alert variant="destructive">
                                                <AlertTriangleIcon aria-hidden="true" />
                                                <AlertTitle>
                                                    Stored readiness is unavailable
                                                </AlertTitle>
                                                <AlertDescription>
                                                    Refresh the page to reload saved
                                                    configuration evidence.
                                                </AlertDescription>
                                            </Alert>
                                        )}
                                    </section>
                                </AccordionContent>
                            </AccordionItem>
                        </Accordion>

                        {isFullError ? (
                            <Alert variant="destructive">
                                <AlertCircleIcon aria-hidden="true" />
                                <AlertTitle>Email operations couldn’t load</AlertTitle>
                                <AlertDescription>
                                    <p>
                                        Stored readiness and message activity are temporarily
                                        unavailable. Check your connection and try again.
                                    </p>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        className="mt-3"
                                        onClick={refresh}
                                    >
                                        Try again
                                    </Button>
                                </AlertDescription>
                            </Alert>
                        ) : readinessQuery.data ? (
                            <>
                                {canManageReconciliation ? (
                                    <EmailReconciliationQueue
                                        query={reconciliationQuery}
                                        messages={messages}
                                    />
                                ) : null}
                                <MetricsSection
                                    summary={readinessQuery.data.summary_24h}
                                />
                            </>
                        ) : (
                            <Alert variant="destructive">
                                <AlertTriangleIcon aria-hidden="true" />
                                <AlertTitle>Readiness is unavailable</AlertTitle>
                                <AlertDescription>
                                    The message log can still be reviewed while readiness
                                    evidence reloads.
                                </AlertDescription>
                            </Alert>
                        )}

                        {!isFullError ? (
                            <>
                                <Alert>
                                    <InfoIcon aria-hidden="true" />
                                    <AlertTitle>Open activity is approximate</AlertTitle>
                                    <AlertDescription>
                                        Privacy protections and inbox preloading can inflate
                                        open counts. Treat opens as a noisy directional
                                        signal; clicks and verified delivery events are
                                        stronger evidence.
                                    </AlertDescription>
                                </Alert>

                                <MessagesSection
                                    messages={messages}
                                    isLoading={messagesQuery.isLoading}
                                    isError={messagesQuery.isError}
                                    hasNextPage={Boolean(messagesQuery.hasNextPage)}
                                    isFetchingNextPage={messagesQuery.isFetchingNextPage}
                                    onLoadMore={() => void messagesQuery.fetchNextPage()}
                                    onRetry={() => void messagesQuery.refetch()}
                                    onSelectMessage={setSelectedMessageId}
                                />
                            </>
                        ) : null}
                    </>
                )}
            </main>

            <EmailOperationDetailSheet
                messageId={selectedMessageId}
                onOpenChange={(open) => {
                    if (!open) setSelectedMessageId(null)
                }}
            />
        </div>
    )
}
