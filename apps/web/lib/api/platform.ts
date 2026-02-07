/**
 * Platform admin API client for ops console.
 */

import api from '@/lib/api';
import type { FormSchema } from '@/lib/api/forms';
import type { ActionConfig, Condition } from '@/lib/api/workflows';
import type { JsonObject } from '@/lib/types/json';
import type { TemplateVariableRead } from '@/lib/types/template-variable';

// Platform user info (from /platform/me)
export interface PlatformUser {
    user_id: string;
    email: string;
    display_name: string;
    is_platform_admin: boolean;
}

// Organization summary for list view
export interface OrganizationSummary {
    id: string;
    name: string;
    slug: string;
    portal_base_url: string;
    timezone: string;
    member_count: number;
    surrogate_count: number;
    subscription_plan: string;
    subscription_status: string;
    created_at: string;
    deleted_at?: string | null;
    purge_at?: string | null;
}

// Organization detail (full info)
export interface OrganizationDetail extends OrganizationSummary {
    active_match_count: number;
    pending_task_count: number;
    ai_enabled: boolean;
    deleted_by_user_id?: string | null;
}

// Organization subscription
export interface OrganizationSubscription {
    id: string;
    organization_id: string;
    plan_key: 'starter' | 'professional' | 'enterprise';
    status: 'active' | 'trial' | 'past_due' | 'canceled';
    auto_renew: boolean;
    current_period_end: string;
    trial_end?: string;
    notes?: string;
    created_at: string;
    updated_at: string;
}

// Create org request
export interface CreateOrganizationRequest {
    name: string;
    slug: string;
    timezone: string;
    admin_email: string;
}

// Org member
export interface OrgMember {
    id: string;
    user_id: string;
    email: string;
    display_name: string;
    role: string;
    is_active: boolean;
    last_login_at?: string;
    created_at: string;
}

// Org invite
export interface OrgInvite {
    id: string;
    email: string;
    role: string;
    status: 'pending' | 'accepted' | 'expired' | 'revoked';
    invited_by_name?: string;
    expires_at?: string;
    created_at: string;
    resend_count?: number;
    can_resend?: boolean;
    resend_cooldown_seconds?: number | null;
    open_count?: number;
    opened_at?: string | null;
    click_count?: number;
    clicked_at?: string | null;
}

// Admin action log entry
export interface AdminActionLog {
    id: string;
    actor_email?: string;
    action: string;
    target_org_name?: string;
    target_user_email?: string;
    metadata?: Record<string, unknown>;
    created_at: string;
}

// Platform stats (for dashboard)
export interface PlatformStats {
    agency_count: number;
    active_user_count: number;
    open_alerts: number;
}

// =============================================================================
// Support Sessions (Role Override)
// =============================================================================

export type SupportSessionRole = 'intake_specialist' | 'case_manager' | 'admin' | 'developer';
export type SupportSessionMode = 'write' | 'read_only';
export type SupportSessionReasonCode =
    | 'onboarding_setup'
    | 'billing_help'
    | 'data_fix'
    | 'bug_repro'
    | 'incident_response'
    | 'other';

export interface SupportSession {
    id: string;
    org_id: string;
    role: SupportSessionRole;
    mode: SupportSessionMode;
    reason_code: SupportSessionReasonCode;
    reason_text: string | null;
    expires_at: string;
    created_at: string;
}

export interface CreateSupportSessionRequest {
    org_id: string;
    role: SupportSessionRole;
    reason_code: SupportSessionReasonCode;
    reason_text?: string | null;
    mode?: SupportSessionMode;
}

// Platform email sender status
export interface PlatformEmailStatus {
    configured: boolean;
    from_email: string | null;
    provider: string;
}

// Platform system email template
export interface SystemEmailTemplate {
    system_key: string;
    name: string;
    subject: string;
    from_email: string | null;
    body: string;
    is_active: boolean;
    current_version: number;
    updated_at: string | null;
}

export interface PlatformSystemEmailTemplateCreate {
    system_key: string;
    name: string;
    subject: string;
    from_email?: string | null;
    body: string;
    is_active?: boolean;
}

export interface PlatformEmailBranding {
    logo_url: string | null;
}

export interface PlatformSystemEmailCampaignTarget {
    org_id: string;
    user_ids: string[];
}

export interface PlatformSystemEmailCampaignRequest {
    targets: PlatformSystemEmailCampaignTarget[];
}

export interface PlatformSystemEmailCampaignFailure {
    org_id: string;
    user_id: string;
    email?: string;
    error: string;
}

export interface PlatformSystemEmailCampaignResponse {
    sent: number;
    suppressed: number;
    failed: number;
    recipients: number;
    failures: PlatformSystemEmailCampaignFailure[];
}

// Platform alert (cross-org)
export interface PlatformAlert {
    id: string;
    organization_id: string;
    org_name: string;
    alert_type: string;
    severity: 'critical' | 'error' | 'warn' | 'info';
    status: 'open' | 'acknowledged' | 'resolved';
    title: string;
    message?: string | undefined;
    occurrence_count: number;
    first_seen_at: string;
    last_seen_at: string;
    resolved_at?: string | undefined;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Get current platform admin user info.
 */
export function getPlatformMe(): Promise<PlatformUser> {
    return api.get<PlatformUser>('/platform/me');
}

/**
 * Get platform stats for dashboard.
 */
export function getPlatformStats(): Promise<PlatformStats> {
    return api.get<PlatformStats>('/platform/stats');
}

/**
 * Create a support session (role override) for a target organization.
 * Sets the session cookie for subsequent portal navigation.
 */
export function createSupportSession(data: CreateSupportSessionRequest): Promise<SupportSession> {
    return api.post<SupportSession>('/platform/support-sessions', data);
}

/**
 * Revoke a support session.
 */
export function revokeSupportSession(sessionId: string): Promise<{ status: 'revoked' }> {
    return api.post(`/platform/support-sessions/${sessionId}/revoke`);
}

/**
 * Get platform/system email sender status (Resend).
 */
export function getPlatformEmailStatus(): Promise<PlatformEmailStatus> {
    return api.get<PlatformEmailStatus>('/platform/email/status');
}

/**
 * List all organizations.
 */
export function listOrganizations(params?: {
    search?: string;
    status?: string;
    limit?: number;
    offset?: number;
}): Promise<{ items: OrganizationSummary[]; total: number }> {
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.set('search', params.search);
    if (params?.status) searchParams.set('status', params.status);
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());
    const query = searchParams.toString();
    return api.get(`/platform/orgs${query ? `?${query}` : ''}`);
}

/**
 * Get organization detail.
 */
export function getOrganization(orgId: string): Promise<OrganizationDetail> {
    return api.get<OrganizationDetail>(`/platform/orgs/${orgId}`);
}

/**
 * Create a new organization.
 */
export function createOrganization(data: CreateOrganizationRequest): Promise<OrganizationDetail> {
    return api.post<OrganizationDetail>('/platform/orgs', data);
}

/**
 * Update organization name and/or slug.
 *
 * Note: Slug changes have significant impact:
 * - Portal URL changes to https://{new_slug}.surrogacyforce.com
 * - Existing sessions become invalid, users must re-login
 * - Old slug immediately returns 404
 */
export function updateOrganization(
    orgId: string,
    data: { name?: string; slug?: string }
): Promise<OrganizationDetail> {
    return api.patch<OrganizationDetail>(`/platform/orgs/${orgId}`, data);
}

/**
 * Get organization subscription.
 */
export function getSubscription(orgId: string): Promise<OrganizationSubscription> {
    return api.get<OrganizationSubscription>(`/platform/orgs/${orgId}/subscription`);
}

/**
 * Update organization subscription.
 */
export function updateSubscription(
    orgId: string,
    data: Partial<Pick<OrganizationSubscription, 'plan_key' | 'status' | 'auto_renew' | 'notes'>>
): Promise<OrganizationSubscription> {
    return api.put<OrganizationSubscription>(`/platform/orgs/${orgId}/subscription`, data);
}

/**
 * Extend subscription by N days.
 */
export function extendSubscription(orgId: string, days: number = 30): Promise<OrganizationSubscription> {
    return api.post<OrganizationSubscription>(`/platform/orgs/${orgId}/subscription/extend`, { days });
}

/**
 * List organization members.
 */
export function listMembers(orgId: string): Promise<OrgMember[]> {
    return api.get<OrgMember[]>(`/platform/orgs/${orgId}/members`);
}

/**
 * Update member (role, deactivate).
 */
export function updateMember(
    orgId: string,
    memberId: string,
    data: { role?: string; is_active?: boolean }
): Promise<OrgMember> {
    return api.patch<OrgMember>(`/platform/orgs/${orgId}/members/${memberId}`, data);
}

/**
 * Reset MFA for a member (forces re-enrollment).
 */
export function resetMemberMfa(orgId: string, memberId: string): Promise<{ message: string }> {
    return api.post(`/platform/orgs/${orgId}/members/${memberId}/mfa/reset`);
}

/**
 * List organization invites.
 */
export function listInvites(orgId: string): Promise<OrgInvite[]> {
    return api.get<OrgInvite[]>(`/platform/orgs/${orgId}/invites`);
}

/**
 * Create invite.
 */
export function createInvite(
    orgId: string,
    data: { email: string; role: string }
): Promise<OrgInvite> {
    return api.post<OrgInvite>(`/platform/orgs/${orgId}/invites`, data);
}

/**
 * Revoke invite.
 */
export function revokeInvite(orgId: string, inviteId: string): Promise<void> {
    return api.post(`/platform/orgs/${orgId}/invites/${inviteId}/revoke`);
}

/**
 * Resend invite.
 */
export function resendInvite(orgId: string, inviteId: string): Promise<OrgInvite> {
    return api.post<OrgInvite>(`/platform/orgs/${orgId}/invites/${inviteId}/resend`);
}

/**
 * Soft delete an organization (30-day grace period).
 */
export function deleteOrganization(orgId: string): Promise<OrganizationDetail> {
    return api.post<OrganizationDetail>(`/platform/orgs/${orgId}/delete`);
}

/**
 * Restore a soft-deleted organization (within grace period).
 */
export function restoreOrganization(orgId: string): Promise<OrganizationDetail> {
    return api.post<OrganizationDetail>(`/platform/orgs/${orgId}/restore`);
}

/**
 * Permanently delete an organization immediately.
 */
export function purgeOrganization(
    orgId: string
): Promise<{ org_id: string; deleted: boolean; scheduled?: boolean; deleted_at?: string | null; purge_at?: string | null }> {
    return api.post(`/platform/orgs/${orgId}/purge`);
}

/**
 * Platform email branding (logo URL).
 */
export function getPlatformEmailBranding(): Promise<PlatformEmailBranding> {
    return api.get<PlatformEmailBranding>('/platform/email/branding');
}

export function updatePlatformEmailBranding(
    data: PlatformEmailBranding
): Promise<PlatformEmailBranding> {
    return api.put<PlatformEmailBranding>('/platform/email/branding', data);
}

export function uploadPlatformEmailBrandingLogo(
    file: File
): Promise<PlatformEmailBranding> {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<PlatformEmailBranding>('/platform/email/branding/logo', formData);
}

/**
 * List platform system email templates.
 */
export function listPlatformSystemEmailTemplates(): Promise<SystemEmailTemplate[]> {
    return api.get<SystemEmailTemplate[]>('/platform/email/system-templates');
}

/**
 * Create a new platform system email template.
 */
export function createPlatformSystemEmailTemplate(
    data: PlatformSystemEmailTemplateCreate
): Promise<SystemEmailTemplate> {
    return api.post<SystemEmailTemplate>('/platform/email/system-templates', data);
}

/**
 * Get platform system email template by system_key.
 */
export function getPlatformSystemEmailTemplate(
    systemKey: string
): Promise<SystemEmailTemplate> {
    return api.get<SystemEmailTemplate>(`/platform/email/system-templates/${systemKey}`);
}

/**
 * Variables allowed in platform system email templates (system-keyed).
 */
export function listPlatformSystemEmailTemplateVariables(systemKey: string): Promise<TemplateVariableRead[]> {
    return api.get<TemplateVariableRead[]>(`/platform/email/system-templates/${systemKey}/variables`);
}

/**
 * Update platform system email template by system_key.
 */
export function updatePlatformSystemEmailTemplate(
    systemKey: string,
    data: {
        subject: string;
        from_email?: string | null;
        body: string;
        is_active: boolean;
        expected_version?: number;
    }
): Promise<SystemEmailTemplate> {
    return api.put<SystemEmailTemplate>(
        `/platform/email/system-templates/${systemKey}`,
        data
    );
}

/**
 * Send a test email using a platform system email template.
 */
export function sendTestPlatformSystemEmailTemplate(
    systemKey: string,
    data: { to_email: string; org_id: string }
): Promise<{ sent: boolean; message_id?: string; email_log_id?: string }> {
    return api.post(`/platform/email/system-templates/${systemKey}/test`, data);
}

/**
 * Send a platform system email template to selected org users.
 */
export function sendPlatformSystemEmailCampaign(
    systemKey: string,
    data: PlatformSystemEmailCampaignRequest
): Promise<PlatformSystemEmailCampaignResponse> {
    return api.post(`/platform/email/system-templates/${systemKey}/campaign`, data);
}

/**
 * Get admin action logs for an org.
 */
export function getAdminActionLogs(
    orgId: string,
    params?: { limit?: number; offset?: number }
): Promise<{ items: AdminActionLog[]; total: number }> {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());
    const query = searchParams.toString();
    return api.get(`/platform/orgs/${orgId}/admin-actions${query ? `?${query}` : ''}`);
}

// =============================================================================
// Platform Alerts
// =============================================================================

/**
 * List all alerts across organizations.
 */
export function listAlerts(params?: {
    status?: string;
    severity?: string;
    org_id?: string;
    limit?: number;
    offset?: number;
}): Promise<{ items: PlatformAlert[]; total: number }> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.severity) searchParams.set('severity', params.severity);
    if (params?.org_id) searchParams.set('org_id', params.org_id);
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());
    const query = searchParams.toString();
    return api.get(`/platform/alerts${query ? `?${query}` : ''}`);
}

/**
 * Acknowledge an alert.
 */
export function acknowledgeAlert(alertId: string): Promise<{ id: string; status: string }> {
    return api.post(`/platform/alerts/${alertId}/acknowledge`);
}

/**
 * Resolve an alert.
 */
export function resolveAlert(alertId: string): Promise<{ id: string; status: string; resolved_at?: string }> {
    return api.post(`/platform/alerts/${alertId}/resolve`);
}

// =============================================================================
// Platform Template Studio
// =============================================================================

export type TemplateStatus = 'draft' | 'published' | 'archived'

export interface PlatformEmailTemplateDraft {
    name: string
    subject: string
    body: string
    from_email?: string | null
    category?: string | null
}

export interface PlatformEmailTemplateListItem {
    id: string
    status: TemplateStatus
    current_version: number
    published_version: number
    is_published_globally: boolean
    draft: PlatformEmailTemplateDraft
    published_at?: string | null
    updated_at: string
}

export interface PlatformEmailTemplate extends PlatformEmailTemplateListItem {
    target_org_ids?: string[]
    published?: PlatformEmailTemplateDraft | null
    created_at: string
}

export type PlatformEmailTemplateCreate = PlatformEmailTemplateDraft

export interface PlatformEmailTemplateUpdate {
    name?: string
    subject?: string
    body?: string
    from_email?: string | null
    category?: string | null
    expected_version?: number | null
}

export interface PlatformEmailTemplateTestSendRequest {
    org_id: string
    to_email: string
    variables?: Record<string, string>
    idempotency_key?: string | null
}

export interface EmailTemplateTestSendResponse {
    success: boolean
    provider_used?: 'resend' | 'gmail' | null
    email_log_id?: string | null
    message_id?: string | null
    error?: string | null
}

export interface PlatformFormTemplateDraft {
    name: string
    description?: string | null
    schema_json?: FormSchema | null
    settings_json?: Record<string, unknown> | null
}

export interface PlatformFormTemplateListItem {
    id: string
    status: TemplateStatus
    current_version: number
    published_version: number
    is_published_globally: boolean
    draft: PlatformFormTemplateDraft
    published_at?: string | null
    updated_at: string
}

export interface PlatformFormTemplate extends PlatformFormTemplateListItem {
    target_org_ids?: string[]
    published?: PlatformFormTemplateDraft | null
    created_at: string
}

export type PlatformFormTemplateCreate = PlatformFormTemplateDraft

export interface PlatformFormTemplateUpdate {
    name?: string
    description?: string | null
    schema_json?: FormSchema | null
    settings_json?: Record<string, unknown> | null
    expected_version?: number | null
}

export interface PlatformWorkflowTemplateDraft {
    name: string
    description?: string | null
    icon?: string
    category?: string
    trigger_type: string
    trigger_config?: JsonObject
    conditions?: Condition[]
    condition_logic?: string
    actions?: ActionConfig[]
}

export interface PlatformWorkflowTemplateListItem {
    id: string
    status: TemplateStatus
    published_version: number
    is_published_globally: boolean
    draft: PlatformWorkflowTemplateDraft
    published_at?: string | null
    updated_at: string
}

export interface PlatformWorkflowTemplate extends PlatformWorkflowTemplateListItem {
    target_org_ids?: string[]
    published?: PlatformWorkflowTemplateDraft | null
    created_at: string
}

export type PlatformWorkflowTemplateCreate = PlatformWorkflowTemplateDraft

export interface PlatformWorkflowTemplateUpdate {
    name?: string
    description?: string | null
    icon?: string
    category?: string
    trigger_type?: string
    trigger_config?: JsonObject
    conditions?: Condition[]
    condition_logic?: string
    actions?: ActionConfig[]
    expected_version?: number | null
}

export interface TemplatePublishRequest {
    publish_all: boolean
    org_ids?: string[] | null
}

export function listPlatformEmailTemplates(): Promise<PlatformEmailTemplateListItem[]> {
    return api.get<PlatformEmailTemplateListItem[]>('/platform/templates/email')
}

export function getPlatformEmailTemplate(id: string): Promise<PlatformEmailTemplate> {
    return api.get<PlatformEmailTemplate>(`/platform/templates/email/${id}`)
}

export function createPlatformEmailTemplate(
    payload: PlatformEmailTemplateCreate
): Promise<PlatformEmailTemplate> {
    return api.post<PlatformEmailTemplate>('/platform/templates/email', payload)
}

export function updatePlatformEmailTemplate(
    id: string,
    payload: PlatformEmailTemplateUpdate
): Promise<PlatformEmailTemplate> {
    return api.patch<PlatformEmailTemplate>(`/platform/templates/email/${id}`, payload)
}

export function publishPlatformEmailTemplate(
    id: string,
    payload: TemplatePublishRequest
): Promise<PlatformEmailTemplate> {
    return api.post<PlatformEmailTemplate>(`/platform/templates/email/${id}/publish`, payload)
}

export function sendTestPlatformEmailTemplate(
    id: string,
    payload: PlatformEmailTemplateTestSendRequest
): Promise<EmailTemplateTestSendResponse> {
    return api.post<EmailTemplateTestSendResponse>(`/platform/templates/email/${id}/test`, payload)
}

/**
 * Variables allowed in platform email templates (template studio).
 */
export function listPlatformEmailTemplateVariables(): Promise<TemplateVariableRead[]> {
    return api.get<TemplateVariableRead[]>('/platform/templates/email/variables');
}

export function listPlatformFormTemplates(): Promise<PlatformFormTemplateListItem[]> {
    return api.get<PlatformFormTemplateListItem[]>('/platform/templates/forms')
}

export function getPlatformFormTemplate(id: string): Promise<PlatformFormTemplate> {
    return api.get<PlatformFormTemplate>(`/platform/templates/forms/${id}`)
}

export function createPlatformFormTemplate(
    payload: PlatformFormTemplateCreate
): Promise<PlatformFormTemplate> {
    return api.post<PlatformFormTemplate>('/platform/templates/forms', payload)
}

export function updatePlatformFormTemplate(
    id: string,
    payload: PlatformFormTemplateUpdate
): Promise<PlatformFormTemplate> {
    return api.patch<PlatformFormTemplate>(`/platform/templates/forms/${id}`, payload)
}

export function publishPlatformFormTemplate(
    id: string,
    payload: TemplatePublishRequest
): Promise<PlatformFormTemplate> {
    return api.post<PlatformFormTemplate>(`/platform/templates/forms/${id}/publish`, payload)
}

export function listPlatformWorkflowTemplates(): Promise<PlatformWorkflowTemplateListItem[]> {
    return api.get<PlatformWorkflowTemplateListItem[]>('/platform/templates/workflows')
}

export function getPlatformWorkflowTemplate(id: string): Promise<PlatformWorkflowTemplate> {
    return api.get<PlatformWorkflowTemplate>(`/platform/templates/workflows/${id}`)
}

export function createPlatformWorkflowTemplate(
    payload: PlatformWorkflowTemplateCreate
): Promise<PlatformWorkflowTemplate> {
    return api.post<PlatformWorkflowTemplate>('/platform/templates/workflows', payload)
}

export function updatePlatformWorkflowTemplate(
    id: string,
    payload: PlatformWorkflowTemplateUpdate
): Promise<PlatformWorkflowTemplate> {
    return api.patch<PlatformWorkflowTemplate>(`/platform/templates/workflows/${id}`, payload)
}

export function publishPlatformWorkflowTemplate(
    id: string,
    payload: TemplatePublishRequest
): Promise<PlatformWorkflowTemplate> {
    return api.post<PlatformWorkflowTemplate>(`/platform/templates/workflows/${id}/publish`, payload)
}
