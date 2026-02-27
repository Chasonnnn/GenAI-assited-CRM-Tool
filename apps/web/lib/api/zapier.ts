/**
 * API client for Zapier webhook settings.
 */

import { api } from '../api';

export interface ZapierSettings {
    webhook_url: string;
    is_active: boolean;
    secret_configured: boolean;
    inbound_webhooks: ZapierInboundWebhook[];
    outbound_webhook_url?: string | null;
    outbound_enabled: boolean;
    outbound_secret_configured: boolean;
    send_hashed_pii: boolean;
    event_mapping: Array<{
        stage_key: string;
        event_name: string;
        enabled: boolean;
    }>;
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
    event_mapping?: Array<{
        stage_key: string;
        event_name: string;
        enabled: boolean;
    }>;
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

export async function parseZapierFieldPaste(
    payload: ZapierFieldPasteRequest,
): Promise<ZapierFieldPasteResponse> {
    return api.post<ZapierFieldPasteResponse>('/integrations/zapier/field-paste', payload);
}
