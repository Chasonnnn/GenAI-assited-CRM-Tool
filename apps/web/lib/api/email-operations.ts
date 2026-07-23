import api from "@/lib/api"

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
