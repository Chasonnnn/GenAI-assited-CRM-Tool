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
    leads_converted: number;
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
