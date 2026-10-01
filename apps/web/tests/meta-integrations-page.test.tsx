import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import MetaIntegrationsPage from '../app/(app)/settings/integrations/meta/page'
import { ApiError } from '@/lib/api'

let mockSearchParams = new URLSearchParams()
let mockPermissions: string[] = ['manage_meta_leads']

vi.mock('@/lib/hooks/use-permission-check', () => ({
    usePermissionCheck: () => ({
        isLoading: false,
        isError: false,
        retry: vi.fn(),
        isRetrying: false,
        can: (permission: string) => mockPermissions.includes(permission),
    }),
}))

const mockToast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock('@/components/ui/toast', () => ({ toast: mockToast }))

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
        mockPermissions = ['manage_meta_leads']
        mockToast.success.mockReset()
        mockToast.error.mockReset()
        mockUseMetaConnections.mockReset()
        mockUseAdminMetaAdAccounts.mockReset()
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

    it('shows a load error without the connect CTA when connections fail to load', () => {
        const refetch = vi.fn()
        mockUseMetaConnections.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(500, 'Internal Server Error', 'boom secret detail'),
            isFetching: false,
            refetch,
        })

        render(<MetaIntegrationsPage />)

        expect(screen.getByText("Couldn't load Meta connections")).toBeInTheDocument()
        expect(screen.queryByText('No connections yet.')).not.toBeInTheDocument()
        expect(screen.queryByRole('button', { name: /connect with facebook/i })).not.toBeInTheDocument()
        expect(screen.queryByText(/boom secret detail/)).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
        expect(refetch).toHaveBeenCalled()
    })

    it('shows a load error instead of the empty state when ad accounts fail to load', () => {
        const refetch = vi.fn()
        mockUseAdminMetaAdAccounts.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(500, 'Internal Server Error', 'boom'),
            isFetching: false,
            refetch,
        })

        render(<MetaIntegrationsPage />)

        expect(screen.getByText("Couldn't load ad accounts")).toBeInTheDocument()
        expect(screen.queryByText('No ad accounts connected yet.')).not.toBeInTheDocument()
        expect(screen.getByText('No connections yet.')).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
        expect(refetch).toHaveBeenCalled()
    })

    it('keeps loaded connections and ad accounts when a background refetch fails', () => {
        const refetchError = new ApiError(500, 'Internal Server Error', 'boom')
        mockUseMetaConnections.mockReturnValue({
            data: [{ id: 'conn-1', meta_user_name: 'Meta User', meta_user_id: 'mu-1', last_error: null, last_error_code: null }],
            isLoading: false,
            isError: true,
            error: refetchError,
            isFetching: false,
            refetch: vi.fn(),
        })
        mockUseAdminMetaAdAccounts.mockReturnValue({
            data: [
                {
                    id: 'acct-1',
                    ad_account_external_id: 'act_123',
                    ad_account_name: 'Main account',
                    capi_enabled: true,
                    is_active: true,
                    hierarchy_synced_at: null,
                    spend_synced_at: null,
                },
            ],
            isLoading: false,
            isError: true,
            error: refetchError,
            isFetching: false,
            refetch: vi.fn(),
        })

        render(<MetaIntegrationsPage />)

        expect(screen.getByText('Meta User')).toBeInTheDocument()
        expect(screen.getByText('Main account')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /connect with facebook/i })).toBeInTheDocument()
        expect(screen.queryByText("Couldn't load Meta connections")).not.toBeInTheDocument()
        expect(screen.queryByText("Couldn't load ad accounts")).not.toBeInTheDocument()
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
        if (!checkbox) throw new Error('Expected Meta connection checkbox')
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

    it('shows the restricted state and sends no Meta requests without manage_meta_leads', () => {
        mockPermissions = ['manage_integrations']

        render(<MetaIntegrationsPage />)

        expect(screen.getByRole('heading', { name: 'Permission required' })).toBeInTheDocument()
        expect(screen.getByText(/Manage Meta Leads permission/)).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: /connect with facebook/i })).not.toBeInTheDocument()
        expect(mockUseMetaConnections).not.toHaveBeenCalled()
        expect(mockUseAdminMetaAdAccounts).not.toHaveBeenCalled()
    })

    it('shows a sanitized toast when Connect with Facebook fails', async () => {
        mockUseMetaConnectUrl.mockReturnValue({
            mutateAsync: vi.fn().mockRejectedValue(
                new ApiError(503, 'Service Unavailable', 'META_APP_SECRET is not configured'),
            ),
            isPending: false,
        })

        render(<MetaIntegrationsPage />)
        fireEvent.click(screen.getByRole('button', { name: /connect with facebook/i }))

        await waitFor(() => {
            expect(mockToast.error).toHaveBeenCalledWith("Couldn't start the Meta connection. Try again.")
        })
    })

    it('deletes an ad account only after confirmation and keeps failures inline', async () => {
        const deleteAccount = vi.fn()
            .mockRejectedValueOnce(new ApiError(500, 'Internal Server Error', 'boom'))
            .mockResolvedValueOnce(undefined)
        mockUseDeleteMetaAdAccount.mockReturnValue({ mutateAsync: deleteAccount, isPending: false })
        mockUseAdminMetaAdAccounts.mockReturnValue({
            data: [
                {
                    id: 'acct-1',
                    ad_account_external_id: 'act_123',
                    ad_account_name: 'Main account',
                    capi_enabled: true,
                    is_active: true,
                    hierarchy_synced_at: null,
                    spend_synced_at: null,
                },
            ],
            isLoading: false,
        })

        render(<MetaIntegrationsPage />)
        fireEvent.click(screen.getByRole('button', { name: 'Delete ad account' }))
        expect(deleteAccount).not.toHaveBeenCalled()

        const dialog = await screen.findByRole('alertdialog', { name: 'Delete Main account?' })
        fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }))

        expect(await within(dialog).findByText("Couldn't delete the ad account. Try again.")).toBeInTheDocument()
        expect(dialog).toBeInTheDocument()

        fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }))
        await waitFor(() => expect(mockToast.success).toHaveBeenCalledWith('Ad account deleted'))
        expect(deleteAccount).toHaveBeenCalledWith('acct-1')
    })

    it('disconnects a Meta account through a destructive confirmation', async () => {
        const disconnect = vi.fn().mockResolvedValue(undefined)
        mockUseDisconnectMetaConnection.mockReturnValue({ mutateAsync: disconnect, isPending: false })
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
        fireEvent.click(screen.getByRole('button', { name: 'Disconnect connection' }))

        const dialog = await screen.findByRole('alertdialog', { name: 'Disconnect Meta account?' })
        const confirm = within(dialog).getByRole('button', { name: 'Disconnect' })
        expect(confirm).toHaveClass('bg-destructive')
        fireEvent.click(confirm)

        await waitFor(() => expect(disconnect).toHaveBeenCalledWith('conn-1'))
        await waitFor(() => expect(mockToast.success).toHaveBeenCalledWith('Meta account disconnected'))
    })
})
