import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import IntegrationsPage from '../app/(app)/settings/integrations/page'

const mockRefetch = vi.fn()
const mockUseIntegrationHealth = vi.fn()
const mockConnectZoom = vi.fn()
const mockConnectGmail = vi.fn()
const mockDisconnectIntegration = vi.fn()

vi.mock('@/lib/hooks/use-ops', () => ({
    useIntegrationHealth: () => mockUseIntegrationHealth(),
}))

vi.mock('@/lib/hooks/use-user-integrations', () => ({
    useUserIntegrations: () => ({ data: [], isLoading: false }),
    useConnectZoom: () => ({ mutate: mockConnectZoom, isPending: false }),
    useConnectGmail: () => ({ mutate: mockConnectGmail, isPending: false }),
    useDisconnectIntegration: () => ({ mutate: mockDisconnectIntegration, isPending: false }),
}))

describe('IntegrationsPage', () => {
    beforeEach(() => {
        mockUseIntegrationHealth.mockReturnValue({
            data: [
                {
                    id: 'ih1',
                    organization_id: 'org1',
                    integration_type: 'meta_leads',
                    integration_key: 'page_123',
                    status: 'healthy',
                    config_status: 'configured',
                    last_success_at: new Date().toISOString(),
                    last_error_at: null,
                    last_error: null,
                },
            ],
            isLoading: false,
            refetch: mockRefetch,
            isFetching: false,
        })

        mockRefetch.mockReset()
        mockConnectZoom.mockReset()
        mockConnectGmail.mockReset()
        mockDisconnectIntegration.mockReset()
    })

    it('renders integration health and can refresh', () => {
        render(<IntegrationsPage />)

        expect(screen.getByText('Integrations')).toBeInTheDocument()
        expect(screen.getByText('Meta Lead Ads')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /refresh/i }))
        expect(mockRefetch).toHaveBeenCalled()
    })
})
