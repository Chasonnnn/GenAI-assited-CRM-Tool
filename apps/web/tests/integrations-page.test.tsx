import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import IntegrationsPage from '../app/(app)/settings/integrations/page'

const mockRefetch = vi.fn()
const mockUseIntegrationHealth = vi.fn()
const mockConnectZoom = vi.fn()
const mockConnectGmail = vi.fn()
const mockConnectGoogleCalendar = vi.fn()
const mockConnectGcp = vi.fn()
const mockDisconnectIntegration = vi.fn()
const mockZapierRotate = vi.fn()
const mockZapierTestLead = vi.fn()
const mockZapierOutboundUpdate = vi.fn()
const mockZapierOutboundTest = vi.fn()

const zapierSettingsData = {
    webhook_url: 'https://api.test/webhooks/zapier/abc',
    is_active: true,
    secret_configured: true,
    outbound_webhook_url: null,
    outbound_enabled: false,
    outbound_secret_configured: false,
    send_hashed_pii: false,
    event_mapping: [
        { stage_slug: 'new_unread', event_name: 'Lead', enabled: true },
        { stage_slug: 'qualified', event_name: 'QualifiedLead', enabled: true },
        { stage_slug: 'matched', event_name: 'ConvertedLead', enabled: true },
    ],
} as const

vi.mock('@/lib/hooks/use-ops', () => ({
    useIntegrationHealth: () => mockUseIntegrationHealth(),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { role: 'admin', user_id: 'u1' } }),
}))

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
        prefetch: vi.fn(),
    }),
}))

vi.mock('@/lib/hooks/use-user-integrations', () => ({
    useUserIntegrations: () => ({ data: [], isLoading: false }),
    useConnectZoom: () => ({ mutate: mockConnectZoom, isPending: false }),
    useConnectGmail: () => ({ mutate: mockConnectGmail, isPending: false }),
    useConnectGoogleCalendar: () => ({ mutate: mockConnectGoogleCalendar, isPending: false }),
    useConnectGcp: () => ({ mutate: mockConnectGcp, isPending: false }),
    useDisconnectIntegration: () => ({ mutate: mockDisconnectIntegration, isPending: false }),
}))

vi.mock('@/lib/hooks/use-zapier', () => ({
    useZapierSettings: () => ({
        data: zapierSettingsData,
        isLoading: false,
    }),
    useRotateZapierSecret: () => ({ mutateAsync: mockZapierRotate, isPending: false }),
    useZapierTestLead: () => ({ mutateAsync: mockZapierTestLead, isPending: false }),
    useUpdateZapierOutboundSettings: () => ({ mutateAsync: mockZapierOutboundUpdate, isPending: false }),
    useZapierOutboundTest: () => ({ mutateAsync: mockZapierOutboundTest, isPending: false }),
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
        mockConnectGoogleCalendar.mockReset()
        mockConnectGcp.mockReset()
        mockDisconnectIntegration.mockReset()
    })

    it('renders integration health and can refresh', () => {
        render(<IntegrationsPage />)

        expect(screen.getByText('Integrations')).toBeInTheDocument()
        expect(screen.getByText('Meta Lead Ads')).toBeInTheDocument()
        expect(screen.getByText('Zapier Webhook')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /send test lead/i })).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /refresh/i }))
        expect(mockRefetch).toHaveBeenCalled()
    })
})
