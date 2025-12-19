/**
 * Admin Meta Pages API client
 */

import api from './index'

// Types
export interface MetaPage {
    id: string
    organization_id: string
    page_id: string
    page_name: string | null
    token_expires_at: string | null
    is_active: boolean
    last_success_at: string | null
    last_error: string | null
    last_error_at: string | null
    created_at: string
    updated_at: string
}

export interface MetaPageCreate {
    page_id: string
    page_name?: string
    access_token: string
    expires_days?: number
}

export interface MetaPageUpdate {
    page_name?: string
    access_token?: string
    expires_days?: number
    is_active?: boolean
}

// API functions
export async function listMetaPages(): Promise<MetaPage[]> {
    return api.get<MetaPage[]>('/admin/meta-pages')
}

export async function createMetaPage(data: MetaPageCreate): Promise<MetaPage> {
    return api.post<MetaPage>('/admin/meta-pages', data)
}

export async function updateMetaPage(pageId: string, data: MetaPageUpdate): Promise<MetaPage> {
    return api.put<MetaPage>(`/admin/meta-pages/${pageId}`, data)
}

export async function deleteMetaPage(pageId: string): Promise<void> {
    return api.delete(`/admin/meta-pages/${pageId}`)
}
