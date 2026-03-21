import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within, act } from '@testing-library/react'
import IntegrationsPage from '../app/(app)/settings/integrations/page'

const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()
const mockUsePipelines = vi.fn()
const mockRefetch = vi.fn()
const mockUseIntegrationHealth = vi.fn()
const mockUseUserIntegrations = vi.fn()
const mockUseGoogleCalendarStatus = vi.fn()
const mockConnectZoom = vi.fn()
const mockConnectGmail = vi.fn()
const mockConnectGoogleCalendar = vi.fn()
const mockSyncGoogleCalendarNow = vi.fn()
const mockConnectGcp = vi.fn()
const mockDisconnectIntegration = vi.fn()
const mockZapierRotate = vi.fn()
const mockZapierInboundCreate = vi.fn()
const mockZapierInboundRotate = vi.fn()
const mockZapierInboundUpdate = vi.fn()
const mockZapierTestLead = vi.fn()
const mockZapierOutboundUpdate = vi.fn()
const mockZapierOutboundTest = vi.fn()
const mockRetryZapierOutboundEvent = vi.fn()
const mockZapierFieldPaste = vi.fn()
const mockZapierInboundDelete = vi.fn()
const mockMetaConnectUrl = vi.fn()
const mockDisconnectMetaConnection = vi.fn()
const mockUpdateMetaAdAccount = vi.fn()
const mockDeleteMetaAdAccount = vi.fn()
const mockUpdateMetaCrmDatasetSettings = vi.fn()
const mockMetaCrmDatasetOutboundTest = vi.fn()
const mockRetryMetaCrmDatasetEvent = vi.fn()
const mockUpdateAISettings = vi.fn()
const mockTestAIKey = vi.fn()
const mockAcceptConsent = vi.fn()
const mockUpdateResendSettings = vi.fn()
const mockTestResendKey = vi.fn()
const mockRotateWebhook = vi.fn()

const createZapierSettingsData = () => ({
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
        { stage_key: 'new_unread', event_name: 'Lead', enabled: true, bucket: null },
        { stage_key: 'pre_qualified', event_name: 'PreQualifiedLead', enabled: true, bucket: null },
        { stage_key: 'matched', event_name: 'ConvertedLead', enabled: true, bucket: null },
    ],
})

const recommendedZapierMapping = [
    { stage_key: 'pre_qualified', event_name: 'Qualified', enabled: true, bucket: 'qualified' },
    { stage_key: 'interview_scheduled', event_name: 'Qualified', enabled: true, bucket: 'qualified' },
    { stage_key: 'application_submitted', event_name: 'Qualified', enabled: true, bucket: 'qualified' },
    { stage_key: 'under_review', event_name: 'Qualified', enabled: true, bucket: 'qualified' },
    { stage_key: 'approved', event_name: 'Qualified', enabled: true, bucket: 'qualified' },
    { stage_key: 'ready_to_match', event_name: 'Converted', enabled: true, bucket: 'converted' },
    { stage_key: 'matched', event_name: 'Converted', enabled: true, bucket: 'converted' },
    { stage_key: 'medical_clearance_passed', event_name: 'Converted', enabled: true, bucket: 'converted' },
    { stage_key: 'legal_clearance_passed', event_name: 'Converted', enabled: true, bucket: 'converted' },
    { stage_key: 'transfer_cycle', event_name: 'Converted', enabled: true, bucket: 'converted' },
    { stage_key: 'second_hcg_confirmed', event_name: 'Converted', enabled: true, bucket: 'converted' },
    { stage_key: 'heartbeat_confirmed', event_name: 'Converted', enabled: true, bucket: 'converted' },
    { stage_key: 'ob_care_established', event_name: 'Converted', enabled: true, bucket: 'converted' },
    { stage_key: 'anatomy_scanned', event_name: 'Converted', enabled: true, bucket: 'converted' },
    { stage_key: 'delivered', event_name: 'Converted', enabled: true, bucket: 'converted' },
    { stage_key: 'lost', event_name: 'Lost', enabled: true, bucket: 'lost' },
    { stage_key: 'disqualified', event_name: 'Not Qualified', enabled: true, bucket: 'not_qualified' },
]

const createMetaCrmDatasetSettingsData = () => ({
    dataset_id: '1428122951556949',
    access_token_configured: true,
    enabled: true,
    crm_name: 'Surrogacy Force CRM',
    send_hashed_pii: true,
    event_mapping: [
        { stage_key: 'new_unread', event_name: 'Lead', enabled: true, bucket: null },
        { stage_key: 'pre_qualified', event_name: 'Qualified', enabled: true, bucket: 'qualified' },
        { stage_key: 'matched', event_name: 'Converted', enabled: true, bucket: 'converted' },
        { stage_key: 'disqualified', event_name: 'Not Qualified', enabled: true, bucket: 'not_qualified' },
    ],
    test_event_code: 'TEST123',
})

let zapierSettingsData = createZapierSettingsData()
let zapierEventsSummaryData = {
    total_count: 3,
    queued_count: 0,
    delivered_count: 1,
    failed_count: 1,
    skipped_count: 1,
    actionable_skipped_count: 1,
    failure_rate: 0.5,
    skipped_rate: 0.33,
    failure_rate_alert: true,
    skipped_rate_alert: false,
    warning_messages: ['Failure rate is elevated for Zapier outbound events.'],
    window_hours: 24,
}
let zapierEventsData = {
    items: [
        {
            id: 'event-1',
            source: 'automatic',
            status: 'failed',
            reason: null,
            event_id: 'evt_1',
            event_name: 'Qualified',
            lead_id: 'lead-1',
            stage_key: 'pre_qualified',
            stage_label: 'Pre Qualified',
            attempts: 3,
            last_error: 'Webhook timeout',
            created_at: '2026-03-07T18:00:00Z',
            updated_at: '2026-03-07T18:05:00Z',
            delivered_at: null,
            last_attempt_at: '2026-03-07T18:05:00Z',
            can_retry: true,
        },
    ],
    total: 1,
}
let metaFormsData = [
    {
        id: 'meta-form-1',
        form_external_id: 'zapier-abc',
        form_name: 'Zapier Intake',
        page_id: 'zapier',
        page_name: null,
        mapping_status: 'mapped',
        current_version_id: 'ver-1',
        mapping_version_id: 'ver-1',
        mapping_updated_at: '2026-03-01T00:00:00Z',
        mapping_updated_by_name: 'Admin',
        is_active: true,
        synced_at: '2026-03-01T00:00:00Z',
        unconverted_leads: 0,
        total_leads: 0,
        last_lead_at: null,
    },
]
let metaConnectionsData = []
let metaAdAccountsData = []
let metaCrmDatasetSettingsData = createMetaCrmDatasetSettingsData()
let metaCrmDatasetEventsSummaryData = {
    total_count: 4,
    queued_count: 1,
    delivered_count: 1,
    failed_count: 1,
    skipped_count: 1,
    actionable_skipped_count: 1,
    failure_rate: 0.25,
    skipped_rate: 0.25,
    failure_rate_alert: true,
    skipped_rate_alert: false,
    warning_messages: ['Failure rate is elevated for direct Meta CRM dataset events.'],
    window_hours: 24,
}
let metaCrmDatasetEventsData = {
    items: [
        {
            id: 'meta-event-1',
            source: 'automatic',
            status: 'failed',
            reason: null,
            event_id: 'meta_evt_1',
            event_name: 'Qualified',
            lead_id: '1559954882011881',
            stage_key: 'pre_qualified',
            stage_label: 'Pre Qualified',
            surrogate_id: 'surrogate-1',
            attempts: 2,
            last_error: 'Unsupported post request',
            created_at: '2026-03-07T18:00:00Z',
            updated_at: '2026-03-07T18:05:00Z',
            delivered_at: null,
            last_attempt_at: '2026-03-07T18:05:00Z',
            can_retry: true,
        },
    ],
    total: 1,
}

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
    webhook_signing_secret_configured: true,
    current_version: 1,
} as const

const pipelineData = [
    {
        id: "pipeline-1",
        is_default: true,
        stages: [
            {
                id: "stage-1",
                stage_key: "new_unread",
                slug: "new_unread",
                label: "New Unread",
                stage_type: "intake",
                is_active: true,
                semantics: { integration_bucket: "intake" },
            },
            {
                id: "stage-2",
                stage_key: "pre_qualified",
                slug: "pre_qualified",
                label: "Pre Qualified",
                stage_type: "intake",
                is_active: true,
                semantics: { integration_bucket: "qualified" },
            },
            {
                id: "stage-3",
                stage_key: "matched",
                slug: "matched",
                label: "Matched",
                stage_type: "post_approval",
                is_active: true,
                semantics: { integration_bucket: "converted" },
            },
            {
                id: "stage-4",
                stage_key: "disqualified",
                slug: "disqualified",
                label: "Disqualified",
                stage_type: "terminal",
                is_active: true,
                semantics: { integration_bucket: "not_qualified" },
            },
        ],
    },
]

vi.mock('@/lib/hooks/use-ops', () => ({
    useIntegrationHealth: () => mockUseIntegrationHealth(),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock('@/lib/hooks/use-permissions', () => ({
    useEffectivePermissions: () => mockUseEffectivePermissions(),
}))

vi.mock('@/lib/hooks/use-pipelines', () => ({
    usePipelines: () => mockUsePipelines(),
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
    DialogContent: ({ children, className }: { children?: ReactNode; className?: string }) => (
        <div role="dialog" className={className}>
            {children}
        </div>
    ),
    DialogHeader: ({ children, className }: { children?: ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
    ),
    DialogTitle: ({ children, className }: { children?: ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
    ),
    DialogDescription: ({ children, className }: { children?: ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
    ),
}))

vi.mock('@/lib/hooks/use-user-integrations', () => ({
    useUserIntegrations: () => mockUseUserIntegrations(),
    useGoogleCalendarStatus: () => mockUseGoogleCalendarStatus(),
    useConnectZoom: () => ({ mutate: mockConnectZoom, isPending: false }),
    useConnectGmail: () => ({ mutate: mockConnectGmail, isPending: false }),
    useConnectGoogleCalendar: () => ({ mutate: mockConnectGoogleCalendar, isPending: false }),
    useSyncGoogleCalendarNow: () => ({ mutate: mockSyncGoogleCalendarNow, isPending: false }),
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
    useZapierOutboundEventsSummary: () => ({ data: zapierEventsSummaryData, isLoading: false }),
    useZapierOutboundEvents: () => ({ data: zapierEventsData, isLoading: false }),
    useRetryZapierOutboundEvent: () => ({ mutateAsync: mockRetryZapierOutboundEvent, isPending: false }),
    useZapierFieldPaste: () => ({ mutateAsync: mockZapierFieldPaste, isPending: false }),
    useDeleteZapierInboundWebhook: () => ({ mutateAsync: mockZapierInboundDelete, isPending: false }),
}))

vi.mock('@/lib/hooks/use-meta-oauth', () => ({
    useMetaConnections: () => ({ data: metaConnectionsData, isLoading: false }),
    useMetaConnectUrl: () => ({ mutateAsync: mockMetaConnectUrl, isPending: false }),
    useDisconnectMetaConnection: () => ({ mutateAsync: mockDisconnectMetaConnection, isPending: false }),
}))

vi.mock('@/lib/hooks/use-admin-meta', () => ({
    useAdminMetaAdAccounts: () => ({ data: metaAdAccountsData, isLoading: false }),
    useUpdateMetaAdAccount: () => ({ mutateAsync: mockUpdateMetaAdAccount, isPending: false }),
    useDeleteMetaAdAccount: () => ({ mutateAsync: mockDeleteMetaAdAccount, isPending: false }),
}))

vi.mock('@/lib/hooks/use-meta-crm-dataset', () => ({
    useMetaCrmDatasetSettings: () => ({
        data: metaCrmDatasetSettingsData,
        isLoading: false,
    }),
    useUpdateMetaCrmDatasetSettings: () => ({
        mutateAsync: mockUpdateMetaCrmDatasetSettings,
        isPending: false,
    }),
    useMetaCrmDatasetOutboundTest: () => ({
        mutateAsync: mockMetaCrmDatasetOutboundTest,
        isPending: false,
    }),
    useMetaCrmDatasetEventsSummary: () => ({
        data: metaCrmDatasetEventsSummaryData,
        isLoading: false,
    }),
    useMetaCrmDatasetEvents: () => ({
        data: metaCrmDatasetEventsData,
        isLoading: false,
    }),
    useRetryMetaCrmDatasetEvent: () => ({
        mutateAsync: mockRetryMetaCrmDatasetEvent,
        isPending: false,
    }),
}))

vi.mock('@/lib/hooks/use-meta-forms', () => ({
    useMetaForms: () => ({ data: metaFormsData, isLoading: false }),
}))

describe('IntegrationsPage', () => {
    beforeEach(() => {
        mockUsePipelines.mockReset()
        zapierSettingsData = createZapierSettingsData()
        zapierEventsSummaryData = {
            total_count: 3,
            queued_count: 0,
            delivered_count: 1,
            failed_count: 1,
            skipped_count: 1,
            actionable_skipped_count: 1,
            failure_rate: 0.5,
            skipped_rate: 0.33,
            failure_rate_alert: true,
            skipped_rate_alert: false,
            warning_messages: ['Failure rate is elevated for Zapier outbound events.'],
            window_hours: 24,
        }
        zapierEventsData = {
            items: [
                {
                    id: 'event-1',
                    source: 'automatic',
                    status: 'failed',
                    reason: null,
                    event_id: 'evt_1',
                    event_name: 'Qualified',
                    lead_id: 'lead-1',
                    stage_key: 'pre_qualified',
                    stage_label: 'Pre Qualified',
                    attempts: 3,
                    last_error: 'Webhook timeout',
                    created_at: '2026-03-07T18:00:00Z',
                    updated_at: '2026-03-07T18:05:00Z',
                    delivered_at: null,
                    last_attempt_at: '2026-03-07T18:05:00Z',
                    can_retry: true,
                },
            ],
            total: 1,
        }
        metaFormsData = [
            {
                id: 'meta-form-1',
                form_external_id: 'zapier-abc',
                form_name: 'Zapier Intake',
                page_id: 'zapier',
                page_name: null,
                mapping_status: 'mapped',
                current_version_id: 'ver-1',
                mapping_version_id: 'ver-1',
                mapping_updated_at: '2026-03-01T00:00:00Z',
                mapping_updated_by_name: 'Admin',
                is_active: true,
                synced_at: '2026-03-01T00:00:00Z',
                unconverted_leads: 0,
                total_leads: 0,
                last_lead_at: null,
            },
        ]
        metaConnectionsData = []
        metaAdAccountsData = []
        metaCrmDatasetSettingsData = createMetaCrmDatasetSettingsData()
        metaCrmDatasetEventsSummaryData = {
            total_count: 4,
            queued_count: 1,
            delivered_count: 1,
            failed_count: 1,
            skipped_count: 1,
            actionable_skipped_count: 1,
            failure_rate: 0.25,
            skipped_rate: 0.25,
            failure_rate_alert: true,
            skipped_rate_alert: false,
            warning_messages: ['Failure rate is elevated for direct Meta CRM dataset events.'],
            window_hours: 24,
        }
        metaCrmDatasetEventsData = {
            items: [
                {
                    id: 'meta-event-1',
                    source: 'automatic',
                    status: 'failed',
                    reason: null,
                    event_id: 'meta_evt_1',
                    event_name: 'Qualified',
                    lead_id: '1559954882011881',
                    stage_key: 'pre_qualified',
                    stage_label: 'Pre Qualified',
                    surrogate_id: 'surrogate-1',
                    attempts: 2,
                    last_error: 'Unsupported post request',
                    created_at: '2026-03-07T18:00:00Z',
                    updated_at: '2026-03-07T18:05:00Z',
                    delivered_at: null,
                    last_attempt_at: '2026-03-07T18:05:00Z',
                    can_retry: true,
                },
            ],
            total: 1,
        }
        mockUseAuth.mockReturnValue({ user: { role: 'admin', user_id: 'u1' } })
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ['manage_integrations'] },
        })
        mockUsePipelines.mockReturnValue({ data: pipelineData, isLoading: false })
        mockUseUserIntegrations.mockReturnValue({ data: [], isLoading: false })
        mockUseGoogleCalendarStatus.mockReturnValue({
            data: {
                connected: false,
                account_email: null,
                expires_at: null,
                tasks_accessible: false,
                tasks_error: 'not_connected',
                last_sync_at: null,
            },
            isLoading: false,
        })
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
        mockSyncGoogleCalendarNow.mockReset()
        mockConnectGcp.mockReset()
        mockDisconnectIntegration.mockReset()
        mockZapierInboundCreate.mockReset()
        mockZapierInboundRotate.mockReset()
        mockZapierInboundUpdate.mockReset()
        mockRetryZapierOutboundEvent.mockReset()
        mockZapierFieldPaste.mockReset()
        mockZapierInboundDelete.mockReset()
        mockMetaConnectUrl.mockReset()
        mockDisconnectMetaConnection.mockReset()
        mockUpdateMetaAdAccount.mockReset()
        mockDeleteMetaAdAccount.mockReset()
        mockUpdateMetaCrmDatasetSettings.mockReset()
        mockMetaCrmDatasetOutboundTest.mockReset()
        mockRetryMetaCrmDatasetEvent.mockReset()
    })

    it('renders integration health and can refresh', () => {
        render(<IntegrationsPage />)

        expect(screen.getByText('Integrations')).toBeInTheDocument()
        expect(screen.getAllByText('Meta Lead Ads').length).toBeGreaterThan(0)
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
        expect(within(zapierCard as HTMLElement).getByTestId('zapier-mapping-health-card-badge')).toHaveTextContent('Mapping Needs Review')
    })

    it('shows healthy mapping badge when recommended zapier mapping is configured', () => {
        zapierSettingsData = {
            ...createZapierSettingsData(),
            event_mapping: recommendedZapierMapping,
        }

        render(<IntegrationsPage />)

        const zapierCard = screen.getByText('Zapier').closest('[data-slot="card"]')
        expect(zapierCard).not.toBeNull()
        expect(within(zapierCard as HTMLElement).getByTestId('zapier-mapping-health-card-badge')).toHaveTextContent('Mapping Healthy')
    })

    it('stacks zapier dialog layout rows in the modal', () => {
        render(<IntegrationsPage />)

        fireEvent.click(screen.getByRole('button', { name: /configure zapier/i }))

        const dialog = screen.getByRole('dialog')
        expect(dialog.className).toContain('h-[85vh]')
        expect(within(dialog).getByTestId('zapier-dialog-body').className).toContain('overflow-y-auto')
        expect(within(dialog).getByTestId('zapier-dialog-body').className).toContain('min-h-0')
        expect(within(dialog).getByTestId('zapier-mapping-health-dialog-badge')).toHaveTextContent('Mapping Needs Review')
        const inboundHeader = within(dialog).getByTestId('zapier-inbound-header')
        expect(inboundHeader.className).not.toContain('md:flex-row')
    })

    it('passes a real lead id to the outbound zapier test action', async () => {
        zapierSettingsData = {
            ...createZapierSettingsData(),
            outbound_webhook_url: 'https://hooks.zapier.com/hooks/catch/123/abc',
            outbound_enabled: true,
        }
        mockZapierOutboundTest.mockResolvedValue({
            status: 'queued',
            event_name: 'Lead',
            event_id: 'evt_123',
            lead_id: 'real-lead-123',
        })

        render(<IntegrationsPage />)

        fireEvent.click(screen.getByRole('button', { name: /configure zapier/i }))

        const dialog = screen.getByRole('dialog')
        fireEvent.change(within(dialog).getByLabelText(/meta lead id/i), {
            target: { value: 'real-lead-123' },
        })
        fireEvent.click(within(dialog).getByRole('button', { name: /send test event/i }))

        expect(mockZapierOutboundTest).toHaveBeenCalledWith({
            stage_key: 'new_unread',
            lead_id: 'real-lead-123',
        })
    })

    it('uses the active zapier form when sending a test lead', async () => {
        mockZapierTestLead.mockResolvedValue({
            status: 'converted',
            duplicate: false,
            meta_lead_id: 'lead-1',
            surrogate_id: 'surrogate-1',
            message: 'Stored',
        })

        render(<IntegrationsPage />)

        fireEvent.click(screen.getByRole('button', { name: /configure zapier/i }))

        const dialog = screen.getByRole('dialog')
        fireEvent.click(within(dialog).getByRole('button', { name: /send test lead/i }))

        expect(mockZapierTestLead).toHaveBeenCalledWith({ form_id: 'zapier-abc' })
    })

    it('shows zapier monitoring and retries failed events', async () => {
        mockRetryZapierOutboundEvent.mockResolvedValue({
            ...zapierEventsData.items[0],
            status: 'queued',
            can_retry: false,
            attempts: 0,
        })

        render(<IntegrationsPage />)

        fireEvent.click(screen.getByRole('button', { name: /configure zapier/i }))

        const dialog = screen.getByRole('dialog')
        fireEvent.click(within(dialog).getByRole('tab', { name: /monitoring/i }))

        expect(within(dialog).getByText('Failure rate is elevated for Zapier outbound events.')).toBeInTheDocument()
        expect(within(dialog).getByText('Webhook timeout')).toBeInTheDocument()

        fireEvent.click(within(dialog).getByRole('button', { name: /retry/i }))

        expect(mockRetryZapierOutboundEvent).toHaveBeenCalledWith({ eventId: 'event-1' })
    })

    it('loads and saves Meta CRM dataset settings in the Meta dialog', async () => {
        mockUpdateMetaCrmDatasetSettings.mockResolvedValue({
            ...metaCrmDatasetSettingsData,
            crm_name: 'EWI CRM',
            test_event_code: 'TEST999',
        })

        render(<IntegrationsPage />)

        fireEvent.click(screen.getByRole('button', { name: /configure meta/i }))

        const dialog = screen.getByRole('dialog')
        expect(within(dialog).getByRole('tab', { name: /configuration/i })).toBeInTheDocument()
        expect(within(dialog).getByDisplayValue('1428122951556949')).toBeInTheDocument()
        expect(within(dialog).getByDisplayValue('Surrogacy Force CRM')).toBeInTheDocument()
        expect(within(dialog).getByLabelText(/meta crm dataset access token/i)).toHaveAttribute('placeholder', '•••••••• (set)')

        fireEvent.change(within(dialog).getByLabelText(/crm name/i), {
            target: { value: 'EWI CRM' },
        })
        fireEvent.change(within(dialog).getByLabelText(/meta crm dataset access token/i), {
            target: { value: 'meta-access-token-123' },
        })
        fireEvent.change(within(dialog).getByLabelText(/test event code/i), {
            target: { value: 'TEST999' },
        })
        await act(async () => {
            fireEvent.click(within(dialog).getByRole('button', { name: /save crm dataset settings/i }))
        })

        expect(mockUpdateMetaCrmDatasetSettings).toHaveBeenCalledWith(expect.objectContaining({
            dataset_id: '1428122951556949',
            access_token: 'meta-access-token-123',
            enabled: true,
            crm_name: 'EWI CRM',
            send_hashed_pii: true,
            test_event_code: 'TEST999',
        }))
    })

    it('sends Meta CRM dataset tests and retries failed monitoring events', async () => {
        mockMetaCrmDatasetOutboundTest.mockResolvedValue({
            status: 'queued',
            event_name: 'Lead',
            event_id: 'meta_evt_test',
            lead_id: '1559954882011881',
        })
        mockRetryMetaCrmDatasetEvent.mockResolvedValue({
            ...metaCrmDatasetEventsData.items[0],
            status: 'queued',
            can_retry: false,
        })

        render(<IntegrationsPage />)

        fireEvent.click(screen.getByRole('button', { name: /configure meta/i }))

        const dialog = screen.getByRole('dialog')
        fireEvent.change(within(dialog).getByLabelText(/real meta lead id/i), {
            target: { value: '1559954882011881' },
        })
        fireEvent.change(within(dialog).getByLabelText(/click id \(fbc\)/i), {
            target: { value: 'fb.1.1772942400.real-click-id' },
        })
        fireEvent.click(within(dialog).getByRole('button', { name: /send meta crm test event/i }))

        expect(mockMetaCrmDatasetOutboundTest).toHaveBeenCalledWith({
            stage_key: 'new_unread',
            lead_id: '1559954882011881',
            fbc: 'fb.1.1772942400.real-click-id',
            test_event_code: 'TEST123',
        })

        fireEvent.click(within(dialog).getByRole('tab', { name: /monitoring/i }))

        expect(within(dialog).getByText('Failure rate is elevated for direct Meta CRM dataset events.')).toBeInTheDocument()
        expect(within(dialog).getByText('Unsupported post request')).toBeInTheDocument()

        fireEvent.click(within(dialog).getByRole('button', { name: /retry/i }))

        expect(mockRetryMetaCrmDatasetEvent).toHaveBeenCalledWith({ eventId: 'meta-event-1' })
    })

    it('shows last sync and triggers sync now for connected Google Calendar', () => {
        const lastSyncAt = '2026-02-21T02:30:00Z'
        mockUseUserIntegrations.mockReturnValue({
            data: [
                {
                    integration_type: 'google_calendar',
                    connected: true,
                    account_email: 'calendaruser@test.com',
                    expires_at: null,
                    last_sync_at: lastSyncAt,
                },
            ],
            isLoading: false,
        })
        mockUseGoogleCalendarStatus.mockReturnValue({
            data: {
                connected: true,
                account_email: 'calendaruser@test.com',
                expires_at: null,
                tasks_accessible: true,
                tasks_error: null,
                last_sync_at: lastSyncAt,
            },
            isLoading: false,
        })

        render(<IntegrationsPage />)

        const googleCard = screen.getByText('Google Calendar + Meeting').closest('[data-slot="card"]')
        expect(googleCard).not.toBeNull()
        expect(within(googleCard as HTMLElement).getByText(/last sync/i)).toBeInTheDocument()

        fireEvent.click(within(googleCard as HTMLElement).getByRole('button', { name: /sync now/i }))
        expect(mockSyncGoogleCalendarNow).toHaveBeenCalled()
    })

    it('keeps personal integrations accessible but blocks org configuration without manage_integrations', () => {
        mockUseAuth.mockReturnValue({ user: { role: 'case_manager', user_id: 'u2' } })
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: [] },
        })

        render(<IntegrationsPage />)

        expect(screen.getByRole('button', { name: /connect zoom/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /connect gmail/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /connect google calendar/i })).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: /configure ai/i })).not.toBeInTheDocument()
        expect(screen.queryByRole('button', { name: /configure email/i })).not.toBeInTheDocument()
        expect(screen.queryByRole('button', { name: /configure zapier/i })).not.toBeInTheDocument()
        expect(screen.queryByRole('button', { name: /configure meta/i })).not.toBeInTheDocument()
    })
})
