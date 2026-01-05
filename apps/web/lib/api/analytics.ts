/**
 * API client for analytics endpoints.
 */

import { api } from '../api';

// Types
export interface AnalyticsSummary {
    total_cases: number;
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

export async function getCasesByStatus(): Promise<StatusCount[]> {
    return api.get<StatusCount[]>('/analytics/cases/by-status');
}

export async function getCasesByAssignee(): Promise<AssigneeCount[]> {
    return api.get<AssigneeCount[]>('/analytics/cases/by-assignee');
}

export async function getCasesTrend(params: TrendParams = {}): Promise<TrendPoint[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);
    if (params.period) searchParams.set('period', params.period);

    const query = searchParams.toString();
    return api.get<TrendPoint[]>(`/analytics/cases/trend${query ? `?${query}` : ''}`);
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
    new_cases: number;
    new_cases_change_pct: number;
    total_active: number;
    needs_attention: number;
    period_days: number;
}

// New API functions
export async function getCasesBySource(params: DateRangeParams = {}): Promise<SourceCount[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);

    const query = searchParams.toString();
    const res = await api.get<{ data: SourceCount[] }>(`/analytics/cases/by-source${query ? `?${query}` : ''}`);
    return res.data;
}

export async function getCasesByState(params: DateRangeParams = {}): Promise<StateCount[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);

    const query = searchParams.toString();
    const res = await api.get<{ data: StateCount[] }>(`/analytics/cases/by-state${query ? `?${query}` : ''}`);
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

export async function getCasesByStateCompare(params: CompareParams = {}): Promise<StateCount[]> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);
    if (params.ad_id) searchParams.set('ad_id', params.ad_id);

    const query = searchParams.toString();
    const res = await api.get<{ data: StateCount[] }>(`/analytics/cases/by-state/compare${query ? `?${query}` : ''}`);
    return res.data;
}

// Meta Spend types
export interface CampaignSpend {
    campaign_id: string;
    campaign_name: string;
    spend: number;
    impressions: number;
    reach: number;
    clicks: number;
    leads: number;
    cost_per_lead: number | null;
}

export interface MetaSpendSummary {
    total_spend: number;
    total_impressions: number;
    total_leads: number;
    cost_per_lead: number | null;
    campaigns: CampaignSpend[];
    time_series?: MetaSpendTimePoint[];
    breakdowns?: MetaSpendBreakdown[];
}

export interface MetaSpendTimePoint {
    date_start: string;
    date_stop: string;
    spend: number;
    impressions: number;
    reach: number;
    clicks: number;
    leads: number;
    cost_per_lead: number | null;
}

export interface MetaSpendBreakdown {
    breakdown_values: Record<string, string>;
    spend: number;
    impressions: number;
    reach: number;
    clicks: number;
    leads: number;
    cost_per_lead: number | null;
}

export async function getMetaSpend(params: DateRangeParams = {}): Promise<MetaSpendSummary> {
    const searchParams = new URLSearchParams();
    if (params.from_date) searchParams.set('from_date', params.from_date);
    if (params.to_date) searchParams.set('to_date', params.to_date);

    const query = searchParams.toString();
    return api.get<MetaSpendSummary>(`/analytics/meta/spend${query ? `?${query}` : ''}`);
}

// Activity Feed types
export interface ActivityFeedItem {
    id: string;
    activity_type: string;
    case_id: string;
    case_number: string | null;
    case_name: string | null;
    actor_name: string | null;
    details: Record<string, unknown> | null;
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
    total_cases: number;
    archived_count: number;
    contacted: number;
    qualified: number;
    pending_match: number;
    matched: number;
    applied: number;
    lost: number;
    conversion_rate: number;
    avg_days_to_match: number | null;
    avg_days_to_apply: number | null;
}

export interface UnassignedPerformanceData {
    total_cases: number;
    archived_count: number;
    contacted: number;
    qualified: number;
    pending_match: number;
    matched: number;
    applied: number;
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
