import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import MetaIntegrationsPage from '../app/(app)/settings/integrations/meta/page'

let mockSearchParams = new URLSearchParams()

vi.mock('next/navigation', () => ({
    useSearchParams: () => mockSearchParams,
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
        back: vi.fn(),
    }),
}))

const mockUseMetaConnections = vi.fn()
const mockUseMetaConnectUrl = vi.fn()
const mockUseDisconnectMetaConnection = vi.fn()
const mockUseMetaAvailableAssetsInfinite = vi.fn()
const mockUseConnectMetaAssets = vi.fn()
const mockUseMetaConnectionsNeedingReauth = vi.fn()
const mockUseMetaConnectionsWithErrors = vi.fn()
const mockUseAdminMetaAdAccounts = vi.fn()
const mockUseUpdateMetaAdAccount = vi.fn()
const mockUseDeleteMetaAdAccount = vi.fn()

vi.mock('@/lib/hooks/use-meta-oauth', () => ({
    useMetaConnections: () => mockUseMetaConnections(),
    useMetaConnectUrl: () => mockUseMetaConnectUrl(),
    useDisconnectMetaConnection: () => mockUseDisconnectMetaConnection(),
    useMetaAvailableAssetsInfinite: (...args: unknown[]) =>
        mockUseMetaAvailableAssetsInfinite(...args),
    useConnectMetaAssets: (...args: unknown[]) => mockUseConnectMetaAssets(...args),
    useMetaConnectionsNeedingReauth: () => mockUseMetaConnectionsNeedingReauth(),
    useMetaConnectionsWithErrors: () => mockUseMetaConnectionsWithErrors(),
}))

vi.mock('@/lib/hooks/use-admin-meta', () => ({
    useAdminMetaAdAccounts: () => mockUseAdminMetaAdAccounts(),
    useUpdateMetaAdAccount: () => mockUseUpdateMetaAdAccount(),
    useDeleteMetaAdAccount: () => mockUseDeleteMetaAdAccount(),
}))

describe('MetaIntegrationsPage (OAuth)', () => {
    beforeEach(() => {
        mockSearchParams = new URLSearchParams()
        mockUseMetaConnections.mockReturnValue({
            data: [],
            isLoading: false,
            isFetching: false,
            refetch: vi.fn(),
        })
        mockUseMetaConnectUrl.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseDisconnectMetaConnection.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseMetaAvailableAssetsInfinite.mockReturnValue({
            data: { pages: [] },
            isLoading: false,
            hasNextPage: false,
            fetchNextPage: vi.fn(),
            isFetchingNextPage: false,
        })
        mockUseConnectMetaAssets.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseMetaConnectionsNeedingReauth.mockReturnValue([])
        mockUseMetaConnectionsWithErrors.mockReturnValue([])
        mockUseAdminMetaAdAccounts.mockReturnValue({ data: [], isLoading: false })
        mockUseUpdateMetaAdAccount.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseDeleteMetaAdAccount.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    })

    it('renders connect CTA when no connections', () => {
        render(<MetaIntegrationsPage />)
        expect(
            screen.getByRole('button', { name: /connect with facebook/i })
        ).toBeInTheDocument()
    })

    it('shows asset selection when step=select-assets', () => {
        mockSearchParams = new URLSearchParams('step=select-assets&connection=conn-1')
        mockUseMetaConnections.mockReturnValue({
            data: [
                {
                    id: 'conn-1',
                    meta_user_name: 'Meta User',
                    last_error: null,
                    last_error_code: null,
                },
            ],
            isLoading: false,
            isFetching: false,
            refetch: vi.fn(),
        })
        mockUseMetaAvailableAssetsInfinite.mockReturnValue({
            data: {
                pages: [
                    {
                        ad_accounts: [
                            {
                                id: 'act_1',
                                name: 'Account One',
                                is_connected: false,
                                connected_by_meta_user: null,
                                connected_by_connection_id: null,
                            },
                        ],
                        pages: [
                            {
                                id: 'page_1',
                                name: 'Page One',
                                is_connected: false,
                                connected_by_meta_user: null,
                                connected_by_connection_id: null,
                            },
                        ],
                        next_cursor: null,
                    },
                ],
            },
            isLoading: false,
            hasNextPage: false,
            fetchNextPage: vi.fn(),
            isFetchingNextPage: false,
        })

        render(<MetaIntegrationsPage />)
        expect(screen.getByText(/select assets for/i)).toBeInTheDocument()
        expect(screen.getByText(/Account One/)).toBeInTheDocument()
        expect(screen.getByText(/Page One/)).toBeInTheDocument()
    })

    it('prompts overwrite confirmation for conflicting assets', () => {
        mockSearchParams = new URLSearchParams('step=select-assets&connection=conn-1')
        mockUseMetaConnections.mockReturnValue({
            data: [
                {
                    id: 'conn-1',
                    meta_user_name: 'Meta User',
                    last_error: null,
                    last_error_code: null,
                },
            ],
            isLoading: false,
            isFetching: false,
            refetch: vi.fn(),
        })
        mockUseMetaAvailableAssetsInfinite.mockReturnValue({
            data: {
                pages: [
                    {
                        ad_accounts: [
                            {
                                id: 'act_1',
                                name: 'Account One',
                                is_connected: true,
                                connected_by_meta_user: 'Other User',
                                connected_by_connection_id: 'conn-2',
                            },
                        ],
                        pages: [],
                        next_cursor: null,
                    },
                ],
            },
            isLoading: false,
            hasNextPage: false,
            fetchNextPage: vi.fn(),
            isFetchingNextPage: false,
        })

        render(<MetaIntegrationsPage />)

        const checkbox = screen.getAllByRole('checkbox')[0]
        fireEvent.click(checkbox)

        fireEvent.click(screen.getByRole('button', { name: /connect selected/i }))
        expect(
            screen.getByRole('button', { name: /overwrite/i })
        ).toBeInTheDocument()
    })

    it('shows reconnection banner for unhealthy connections', () => {
        mockUseMetaConnectionsNeedingReauth.mockReturnValue([
            {
                id: 'conn-1',
                meta_user_name: 'Meta User',
                last_error: 'Token expired',
                last_error_code: 'auth',
            },
        ])

        render(<MetaIntegrationsPage />)
        expect(screen.getByText(/reconnect required/i)).toBeInTheDocument()
    })

    it('shows manage lead forms action when connected', () => {
        mockUseMetaConnections.mockReturnValue({
            data: [
                {
                    id: 'conn-1',
                    meta_user_name: 'Meta User',
                    last_error: null,
                    last_error_code: null,
                },
            ],
            isLoading: false,
            isFetching: false,
            refetch: vi.fn(),
        })

        render(<MetaIntegrationsPage />)
        expect(
            screen.getByRole('link', { name: /manage lead forms/i })
        ).toBeInTheDocument()
    })
})
