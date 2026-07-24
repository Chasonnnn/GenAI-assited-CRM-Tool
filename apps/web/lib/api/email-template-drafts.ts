/**
 * Email Template Drafts API client.
 *
 * Drafts are isolated from production templates until an explicit publish.
 */

import api from '../api'
import type {
    EmailTemplate,
    EmailTemplateTestSendRequest,
    EmailTemplateTestSendResponse,
} from '@/lib/api/email-templates'

export type EmailTemplateDraftScope = 'org' | 'personal'

export interface EmailTemplateDraft {
    id: string
    organization_id: string
    template_id: string | null
    created_by_user_id: string | null
    updated_by_user_id: string | null
    scope: EmailTemplateDraftScope
    owner_user_id: string | null
    owner_name: string | null
    name: string
    subject: string
    from_email: string | null
    body: string
    is_active: boolean
    category: string | null
    base_version: number
    revision: number
    published_version: number | null
    is_stale: boolean
    last_tested_revision: number | null
    last_tested_at: string | null
    created_at: string
    updated_at: string
}

export interface EmailTemplateDraftCreate {
    name: string
    subject: string
    from_email?: string | null
    body: string
    scope?: EmailTemplateDraftScope
}

export interface EmailTemplateDraftUpdate {
    name?: string
    subject?: string
    from_email?: string | null
    body?: string
    is_active?: boolean
    expected_revision: number
}

export interface EmailTemplateDraftPublishRequest {
    expected_revision: number
    expected_published_version: number | null
}

export interface EmailTemplateDraftRestoreVersionRequest {
    target_version: number
    expected_revision: number
}

export interface EmailTemplateDraftTestSendRequest
    extends EmailTemplateTestSendRequest {
    expected_revision: number
}

export interface EmailTemplateDraftTestSendResponse
    extends EmailTemplateTestSendResponse {
    tested_revision: number
}

export interface ListEmailTemplateDraftsParams {
    scope?: EmailTemplateDraftScope | null
    showAllPersonal?: boolean
}

export async function listEmailTemplateDrafts(
    params: ListEmailTemplateDraftsParams = {},
): Promise<EmailTemplateDraft[]> {
    const searchParams = new URLSearchParams()
    if (params.scope) {
        searchParams.set('scope', params.scope)
    }
    if (params.showAllPersonal) {
        searchParams.set('show_all_personal', 'true')
    }
    const query = searchParams.toString()
    return api.get<EmailTemplateDraft[]>(
        query ? `/email-template-drafts?${query}` : '/email-template-drafts',
    )
}

export async function getEmailTemplateDraft(id: string): Promise<EmailTemplateDraft> {
    return api.get<EmailTemplateDraft>(
        `/email-template-drafts/${encodeURIComponent(id)}`,
    )
}

export async function createEmailTemplateDraft(
    data: EmailTemplateDraftCreate,
): Promise<EmailTemplateDraft> {
    return api.post<EmailTemplateDraft>('/email-template-drafts', data)
}

export async function createEmailTemplateDraftFromTemplate(
    templateId: string,
): Promise<EmailTemplateDraft> {
    return api.post<EmailTemplateDraft>(
        `/email-template-drafts/from-template/${encodeURIComponent(templateId)}`,
    )
}

export async function updateEmailTemplateDraft(
    id: string,
    data: EmailTemplateDraftUpdate,
): Promise<EmailTemplateDraft> {
    return api.patch<EmailTemplateDraft>(
        `/email-template-drafts/${encodeURIComponent(id)}`,
        data,
    )
}

export async function discardEmailTemplateDraft(
    id: string,
    expectedRevision: number,
): Promise<void> {
    return api.delete<void>(
        `/email-template-drafts/${encodeURIComponent(id)}?expected_revision=${expectedRevision}`,
    )
}

export async function publishEmailTemplateDraft(
    id: string,
    data: EmailTemplateDraftPublishRequest,
): Promise<EmailTemplate> {
    return api.post<EmailTemplate>(
        `/email-template-drafts/${encodeURIComponent(id)}/publish`,
        data,
    )
}

export async function restoreEmailTemplateDraftVersion(
    id: string,
    data: EmailTemplateDraftRestoreVersionRequest,
): Promise<EmailTemplateDraft> {
    return api.post<EmailTemplateDraft>(
        `/email-template-drafts/${encodeURIComponent(id)}/restore-version`,
        data,
    )
}

export async function sendTestEmailTemplateDraft(
    id: string,
    payload: EmailTemplateDraftTestSendRequest,
): Promise<EmailTemplateDraftTestSendResponse> {
    return api.post<EmailTemplateDraftTestSendResponse>(
        `/email-template-drafts/${encodeURIComponent(id)}/test`,
        payload,
    )
}

export type {
    EmailTemplateTestSendRequest,
    EmailTemplateTestSendResponse,
}
