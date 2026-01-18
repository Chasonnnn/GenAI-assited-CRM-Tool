/**
 * Campaign API client
 */
import api from './index'

// =============================================================================
// Types
// =============================================================================

export interface FilterCriteria {
    stage_ids?: string[]
    stage_slugs?: string[]
    states?: string[]
    created_after?: string
    created_before?: string
    source?: string
    is_priority?: boolean
    has_email?: boolean
}

export interface CampaignCreate {
    name: string
    description?: string
    email_template_id: string
    recipient_type: "case" | "intended_parent"
    filter_criteria?: FilterCriteria
    scheduled_at?: string
}

export interface CampaignUpdate {
    name?: string
    description?: string
    email_template_id?: string
    recipient_type?: "case" | "intended_parent"
    filter_criteria?: FilterCriteria
    scheduled_at?: string
}

export interface Campaign {
    id: string
    name: string
    description: string | null
    email_template_id: string
    email_template_name: string | null
    recipient_type: "case" | "intended_parent"
    filter_criteria: FilterCriteria
    scheduled_at: string | null
    status: "draft" | "scheduled" | "sending" | "completed" | "cancelled" | "failed"
    created_by_user_id: string | null
    created_by_name: string | null
    created_at: string
    updated_at: string
    total_recipients: number
    sent_count: number
    failed_count: number
    skipped_count: number
    opened_count: number
    clicked_count: number
}

export interface CampaignListItem {
    id: string
    name: string
    email_template_name: string | null
    recipient_type: "case" | "intended_parent"
    status: "draft" | "scheduled" | "sending" | "completed" | "cancelled" | "failed"
    scheduled_at: string | null
    total_recipients: number
    sent_count: number
    failed_count: number
    opened_count: number
    clicked_count: number
    created_at: string
}

export interface CampaignRun {
    id: string
    campaign_id: string
    started_at: string
    completed_at: string | null
    status: "running" | "completed" | "failed"
    error_message: string | null
    total_count: number
    sent_count: number
    failed_count: number
    skipped_count: number
    opened_count: number
    clicked_count: number
}

export interface CampaignRecipient {
    id: string
    entity_type: string
    entity_id: string
    recipient_email: string
    recipient_name: string | null
    status: "pending" | "sent" | "delivered" | "failed" | "skipped"
    error: string | null
    skip_reason: string | null
    sent_at: string | null
}

export interface RecipientPreview {
    entity_type: string
    entity_id: string
    email: string
    name: string | null
    stage: string | null
}

export interface CampaignPreview {
    total_count: number
    sample_recipients: RecipientPreview[]
}

export interface CampaignSendResponse {
    message: string
    run_id: string | null
    scheduled_at: string | null
}

export interface Suppression {
    id: string
    email: string
    reason: "opt_out" | "bounced" | "archived" | "complaint"
    created_at: string
}

// =============================================================================
// API Functions
// =============================================================================

export async function listCampaigns(params?: {
    status?: string
    limit?: number
    offset?: number
}): Promise<CampaignListItem[]> {
    const query = new URLSearchParams()
    if (params?.status) query.set("status", params.status)
    if (params?.limit) query.set("limit", String(params.limit))
    if (params?.offset) query.set("offset", String(params.offset))

    const queryStr = query.toString()
    return api.get<CampaignListItem[]>(`/campaigns${queryStr ? `?${queryStr}` : ""}`)
}

export async function getCampaign(id: string): Promise<Campaign> {
    return api.get<Campaign>(`/campaigns/${id}`)
}

export async function createCampaign(data: CampaignCreate): Promise<Campaign> {
    return api.post<Campaign>("/campaigns", data)
}

export async function updateCampaign(id: string, data: CampaignUpdate): Promise<Campaign> {
    return api.patch<Campaign>(`/campaigns/${id}`, data)
}

export async function deleteCampaign(id: string): Promise<void> {
    return api.delete(`/campaigns/${id}`)
}

export async function duplicateCampaign(id: string): Promise<Campaign> {
    const original = await getCampaign(id)
    const payload: CampaignCreate = {
        name: `${original.name} (Copy)`,
        email_template_id: original.email_template_id,
        recipient_type: original.recipient_type,
        filter_criteria: original.filter_criteria,
    }
    if (original.description) {
        payload.description = original.description
    }
    return createCampaign(payload)
}

// Preview & Send

export async function previewRecipients(
    campaignId: string,
    limit?: number
): Promise<CampaignPreview> {
    const query = limit ? `?limit=${limit}` : ""
    return api.get<CampaignPreview>(`/campaigns/${campaignId}/preview${query}`)
}

/**
 * Preview recipients matching filter criteria BEFORE creating a campaign.
 * Use this in Step 4 of campaign creation to show recipient count.
 */
export async function previewFilters(
    recipientType: "case" | "intended_parent",
    filterCriteria: FilterCriteria,
    limit?: number
): Promise<CampaignPreview> {
    const query = limit ? `?limit=${limit}` : ""
    return api.post<CampaignPreview>(`/campaigns/preview-filters${query}`, {
        recipient_type: recipientType,
        filter_criteria: filterCriteria,
    })
}

export async function sendCampaign(
    campaignId: string,
    sendNow = true
): Promise<CampaignSendResponse> {
    return api.post<CampaignSendResponse>(`/campaigns/${campaignId}/send`, { send_now: sendNow })
}

export async function cancelCampaign(campaignId: string): Promise<{ message: string }> {
    return api.post<{ message: string }>(`/campaigns/${campaignId}/cancel`)
}

// Runs

export async function listCampaignRuns(
    campaignId: string,
    limit?: number
): Promise<CampaignRun[]> {
    const query = limit ? `?limit=${limit}` : ""
    return api.get<CampaignRun[]>(`/campaigns/${campaignId}/runs${query}`)
}

export async function getCampaignRun(
    campaignId: string,
    runId: string
): Promise<CampaignRun> {
    return api.get<CampaignRun>(`/campaigns/${campaignId}/runs/${runId}`)
}

export async function listRunRecipients(
    campaignId: string,
    runId: string,
    params?: { status?: string; limit?: number; offset?: number }
): Promise<CampaignRecipient[]> {
    const query = new URLSearchParams()
    if (params?.status) query.set("status", params.status)
    if (params?.limit) query.set("limit", String(params.limit))
    if (params?.offset) query.set("offset", String(params.offset))

    const queryStr = query.toString()
    return api.get<CampaignRecipient[]>(
        `/campaigns/${campaignId}/runs/${runId}/recipients${queryStr ? `?${queryStr}` : ""}`
    )
}

// Suppression List

export async function listSuppressions(params?: {
    limit?: number
    offset?: number
}): Promise<Suppression[]> {
    const query = new URLSearchParams()
    if (params?.limit) query.set("limit", String(params.limit))
    if (params?.offset) query.set("offset", String(params.offset))

    const queryStr = query.toString()
    return api.get<Suppression[]>(`/campaigns/suppressions${queryStr ? `?${queryStr}` : ""}`)
}

export async function addSuppression(email: string, reason = "opt_out"): Promise<Suppression> {
    return api.post<Suppression>("/campaigns/suppressions", { email, reason })
}

export async function removeSuppression(email: string): Promise<void> {
    return api.delete(`/campaigns/suppressions/${encodeURIComponent(email)}`)
}
