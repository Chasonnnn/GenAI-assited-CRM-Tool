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

export interface MetaAdAccount {
    id: string
    organization_id: string
    ad_account_external_id: string
    ad_account_name: string | null
    token_expires_at: string | null
    pixel_id: string | null
    capi_enabled: boolean
    hierarchy_synced_at: string | null
    spend_synced_at: string | null
    is_active: boolean
    last_error: string | null
    last_error_at: string | null
    created_at: string
    updated_at: string
}

export interface MetaAdAccountCreate {
    ad_account_external_id: string
    ad_account_name?: string
    system_token: string
    expires_days?: number
    pixel_id?: string
    capi_enabled?: boolean
    capi_token?: string
}

export interface MetaAdAccountUpdate {
    ad_account_name?: string
    system_token?: string
    expires_days?: number
    pixel_id?: string
    capi_enabled?: boolean
    capi_token?: string
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

export async function listMetaAdAccounts(): Promise<MetaAdAccount[]> {
    return api.get<MetaAdAccount[]>('/admin/meta-ad-accounts')
}

export async function createMetaAdAccount(
    data: MetaAdAccountCreate
): Promise<MetaAdAccount> {
    return api.post<MetaAdAccount>('/admin/meta-ad-accounts', data)
}

export async function updateMetaAdAccount(
    accountId: string,
    data: MetaAdAccountUpdate
): Promise<MetaAdAccount> {
    return api.put<MetaAdAccount>(`/admin/meta-ad-accounts/${accountId}`, data)
}

export async function deleteMetaAdAccount(accountId: string): Promise<void> {
    return api.delete(`/admin/meta-ad-accounts/${accountId}`)
}
