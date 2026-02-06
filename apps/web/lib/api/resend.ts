/**
 * API client for Resend email configuration endpoints.
 */

import { api } from '../api';

// Types
export interface ResendSettings {
    email_provider: 'resend' | 'gmail' | null;
    api_key_masked: string | null;
    from_email: string | null;
    from_name: string | null;
    reply_to_email: string | null;
    verified_domain: string | null;
    last_key_validated_at: string | null;
    default_sender_user_id: string | null;
    default_sender_name: string | null;
    default_sender_email: string | null;
    webhook_url: string;
    webhook_signing_secret_configured: boolean;
    current_version: number;
}

export interface ResendSettingsUpdate {
    email_provider?: 'resend' | 'gmail' | '';
    api_key?: string;
    from_email?: string;
    from_name?: string;
    reply_to_email?: string;
    webhook_signing_secret?: string;
    default_sender_user_id?: string | null;
    expected_version?: number;
}

export interface TestKeyResponse {
    valid: boolean;
    error: string | null;
    verified_domains: string[];
}

export interface RotateWebhookResponse {
    webhook_url: string;
}

export interface EligibleSender {
    user_id: string;
    display_name: string;
    email: string;
    gmail_email: string;
}

// ============================================================================
// Settings API
// ============================================================================

export async function getResendSettings(): Promise<ResendSettings> {
    return api.get<ResendSettings>('/resend/settings');
}

export async function updateResendSettings(update: ResendSettingsUpdate): Promise<ResendSettings> {
    return api.patch<ResendSettings>('/resend/settings', update);
}

export async function testResendKey(api_key: string): Promise<TestKeyResponse> {
    return api.post<TestKeyResponse>('/resend/settings/test', { api_key });
}

export async function rotateWebhook(): Promise<RotateWebhookResponse> {
    return api.post<RotateWebhookResponse>('/resend/settings/rotate-webhook');
}

// ============================================================================
// Gmail Senders API
// ============================================================================

export async function listEligibleSenders(): Promise<EligibleSender[]> {
    return api.get<EligibleSender[]>('/resend/eligible-senders');
}
