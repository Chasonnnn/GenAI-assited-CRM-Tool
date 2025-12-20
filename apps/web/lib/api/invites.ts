/**
 * Invitations API client
 */

import { api } from "./client"

export interface Invite {
    id: string
    email: string
    role: string
    status: "pending" | "accepted" | "expired" | "revoked"
    invited_by_user_id: string | null
    expires_at: string | null
    resend_count: number
    can_resend: boolean
    resend_cooldown_seconds: number | null
    created_at: string
}

export interface InviteListResponse {
    invites: Invite[]
    pending_count: number
}

export interface CreateInviteRequest {
    email: string
    role: string
}

export const invitesApi = {
    /**
     * List all invitations
     */
    list: () => api.get<InviteListResponse>("/settings/invites"),

    /**
     * Create a new invitation
     */
    create: (data: CreateInviteRequest) =>
        api.post<Invite>("/settings/invites", data),

    /**
     * Resend an invitation email
     */
    resend: (inviteId: string) =>
        api.post(`/settings/invites/${inviteId}/resend`),

    /**
     * Revoke an invitation
     */
    revoke: (inviteId: string) =>
        api.delete(`/settings/invites/${inviteId}`),
}
