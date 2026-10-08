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

export type TwilioSenderType = "10dlc" | "toll_free" | "unknown"
export type TwilioTollFreeVerificationStatus =
    | "PENDING_REVIEW"
    | "IN_REVIEW"
    | "TWILIO_APPROVED"
    | "TWILIO_REJECTED"

export interface TwilioRouteReadiness {
    status: TwilioReadinessStatus
    can_send_sms: boolean
    can_send_mms: boolean
    can_receive: boolean
    sender_type: TwilioSenderType | null
    toll_free_verification_status: TwilioTollFreeVerificationStatus | null
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

export type TwilioReadinessGateStatus = "pass" | "fail" | "pending" | "skipped"

/** One launch requirement, projected server-side from the same codes that gate sending. */
export interface TwilioReadinessGate {
    key: string
    label: string
    status: TwilioReadinessGateStatus
    detail: string | null
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
    gates: TwilioReadinessGate[]
}

export interface TwilioReadinessCheckResponse {
    check_status: "queued" | "running"
    queued_at: string
    readiness: TwilioReadiness
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
    published_at: string | null
    created_at: string
}

export interface MessagingTemplateCreate {
    name: string
    purpose: TwilioMessagingPurpose
    body: string
    is_enrollment_confirmation: boolean
}

export interface MessagingTemplateDraftUpdate {
    name?: string
    body?: string
    is_enrollment_confirmation?: boolean
}

export interface MessagingTemplateUse {
    kind: "workflow" | "campaign"
    id: string
    name: string
}

export interface MessagingTemplateUsage {
    template_key: string
    uses: MessagingTemplateUse[]
}

export interface MessagingSmsVariable {
    name: string
    description: string
    sample: string
}

export interface MessagingTestPhone {
    id: string
    label: string
    phone_last4: string
    verified_at: string | null
    code_expires_at: string | null
    stopped_purposes: TwilioMessagingPurpose[]
    created_by_name: string | null
    created_at: string
}

export interface MessagingTestSend {
    id: string
    provider_status: string | null
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

/** Queue a no-send provider check on the worker; the fresh evidence arrives via getTwilioReadiness. */
export function queueTwilioReadinessCheck(): Promise<TwilioReadinessCheckResponse> {
    return api.post<TwilioReadinessCheckResponse>("/twilio/readiness")
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

export function createMessagingTemplate(
    template: MessagingTemplateCreate,
): Promise<MessagingTemplateVersion> {
    return api.post<MessagingTemplateVersion>("/messaging/templates", template)
}

/** Edit a draft version in place. */
export function updateMessagingTemplateDraft(
    templateId: string,
    update: MessagingTemplateDraftUpdate,
): Promise<MessagingTemplateVersion> {
    return api.patch<MessagingTemplateVersion>(`/messaging/templates/${templateId}`, update)
}

/** Start the next draft version from the latest version of a template. */
export function createMessagingTemplateVersion(
    templateKey: string,
    update: MessagingTemplateDraftUpdate,
): Promise<MessagingTemplateVersion> {
    return api.post<MessagingTemplateVersion>(`/messaging/templates/${templateKey}/versions`, update)
}

export function publishMessagingTemplate(templateId: string): Promise<MessagingTemplateVersion> {
    return api.post<MessagingTemplateVersion>(`/messaging/templates/${templateId}/publish`)
}

export function listMessagingTemplateUsage(): Promise<MessagingTemplateUsage[]> {
    return api.get<MessagingTemplateUsage[]>("/messaging/templates/usage")
}

export function listMessagingSmsVariables(): Promise<MessagingSmsVariable[]> {
    return api.get<MessagingSmsVariable[]>("/messaging/template-variables")
}

export function sendMessagingTemplateTest(
    templateId: string,
    testPhoneId: string,
): Promise<MessagingTestSend> {
    return api.post<MessagingTestSend>(`/messaging/templates/${templateId}/test-sends`, {
        test_phone_id: testPhoneId,
    })
}

export function listMessagingTestPhones(): Promise<MessagingTestPhone[]> {
    return api.get<MessagingTestPhone[]>("/messaging/test-phones")
}

/** Add a test phone, or text a new code to one that is not verified yet. */
export function addMessagingTestPhone(request: {
    label: string
    phone: string
}): Promise<MessagingTestPhone> {
    return api.post<MessagingTestPhone>("/messaging/test-phones", request)
}

export function verifyMessagingTestPhone(
    testPhoneId: string,
    code: string,
): Promise<MessagingTestPhone> {
    return api.post<MessagingTestPhone>(`/messaging/test-phones/${testPhoneId}/verify`, { code })
}

export function removeMessagingTestPhone(testPhoneId: string): Promise<void> {
    return api.delete<void>(`/messaging/test-phones/${testPhoneId}`)
}
