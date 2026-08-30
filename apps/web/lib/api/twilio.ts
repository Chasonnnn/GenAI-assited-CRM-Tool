/**
 * Organization-scoped Twilio messaging configuration and readiness contracts.
 *
 * Read models expose only masked identifiers and configured flags. Full
 * identifiers and secrets are accepted only by write/test requests.
 */

import api from "../api"

export type TwilioMessagingPurpose = "operational" | "promotional"
export type TwilioReadinessStatus =
    | "ready"
    | "degraded"
    | "blocked"
    | "not_configured"
    | "action_required"
    | "unknown"

export interface TwilioRouteSettings {
    purpose: TwilioMessagingPurpose
    messaging_service_sid_masked: string | null
    sender_phone_masked: string | null
    a2p_status: string
    advanced_opt_out_status: string
    consent_management_status: string
    capability_evidence: Record<string, unknown> | null
    inbound_webhook_url: string
    status_callback_url: string
    webhook_id: string
    enabled: boolean
}

export interface TwilioSettings {
    enabled: boolean
    account_sid_masked: string | null
    api_key_sid_masked: string | null
    api_secret_configured: boolean
    auth_token_configured: boolean
    legal_messaging_brand: string | null
    operational_disclosure: string | null
    promotional_disclosure: string | null
    sms_terms_url: string | null
    privacy_policy_url: string | null
    support_contact: string | null
    expected_frequency: string | null
    counsel_approved_at: string | null
    compliance_toolkit_enabled: boolean
    twilio_edition: string | null
    baa_verified_at: string | null
    compliance_approved_at: string | null
    phi_enabled: boolean
    current_version: number
    routes: Record<TwilioMessagingPurpose, TwilioRouteSettings>
}

export interface TwilioRouteSettingsUpdate {
    messaging_service_sid?: string
    sender_phone_e164?: string
    enabled?: boolean
}

export interface TwilioSettingsUpdate {
    enabled?: boolean
    account_sid?: string
    api_key_sid?: string
    api_secret?: string
    auth_token?: string
    legal_messaging_brand?: string | null
    operational_disclosure?: string | null
    promotional_disclosure?: string | null
    sms_terms_url?: string | null
    privacy_policy_url?: string | null
    support_contact?: string | null
    expected_frequency?: string | null
    counsel_approved_at?: string | null
    compliance_toolkit_enabled?: boolean
    twilio_edition?: string | null
    baa_verified_at?: string | null
    compliance_approved_at?: string | null
    phi_enabled?: boolean
    routes?: Partial<Record<TwilioMessagingPurpose, TwilioRouteSettingsUpdate>>
    expected_version: number
}

export interface TwilioCredentialTestRequest {
    account_sid?: string
    api_key_sid?: string
    api_secret?: string
    auth_token?: string
    routes?: Partial<
        Record<
            TwilioMessagingPurpose,
            { messaging_service_sid?: string; sender_phone_e164?: string }
        >
    >
}

export interface TwilioCredentialTestResponse {
    valid: boolean
    account_status: string | null
    twilio_edition: string | null
    capabilities: Record<string, boolean>
    route_capabilities: Partial<
        Record<TwilioMessagingPurpose, Record<string, boolean | string | null>>
    >
    error: string | null
    warning: string | null
}

export interface TwilioProviderCapabilities {
    send_sms: boolean
    send_mms: boolean
    receive_sms: boolean
    receive_mms: boolean
    status_callbacks: boolean
}

export interface TwilioRouteReadiness {
    status: TwilioReadinessStatus
    can_send_sms: boolean
    can_send_mms: boolean
    can_receive: boolean
    issues: string[]
}

export interface TwilioProviderReadiness {
    status: TwilioReadinessStatus
    credentials_valid: boolean
    account_status: string | null
    checked_at: string | null
    capabilities: TwilioProviderCapabilities
    routes: Record<TwilioMessagingPurpose, TwilioRouteReadiness>
}

export interface TwilioQueueReadiness {
    status: TwilioReadinessStatus
    queued_count: number
    processing_count: number
    failed_count: number
    oldest_queued_at: string | null
}

export interface TwilioReconciliationReadiness {
    status: TwilioReadinessStatus
    action_required_count: number
    unresolved_event_count: number
    last_reconciled_at: string | null
}

export interface TwilioReadinessIssue {
    code: string
    severity: "info" | "warning" | "error"
    message: string
    route: TwilioMessagingPurpose | null
}

export interface TwilioReadiness {
    overall_status: TwilioReadinessStatus
    checked_at: string | null
    provider: TwilioProviderReadiness
    local: {
        queue: TwilioQueueReadiness
        reconciliation: TwilioReconciliationReadiness
    }
    issues: TwilioReadinessIssue[]
}

export interface MessagingTemplateVersion {
    id: string
    template_key: string
    version: number
    name: string
    purpose: TwilioMessagingPurpose
    body: string
    status: "draft" | "published" | "retired"
    is_enrollment_confirmation: boolean
    content_classification: "no_phi" | "phi"
}

export function getTwilioSettings(): Promise<TwilioSettings> {
    return api.get<TwilioSettings>("/twilio/settings")
}

export function updateTwilioSettings(
    update: TwilioSettingsUpdate,
): Promise<TwilioSettings> {
    return api.patch<TwilioSettings>("/twilio/settings", update)
}

export function testTwilioCredentials(
    request: TwilioCredentialTestRequest,
): Promise<TwilioCredentialTestResponse> {
    return api.post<TwilioCredentialTestResponse>("/twilio/settings/test", request)
}

export function getTwilioReadiness(): Promise<TwilioReadiness> {
    return api.get<TwilioReadiness>("/twilio/readiness")
}

export function listMessagingTemplates(params?: {
    purpose?: TwilioMessagingPurpose
    status?: "draft" | "published" | "retired"
}): Promise<MessagingTemplateVersion[]> {
    const query = new URLSearchParams()
    if (params?.purpose) query.set("purpose", params.purpose)
    if (params?.status) query.set("status", params.status)
    const suffix = query.size ? `?${query.toString()}` : ""
    return api.get<MessagingTemplateVersion[]>(`/messaging/templates${suffix}`)
}
