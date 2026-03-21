import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import SettingsPage from '../app/(app)/settings/page'

const mockReplace = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({ replace: mockReplace }),
}))

const mockUpdateNotificationSettings = vi.fn()
const mockRollbackPipeline = vi.fn()
const mockRollbackTemplate = vi.fn()

const versionModalSpy = vi.fn()

type VersionHistoryModalProps = {
    open: boolean
    entityType?: string
    title?: string
}

vi.mock('@/components/version-history-modal', () => ({
    VersionHistoryModal: (props: VersionHistoryModalProps) => {
        versionModalSpy(props)
        if (!props.open) return null
        return (
            <div data-testid="version-history-modal">
                {props.entityType}:{props.title}
            </div>
        )
    },
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({
        user: {
            role: 'developer',
            org_id: 'org-1',
            org_name: 'Test Organization',
        },
        refetch: vi.fn(),
    }),
}))

const mockGetOrgSettings = vi.fn()
const mockUpdateOrgSettings = vi.fn()
const mockUpdateProfile = vi.fn()
const mockGetIntelligentSuggestionSettings = vi.fn()
const mockUpdateIntelligentSuggestionSettings = vi.fn()
const mockGetIntelligentSuggestionTemplates = vi.fn()
const mockGetIntelligentSuggestionRules = vi.fn()
const mockCreateIntelligentSuggestionRule = vi.fn()
const mockUpdateIntelligentSuggestionRule = vi.fn()
const mockDeleteIntelligentSuggestionRule = vi.fn()

vi.mock('@/lib/api/settings', async (importOriginal) => {
    const actual = await importOriginal<typeof import('@/lib/api/settings')>()
    return {
        ...actual,
        getOrgSettings: () => mockGetOrgSettings(),
        updateOrgSettings: (payload: unknown) => mockUpdateOrgSettings(payload),
        updateProfile: (payload: unknown) => mockUpdateProfile(payload),
        getIntelligentSuggestionSettings: () => mockGetIntelligentSuggestionSettings(),
        updateIntelligentSuggestionSettings: (payload: unknown) => mockUpdateIntelligentSuggestionSettings(payload),
        getIntelligentSuggestionTemplates: () => mockGetIntelligentSuggestionTemplates(),
        getIntelligentSuggestionRules: () => mockGetIntelligentSuggestionRules(),
        createIntelligentSuggestionRule: (payload: unknown) => mockCreateIntelligentSuggestionRule(payload),
        updateIntelligentSuggestionRule: (ruleId: string, payload: unknown) =>
            mockUpdateIntelligentSuggestionRule(ruleId, payload),
        deleteIntelligentSuggestionRule: (ruleId: string) => mockDeleteIntelligentSuggestionRule(ruleId),
    }
})

vi.mock('@/lib/hooks/use-notifications', () => ({
    useNotificationSettings: () => ({
        data: {
            surrogate_assigned: true,
            surrogate_status_changed: true,
            surrogate_claim_available: true,
            task_assigned: true,
            workflow_approvals: true,
            task_reminders: true,
            appointments: true,
            contact_reminder: true,
            intelligent_suggestion_digest: true,
            status_change_decisions: true,
            approval_timeouts: true,
            security_alerts: true,
        },
        isLoading: false,
    }),
    useUpdateNotificationSettings: () => ({ mutate: mockUpdateNotificationSettings, isPending: false }),
    useNotifications: () => ({ data: { items: [], unread_count: 0 }, isLoading: false }),
    useUnreadCount: () => ({ data: { count: 0 }, isLoading: false }),
    useMarkRead: () => ({ mutate: vi.fn(), isPending: false }),
    useMarkAllRead: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/hooks/use-pipelines', () => ({
    usePipelines: () => ({
        data: [
            {
                id: 'p1',
                name: 'Default Pipeline',
                is_default: true,
                stages: [{
                    id: 'stage-1',
                    stage_key: 'new_unread',
                    slug: 'new_unread',
                    label: 'New',
                    color: '#000',
                    order: 1,
                    stage_type: 'intake',
                    is_active: true,
                }],
                current_version: 3,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
        ],
        isLoading: false,
    }),
    usePipelineVersions: (id: string | null) => ({
        data: id
            ? [
                {
                    id: 'pv1',
                    version: 1,
                    payload: { name: 'Default Pipeline', stages: [] },
                    comment: 'init',
                    created_by_user_id: null,
                    created_at: new Date().toISOString(),
                },
            ]
            : [],
        isLoading: false,
    }),
    useRollbackPipeline: () => ({ mutate: mockRollbackPipeline, isPending: false }),
}))

vi.mock('@/lib/hooks/use-email-templates', () => ({
    useEmailTemplates: () => ({
        data: [
            {
                id: 't1',
                name: 'Welcome',
                subject: 'Hello',
                is_active: true,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
        ],
        isLoading: false,
    }),
    useTemplateVersions: (id: string | null) => ({
        data: id
            ? [
                {
                    id: 'tv1',
                    version: 1,
                    payload: { name: 'Welcome', subject: 'Hello', body: 'Body', is_active: true },
                    comment: null,
                    created_by_user_id: null,
                    created_at: new Date().toISOString(),
                },
            ]
            : [],
        isLoading: false,
    }),
    useRollbackTemplate: () => ({ mutate: mockRollbackTemplate, isPending: false }),
}))

vi.mock('@/lib/hooks/use-system', () => ({
    useSystemHealth: () => ({ data: { version: '0.16.0' }, isLoading: false }),
}))

async function renderSettingsPage(searchParams: Record<string, string | string[] | undefined> = {}) {
    await act(async () => {
        render(<SettingsPage searchParams={Promise.resolve(searchParams)} />)
    })
}

describe('SettingsPage', () => {
    beforeEach(() => {
        mockUpdateNotificationSettings.mockReset()
        mockRollbackPipeline.mockReset()
        mockRollbackTemplate.mockReset()
        versionModalSpy.mockClear()
        mockGetOrgSettings.mockResolvedValue({
            name: 'Test Organization',
            address: '123 Main St',
            phone: '(555) 123-4567',
            email: 'contact@example.com',
            portal_base_url: 'https://test-org.surrogacyforce.com',
        })
        mockUpdateOrgSettings.mockResolvedValue({})
        mockUpdateProfile.mockResolvedValue({})
        mockGetIntelligentSuggestionSettings.mockResolvedValue({
            enabled: true,
            new_unread_enabled: true,
            new_unread_business_days: 1,
            meeting_outcome_enabled: true,
            meeting_outcome_business_days: 1,
            stuck_enabled: true,
            stuck_business_days: 5,
            daily_digest_enabled: true,
            digest_hour_local: 9,
        })
        mockGetIntelligentSuggestionTemplates.mockResolvedValue([
            {
                template_key: 'stage_followup_custom',
                name: 'Custom stage follow-up',
                description: 'No updates after X business days at a selected stage.',
                rule_kind: 'stage_inactivity',
                default_stage_slug: 'new_unread',
                default_business_days: 2,
                is_default: false,
            },
            {
                template_key: 'new_unread_followup',
                name: 'New unread follow-up',
                description: 'No updates after X business days in New Unread.',
                rule_kind: 'stage_inactivity',
                default_stage_slug: 'new_unread',
                default_business_days: 1,
                is_default: true,
            },
        ])
        mockGetIntelligentSuggestionRules.mockResolvedValue([
            {
                id: 'rule-1',
                organization_id: 'org-1',
                template_key: 'new_unread_followup',
                name: 'New unread follow-up',
                rule_kind: 'stage_inactivity',
                stage_slug: 'new_unread',
                business_days: 1,
                enabled: true,
                sort_order: 0,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
        ])
        mockCreateIntelligentSuggestionRule.mockResolvedValue({})
        mockUpdateIntelligentSuggestionRule.mockResolvedValue({})
        mockDeleteIntelligentSuggestionRule.mockResolvedValue({})
        mockUpdateIntelligentSuggestionSettings.mockResolvedValue({})
    })

    it('renders general tab by default', async () => {
        await renderSettingsPage()
        // There are multiple "General" texts (tab + heading), so use getAllByText
        expect(screen.getAllByText('General').length).toBeGreaterThan(0)
        expect(screen.getByText('Profile and access settings')).toBeDefined()
        expect(screen.getByText('v0.16.0')).toBeDefined()
    })

    it('shows a friendly role label instead of the raw role value', async () => {
        await renderSettingsPage()

        expect(screen.getByText('Developer')).toBeInTheDocument()
        expect(screen.queryByText('developer')).not.toBeInTheDocument()
    })

    it('shows organization branding section in email signature tab', async () => {
        await renderSettingsPage({ tab: 'email-signature' })

        expect(screen.getByText('Organization Branding')).toBeInTheDocument()
        expect(screen.queryByText('Organization Info')).not.toBeInTheDocument()
        expect(screen.queryByText('Signature Branding')).not.toBeInTheDocument()
    })

    it('shows intelligent suggestions tab for admin roles', async () => {
        await renderSettingsPage()
        expect(screen.getByText('Intelligent Suggestions')).toBeInTheDocument()
    })

    // Note: Pipeline version history test removed - pipelines moved to dedicated /settings/pipelines page
})
