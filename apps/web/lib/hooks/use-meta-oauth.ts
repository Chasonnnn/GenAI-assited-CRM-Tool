/**
 * React Query hooks for Meta OAuth integration
 */

import {
    useInfiniteQuery,
    useMutation,
    useQuery,
    useQueryClient,
} from '@tanstack/react-query'
import {
    connectAssets,
    disconnectMetaConnection,
    getMetaConnectUrl,
    listAvailableAssets,
    listMetaConnections,
    type ConnectAssetsRequest,
} from '@/lib/api/meta-oauth'
import { adminMetaAdAccountKeys } from './use-admin-meta'

// Query keys
const metaOAuthKeys = {
    all: ['meta-oauth'] as const,
    connections: () => [...metaOAuthKeys.all, 'connections'] as const,
    connectionsList: () => [...metaOAuthKeys.connections(), 'list'] as const,
    availableAssets: (connectionId: string) =>
        [...metaOAuthKeys.all, 'available-assets', connectionId] as const,
    availableAssetsSearch: (connectionId: string, search: string) =>
        [...metaOAuthKeys.availableAssets(connectionId), search] as const,
}

// Hooks

/**
 * Get OAuth connect URL
 */
export function useMetaConnectUrl() {
    return useMutation({
        mutationFn: getMetaConnectUrl,
    })
}

/**
 * List OAuth connections for the organization
 */
export function useMetaConnections(enabled = true) {
    return useQuery({
        queryKey: metaOAuthKeys.connectionsList(),
        queryFn: async () => {
            const response = await listMetaConnections()
            return response.connections
        },
        enabled,
    })
}

/**
 * Disconnect an OAuth connection
 */
export function useDisconnectMetaConnection() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (connectionId: string) => disconnectMetaConnection(connectionId),
        onSuccess: (_result, connectionId) => {
            // Invalidate connections and assets lists
            void queryClient.invalidateQueries({ queryKey: metaOAuthKeys.connections() })
            void queryClient.invalidateQueries({ queryKey: metaOAuthKeys.availableAssets(connectionId) })
            void queryClient.invalidateQueries({ queryKey: adminMetaAdAccountKeys.lists() })
        },
    })
}

/**
 * List available assets with infinite scroll pagination
 */
export function useMetaAvailableAssetsInfinite(connectionId: string | null, search?: string) {
    return useInfiniteQuery({
        queryKey: metaOAuthKeys.availableAssetsSearch(connectionId || '', search || ''),
        queryFn: ({ pageParam }) => {
            const params: { cursor?: string; search?: string } = {}
            if (pageParam) params.cursor = pageParam as string
            if (search) params.search = search
            return listAvailableAssets(connectionId!, Object.keys(params).length > 0 ? params : undefined)
        },
        initialPageParam: undefined as string | undefined,
        getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
        enabled: !!connectionId,
    })
}

/**
 * Connect assets to an OAuth connection
 */
export function useConnectMetaAssets(connectionId: string) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: ConnectAssetsRequest) => connectAssets(connectionId, data),
        onSuccess: () => {
            // Invalidate relevant queries
            void queryClient.invalidateQueries({ queryKey: metaOAuthKeys.connections() })
            void queryClient.invalidateQueries({
                queryKey: metaOAuthKeys.availableAssets(connectionId),
            })
            void queryClient.invalidateQueries({ queryKey: adminMetaAdAccountKeys.lists() })
        },
    })
}

/**
 * Helper hook to get connections needing reauth
 */
export function useMetaConnectionsNeedingReauth() {
    const { data: connections } = useMetaConnections()

    return connections?.filter((conn) => conn.last_error_code === 'auth') || []
}

/**
 * Helper hook to get connections with any error
 */
export function useMetaConnectionsWithErrors() {
    const { data: connections } = useMetaConnections()

    return connections?.filter((conn) => conn.last_error) || []
}
