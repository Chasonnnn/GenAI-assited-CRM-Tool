/**
 * Email Templates API client
 */

import { api } from './base'

// Types
export interface EmailTemplate {
    id: string
    organization_id: string
    created_by_user_id: string | null
    name: string
    subject: string
    body: string
    is_active: boolean
    created_at: string
    updated_at: string
}

export interface EmailTemplateListItem {
    id: string
    name: string
    subject: string
    is_active: boolean
    created_at: string
    updated_at: string
}

export interface EmailTemplateCreate {
    name: string
    subject: string
    body: string
}

export interface EmailTemplateUpdate {
    name?: string
    subject?: string
    body?: string
    is_active?: boolean
}

export interface EmailSendRequest {
    template_id: string
    recipient_email: string
    variables?: Record<string, string>
    case_id?: string
    schedule_at?: string
}

export interface EmailLog {
    id: string
    organization_id: string
    job_id: string | null
    template_id: string | null
    case_id: string | null
    recipient_email: string
    subject: string
    body: string
    status: string
    sent_at: string | null
    error: string | null
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
