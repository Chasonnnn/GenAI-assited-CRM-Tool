import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import MetaIntegrationsPage from '../app/(app)/settings/integrations/meta/page'

const mockUseMetaPages = vi.fn()
const mockUseAdminMetaAdAccounts = vi.fn()

vi.mock('@/lib/hooks/use-admin-meta', () => ({
    useMetaPages: () => mockUseMetaPages(),
    useCreateMetaPage: () => ({ mutateAsync: vi.fn(), isPending: false, isSuccess: false }),
    useDeleteMetaPage: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useAdminMetaAdAccounts: () => mockUseAdminMetaAdAccounts(),
    useCreateMetaAdAccount: () => ({ mutateAsync: vi.fn(), isPending: false, isSuccess: false }),
    useUpdateMetaAdAccount: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteMetaAdAccount: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('MetaIntegrationsPage', () => {
    beforeEach(() => {
        mockUseMetaPages.mockReturnValue({
            data: [],
            isLoading: false,
            isFetching: false,
            refetch: vi.fn(),
        })
        mockUseAdminMetaAdAccounts.mockReturnValue({
            data: [
                {
                    id: 'account-1',
                    organization_id: 'org-1',
                    ad_account_external_id: 'act_123456',
                    ad_account_name: 'Primary Ads',
                    token_expires_at: null,
                    pixel_id: 'pixel_1',
                    capi_enabled: true,
                    hierarchy_synced_at: null,
                    spend_synced_at: null,
                    is_active: true,
                    last_error: null,
                    last_error_at: null,
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                },
            ],
            isLoading: false,
            isFetching: false,
            refetch: vi.fn(),
        })
    })

    it('renders Meta ad accounts section', () => {
        render(<MetaIntegrationsPage />)
        expect(screen.getByText('Meta Ad Accounts')).toBeInTheDocument()
        expect(screen.getByText('act_123456')).toBeInTheDocument()
    })
})
