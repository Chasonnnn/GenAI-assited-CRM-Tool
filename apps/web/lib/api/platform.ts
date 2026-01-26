/**
 * Platform admin API client for ops console.
 */

import api from '@/lib/api';

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

// Platform email sender status
export interface PlatformEmailStatus {
    configured: boolean;
    from_email: string | null;
    provider: string;
}

// Org-scoped system email template
export interface SystemEmailTemplate {
    system_key: string;
    subject: string;
    from_email: string | null;
    body: string;
    is_active: boolean;
    current_version: number;
    updated_at: string | null;
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
 * Get org-scoped system email template by system_key.
 */
export function getOrgSystemEmailTemplate(
    orgId: string,
    systemKey: string
): Promise<SystemEmailTemplate> {
    return api.get<SystemEmailTemplate>(`/platform/orgs/${orgId}/email/system-templates/${systemKey}`);
}

/**
 * Update org-scoped system email template by system_key.
 */
export function updateOrgSystemEmailTemplate(
    orgId: string,
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
        `/platform/orgs/${orgId}/email/system-templates/${systemKey}`,
        data
    );
}

/**
 * Send a test email using an org-scoped system email template.
 */
export function sendTestOrgSystemEmailTemplate(
    orgId: string,
    systemKey: string,
    data: { to_email: string }
): Promise<{ sent: boolean; message_id?: string; email_log_id?: string }> {
    return api.post(
        `/platform/orgs/${orgId}/email/system-templates/${systemKey}/test`,
        data
    );
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
