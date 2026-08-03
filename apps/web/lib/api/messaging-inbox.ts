import api from "../api"

export type MessagingPurpose = "operational" | "promotional"
export type MessagingEntityType = "surrogate" | "intake_lead" | "meta_lead"

export interface MessagingLinkedEntity {
    entity_type: MessagingEntityType
    entity_id: string
    label: string
}

export interface MessagingConversationSummary {
    id: string
    contact_id: string
    masked_phone: string
    purpose: MessagingPurpose
    route_id: string
    route_label: string
    unread_count: number
    unlinked: boolean
    linked_entities: MessagingLinkedEntity[]
    last_message_at: string | null
    last_message_direction: "inbound" | "outbound" | null
    last_message_preview: string | null
}

export interface MessagingConversationListResponse {
    items: MessagingConversationSummary[]
    total: number
    limit: number
    offset: number
}

export interface MessagingMedia {
    id: string
    filename: string | null
    content_type: string
    byte_size: number
    scan_status: string
    provider_deleted: boolean
    quarantined: boolean
}

export interface MessagingDeliveryAttempt {
    id: string
    attempt_number: number
    outcome: string
    started_at: string
    completed_at: string | null
    provider_http_status: number | null
    error_type: string | null
    error_message: string | null
}

export interface MessagingDeliveryStatusEvent {
    id: string
    status: string | null
    received_at: string
}

export interface MessagingDelivery {
    id: string
    status: string
    source_type: string
    attempt_count: number
    max_attempts: number
    created_at: string
    completed_at: string | null
    last_error_type: string | null
    last_error: string | null
    attempts: MessagingDeliveryAttempt[]
    status_events: MessagingDeliveryStatusEvent[]
}

export interface MessagingMessage {
    id: string
    direction: "inbound" | "outbound"
    purpose: MessagingPurpose
    body: string
    provider_status: string | null
    is_unread: boolean
    created_at: string
    media: MessagingMedia[]
    delivery: MessagingDelivery | null
}

export interface MessagingConsentEvent {
    id: string
    purpose: string
    action: string
    source: string
    occurred_at: string
    instruction_text: string | null
    disclosure_hash: string | null
}

export interface MessagingReconciliationCase {
    id: string
    case_type: string
    status: string
    reason_code: string
    detected_at: string
    resolved_at: string | null
    resolution_code: string | null
    version: number
}

export interface MessagingConversationDetail extends MessagingConversationSummary {
    consent_states: Record<MessagingPurpose, string>
    global_suppression_active: boolean
    global_suppression_reason: string
    messages: MessagingMessage[]
    consent_timeline: MessagingConsentEvent[]
    reconciliation_cases: MessagingReconciliationCase[]
}

export interface MessagingConversationFilters {
    unread?: boolean
    unlinked?: boolean
    purpose?: MessagingPurpose
    limit?: number
    offset?: number
}

export interface MessagingConversationLinkRequest {
    entity_type: MessagingEntityType
    entity_id: string
}

export interface MessagingReconciliationUpdateRequest {
    expected_version: number
    action: "resolve" | "dismiss"
    resolution_code: string
}

function listQuery(filters: MessagingConversationFilters): string {
    const params = new URLSearchParams()
    if (filters.unread !== undefined) params.set("unread", String(filters.unread))
    if (filters.unlinked !== undefined) params.set("unlinked", String(filters.unlinked))
    if (filters.purpose) params.set("purpose", filters.purpose)
    params.set("limit", String(filters.limit ?? 50))
    params.set("offset", String(filters.offset ?? 0))
    return params.toString()
}

export function getMessagingConversations(
    filters: MessagingConversationFilters = {},
): Promise<MessagingConversationListResponse> {
    return api.get<MessagingConversationListResponse>(
        `/messaging/conversations?${listQuery(filters)}`,
    )
}

export function getCandidateMessagingConversations(
    candidateId: string,
    options: Pick<MessagingConversationFilters, "limit" | "offset"> = {},
): Promise<MessagingConversationListResponse> {
    return api.get<MessagingConversationListResponse>(
        `/messaging/candidates/${candidateId}/conversations?${listQuery(options)}`,
    )
}

export function getMessagingConversation(
    conversationId: string,
): Promise<MessagingConversationDetail> {
    return api.get<MessagingConversationDetail>(
        `/messaging/conversations/${conversationId}`,
    )
}

export function markMessagingConversationRead(
    conversationId: string,
): Promise<MessagingConversationDetail> {
    return api.post<MessagingConversationDetail>(
        `/messaging/conversations/${conversationId}/read`,
        {},
    )
}

export function linkMessagingConversation(
    conversationId: string,
    request: MessagingConversationLinkRequest,
): Promise<MessagingConversationDetail> {
    return api.post<MessagingConversationDetail>(
        `/messaging/conversations/${conversationId}/link`,
        request,
    )
}

export function updateMessagingReconciliation(
    caseId: string,
    request: MessagingReconciliationUpdateRequest,
): Promise<MessagingReconciliationCase> {
    return api.patch<MessagingReconciliationCase>(
        `/messaging/reconciliation/${caseId}`,
        request,
    )
}
