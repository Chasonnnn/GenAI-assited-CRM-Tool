/**
 * Meta OAuth API client for Facebook Login for Business
 */

import api from './index'

// Types

export interface MetaOAuthConnection {
    id: string
    meta_user_id: string
    meta_user_name: string | null
    granted_scopes: string[]
    is_active: boolean
    last_validated_at: string | null
    last_error: string | null
    last_error_at: string | null
    last_error_code: string | null
    token_expires_at: string | null
    created_at: string
    updated_at: string
}

export interface MetaConnectionsListResponse {
    connections: MetaOAuthConnection[]
}

export interface MetaOAuthConnectResponse {
    auth_url: string
}

export interface AdAccountOption {
    id: string
    name: string | null
    business_name?: string | null
    is_connected: boolean
    connected_by_meta_user: string | null
    connected_by_connection_id: string | null
}

export interface PageOption {
    id: string
    name: string | null
    is_connected: boolean
    connected_by_meta_user: string | null
    connected_by_connection_id: string | null
}

export interface AvailableAssetsResponse {
    ad_accounts: AdAccountOption[]
    pages: PageOption[]
    next_cursor: string | null
}

export interface ConnectAssetsRequest {
    ad_account_ids: string[]
    page_ids: string[]
    overwrite_existing: boolean
}

export interface ConnectAssetsResponse {
    ad_accounts: string[]
    pages: string[]
    overwrites: Array<{
        asset_id: string
        asset_type: string
        previous_user: string
    }>
}

export interface DisconnectResponse {
    success: boolean
    unlinked: number
}

// Error categories for health status
export type ErrorCategory = 'auth' | 'rate_limit' | 'transient' | 'permission' | 'unknown'

// API functions

/**
 * Get OAuth authorization URL
 */
export async function getMetaConnectUrl(): Promise<MetaOAuthConnectResponse> {
    return api.get<MetaOAuthConnectResponse>('/integrations/meta/connect')
}

/**
 * List OAuth connections for the organization
 */
export async function listMetaConnections(): Promise<MetaConnectionsListResponse> {
    return api.get<MetaConnectionsListResponse>('/integrations/meta/connections')
}

/**
 * Get a specific OAuth connection
 */
export async function getMetaConnection(connectionId: string): Promise<MetaOAuthConnection> {
    return api.get<MetaOAuthConnection>(`/integrations/meta/connections/${connectionId}`)
}

/**
 * Disconnect an OAuth connection (unlinks all assets)
 */
export async function disconnectMetaConnection(connectionId: string): Promise<DisconnectResponse> {
    return api.delete<DisconnectResponse>(`/integrations/meta/connections/${connectionId}`)
}

/**
 * List available assets for a connection
 */
export async function listAvailableAssets(
    connectionId: string,
    params?: { cursor?: string; search?: string }
): Promise<AvailableAssetsResponse> {
    const queryParams = new URLSearchParams()
    if (params?.cursor) queryParams.set('cursor', params.cursor)
    if (params?.search) queryParams.set('search', params.search)

    const query = queryParams.toString()
    const url = `/integrations/meta/connections/${connectionId}/available-assets${query ? `?${query}` : ''}`

    return api.get<AvailableAssetsResponse>(url)
}

/**
 * Connect assets using a specific OAuth connection
 */
export async function connectAssets(
    connectionId: string,
    data: ConnectAssetsRequest
): Promise<ConnectAssetsResponse> {
    return api.post<ConnectAssetsResponse>(
        `/integrations/meta/connections/${connectionId}/connect-assets`,
        data
    )
}

// Helpers

/**
 * Get human-readable health status for a connection
 */
export function getConnectionHealthStatus(
    connection: MetaOAuthConnection
): 'healthy' | 'needs_reauth' | 'rate_limited' | 'permission_error' | 'error' {
    if (!connection.last_error) {
        return 'healthy'
    }

    switch (connection.last_error_code) {
        case 'auth':
            return 'needs_reauth'
        case 'rate_limit':
            return 'rate_limited'
        case 'permission':
            return 'permission_error'
        default:
            return 'error'
    }
}

/**
 * Check if a connection needs reauthorization
 */
export function connectionNeedsReauth(connection: MetaOAuthConnection): boolean {
    return connection.last_error_code === 'auth'
}

/**
 * Parse Meta error message for display
 */
export function parseMetaError(error: string | null): string {
    if (!error) return ''

    // Try to extract meaningful message from Meta API error
    try {
        // Meta errors often contain JSON
        if (error.includes('"message"')) {
            const match = error.match(/"message":\s*"([^"]+)"/)
            if (match?.[1]) return match[1]
        }
    } catch {
        // Fall through to return original
    }

    // Truncate long errors
    if (error.length > 200) {
        return error.substring(0, 200) + '...'
    }

    return error
}
