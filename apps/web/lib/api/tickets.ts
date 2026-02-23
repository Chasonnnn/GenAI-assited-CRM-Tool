/**
 * Ticketing API client.
 */

import api from './index'

export type TicketStatus = 'new' | 'open' | 'pending' | 'resolved' | 'closed' | 'spam'
export type TicketPriority = 'low' | 'normal' | 'high' | 'urgent'
export type TicketLinkStatus = 'unlinked' | 'linked' | 'needs_review'

export interface TicketListItem {
    id: string
    ticket_code: string
    status: TicketStatus
    priority: TicketPriority
    subject: string | null
    requester_email: string | null
    requester_name: string | null
    assignee_user_id: string | null
    assignee_queue_id: string | null
    surrogate_id: string | null
    surrogate_link_status: TicketLinkStatus
    first_message_at: string | null
    last_message_at: string | null
    last_activity_at: string | null
    created_at: string
    updated_at: string
}

export interface TicketMessageAttachment {
    id: string
    attachment_id: string
    filename: string | null
    content_type: string | null
    size_bytes: number
    is_inline: boolean
    content_id: string | null
}

export interface TicketMessageOccurrence {
    id: string
    mailbox_id: string
    gmail_message_id: string
    gmail_thread_id: string | null
    state: string
    original_recipient: string | null
    original_recipient_source: string | null
    original_recipient_confidence: string | null
    original_recipient_evidence: Record<string, unknown>
    parse_error: string | null
    stitch_error: string | null
    link_error: string | null
    created_at: string
}

export interface TicketMessage {
    id: string
    message_id: string
    direction: 'inbound' | 'outbound'
    stitched_at: string
    stitch_reason: string
    stitch_confidence: string
    rfc_message_id: string | null
    gmail_thread_id: string | null
    date_header: string | null
    subject: string | null
    from_email: string | null
    from_name: string | null
    to_emails: string[]
    cc_emails: string[]
    reply_to_emails: string[]
    snippet: string | null
    body_text: string | null
    body_html_sanitized: string | null
    attachments: TicketMessageAttachment[]
    occurrences: TicketMessageOccurrence[]
}

export interface TicketEvent {
    id: string
    actor_user_id: string | null
    event_type: string
    event_data: Record<string, unknown>
    created_at: string
}

export interface TicketNote {
    id: string
    author_user_id: string | null
    body_markdown: string
    body_html_sanitized: string | null
    created_at: string
    updated_at: string
}

export interface TicketSurrogateCandidate {
    id: string
    surrogate_id: string
    confidence: string
    evidence_json: Record<string, unknown>
    is_selected: boolean
    created_at: string
}

export interface TicketDetailResponse {
    ticket: TicketListItem
    messages: TicketMessage[]
    events: TicketEvent[]
    notes: TicketNote[]
    candidates: TicketSurrogateCandidate[]
}

export interface TicketListResponse {
    items: TicketListItem[]
    next_cursor: string | null
}

export interface TicketListParams {
    limit?: number
    cursor?: string
    status?: TicketStatus
    priority?: TicketPriority
    queue_id?: string
    assignee_user_id?: string
    surrogate_id?: string
    needs_review?: boolean
    q?: string
}

export interface TicketPatchRequest {
    status?: TicketStatus
    priority?: TicketPriority
    assignee_user_id?: string | null
    assignee_queue_id?: string | null
}

export interface TicketReplyRequest {
    to_emails: string[]
    cc_emails?: string[]
    subject?: string
    body_text: string
    body_html?: string
    idempotency_key?: string
}

export interface TicketComposeRequest {
    to_emails: string[]
    cc_emails?: string[]
    subject: string
    body_text: string
    body_html?: string
    surrogate_id?: string
    queue_id?: string
    idempotency_key?: string
}

export interface TicketSendResult {
    status: string
    ticket_id: string
    message_id: string
    provider: string
    gmail_message_id: string | null
    gmail_thread_id: string | null
    job_id?: string | null
}

export interface TicketSendIdentity {
    integration_id: string
    account_email: string
    provider: string
    is_default: boolean
}

export interface TicketSendIdentityResponse {
    items: TicketSendIdentity[]
}

function buildQuery(params: TicketListParams = {}): string {
    const search = new URLSearchParams()

    if (params.limit) search.set('limit', String(params.limit))
    if (params.cursor) search.set('cursor', params.cursor)
    if (params.status) search.set('status', params.status)
    if (params.priority) search.set('priority', params.priority)
    if (params.queue_id) search.set('queue_id', params.queue_id)
    if (params.assignee_user_id) search.set('assignee_user_id', params.assignee_user_id)
    if (params.surrogate_id) search.set('surrogate_id', params.surrogate_id)
    if (params.needs_review !== undefined) search.set('needs_review', String(params.needs_review))
    if (params.q) search.set('q', params.q)

    const query = search.toString()
    return query ? `?${query}` : ''
}

export function getTickets(params: TicketListParams = {}): Promise<TicketListResponse> {
    return api.get<TicketListResponse>(`/tickets${buildQuery(params)}`)
}

export function getTicket(ticketId: string): Promise<TicketDetailResponse> {
    return api.get<TicketDetailResponse>(`/tickets/${ticketId}`)
}

export function patchTicket(ticketId: string, data: TicketPatchRequest): Promise<TicketListItem> {
    return api.patch<TicketListItem>(`/tickets/${ticketId}`, data)
}

export function replyTicket(ticketId: string, data: TicketReplyRequest): Promise<TicketSendResult> {
    return api.post<TicketSendResult>(`/tickets/${ticketId}/reply`, data)
}

export function composeTicket(data: TicketComposeRequest): Promise<TicketSendResult> {
    return api.post<TicketSendResult>('/tickets/compose', data)
}

export function addTicketNote(ticketId: string, bodyMarkdown: string): Promise<TicketNote> {
    return api.post<TicketNote>(`/tickets/${ticketId}/notes`, { body_markdown: bodyMarkdown })
}

export function linkTicketSurrogate(
    ticketId: string,
    data: { surrogate_id?: string | null; reason?: string }
): Promise<TicketListItem> {
    return api.post<TicketListItem>(`/tickets/${ticketId}/link-surrogate`, data)
}

export function getTicketSendIdentities(): Promise<TicketSendIdentityResponse> {
    return api.get<TicketSendIdentityResponse>('/tickets/send-identities')
}

export async function getTicketAttachmentDownloadUrl(
    ticketId: string,
    attachmentId: string
): Promise<string> {
    const payload = await api.get<{ download_url: string }>(
        `/tickets/${ticketId}/attachments/${attachmentId}/download`
    )
    return payload.download_url
}
