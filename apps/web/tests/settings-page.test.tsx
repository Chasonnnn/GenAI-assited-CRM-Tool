import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import SettingsPage from '../app/(app)/settings/page'

const mockReplace = vi.fn()
let mockSearchParams = new URLSearchParams()

vi.mock('next/navigation', () => ({
    useRouter: () => ({ replace: mockReplace }),
    useSearchParams: () => mockSearchParams,
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

vi.mock('@/lib/api/settings', async (importOriginal) => {
    const actual = await importOriginal<typeof import('@/lib/api/settings')>()
    return {
        ...actual,
        getOrgSettings: () => mockGetOrgSettings(),
        updateOrgSettings: (payload: unknown) => mockUpdateOrgSettings(payload),
        updateProfile: (payload: unknown) => mockUpdateProfile(payload),
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
                stages: [{ status: 'new_unread', label: 'New', color: '#000' }],
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

describe('SettingsPage', () => {
    beforeEach(() => {
        mockUpdateNotificationSettings.mockReset()
        mockRollbackPipeline.mockReset()
        mockRollbackTemplate.mockReset()
        versionModalSpy.mockClear()
        mockSearchParams = new URLSearchParams()
        mockGetOrgSettings.mockResolvedValue({
            name: 'Test Organization',
            address: '123 Main St',
            phone: '(555) 123-4567',
            email: 'contact@example.com',
            portal_base_url: 'https://test-org.surrogacyforce.com',
        })
        mockUpdateOrgSettings.mockResolvedValue({})
        mockUpdateProfile.mockResolvedValue({})
    })

    it('renders general tab by default', () => {
        render(<SettingsPage />)
        // There are multiple "General" texts (tab + heading), so use getAllByText
        expect(screen.getAllByText('General').length).toBeGreaterThan(0)
        expect(screen.getByText('Profile and access settings')).toBeDefined()
        expect(screen.getByText('v0.16.0')).toBeDefined()
    })

    it('shows a friendly role label instead of the raw role value', () => {
        render(<SettingsPage />)

        expect(screen.getByText('Developer')).toBeInTheDocument()
        expect(screen.queryByText('developer')).not.toBeInTheDocument()
    })

    it('shows organization branding section in email signature tab', async () => {
        mockSearchParams = new URLSearchParams('tab=email-signature')
        render(<SettingsPage />)

        expect(await screen.findByText('Organization Branding')).toBeInTheDocument()
        expect(screen.queryByText('Organization Info')).not.toBeInTheDocument()
        expect(screen.queryByText('Signature Branding')).not.toBeInTheDocument()
    })

    // Note: Pipeline version history test removed - pipelines moved to dedicated /settings/pipelines page
})
