/**
 * Email Templates API client
 */

import api from './index'

// Types
export interface EmailTemplate {
    id: string
    organization_id: string
    created_by_user_id: string | null
    name: string
    subject: string
    from_email: string | null
    body: string
    is_active: boolean
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
    created_at: string
    updated_at: string
}

export interface EmailTemplateCreate {
    name: string
    subject: string
    from_email?: string | null
    body: string
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

// API functions
export async function listTemplates(activeOnly: boolean = true): Promise<EmailTemplateListItem[]> {
    return api.get<EmailTemplateListItem[]>(`/email-templates?active_only=${activeOnly}`)
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
