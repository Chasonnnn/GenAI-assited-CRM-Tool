/**
 * Signature API client (enhanced)
 * 
 * User endpoints: social links + preview
 * Admin endpoints: org signature settings
 */

import api from './index'

// =============================================================================
// User Types (signature overrides + social links + read-only org branding)
// =============================================================================

export interface UserSignature {
    // Signature overrides (user-editable, NULL = use profile)
    signature_name: string | null
    signature_title: string | null
    signature_phone: string | null
    signature_photo_url: string | null
    // User-editable social links
    signature_linkedin: string | null
    signature_twitter: string | null
    signature_instagram: string | null
    // Profile defaults (for UI placeholders)
    profile_name: string
    profile_title: string | null
    profile_phone: string | null
    profile_photo_url: string | null
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
    signature_name?: string | null
    signature_title?: string | null
    signature_phone?: string | null
    // NOTE: No signature_photo_url - use dedicated upload/delete endpoints
    signature_linkedin?: string | null
    signature_twitter?: string | null
    signature_instagram?: string | null
}

export interface SignaturePhotoResponse {
    signature_photo_url: string | null
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

export interface SocialLink {
    platform: string
    url: string
}

export interface OrgSignature {
    signature_template: string | null
    signature_logo_url: string | null
    signature_primary_color: string | null
    signature_company_name: string | null
    signature_address: string | null
    signature_phone: string | null
    signature_website: string | null
    signature_social_links: SocialLink[] | null
    signature_disclaimer: string | null
    available_templates: SignatureTemplate[]
}

export interface OrgSignatureUpdate {
    signature_template?: string | null
    signature_primary_color?: string | null
    signature_company_name?: string | null
    signature_address?: string | null
    signature_phone?: string | null
    signature_website?: string | null
    signature_social_links?: SocialLink[] | null
    signature_disclaimer?: string | null
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

export async function uploadSignaturePhoto(file: File): Promise<SignaturePhotoResponse> {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<SignaturePhotoResponse>('/auth/me/signature/photo', formData)
}

export async function deleteSignaturePhoto(): Promise<SignaturePhotoResponse> {
    return api.delete<SignaturePhotoResponse>('/auth/me/signature/photo')
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
    return api.post<{ signature_logo_url: string }>('/settings/organization/signature/logo', formData)
}

export async function deleteOrgLogo(): Promise<{ status: string }> {
    return api.delete<{ status: string }>('/settings/organization/signature/logo')
}

export async function getOrgSignaturePreview(
    template?: string,
    mode?: "org_only"
): Promise<SignaturePreview> {
    const searchParams = new URLSearchParams()
    if (template) searchParams.set("template", template)
    if (mode) searchParams.set("mode", mode)
    const params = searchParams.toString()
    return api.get<SignaturePreview>(`/settings/organization/signature/preview${params ? `?${params}` : ""}`)
}
