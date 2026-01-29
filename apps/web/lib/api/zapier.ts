/**
 * API client for Zapier webhook settings.
 */

import { api } from '../api';

export interface ZapierSettings {
    webhook_url: string;
    is_active: boolean;
    secret_configured: boolean;
    outbound_webhook_url?: string | null;
    outbound_enabled: boolean;
    outbound_secret_configured: boolean;
    send_hashed_pii: boolean;
    event_mapping: Array<{
        stage_slug: string;
        event_name: string;
        enabled: boolean;
    }>;
}

export interface RotateZapierSecretResponse {
    webhook_url: string;
    webhook_secret: string;
}

export interface ZapierOutboundSettingsRequest {
    outbound_webhook_url?: string | null;
    outbound_webhook_secret?: string | null;
    outbound_enabled?: boolean;
    send_hashed_pii?: boolean;
    event_mapping?: Array<{
        stage_slug: string;
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
}

export interface ZapierOutboundTestRequest {
    stage_slug?: string;
    lead_id?: string;
}

export interface ZapierOutboundTestResponse {
    status: string;
    event_name: string;
    event_id: string;
}

export async function getZapierSettings(): Promise<ZapierSettings> {
    return api.get<ZapierSettings>('/integrations/zapier/settings');
}

export async function rotateZapierSecret(): Promise<RotateZapierSecretResponse> {
    return api.post<RotateZapierSecretResponse>('/integrations/zapier/settings/rotate-secret');
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
