/**
 * API client for ops endpoints (integration health, alerts).
 */

import { api } from '../api';

// Types
export interface IntegrationHealth {
    id: string;
    integration_type: string;
    integration_key: string | null;
    status: 'healthy' | 'degraded' | 'error';
    config_status: 'configured' | 'missing_token' | 'expired_token';
    last_success_at: string | null;
    last_error_at: string | null;
    last_error: string | null;
    error_count_24h: number;
}

export interface Alert {
    id: string;
    alert_type: string;
    severity: 'warn' | 'error' | 'critical';
    status: 'open' | 'acknowledged' | 'resolved' | 'snoozed';
    title: string;
    message: string | null;
    integration_key: string | null;
    occurrence_count: number;
    first_seen_at: string;
    last_seen_at: string;
    resolved_at: string | null;
}

export interface AlertSummary {
    warn: number;
    error: number;
    critical: number;
}

export interface AlertsListResponse {
    items: Alert[];
    total: number;
}

export interface AlertsListParams {
    status?: string;
    severity?: string;
    limit?: number;
    offset?: number;
}

// API Functions
export async function getIntegrationHealth(): Promise<IntegrationHealth[]> {
    return api.get<IntegrationHealth[]>('/ops/health');
}

export async function getAlertsSummary(): Promise<AlertSummary> {
    return api.get<AlertSummary>('/ops/alerts/summary');
}

export async function getAlerts(params: AlertsListParams = {}): Promise<AlertsListResponse> {
    const searchParams = new URLSearchParams();
    if (params.status) searchParams.set('status', params.status);
    if (params.severity) searchParams.set('severity', params.severity);
    if (params.limit) searchParams.set('limit', params.limit.toString());
    if (params.offset) searchParams.set('offset', params.offset.toString());

    const query = searchParams.toString();
    return api.get<AlertsListResponse>(`/ops/alerts${query ? `?${query}` : ''}`);
}

export async function resolveAlert(alertId: string): Promise<{ status: string; alert_id: string }> {
    return api.post<{ status: string; alert_id: string }>(`/ops/alerts/${alertId}/resolve`, {});
}

export async function acknowledgeAlert(alertId: string): Promise<{ status: string; alert_id: string }> {
    return api.post<{ status: string; alert_id: string }>(`/ops/alerts/${alertId}/acknowledge`, {});
}

export async function snoozeAlert(alertId: string, hours: number = 24): Promise<{ status: string; alert_id: string; hours: number }> {
    return api.post<{ status: string; alert_id: string; hours: number }>(`/ops/alerts/${alertId}/snooze?hours=${hours}`, {});
}
