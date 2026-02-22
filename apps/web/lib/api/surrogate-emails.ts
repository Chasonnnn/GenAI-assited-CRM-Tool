/**
 * Surrogate-scoped email/ticket API client.
 */

import api from './index'

export interface SurrogateEmailTicketItem {
    id: string
    ticket_code: string
    subject: string | null
    status: string
    priority: string
    requester_email: string | null
    last_activity_at: string | null
    created_at: string
}

export interface SurrogateEmailTicketListResponse {
    items: SurrogateEmailTicketItem[]
}

export interface SurrogateEmailContact {
    id: string
    surrogate_id: string
    email: string
    email_domain: string | null
    source: 'system' | 'manual'
    label: string | null
    contact_type: string | null
    is_active: boolean
    created_by_user_id: string | null
    created_at: string
    updated_at: string
}

export interface SurrogateEmailContactListResponse {
    items: SurrogateEmailContact[]
}

export interface SurrogateEmailContactCreatePayload {
    email: string
    label?: string
    contact_type?: string
}

export interface SurrogateEmailContactPatchPayload {
    email?: string
    label?: string
    contact_type?: string
    is_active?: boolean
}

export function getSurrogateEmails(surrogateId: string): Promise<SurrogateEmailTicketListResponse> {
    return api.get<SurrogateEmailTicketListResponse>(`/surrogates/${surrogateId}/emails`)
}

export function getSurrogateEmailContacts(
    surrogateId: string
): Promise<SurrogateEmailContactListResponse> {
    return api.get<SurrogateEmailContactListResponse>(`/surrogates/${surrogateId}/email-contacts`)
}

export function createSurrogateEmailContact(
    surrogateId: string,
    data: SurrogateEmailContactCreatePayload
): Promise<SurrogateEmailContact> {
    return api.post<SurrogateEmailContact>(`/surrogates/${surrogateId}/email-contacts`, data)
}

export function patchSurrogateEmailContact(
    surrogateId: string,
    contactId: string,
    data: SurrogateEmailContactPatchPayload
): Promise<SurrogateEmailContact> {
    return api.patch<SurrogateEmailContact>(
        `/surrogates/${surrogateId}/email-contacts/${contactId}`,
        data
    )
}

export function deactivateSurrogateEmailContact(
    surrogateId: string,
    contactId: string
): Promise<{ success: boolean }> {
    return api.delete<{ success: boolean }>(`/surrogates/${surrogateId}/email-contacts/${contactId}`)
}
