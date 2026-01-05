/**
 * React Query hooks for Analytics module.
 */

import { useQuery } from '@tanstack/react-query';
import * as analyticsApi from '../api/analytics';
import type { DateRangeParams, TrendParams, PerformanceByUserParams } from '../api/analytics';

// Query keys
export const analyticsKeys = {
    all: ['analytics'] as const,
    summary: (params?: DateRangeParams) => [...analyticsKeys.all, 'summary', params] as const,
    byStatus: () => [...analyticsKeys.all, 'by-status'] as const,
    byAssignee: () => [...analyticsKeys.all, 'by-assignee'] as const,
    trend: (params?: TrendParams) => [...analyticsKeys.all, 'trend', params] as const,
    metaPerformance: (params?: DateRangeParams) => [...analyticsKeys.all, 'meta', params] as const,
};

/**
 * Fetch analytics summary.
 */
export function useAnalyticsSummary(params: DateRangeParams = {}) {
    return useQuery({
        queryKey: analyticsKeys.summary(params),
        queryFn: () => analyticsApi.getAnalyticsSummary(params),
        staleTime: 60 * 1000, // 1 minute
    });
}

/**
 * Fetch cases by status.
 * Auto-refreshes every 60 seconds for real-time updates.
 */
export function useCasesByStatus() {
    return useQuery({
        queryKey: analyticsKeys.byStatus(),
        queryFn: analyticsApi.getCasesByStatus,
        staleTime: 60 * 1000,
        refetchInterval: 60 * 1000, // Auto-refresh every 60 seconds
    });
}

/**
 * Fetch cases by assignee.
 */
export function useCasesByAssignee() {
    return useQuery({
        queryKey: analyticsKeys.byAssignee(),
        queryFn: analyticsApi.getCasesByAssignee,
        staleTime: 60 * 1000,
    });
}

/**
 * Fetch cases trend over time.
 * Auto-refreshes every 60 seconds for real-time updates.
 */
export function useCasesTrend(params: TrendParams = {}) {
    return useQuery({
        queryKey: analyticsKeys.trend(params),
        queryFn: () => analyticsApi.getCasesTrend(params),
        staleTime: 60 * 1000,
        refetchInterval: 60 * 1000, // Auto-refresh every 60 seconds
    });
}

/**
 * Fetch Meta Lead Ads performance.
 */
export function useMetaPerformance(params: DateRangeParams = {}) {
    return useQuery({
        queryKey: analyticsKeys.metaPerformance(params),
        queryFn: () => analyticsApi.getMetaPerformance(params),
        staleTime: 60 * 1000,
    });
}

/**
 * Fetch cases by source.
 */
export function useCasesBySource(params: DateRangeParams = {}) {
    return useQuery({
        queryKey: [...analyticsKeys.all, 'by-source', params] as const,
        queryFn: () => analyticsApi.getCasesBySource(params),
        staleTime: 60 * 1000,
    });
}

/**
 * Fetch cases by state.
 */
export function useCasesByState(params: DateRangeParams = {}) {
    return useQuery({
        queryKey: [...analyticsKeys.all, 'by-state', params] as const,
        queryFn: () => analyticsApi.getCasesByState(params),
        staleTime: 60 * 1000,
    });
}

/**
 * Fetch conversion funnel.
 */
export function useFunnel(params: DateRangeParams = {}) {
    return useQuery({
        queryKey: [...analyticsKeys.all, 'funnel', params] as const,
        queryFn: () => analyticsApi.getFunnel(params),
        staleTime: 60 * 1000,
    });
}

/**
 * Fetch KPIs.
 */
export function useKPIs(params: DateRangeParams = {}) {
    return useQuery({
        queryKey: [...analyticsKeys.all, 'kpis', params] as const,
        queryFn: () => analyticsApi.getKPIs(params),
        staleTime: 60 * 1000,
    });
}

interface CompareParams extends DateRangeParams {
    ad_id?: string;
}

/**
 * Fetch campaigns for filter dropdown.
 */
export function useCampaigns() {
    return useQuery({
        queryKey: [...analyticsKeys.all, 'campaigns'] as const,
        queryFn: analyticsApi.getCampaigns,
        staleTime: 5 * 60 * 1000,
    });
}

/**
 * Fetch funnel with campaign filter.
 */
export function useFunnelCompare(params: CompareParams = {}) {
    return useQuery({
        queryKey: [...analyticsKeys.all, 'funnel-compare', params] as const,
        queryFn: () => analyticsApi.getFunnelCompare(params),
        staleTime: 60 * 1000,
    });
}

/**
 * Fetch cases by state with campaign filter.
 */
export function useCasesByStateCompare(params: CompareParams = {}) {
    return useQuery({
        queryKey: [...analyticsKeys.all, 'by-state-compare', params] as const,
        queryFn: () => analyticsApi.getCasesByStateCompare(params),
        staleTime: 60 * 1000,
    });
}

/**
 * Fetch Meta Ads spend data.
 */
export function useMetaSpend(params: DateRangeParams = {}) {
    return useQuery({
        queryKey: [...analyticsKeys.all, 'meta-spend', params] as const,
        queryFn: () => analyticsApi.getMetaSpend(params),
        staleTime: 60 * 1000,
    });
}

interface ActivityFeedParams {
    limit?: number;
    offset?: number;
    activity_type?: string;
    user_id?: string;
}

/**
 * Fetch org-wide activity feed.
 */
export function useActivityFeed(params: ActivityFeedParams = {}) {
    return useQuery({
        queryKey: [...analyticsKeys.all, 'activity-feed', params] as const,
        queryFn: () => analyticsApi.getActivityFeed(params),
        staleTime: 30 * 1000, // 30 seconds - activity feeds need fresher data
    });
}

/**
 * Fetch individual performance by user.
 * Supports cohort mode (cases created in range) and activity mode (status changes in range).
 */
export function usePerformanceByUser(params: PerformanceByUserParams = {}) {
    return useQuery({
        queryKey: [...analyticsKeys.all, 'performance-by-user', params] as const,
        queryFn: () => analyticsApi.getPerformanceByUser(params),
        staleTime: 60 * 1000,
    });
}
