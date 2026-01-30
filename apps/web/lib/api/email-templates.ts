/**
 * Email Templates API client
 */

import api from './index'

// Types
export type EmailTemplateScope = 'org' | 'personal'

export interface EmailTemplate {
    id: string
    organization_id: string
    created_by_user_id: string | null
    name: string
    subject: string
    from_email: string | null
    body: string
    is_active: boolean
    scope: EmailTemplateScope
    owner_user_id: string | null
    owner_name: string | null
    source_template_id: string | null
    is_system_template: boolean
    current_version: number
    created_at: string
    updated_at: string
}

export interface EmailTemplateListItem {
    id: string
    name: string
    subject: string
    from_email: string | null
    is_active: boolean
    scope: EmailTemplateScope
    owner_user_id: string | null
    owner_name: string | null
    is_system_template: boolean
    created_at: string
    updated_at: string
}

export interface EmailTemplateCreate {
    name: string
    subject: string
    from_email?: string | null
    body: string
    scope?: EmailTemplateScope
}

export interface EmailTemplateCopyRequest {
    name: string
}

export interface EmailTemplateShareRequest {
    name: string
}

export interface EmailTemplateUpdate {
    name?: string
    subject?: string
    from_email?: string | null
    body?: string
    is_active?: boolean
    expected_version?: number
}

export interface EmailSendRequest {
    template_id: string
    recipient_email: string
    variables?: Record<string, string>
    surrogate_id?: string
    schedule_at?: string
}

export interface EmailLog {
    id: string
    organization_id: string
    job_id: string | null
    template_id: string | null
    surrogate_id: string | null
    recipient_email: string
    subject: string
    body: string
    status: string
    sent_at: string | null
    error: string | null
    created_at: string
}

export interface EmailTemplateVersion {
    id: string
    version: number
    payload: {
        name: string
        subject: string
        from_email: string | null
        body: string
        is_active: boolean
    }
    comment: string | null
    created_by_user_id: string | null
    created_at: string
}

export interface ListTemplatesParams {
    activeOnly?: boolean
    scope?: EmailTemplateScope | null
    showAllPersonal?: boolean
}

// API functions
export async function listTemplates(params: ListTemplatesParams = {}): Promise<EmailTemplateListItem[]> {
    const { activeOnly = true, scope, showAllPersonal = false } = params
    const searchParams = new URLSearchParams()
    searchParams.set('active_only', String(activeOnly))
    if (scope) {
        searchParams.set('scope', scope)
    }
    if (showAllPersonal) {
        searchParams.set('show_all_personal', 'true')
    }
    return api.get<EmailTemplateListItem[]>(`/email-templates?${searchParams.toString()}`)
}

export async function getTemplate(id: string): Promise<EmailTemplate> {
    return api.get<EmailTemplate>(`/email-templates/${id}`)
}

export async function createTemplate(data: EmailTemplateCreate): Promise<EmailTemplate> {
    return api.post<EmailTemplate>('/email-templates', data)
}

export async function updateTemplate(id: string, data: EmailTemplateUpdate): Promise<EmailTemplate> {
    return api.patch<EmailTemplate>(`/email-templates/${id}`, data)
}

export async function deleteTemplate(id: string): Promise<void> {
    return api.delete(`/email-templates/${id}`)
}

export async function sendEmail(data: EmailSendRequest): Promise<EmailLog> {
    return api.post<EmailLog>('/email-templates/send', data)
}

// ============================================================================
// Version History API
// ============================================================================

export async function getTemplateVersions(id: string): Promise<EmailTemplateVersion[]> {
    const response = await api.get<{ versions: EmailTemplateVersion[] }>(`/email-templates/${id}/versions`)
    return response.versions
}

export async function rollbackTemplate(id: string, version: number): Promise<EmailTemplate> {
    return api.post<EmailTemplate>(`/email-templates/${id}/rollback`, { target_version: version })
}

// ============================================================================
// Copy & Share API
// ============================================================================

/**
 * Copy an org/system template to your personal templates.
 * Any authenticated user can copy - no manage permission required.
 */
export async function copyTemplateToPersonal(
    id: string,
    data: EmailTemplateCopyRequest
): Promise<EmailTemplate> {
    return api.post<EmailTemplate>(`/email-templates/${id}/copy`, data)
}

/**
 * Share a personal template with the organization.
 * Creates an org copy while keeping the personal template.
 * Any user can share their own personal templates.
 */
export async function shareTemplateWithOrg(
    id: string,
    data: EmailTemplateShareRequest
): Promise<EmailTemplate> {
    return api.post<EmailTemplate>(`/email-templates/${id}/share`, data)
}
