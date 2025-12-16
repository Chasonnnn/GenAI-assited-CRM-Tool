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
