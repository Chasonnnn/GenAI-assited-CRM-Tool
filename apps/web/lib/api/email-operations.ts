import api from "../api"
import type { ResendReadinessEnvelope } from "@/lib/types/resend-readiness"

export type EmailOperationsOverall = "ready" | "needs_attention" | "not_configured"
export type EmailOperationsCheckStatus = "pass" | "fail" | "unknown" | "not_applicable"

export interface EmailOperationsReadinessCheck {
    key: string
    status: EmailOperationsCheckStatus
    detail: string
    observed_at: string | null
}

export interface EmailOperationsSummary24h {
    messages: number
    pending: number
    sent: number
    failed: number
    delivered: number
    bounced: number
    complained: number
    estimated_opens: number
    clicks: number
    delivery_attempts: number
    webhook_events: number
}

export interface EmailOperationsReadiness {
    overall: EmailOperationsOverall
    can_send: boolean
    can_track: boolean
    provider: string | null
    provider_scope: string | null
    provider_account_id: string | null
    recent_webhook_activity: EmailOperationsCheckStatus
    last_webhook_received_at: string | null
    checks: EmailOperationsReadinessCheck[]
    summary_24h: EmailOperationsSummary24h
}

export interface EmailOperationMessage {
    id: string
    recipient_email: string
    subject: string
    from_email: string | null
    purpose: string | null
    source_type: string | null
    source_id: string | null
    provider: string | null
    provider_scope: string | null
    provider_account_id: string | null
    provider_message_id: string | null
    status: string
    provider_status: string | null
    delivery_status: string | null
    attempt_count: number | null
    max_attempts: number | null
    created_at: string
    sent_at: string | null
    delivered_at: string | null
    bounced_at: string | null
    bounce_type: string | null
    complained_at: string | null
    estimated_opened_at: string | null
    estimated_open_count: number
    clicked_at: string | null
    click_count: number
    open_tracking: "estimated"
}

export interface EmailOperationMessagePage {
    items: EmailOperationMessage[]
    next_cursor: string | null
}

export type EmailReconciliationCaseType = "orphan_webhook" | "unknown_delivery"
export type EmailReconciliationStatus =
    | "pending"
    | "running"
    | "action_required"
    | "resolved"
    | "dismissed"
export type EmailReconciliationListStatus = "monitoring" | EmailReconciliationStatus
export type EmailReconciliationAction =
    | "retry_correlation"
    | "link_event"
    | "dismiss"
    | "confirm_sent"
    | "confirm_not_sent"

export interface EmailReconciliationCase {
    id: string
    case_type: EmailReconciliationCaseType
    status: EmailReconciliationStatus
    reason_code: string
    version: number
    provider: "resend"
    event_type: string | null
    event_created_at: string | null
    received_at: string | null
    message_id: string | null
    delivery_id: string | null
    attempt_count: number | null
    max_attempts: number | null
    next_attempt_at: string | null
    available_actions: EmailReconciliationAction[]
    detected_at: string
    updated_at: string
}

export interface EmailReconciliationCounts {
    monitoring: number
    action_required: number
    resolved: number
}

export interface EmailReconciliationCasePage {
    items: EmailReconciliationCase[]
    next_cursor: string | null
    counts: EmailReconciliationCounts
}

export interface RetryEmailReconciliationCaseInput {
    caseId: string
    expectedVersion: number
}

export type EmailReconciliationDismissResolution =
    | "unsupported_event"
    | "test_event"
    | "not_actionable"

export interface DismissEmailReconciliationCaseInput
    extends RetryEmailReconciliationCaseInput {
    resolutionCode: EmailReconciliationDismissResolution
}

export interface LinkEmailReconciliationEventInput
    extends RetryEmailReconciliationCaseInput {
    emailLogId: string
}

export interface ConfirmEmailReconciliationSentInput
    extends RetryEmailReconciliationCaseInput {
    providerMessageId: string
}

export type ConfirmEmailReconciliationNotSentInput =
    RetryEmailReconciliationCaseInput

export interface EmailOperationDelivery {
    id: string
    status: string
    run_at: string
    attempt_count: number
    max_attempts: number
    first_attempt_at: string | null
    last_attempt_at: string | null
    completed_at: string | null
    last_error_type: string | null
    provider_message_id: string | null
    created_at: string
    updated_at: string
}

export interface EmailOperationDeliveryAttempt {
    id: string
    attempt_number: number
    started_at: string
    completed_at: string | null
    outcome: string
    provider_http_status: number | null
    error_type: string | null
    provider_message_id: string | null
    retry_after_seconds: number | null
}

export interface EmailOperationProviderEvent {
    id: string
    provider_event_id: string
    event_type: string
    event_created_at: string
    received_at: string
    processed_at: string | null
}

export interface EmailOperationMessageDetail extends EmailOperationMessage {
    delivery: EmailOperationDelivery | null
    attempts: EmailOperationDeliveryAttempt[]
    provider_events: EmailOperationProviderEvent[]
}

export async function getEmailOperationsReadiness(): Promise<EmailOperationsReadiness> {
    return api.get<EmailOperationsReadiness>("/email-operations/readiness")
}

export async function getEmailOperationsLiveReadiness(): Promise<ResendReadinessEnvelope> {
    return api.get<ResendReadinessEnvelope>("/email-operations/readiness/live")
}

export async function requestEmailOperationsReadinessCheck(): Promise<ResendReadinessEnvelope> {
    return api.post<ResendReadinessEnvelope>("/email-operations/readiness/check")
}

export async function getEmailOperationsMessages(options?: {
    limit?: number
    cursor?: string
}): Promise<EmailOperationMessagePage> {
    const params = new URLSearchParams()
    params.set("limit", String(options?.limit ?? 25))
    if (options?.cursor) params.set("cursor", options.cursor)
    return api.get<EmailOperationMessagePage>(
        `/email-operations/messages?${params.toString()}`,
    )
}

export async function getEmailOperationMessage(
    messageId: string,
): Promise<EmailOperationMessageDetail> {
    return api.get<EmailOperationMessageDetail>(
        `/email-operations/messages/${encodeURIComponent(messageId)}`,
    )
}

export async function getEmailReconciliationCases(options?: {
    status?: EmailReconciliationListStatus
    limit?: number
    cursor?: string
}): Promise<EmailReconciliationCasePage> {
    const params = new URLSearchParams()
    params.set("limit", String(options?.limit ?? 25))
    params.set("status", options?.status ?? "action_required")
    if (options?.cursor) params.set("cursor", options.cursor)
    return api.get<EmailReconciliationCasePage>(
        `/email-operations/reconciliation-cases?${params.toString()}`,
    )
}

export async function retryEmailReconciliationCorrelation({
    caseId,
    expectedVersion,
}: RetryEmailReconciliationCaseInput): Promise<EmailReconciliationCase> {
    return api.post<EmailReconciliationCase>(
        `/email-operations/reconciliation-cases/${encodeURIComponent(caseId)}/retry-correlation`,
        { expected_version: expectedVersion },
    )
}

export async function dismissEmailReconciliationCase({
    caseId,
    expectedVersion,
    resolutionCode,
}: DismissEmailReconciliationCaseInput): Promise<EmailReconciliationCase> {
    return api.post<EmailReconciliationCase>(
        `/email-operations/reconciliation-cases/${encodeURIComponent(caseId)}/dismiss`,
        {
            expected_version: expectedVersion,
            resolution_code: resolutionCode,
        },
    )
}

export async function linkEmailReconciliationEvent({
    caseId,
    expectedVersion,
    emailLogId,
}: LinkEmailReconciliationEventInput): Promise<EmailReconciliationCase> {
    return api.post<EmailReconciliationCase>(
        `/email-operations/reconciliation-cases/${encodeURIComponent(caseId)}/link-event`,
        {
            expected_version: expectedVersion,
            email_log_id: emailLogId,
        },
    )
}

export async function confirmEmailReconciliationSent({
    caseId,
    expectedVersion,
    providerMessageId,
}: ConfirmEmailReconciliationSentInput): Promise<EmailReconciliationCase> {
    return api.post<EmailReconciliationCase>(
        `/email-operations/reconciliation-cases/${encodeURIComponent(caseId)}/resolve-delivery`,
        {
            expected_version: expectedVersion,
            outcome: "confirm_sent",
            provider_message_id: providerMessageId,
        },
    )
}

export async function confirmEmailReconciliationNotSent({
    caseId,
    expectedVersion,
}: ConfirmEmailReconciliationNotSentInput): Promise<EmailReconciliationCase> {
    return api.post<EmailReconciliationCase>(
        `/email-operations/reconciliation-cases/${encodeURIComponent(caseId)}/resolve-delivery`,
        {
            expected_version: expectedVersion,
            outcome: "confirm_not_sent",
        },
    )
}
