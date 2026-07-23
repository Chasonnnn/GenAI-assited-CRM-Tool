"use client"

import {
    AlertCircleIcon,
    CheckCircle2Icon,
    Clock3Icon,
    MailCheckIcon,
    RefreshCwIcon,
    SendIcon,
} from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime } from "@/lib/formatters"
import { useEmailOperationMessage } from "@/lib/hooks/use-email-operations"
import {
    getAttemptOutcomeLabel,
    getErrorTypeLabel,
    getMessageStatusLabel,
    getProviderEventLabel,
    getProviderLabel,
    getProviderScopeLabel,
} from "./email-operation-labels"

interface EmailOperationDetailSheetProps {
    messageId: string | null
    onOpenChange: (open: boolean) => void
}

const ACTION_NEEDED_MESSAGE_STATUSES = new Set([
    "failed",
    "bounced",
    "complained",
    "suppressed",
    "reconciliation_required",
])

function getMessageStatusVariant(status: string | null): "destructive" | "secondary" {
    return status && ACTION_NEEDED_MESSAGE_STATUSES.has(status)
        ? "destructive"
        : "secondary"
}

function DetailSkeleton() {
    return (
        <div className="space-y-5 p-6" aria-label="Loading message details">
            <span className="sr-only">Loading message details…</span>
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-48 w-full" />
        </div>
    )
}

function DetailField({ label, value }: { label: string; value: string }) {
    return (
        <div className="space-y-1">
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {label}
            </dt>
            <dd className="break-words text-sm font-medium">{value}</dd>
        </div>
    )
}

export function EmailOperationDetailSheet({
    messageId,
    onOpenChange,
}: EmailOperationDetailSheetProps) {
    const detailQuery = useEmailOperationMessage(messageId)
    const message = detailQuery.data
    const effectiveStatus = message
        ? (message.provider_status ?? message.delivery_status ?? message.status)
        : null

    return (
        <Sheet
            open={messageId !== null}
            onOpenChange={(open) => {
                onOpenChange(open)
            }}
        >
            <SheetContent className="w-full sm:max-w-xl lg:max-w-2xl">
                <SheetHeader className="border-b pr-16">
                    <div className="flex items-center gap-3">
                        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                            <MailCheckIcon className="size-5" aria-hidden="true" />
                        </div>
                        <div className="min-w-0">
                            <SheetTitle>Message details</SheetTitle>
                            <p className="truncate font-medium">
                                {message?.subject ?? "Loading message"}
                            </p>
                        </div>
                    </div>
                    <SheetDescription>
                        {message
                            ? `Recipient: ${message.recipient_email}. Content, headers, and raw provider payloads are intentionally excluded.`
                            : "Loading sanitized delivery diagnostics."}
                    </SheetDescription>
                </SheetHeader>

                {detailQuery.isLoading ? (
                    <DetailSkeleton />
                ) : detailQuery.isError || !message ? (
                    <div className="p-6">
                        <Alert variant="destructive">
                            <AlertCircleIcon aria-hidden="true" />
                            <AlertTitle>Couldn’t load message details</AlertTitle>
                            <AlertDescription>
                                <p>Check your connection, then try loading this message again.</p>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    className="mt-3"
                                    onClick={() => void detailQuery.refetch()}
                                >
                                    <RefreshCwIcon aria-hidden="true" />
                                    Try again
                                </Button>
                            </AlertDescription>
                        </Alert>
                    </div>
                ) : (
                    <ScrollArea className="min-h-0 flex-1">
                        <div className="space-y-6 p-6">
                            <section
                                className="space-y-4 rounded-xl border bg-card p-4"
                                aria-labelledby="message-overview-heading"
                            >
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                    <h3
                                        id="message-overview-heading"
                                        className="font-semibold"
                                    >
                                        Message overview
                                    </h3>
                                    <Badge
                                        variant={getMessageStatusVariant(effectiveStatus)}
                                    >
                                        {getMessageStatusLabel(effectiveStatus)}
                                    </Badge>
                                </div>
                                <dl className="grid gap-4 sm:grid-cols-2">
                                    <DetailField
                                        label="Provider"
                                        value={getProviderLabel(message.provider)}
                                    />
                                    <DetailField
                                        label="Credential scope"
                                        value={getProviderScopeLabel(message.provider_scope)}
                                    />
                                    <DetailField
                                        label="Provider account"
                                        value={message.provider_account_id ?? "Not recorded"}
                                    />
                                    <DetailField
                                        label="Provider message"
                                        value={message.provider_message_id ?? "Not assigned"}
                                    />
                                    <DetailField
                                        label="Created"
                                        value={formatDateTime(message.created_at, "Unknown")}
                                    />
                                    <DetailField
                                        label="Sent"
                                        value={formatDateTime(message.sent_at, "Not sent")}
                                    />
                                </dl>
                                <div className="grid gap-3 sm:grid-cols-2">
                                    <div className="rounded-lg bg-muted/50 p-3">
                                        <p className="text-xs text-muted-foreground">
                                            Estimated opens
                                        </p>
                                        <p className="mt-1 text-xl font-semibold">
                                            {message.estimated_open_count}
                                        </p>
                                    </div>
                                    <div className="rounded-lg bg-muted/50 p-3">
                                        <p className="text-xs text-muted-foreground">Clicks</p>
                                        <p className="mt-1 text-xl font-semibold">
                                            {message.click_count}
                                        </p>
                                    </div>
                                </div>
                                {message.delivery ? (
                                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-background p-3">
                                        <div>
                                            <p className="text-sm font-medium">
                                                Outbox delivery
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                {message.delivery.attempt_count} of{" "}
                                                {message.delivery.max_attempts} attempts used
                                            </p>
                                        </div>
                                        <Badge
                                            variant={getMessageStatusVariant(
                                                message.delivery.status,
                                            )}
                                        >
                                            {getMessageStatusLabel(
                                                message.delivery.status,
                                            )}
                                        </Badge>
                                    </div>
                                ) : null}
                            </section>

                            <section
                                className="space-y-3"
                                aria-labelledby="delivery-attempts-heading"
                            >
                                <div>
                                    <h3
                                        id="delivery-attempts-heading"
                                        className="font-semibold"
                                    >
                                        Delivery attempts
                                    </h3>
                                    <p className="text-sm text-muted-foreground">
                                        Provider requests in recorded attempt order.
                                    </p>
                                </div>
                                {message.attempts.length === 0 ? (
                                    <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                                        No provider attempts are recorded for this message.
                                    </div>
                                ) : (
                                    <ol className="space-y-3">
                                        {message.attempts.map((attempt) => {
                                            const errorLabel = getErrorTypeLabel(
                                                attempt.error_type,
                                            )
                                            return (
                                                <li
                                                    key={attempt.id}
                                                    className="rounded-xl border bg-card p-4"
                                                >
                                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                                        <div className="flex items-center gap-3">
                                                            <div className="flex size-8 items-center justify-center rounded-full bg-muted text-xs font-semibold">
                                                                {attempt.attempt_number}
                                                            </div>
                                                            <div>
                                                                <p className="font-medium">
                                                                    Attempt{" "}
                                                                    {attempt.attempt_number}
                                                                </p>
                                                                <p className="text-xs text-muted-foreground">
                                                                    {formatDateTime(
                                                                        attempt.started_at,
                                                                        "Unknown",
                                                                    )}
                                                                </p>
                                                            </div>
                                                        </div>
                                                        <Badge
                                                            variant={
                                                                attempt.outcome === "succeeded"
                                                                    ? "default"
                                                                    : [
                                                                            "in_progress",
                                                                            "retryable_error",
                                                                        ].includes(
                                                                            attempt.outcome,
                                                                        )
                                                                      ? "secondary"
                                                                      : "destructive"
                                                            }
                                                        >
                                                            {getAttemptOutcomeLabel(
                                                                attempt.outcome,
                                                            )}
                                                        </Badge>
                                                    </div>
                                                    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                                                        {attempt.provider_http_status !== null ? (
                                                            <span>
                                                                HTTP{" "}
                                                                {attempt.provider_http_status}
                                                            </span>
                                                        ) : null}
                                                        {errorLabel ? (
                                                            <span className="font-medium text-foreground">
                                                                {errorLabel}
                                                            </span>
                                                        ) : null}
                                                        {attempt.retry_after_seconds !== null ? (
                                                            <span>
                                                                Retried after{" "}
                                                                {attempt.retry_after_seconds}s
                                                            </span>
                                                        ) : null}
                                                    </div>
                                                </li>
                                            )
                                        })}
                                    </ol>
                                )}
                            </section>

                            <section
                                className="space-y-3"
                                aria-labelledby="provider-events-heading"
                            >
                                <div>
                                    <h3
                                        id="provider-events-heading"
                                        className="font-semibold"
                                    >
                                        Provider timeline
                                    </h3>
                                    <p className="text-sm text-muted-foreground">
                                        Verified events ordered by provider event time.
                                    </p>
                                </div>
                                {message.provider_events.length === 0 ? (
                                    <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                                        No verified provider events are recorded yet.
                                    </div>
                                ) : (
                                    <ol className="relative space-y-4 border-l pl-5">
                                        {message.provider_events.map((event) => (
                                            <li key={event.id} className="relative">
                                                <span className="absolute -left-[1.65rem] top-0.5 flex size-5 items-center justify-center rounded-full border bg-background">
                                                    {event.event_type === "email.delivered" ? (
                                                        <CheckCircle2Icon
                                                            className="size-3 text-primary"
                                                            aria-hidden="true"
                                                        />
                                                    ) : event.event_type === "email.sent" ? (
                                                        <SendIcon
                                                            className="size-3 text-primary"
                                                            aria-hidden="true"
                                                        />
                                                    ) : (
                                                        <Clock3Icon
                                                            className="size-3 text-muted-foreground"
                                                            aria-hidden="true"
                                                        />
                                                    )}
                                                </span>
                                                <p className="font-medium">
                                                    {getProviderEventLabel(event.event_type)}
                                                </p>
                                                <p className="text-xs text-muted-foreground">
                                                    Provider time{" "}
                                                    {formatDateTime(
                                                        event.event_created_at,
                                                        "Unknown",
                                                    )}
                                                </p>
                                                <p className="text-xs text-muted-foreground">
                                                    Received{" "}
                                                    {formatDateTime(
                                                        event.received_at,
                                                        "Unknown",
                                                    )}
                                                </p>
                                            </li>
                                        ))}
                                    </ol>
                                )}
                            </section>
                        </div>
                    </ScrollArea>
                )}
            </SheetContent>
        </Sheet>
    )
}
