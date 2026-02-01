import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import IntegrationsPage from '../app/(app)/settings/integrations/page'

const mockRefetch = vi.fn()
const mockUseIntegrationHealth = vi.fn()
const mockConnectZoom = vi.fn()
const mockConnectGmail = vi.fn()
const mockConnectGoogleCalendar = vi.fn()
const mockConnectGcp = vi.fn()
const mockDisconnectIntegration = vi.fn()
const mockZapierRotate = vi.fn()
const mockZapierInboundCreate = vi.fn()
const mockZapierInboundRotate = vi.fn()
const mockZapierInboundUpdate = vi.fn()
const mockZapierTestLead = vi.fn()
const mockZapierOutboundUpdate = vi.fn()
const mockZapierOutboundTest = vi.fn()
const mockZapierFieldPaste = vi.fn()
const mockZapierInboundDelete = vi.fn()
const mockUpdateAISettings = vi.fn()
const mockTestAIKey = vi.fn()
const mockAcceptConsent = vi.fn()
const mockUpdateResendSettings = vi.fn()
const mockTestResendKey = vi.fn()
const mockRotateWebhook = vi.fn()

const zapierSettingsData = {
    webhook_url: 'https://api.test/webhooks/zapier/abc',
    is_active: true,
    secret_configured: true,
    inbound_webhooks: [
        {
            webhook_id: 'abc',
            webhook_url: 'https://api.test/webhooks/zapier/abc',
            label: 'Primary',
            is_active: true,
            secret_configured: true,
            created_at: '2026-01-01T00:00:00Z',
        },
    ],
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

const aiSettingsData = {
    is_enabled: true,
    provider: 'gemini',
    model: 'gemini-3-flash-preview',
    api_key_masked: 'sk-****',
    vertex_wif: null,
    vertex_api_key: null,
    consent_accepted_at: '2026-01-01T00:00:00Z',
} as const

const resendSettingsData = {
    email_provider: 'resend',
    api_key_masked: 're_****',
    from_email: 'no-reply@surrogacyforce.com',
    from_name: null,
    reply_to_email: null,
    verified_domain: 'surrogacyforce.com',
    last_key_validated_at: null,
    default_sender_user_id: null,
    default_sender_name: null,
    default_sender_email: null,
    webhook_url: 'https://api.test/webhooks/resend/abc',
    current_version: 1,
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

vi.mock('@/components/ui/dialog', () => ({
    Dialog: ({ open, children }: { open?: boolean; children?: ReactNode }) =>
        open ? <div data-testid="dialog-root">{children}</div> : null,
    DialogContent: ({ children }: { children?: ReactNode }) => <div role="dialog">{children}</div>,
    DialogHeader: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogDescription: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}))

vi.mock('@/lib/hooks/use-user-integrations', () => ({
    useUserIntegrations: () => ({ data: [], isLoading: false }),
    useConnectZoom: () => ({ mutate: mockConnectZoom, isPending: false }),
    useConnectGmail: () => ({ mutate: mockConnectGmail, isPending: false }),
    useConnectGoogleCalendar: () => ({ mutate: mockConnectGoogleCalendar, isPending: false }),
    useConnectGcp: () => ({ mutate: mockConnectGcp, isPending: false }),
    useDisconnectIntegration: () => ({ mutate: mockDisconnectIntegration, isPending: false }),
}))

vi.mock('@/lib/hooks/use-ai', () => ({
    useAISettings: () => ({ data: aiSettingsData, isLoading: false }),
    useAIConsent: () => ({ data: { consent_text: 'Consent', consent_accepted_at: aiSettingsData.consent_accepted_at, consent_accepted_by: 'Admin' }, isLoading: false }),
    useAcceptConsent: () => ({ mutateAsync: mockAcceptConsent, isPending: false }),
    useUpdateAISettings: () => ({ mutateAsync: mockUpdateAISettings, isPending: false }),
    useTestAPIKey: () => ({ mutateAsync: mockTestAIKey, isPending: false }),
}))

vi.mock('@/lib/hooks/use-resend', () => ({
    useResendSettings: () => ({ data: resendSettingsData, isLoading: false }),
    useUpdateResendSettings: () => ({ mutateAsync: mockUpdateResendSettings, isPending: false }),
    useTestResendKey: () => ({ mutateAsync: mockTestResendKey, isPending: false }),
    useRotateWebhook: () => ({ mutateAsync: mockRotateWebhook, isPending: false }),
    useEligibleSenders: () => ({ data: [], isLoading: false }),
}))

vi.mock('@/lib/hooks/use-zapier', () => ({
    useZapierSettings: () => ({
        data: zapierSettingsData,
        isLoading: false,
    }),
    useRotateZapierSecret: () => ({ mutateAsync: mockZapierRotate, isPending: false }),
    useCreateZapierInboundWebhook: () => ({ mutateAsync: mockZapierInboundCreate, isPending: false }),
    useRotateZapierInboundWebhook: () => ({ mutateAsync: mockZapierInboundRotate, isPending: false }),
    useUpdateZapierInboundWebhook: () => ({ mutateAsync: mockZapierInboundUpdate, isPending: false }),
    useZapierTestLead: () => ({ mutateAsync: mockZapierTestLead, isPending: false }),
    useUpdateZapierOutboundSettings: () => ({ mutateAsync: mockZapierOutboundUpdate, isPending: false }),
    useZapierOutboundTest: () => ({ mutateAsync: mockZapierOutboundTest, isPending: false }),
    useZapierFieldPaste: () => ({ mutateAsync: mockZapierFieldPaste, isPending: false }),
    useDeleteZapierInboundWebhook: () => ({ mutateAsync: mockZapierInboundDelete, isPending: false }),
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
        mockZapierInboundCreate.mockReset()
        mockZapierInboundRotate.mockReset()
        mockZapierInboundUpdate.mockReset()
        mockZapierFieldPaste.mockReset()
        mockZapierInboundDelete.mockReset()
    })

    it('renders integration health and can refresh', () => {
        render(<IntegrationsPage />)

        expect(screen.getByText('Integrations')).toBeInTheDocument()
        expect(screen.getByText('Meta Lead Ads')).toBeInTheDocument()
        expect(screen.getByText('AI Assistant')).toBeInTheDocument()
        expect(screen.getByText('Email Delivery')).toBeInTheDocument()
        expect(screen.getByText('Zapier')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /configure zapier/i })).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /refresh/i }))
        expect(mockRefetch).toHaveBeenCalled()
    })

    it('shows status badge in AI dialog header', () => {
        render(<IntegrationsPage />)

        fireEvent.click(screen.getByRole('button', { name: /configure ai/i }))

        const dialog = screen.getByRole('dialog')
        expect(within(dialog).getByText('AI Configuration')).toBeInTheDocument()
        expect(within(dialog).getByText('Enabled', { selector: '[data-slot="badge"]' })).toBeInTheDocument()
    })

    it('shows status badges on organization integration cards', () => {
        render(<IntegrationsPage />)

        const aiCard = screen.getByText('AI Assistant').closest('[data-slot="card"]')
        const emailCard = screen.getByText('Email Delivery').closest('[data-slot="card"]')
        const zapierCard = screen.getByText('Zapier').closest('[data-slot="card"]')

        expect(aiCard).not.toBeNull()
        expect(emailCard).not.toBeNull()
        expect(zapierCard).not.toBeNull()

        expect(within(aiCard as HTMLElement).getByText('Enabled', { selector: '[data-slot="badge"]' })).toBeInTheDocument()
        expect(within(emailCard as HTMLElement).getByText('Configured', { selector: '[data-slot="badge"]' })).toBeInTheDocument()
        expect(within(zapierCard as HTMLElement).getByText('Active', { selector: '[data-slot="badge"]' })).toBeInTheDocument()
    })
})
