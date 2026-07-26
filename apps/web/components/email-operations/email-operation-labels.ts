import type {
    EmailOperationsCheckStatus,
    EmailOperationsOverall,
} from "@/lib/api/email-operations"

const PROVIDER_LABELS: Record<string, string> = {
    resend: "Resend",
    gmail: "Gmail",
}

const PROVIDER_SCOPE_LABELS: Record<string, string> = {
    platform: "Platform credential",
    organization: "Organization credential",
    user: "User credential",
}

const MESSAGE_STATUS_LABELS: Record<string, string> = {
    pending: "Queued",
    leased: "Sending",
    retry_scheduled: "Retry scheduled",
    sent: "Sent",
    delivered: "Delivery confirmed",
    delivery_delayed: "Delayed",
    failed: "Failed",
    skipped: "Skipped",
    suppressed: "Suppressed",
    bounced: "Bounced",
    complained: "Complaint received",
    cancelled: "Cancelled",
    reconciliation_required: "Needs reconciliation",
}

const ATTEMPT_OUTCOME_LABELS: Record<string, string> = {
    in_progress: "In progress",
    succeeded: "Succeeded",
    retryable_error: "Retryable error",
    terminal_error: "Terminal error",
    lease_expired: "Lease expired",
}

const EVENT_LABELS: Record<string, string> = {
    "email.scheduled": "Scheduled",
    "email.sent": "Sent",
    "email.delivery_delayed": "Delivery delayed",
    "email.delivered": "Delivered",
    "email.failed": "Failed",
    "email.suppressed": "Suppressed",
    "email.bounced": "Bounced",
    "email.complained": "Complaint received",
    "email.opened": "Estimated open",
    "email.clicked": "Clicked",
}

const CHECK_LABELS: Record<string, string> = {
    provider_selected: "Provider selected",
    api_key_configured: "API key stored",
    api_key_validated: "API key validated",
    sender_configured: "Sender configured",
    domain_verified: "Sending domain verified",
    webhook_signing_secret_configured: "Webhook signing enabled",
    recent_webhook_activity: "Recent webhook activity",
}

const ERROR_TYPE_LABELS: Record<string, string> = {
    rate_limited: "Rate limited",
    lease_expired: "Lease expired",
    provider_error: "Provider error",
    configuration_error: "Configuration error",
}

const RECONCILIATION_CASE_LABELS: Record<string, string> = {
    orphan_webhook: "Orphan provider event",
    unknown_delivery: "Unknown delivery outcome",
}

const RECONCILIATION_REASON_LABELS: Record<string, string> = {
    automatic_correlation_exhausted: "Automatic correlation exhausted",
    provider_outcome_unknown: "Provider outcome unknown",
    idempotency_window_expired: "Safe retry window expired",
    delivery_lease_expired: "Delivery worker outcome unknown",
    worker_claim_expired: "Correlation worker stopped",
    unsupported_event: "Unsupported provider event",
}

function friendlyFallback(value: string): string {
    const normalized = value.replace(/[._-]+/g, " ").trim()
    if (!normalized) return "Unknown"
    return `${normalized.charAt(0).toUpperCase()}${normalized.slice(1)}`
}

export function getProviderLabel(value: string | null): string {
    if (!value) return "Not recorded"
    return PROVIDER_LABELS[value] ?? friendlyFallback(value)
}

export function getProviderScopeLabel(value: string | null): string {
    if (!value) return "Scope not recorded"
    return PROVIDER_SCOPE_LABELS[value] ?? friendlyFallback(value)
}

export function getMessageStatusLabel(value: string | null): string {
    if (!value) return "Status pending"
    return MESSAGE_STATUS_LABELS[value] ?? friendlyFallback(value)
}

export function getAttemptOutcomeLabel(value: string): string {
    return ATTEMPT_OUTCOME_LABELS[value] ?? friendlyFallback(value)
}

export function getProviderEventLabel(value: string): string {
    return EVENT_LABELS[value] ?? friendlyFallback(value)
}

export function getReadinessCheckLabel(value: string): string {
    return CHECK_LABELS[value] ?? friendlyFallback(value)
}

export function getErrorTypeLabel(value: string | null): string | null {
    if (!value) return null
    return ERROR_TYPE_LABELS[value] ?? friendlyFallback(value)
}

export function getOverallLabel(value: EmailOperationsOverall): string {
    if (value === "ready") return "Ready"
    if (value === "needs_attention") return "Needs attention"
    return "Not configured"
}

export function getCheckStatusLabel(value: EmailOperationsCheckStatus): string {
    if (value === "pass") return "Passed"
    if (value === "fail") return "Action needed"
    if (value === "unknown") return "Not enough evidence"
    return "Not applicable"
}

export function getWebhookActivityLabel(value: EmailOperationsCheckStatus): string {
    if (value === "pass") return "Receiving events"
    if (value === "fail") return "Events missing"
    if (value === "unknown") return "Awaiting first signal"
    return "Not applicable"
}

export function getReconciliationCaseLabel(value: string): string {
    return RECONCILIATION_CASE_LABELS[value] ?? "Provider reconciliation case"
}

export function getReconciliationReasonLabel(value: string): string {
    return RECONCILIATION_REASON_LABELS[value] ?? "Operator review needed"
}
