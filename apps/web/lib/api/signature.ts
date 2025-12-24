/**
 * Signature API client
 */

import api from './index'

// Types
export interface Signature {
    signature_name: string | null
    signature_title: string | null
    signature_company: string | null
    signature_phone: string | null
    signature_email: string | null
    signature_address: string | null
    signature_website: string | null
    signature_logo_url: string | null
    signature_html: string | null
}

export interface SignatureUpdate {
    signature_name?: string | null
    signature_title?: string | null
    signature_company?: string | null
    signature_phone?: string | null
    signature_email?: string | null
    signature_address?: string | null
    signature_website?: string | null
    signature_logo_url?: string | null
    signature_html?: string | null
}

// API functions
export async function getSignature(): Promise<Signature> {
    return api.get<Signature>('/auth/me/signature')
}

export async function updateSignature(data: SignatureUpdate): Promise<Signature> {
    return api.put<Signature>('/auth/me/signature', data)
}
