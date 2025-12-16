/**
 * React Query hooks for Analytics module.
 */

import { useQuery } from '@tanstack/react-query';
import * as analyticsApi from '../api/analytics';
import type { DateRangeParams, TrendParams } from '../api/analytics';

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
 */
export function useCasesByStatus() {
    return useQuery({
        queryKey: analyticsKeys.byStatus(),
        queryFn: analyticsApi.getCasesByStatus,
        staleTime: 60 * 1000,
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
 */
export function useCasesTrend(params: TrendParams = {}) {
    return useQuery({
        queryKey: analyticsKeys.trend(params),
        queryFn: () => analyticsApi.getCasesTrend(params),
        staleTime: 60 * 1000,
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
