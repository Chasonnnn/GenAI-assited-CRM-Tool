/**
 * Signature API client (enhanced)
 * 
 * User endpoints: social links + preview
 * Admin endpoints: org signature settings
 */

import api from './index'

// =============================================================================
// User Types (social links + read-only org branding)
// =============================================================================

export interface UserSignature {
    // User-editable social links
    signature_linkedin: string | null
    signature_twitter: string | null
    signature_instagram: string | null
    // Org branding (read-only for users)
    org_signature_template: string | null
    org_signature_logo_url: string | null
    org_signature_primary_color: string | null
    org_signature_company_name: string | null
    org_signature_address: string | null
    org_signature_phone: string | null
    org_signature_website: string | null
}

export interface UserSignatureUpdate {
    signature_linkedin?: string | null
    signature_twitter?: string | null
    signature_instagram?: string | null
}

export interface SignaturePreview {
    html: string
}

// =============================================================================
// Admin Types (org signature settings)
// =============================================================================

export interface SignatureTemplate {
    id: string
    name: string
    description: string
}

export interface OrgSignature {
    signature_template: string | null
    signature_logo_url: string | null
    signature_primary_color: string | null
    signature_company_name: string | null
    signature_address: string | null
    signature_phone: string | null
    signature_website: string | null
    available_templates: SignatureTemplate[]
}

export interface OrgSignatureUpdate {
    signature_template?: string | null
    signature_primary_color?: string | null
    signature_company_name?: string | null
    signature_address?: string | null
    signature_phone?: string | null
    signature_website?: string | null
}

// =============================================================================
// User API functions
// =============================================================================

export async function getUserSignature(): Promise<UserSignature> {
    return api.get<UserSignature>('/auth/me/signature')
}

export async function updateUserSignature(data: UserSignatureUpdate): Promise<UserSignature> {
    return api.patch<UserSignature>('/auth/me/signature', data)
}

export async function getSignaturePreview(): Promise<SignaturePreview> {
    return api.get<SignaturePreview>('/auth/me/signature/preview')
}

// =============================================================================
// Admin API functions
// =============================================================================

export async function getOrgSignature(): Promise<OrgSignature> {
    return api.get<OrgSignature>('/settings/organization/signature')
}

export async function updateOrgSignature(data: OrgSignatureUpdate): Promise<OrgSignature> {
    return api.patch<OrgSignature>('/settings/organization/signature', data)
}

export async function uploadOrgLogo(file: File): Promise<{ signature_logo_url: string }> {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<{ signature_logo_url: string }>('/settings/organization/signature/logo', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    })
}

export async function deleteOrgLogo(): Promise<{ status: string }> {
    return api.delete<{ status: string }>('/settings/organization/signature/logo')
}

// Legacy exports for backward compatibility (deprecated)
export type Signature = UserSignature
export type SignatureUpdate = UserSignatureUpdate
export const getSignature = getUserSignature
export const updateSignature = updateUserSignature
