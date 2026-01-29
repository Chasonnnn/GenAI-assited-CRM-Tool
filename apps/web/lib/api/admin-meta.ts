/**
 * Admin Meta Ad Accounts API client
 */

import api from './index'

export interface MetaAdAccount {
    id: string
    organization_id: string
    ad_account_external_id: string
    ad_account_name: string | null
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
    pixel_id?: string
    capi_enabled?: boolean
}

export interface MetaAdAccountUpdate {
    ad_account_name?: string
    pixel_id?: string
    capi_enabled?: boolean
    is_active?: boolean
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
