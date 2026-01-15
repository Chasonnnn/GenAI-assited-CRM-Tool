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
    useAuth: () => ({ user: { role: 'developer' } }),
}))

vi.mock('@/lib/hooks/use-notifications', () => ({
    useNotificationSettings: () => ({
        data: {
            surrogate_assigned: true,
            surrogate_status_changed: true,
            surrogate_claim_available: true,
            task_assigned: true,
            workflow_approvals: true,
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

describe('SettingsPage', () => {
    beforeEach(() => {
        mockUpdateNotificationSettings.mockReset()
        mockRollbackPipeline.mockReset()
        mockRollbackTemplate.mockReset()
        versionModalSpy.mockClear()
        mockSearchParams = new URLSearchParams()
    })

    it('renders general tab by default', () => {
        render(<SettingsPage />)
        // There are multiple "General" texts (tab + heading), so use getAllByText
        expect(screen.getAllByText('General').length).toBeGreaterThan(0)
        expect(screen.getByText('Profile and access settings')).toBeDefined()
    })

    // Note: Pipeline version history test removed - pipelines moved to dedicated /settings/pipelines page
})
