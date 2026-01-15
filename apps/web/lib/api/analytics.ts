/**
 * API client for analytics endpoints.
 */

import { api } from '../api';
import type { JsonObject } from '../types/json';

// Types
export interface AnalyticsSummary {
    total_surrogates: number;
    new_this_period: number;
    qualified_rate: number;
    avg_time_to_qualified_hours: number | null;
}

export interface StatusCount {
    status: string;
    count: number;
}

export interface AssigneeCount {
    user_id: string | null;
    user_email: string | null;
    count: number;
}

export interface TrendPoint {
    date: string;
    count: number;
}

export interface MetaPerformance {
    leads_received: number;
    leads_qualified: number;
    leads_converted: number;
    qualification_rate: number;
    conversion_rate: number;
    avg_time_to_convert_hours: number | null;
}

export interface DateRangeParams {
    from_date?: string;
    to_date?: string;
}

export interface TrendParams extends DateRangeParams {
    period?: 'day' | 'week' | 'month';
}

// API Functions
export async function getAnalyticsSummary(params: DateRangeParams = {}): Promise<AnalyticsSummary> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);

    const query = searchParams.toString();
    return api.get<AnalyticsSummary>(`/analytics/summary${query ? `?${query}` : ''}`);
}

export async function getSurrogatesByStatus(): Promise<StatusCount[]> {
    return api.get<StatusCount[]>('/analytics/surrogates/by-status');
}

export async function getSurrogatesByAssignee(): Promise<AssigneeCount[]> {
    return api.get<AssigneeCount[]>('/analytics/surrogates/by-assignee');
}

export async function getSurrogatesTrend(params: TrendParams = {}): Promise<TrendPoint[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);
    if (params.period) searchParams.set('period', params.period);

    const query = searchParams.toString();
    return api.get<TrendPoint[]>(`/analytics/surrogates/trend${query ? `?${query}` : ''}`);
}

export async function getMetaPerformance(params: DateRangeParams = {}): Promise<MetaPerformance> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);

    const query = searchParams.toString();
    return api.get<MetaPerformance>(`/analytics/meta/performance${query ? `?${query}` : ''}`);
}

// New types for Phase A endpoints
export interface SourceCount {
    source: string;
    count: number;
}

export interface StateCount {
    state: string;
    count: number;
}

export interface FunnelStage {
    stage: string;
    label: string;
    count: number;
    percentage: number;
}

export interface KPIs {
    new_surrogates: number;
    new_surrogates_change_pct: number;
    total_active: number;
    needs_attention: number;
    period_days: number;
}

// New API functions
export async function getSurrogatesBySource(params: DateRangeParams = {}): Promise<SourceCount[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);

    const query = searchParams.toString();
    const res = await api.get<{ data: SourceCount[] }>(`/analytics/surrogates/by-source${query ? `?${query}` : ''}`);
    return res.data;
}

export async function getSurrogatesByState(params: DateRangeParams = {}): Promise<StateCount[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);

    const query = searchParams.toString();
    const res = await api.get<{ data: StateCount[] }>(`/analytics/surrogates/by-state${query ? `?${query}` : ''}`);
    return res.data;
}

export async function getFunnel(params: DateRangeParams = {}): Promise<FunnelStage[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);

    const query = searchParams.toString();
    const res = await api.get<{ data: FunnelStage[] }>(`/analytics/funnel${query ? `?${query}` : ''}`);
    return res.data;
}

export async function getKPIs(params: DateRangeParams = {}): Promise<KPIs> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);

    const query = searchParams.toString();
    return api.get<KPIs>(`/analytics/kpis${query ? `?${query}` : ''}`);
}

// Campaign types
export interface Campaign {
    ad_id: string;
    ad_name: string;
    lead_count: number;
}

interface CompareParams extends DateRangeParams {
    ad_id?: string;
}

export async function getCampaigns(): Promise<Campaign[]> {
    const res = await api.get<{ data: Campaign[] }>('/analytics/campaigns');
    return res.data;
}

export async function getFunnelCompare(params: CompareParams = {}): Promise<FunnelStage[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);
    if (params.ad_id) searchParams.set('ad_id', params.ad_id);

    const query = searchParams.toString();
    const res = await api.get<{ data: FunnelStage[] }>(`/analytics/funnel/compare${query ? `?${query}` : ''}`);
    return res.data;
}

export async function getSurrogatesByStateCompare(params: CompareParams = {}): Promise<StateCount[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);
    if (params.ad_id) searchParams.set('ad_id', params.ad_id);

    const query = searchParams.toString();
    const res = await api.get<{ data: StateCount[] }>(`/analytics/surrogates/by-state/compare${query ? `?${query}` : ''}`);
    return res.data;
}

// Activity Feed types
export interface ActivityFeedItem {
    id: string;
    activity_type: string;
    surrogate_id: string;
    surrogate_number: string | null;
    surrogate_name: string | null;
    actor_name: string | null;
    details: JsonObject | null;
    created_at: string;
}

export interface ActivityFeedResponse {
    items: ActivityFeedItem[];
    has_more: boolean;
}

export interface ActivityFeedParams {
    limit?: number;
    offset?: number;
    activity_type?: string;
    user_id?: string;
}

export async function getActivityFeed(params: ActivityFeedParams = {}): Promise<ActivityFeedResponse> {
    const searchParams = new URLSearchParams();
    if (params.limit) searchParams.set('limit', params.limit.toString());
    if (params.offset) searchParams.set('offset', params.offset.toString());
    if (params.activity_type) searchParams.set('activity_type', params.activity_type);
    if (params.user_id) searchParams.set('user_id', params.user_id);

    const query = searchParams.toString();
    return api.get<ActivityFeedResponse>(`/analytics/activity-feed${query ? `?${query}` : ''}`);
}

// Performance by User types
export interface UserPerformanceData {
    user_id: string;
    user_name: string;
    total_surrogates: number;
    archived_count: number;
    contacted: number;
    qualified: number;
    ready_to_match: number;
    matched: number;
    application_submitted: number;
    lost: number;
    conversion_rate: number;
    avg_days_to_match: number | null;
    avg_days_to_application_submitted: number | null;
}

export interface UnassignedPerformanceData {
    total_surrogates: number;
    archived_count: number;
    contacted: number;
    qualified: number;
    ready_to_match: number;
    matched: number;
    application_submitted: number;
    lost: number;
}

export interface PerformanceByUserResponse {
    from_date: string;
    to_date: string;
    mode: 'cohort' | 'activity';
    as_of: string;
    pipeline_id: string | null;
    data: UserPerformanceData[];
    unassigned: UnassignedPerformanceData;
}

export interface PerformanceByUserParams extends DateRangeParams {
    mode?: 'cohort' | 'activity';
}

export async function getPerformanceByUser(params: PerformanceByUserParams = {}): Promise<PerformanceByUserResponse> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);
    if (params.mode) searchParams.set('mode', params.mode);

    const query = searchParams.toString();
    return api.get<PerformanceByUserResponse>(`/analytics/performance/by-user${query ? `?${query}` : ''}`);
}

/**
 * Export analytics as PDF.
 * Uses a hidden iframe to download with cookies.
 */
export async function exportAnalyticsPDF(params: DateRangeParams = {}): Promise<void> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);

    const query = searchParams.toString();
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
    const url = `${baseUrl}/analytics/export/pdf${query ? `?${query}` : ''}`;

    const response = await fetch(url, {
        method: 'GET',
        credentials: 'include',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        },
    });

    if (!response.ok) {
        throw new Error(`Export failed (${response.status})`);
    }

    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/pdf')) {
        const errorText = await response.text();
        throw new Error(errorText || 'Export failed (unexpected response)');
    }

    const filenameDate = (params.to_date || params.from_date || new Date().toISOString().slice(0, 10))
        .replace(/-/g, '');
    const filename = `${filenameDate}report.pdf`;

    const buffer = await response.arrayBuffer();
    const headerBytes = new Uint8Array(buffer.slice(0, 4));
    const headerText = String.fromCharCode(...headerBytes);
    if (headerText !== '%PDF') {
        const errorText = new TextDecoder().decode(buffer);
        throw new Error(errorText || 'Export failed (invalid PDF)');
    }

    const blob = new Blob([buffer], { type: 'application/pdf' });
    const blobUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(blobUrl);
}

// =============================================================================
// Meta Ad Account Types (Stored Data)
// =============================================================================

export interface MetaAdAccount {
    id: string;
    ad_account_external_id: string;
    ad_account_name: string;
    hierarchy_synced_at: string | null;
    spend_synced_at: string | null;
}

export interface SpendSyncStatus {
    sync_status: 'synced' | 'pending' | 'never';
    last_synced_at: string | null;
    ad_accounts_configured: number;
}

export interface StoredCampaignSpend {
    campaign_external_id: string;
    campaign_name: string;
    spend: number;
    impressions: number;
    clicks: number;
    leads: number;
    cost_per_lead: number | null;
}

export interface SpendBreakdownItem {
    breakdown_value: string;
    spend: number;
    impressions: number;
    clicks: number;
    leads: number;
    cost_per_lead: number | null;
}

export interface SpendTrendPoint {
    date: string;
    spend: number;
    impressions: number;
    clicks: number;
    leads: number;
    cost_per_lead: number | null;
}

export interface SpendTotals extends SpendSyncStatus {
    total_spend: number;
    total_impressions: number;
    total_clicks: number;
    total_leads: number;
    cost_per_lead: number | null;
}

export interface FormPerformance {
    form_external_id: string;
    form_name: string;
    lead_count: number;
    surrogate_count: number;
    qualified_count: number;
    conversion_rate: number;
    qualified_rate: number;
}

export interface MetaCampaignListItem {
    campaign_external_id: string;
    campaign_name: string;
    status: string;
    objective: string | null;
}

// Params interfaces
export interface SpendParams extends DateRangeParams {
    ad_account_id?: string;
}

export interface SpendTrendParams extends SpendParams {
    campaign_external_id?: string;
}

export interface BreakdownParams extends SpendParams {
    breakdown_type: 'publisher_platform' | 'platform_position' | 'age' | 'region';
}

// =============================================================================
// Meta Ad Account API Functions
// =============================================================================

export async function getMetaAdAccounts(): Promise<MetaAdAccount[]> {
    const res = await api.get<{ data: MetaAdAccount[] }>('/analytics/meta/ad-accounts');
    return res.data;
}

export async function getSpendTotals(params: SpendParams = {}): Promise<SpendTotals> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);
    if (params.ad_account_id) searchParams.set('ad_account_id', params.ad_account_id);

    const query = searchParams.toString();
    return api.get<SpendTotals>(`/analytics/meta/spend/totals${query ? `?${query}` : ''}`);
}

export async function getSpendByCampaign(params: SpendParams = {}): Promise<StoredCampaignSpend[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);
    if (params.ad_account_id) searchParams.set('ad_account_id', params.ad_account_id);

    const query = searchParams.toString();
    const res = await api.get<{ data: StoredCampaignSpend[] }>(`/analytics/meta/spend/by-campaign${query ? `?${query}` : ''}`);
    return res.data;
}

export async function getSpendByBreakdown(params: BreakdownParams): Promise<SpendBreakdownItem[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);
    if (params.ad_account_id) searchParams.set('ad_account_id', params.ad_account_id);
    searchParams.set('breakdown_type', params.breakdown_type);

    const query = searchParams.toString();
    const res = await api.get<{ data: SpendBreakdownItem[] }>(`/analytics/meta/spend/by-breakdown?${query}`);
    return res.data;
}

export async function getSpendTrend(params: SpendTrendParams = {}): Promise<SpendTrendPoint[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);
    if (params.ad_account_id) searchParams.set('ad_account_id', params.ad_account_id);
    if (params.campaign_external_id) searchParams.set('campaign_external_id', params.campaign_external_id);

    const query = searchParams.toString();
    const res = await api.get<{ data: SpendTrendPoint[] }>(`/analytics/meta/spend/trend${query ? `?${query}` : ''}`);
    return res.data;
}

export async function getFormPerformance(params: DateRangeParams = {}): Promise<FormPerformance[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);

    const query = searchParams.toString();
    const res = await api.get<{ data: FormPerformance[] }>(`/analytics/meta/forms${query ? `?${query}` : ''}`);
    return res.data;
}

export async function getMetaCampaignList(params: { ad_account_id?: string } = {}): Promise<MetaCampaignListItem[]> {
    const searchParams = new URLSearchParams();
    if (params.ad_account_id) searchParams.set('ad_account_id', params.ad_account_id);

    const query = searchParams.toString();
    const res = await api.get<{ data: MetaCampaignListItem[] }>(`/analytics/meta/campaigns${query ? `?${query}` : ''}`);
    return res.data;
}
