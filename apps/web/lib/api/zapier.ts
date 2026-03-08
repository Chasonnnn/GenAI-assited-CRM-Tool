/**
 * API client for Zapier webhook settings.
 */

import { api } from '../api';

export type ZapierStageBucket = 'qualified' | 'converted' | 'lost' | 'not_qualified';

export interface ZapierEventMappingItem {
    stage_key: string;
    event_name: string;
    enabled: boolean;
    bucket?: ZapierStageBucket | null;
}

export interface ZapierSettings {
    webhook_url: string;
    is_active: boolean;
    secret_configured: boolean;
    inbound_webhooks: ZapierInboundWebhook[];
    outbound_webhook_url?: string | null;
    outbound_enabled: boolean;
    outbound_secret_configured: boolean;
    send_hashed_pii: boolean;
    event_mapping: ZapierEventMappingItem[];
}

export interface ZapierInboundWebhook {
    webhook_id: string;
    webhook_url: string;
    label?: string | null;
    is_active: boolean;
    secret_configured: boolean;
    created_at: string;
}

export interface RotateZapierSecretResponse {
    webhook_url: string;
    webhook_secret: string;
    webhook_id?: string | null;
}

export interface ZapierOutboundSettingsRequest {
    outbound_webhook_url?: string | null;
    outbound_webhook_secret?: string | null;
    outbound_enabled?: boolean;
    send_hashed_pii?: boolean;
    event_mapping?: ZapierEventMappingItem[];
}

export interface ZapierTestLeadRequest {
    form_id?: string;
    fields?: Record<string, unknown>;
}

export interface ZapierTestLeadResponse {
    status: string;
    duplicate: boolean;
    meta_lead_id: string;
    surrogate_id?: string | null;
    message?: string | null;
}

export interface ZapierInboundWebhookCreateRequest {
    label?: string | null;
}

export interface ZapierInboundWebhookCreateResponse {
    webhook_id: string;
    webhook_url: string;
    webhook_secret: string;
    label?: string | null;
    is_active: boolean;
}

export interface ZapierInboundWebhookUpdateRequest {
    label?: string | null;
    is_active?: boolean | null;
}

export interface ZapierOutboundTestRequest {
    stage_key?: string;
    lead_id?: string;
}

export interface ZapierOutboundTestResponse {
    status: string;
    event_name: string;
    event_id: string;
    lead_id: string;
}

export type ZapierOutboundEventStatus = 'queued' | 'delivered' | 'failed' | 'skipped';

export interface ZapierOutboundEvent {
    id: string;
    source: string;
    status: ZapierOutboundEventStatus;
    reason?: string | null;
    event_id?: string | null;
    event_name?: string | null;
    lead_id?: string | null;
    stage_key?: string | null;
    stage_slug?: string | null;
    stage_label?: string | null;
    surrogate_id?: string | null;
    attempts: number;
    last_error?: string | null;
    created_at: string;
    updated_at: string;
    delivered_at?: string | null;
    last_attempt_at?: string | null;
    can_retry: boolean;
}

export interface ZapierOutboundEventsResponse {
    items: ZapierOutboundEvent[];
    total: number;
}

export interface ZapierOutboundEventsSummary {
    window_hours: number;
    total_count: number;
    queued_count: number;
    delivered_count: number;
    failed_count: number;
    skipped_count: number;
    actionable_skipped_count: number;
    failure_rate: number;
    skipped_rate: number;
    failure_rate_alert: boolean;
    skipped_rate_alert: boolean;
    warning_messages: string[];
}

export interface ZapierOutboundEventsRequest {
    status?: ZapierOutboundEventStatus;
    limit?: number;
    offset?: number;
}

export interface RetryZapierOutboundEventRequest {
    reason?: string | null;
}

export interface ZapierFieldPasteRequest {
    paste: string;
    webhook_id?: string;
    form_id?: string;
    form_name?: string;
}

export interface ZapierFieldPasteResponse {
    form_id: string;
    form_name?: string | null;
    meta_form_id: string;
    field_count: number;
    field_keys: string[];
    mapping_url: string;
}

export async function getZapierSettings(): Promise<ZapierSettings> {
    return api.get<ZapierSettings>('/integrations/zapier/settings');
}

export async function rotateZapierSecret(): Promise<RotateZapierSecretResponse> {
    return api.post<RotateZapierSecretResponse>('/integrations/zapier/settings/rotate-secret');
}

export async function createZapierInboundWebhook(
    payload: ZapierInboundWebhookCreateRequest,
): Promise<ZapierInboundWebhookCreateResponse> {
    return api.post<ZapierInboundWebhookCreateResponse>('/integrations/zapier/webhooks', payload);
}

export async function rotateZapierInboundWebhookSecret(
    webhookId: string,
): Promise<RotateZapierSecretResponse> {
    return api.post<RotateZapierSecretResponse>(`/integrations/zapier/webhooks/${webhookId}/rotate-secret`);
}

export async function updateZapierInboundWebhook(
    webhookId: string,
    payload: ZapierInboundWebhookUpdateRequest,
): Promise<ZapierInboundWebhook> {
    return api.patch<ZapierInboundWebhook>(`/integrations/zapier/webhooks/${webhookId}`, payload);
}

export async function deleteZapierInboundWebhook(webhookId: string): Promise<void> {
    return api.delete<void>(`/integrations/zapier/webhooks/${webhookId}`);
}

export async function updateZapierOutboundSettings(
    payload: ZapierOutboundSettingsRequest,
): Promise<ZapierSettings> {
    return api.post<ZapierSettings>('/integrations/zapier/settings/outbound', payload);
}

export async function sendZapierTestLead(
    payload: ZapierTestLeadRequest,
): Promise<ZapierTestLeadResponse> {
    return api.post<ZapierTestLeadResponse>('/integrations/zapier/test-lead', payload);
}

export async function sendZapierOutboundTest(
    payload: ZapierOutboundTestRequest,
): Promise<ZapierOutboundTestResponse> {
    return api.post<ZapierOutboundTestResponse>('/integrations/zapier/test-outbound', payload);
}

export async function getZapierOutboundEvents(
    params: ZapierOutboundEventsRequest = {},
): Promise<ZapierOutboundEventsResponse> {
    const searchParams = new URLSearchParams();
    if (params.status) {
        searchParams.set('status', params.status);
    }
    if (params.limit !== undefined) {
        searchParams.set('limit', String(params.limit));
    }
    if (params.offset !== undefined) {
        searchParams.set('offset', String(params.offset));
    }
    const query = searchParams.toString();
    return api.get<ZapierOutboundEventsResponse>(
        `/integrations/zapier/events${query ? `?${query}` : ''}`,
    );
}

export async function getZapierOutboundEventsSummary(
    windowHours = 24,
): Promise<ZapierOutboundEventsSummary> {
    return api.get<ZapierOutboundEventsSummary>(
        `/integrations/zapier/events/summary?window_hours=${windowHours}`,
    );
}

export async function retryZapierOutboundEvent(
    eventId: string,
    payload: RetryZapierOutboundEventRequest = {},
): Promise<ZapierOutboundEvent> {
    return api.post<ZapierOutboundEvent>(`/integrations/zapier/events/${eventId}/retry`, payload);
}

export async function parseZapierFieldPaste(
    payload: ZapierFieldPasteRequest,
): Promise<ZapierFieldPasteResponse> {
    return api.post<ZapierFieldPasteResponse>('/integrations/zapier/field-paste', payload);
}
