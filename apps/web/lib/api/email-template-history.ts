import api from "../api"

import type { EmailTemplate } from "./email-templates"

export interface EmailTemplateVersion {
    id: string
    version: number
    created_by_user_id: string | null
    comment: string | null
    created_at: string
}

export async function listEmailTemplateVersions(
    id: string,
    limit = 50,
): Promise<EmailTemplateVersion[]> {
    const searchParams = new URLSearchParams({ limit: String(limit) })
    return api.get<EmailTemplateVersion[]>(
        `/email-templates/${id}/versions?${searchParams.toString()}`,
    )
}

export async function rollbackEmailTemplate(
    id: string,
    targetVersion: number,
): Promise<EmailTemplate> {
    return api.post<EmailTemplate>(`/email-templates/${id}/rollback`, {
        target_version: targetVersion,
    })
}
