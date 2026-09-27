import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { ApiError } from '@/lib/api'
import SettingsPage from '../app/(app)/settings/page'

const mockReplace = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({ replace: mockReplace }),
}))

const mockUpdateNotificationSettings = vi.fn()
const mockRollbackPipeline = vi.fn()
const mockToastError = vi.fn()
const mockToastSuccess = vi.fn()
const mockRevokeSession = vi.fn()
const mockRevokeAllSessions = vi.fn()

let mockUser: Record<string, string> = {
    user_id: 'user-1',
    role: 'developer',
    org_id: 'org-1',
    org_name: 'Test Organization',
    display_name: 'Dana Developer',
    title: 'Agency Director',
    phone: '(555) 000-1111',
    email: 'dana@example.com',
}

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({
        user: mockUser,
        refetch: vi.fn(),
    }),
}))

vi.mock('@/components/ui/toast', () => ({
    toast: {
        success: (...args: unknown[]) => mockToastSuccess(...args),
        error: (...args: unknown[]) => mockToastError(...args),
    },
}))

let mockSessions: Array<Record<string, unknown>> = []

vi.mock('@/lib/hooks/use-sessions', () => ({
    useSessions: () => ({ data: mockSessions, isLoading: false }),
    useRevokeSession: () => ({ mutateAsync: mockRevokeSession, isPending: false }),
    useRevokeAllSessions: () => ({ mutateAsync: mockRevokeAllSessions, isPending: false }),
    useUploadAvatar: () => ({ mutate: vi.fn(), isPending: false }),
    useDeleteAvatar: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

const mockGetOrgSettings = vi.fn()
const mockUpdateOrgSettings = vi.fn()
const mockUpdateProfile = vi.fn()
const mockUpdateOrgSignature = vi.fn()
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

let mockOrgSignature = {
    signature_social_links: [
        { platform: 'LinkedIn', url: 'https://linkedin.com/company/test' },
    ],
}

vi.mock('@/lib/hooks/use-signature', () => ({
    useOrgSignature: () => ({ data: mockOrgSignature, isLoading: false }),
    useUpdateOrgSignature: () => ({ mutateAsync: mockUpdateOrgSignature, isPending: false }),
    useUploadOrgLogo: () => ({ mutate: vi.fn(), isPending: false }),
    useDeleteOrgLogo: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

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
}))

vi.mock('@/lib/hooks/use-system', () => ({
    useSystemHealth: () => ({ data: { version: '0.16.0' }, isLoading: false }),
}))

async function renderSettingsPage(searchParams: Record<string, string | string[] | undefined> = {}) {
    let result: ReturnType<typeof render> | undefined
    await act(async () => {
        result = render(<SettingsPage searchParams={Promise.resolve(searchParams)} />)
    })
    return result!
}

describe('SettingsPage', () => {
    beforeEach(() => {
        mockUser = {
            user_id: 'user-1',
            role: 'developer',
            org_id: 'org-1',
            org_name: 'Test Organization',
            display_name: 'Dana Developer',
            title: 'Agency Director',
            phone: '(555) 000-1111',
            email: 'dana@example.com',
        }
        mockSessions = []
        mockToastError.mockReset()
        mockToastSuccess.mockReset()
        mockRevokeSession.mockReset()
        mockRevokeAllSessions.mockReset()
        mockUpdateProfile.mockReset()
        mockUpdateNotificationSettings.mockReset()
        mockUpdateOrgSignature.mockReset()
        mockUpdateOrgSignature.mockResolvedValue({})
        mockOrgSignature = {
            signature_social_links: [
                { platform: 'LinkedIn', url: 'https://linkedin.com/company/test' },
            ],
        }
        mockRollbackPipeline.mockReset()
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
        expect(screen.queryByText('Profile and access settings')).not.toBeInTheDocument()
        expect(screen.getByText('v0.16.0')).toBeDefined()
    })

    it('shows a friendly role label instead of the raw role value', async () => {
        await renderSettingsPage()

        expect(screen.getByText('Developer')).toBeInTheDocument()
        expect(screen.queryByText('developer')).not.toBeInTheDocument()
    })

    it('shows organization branding section in email signature tab', async () => {
        await renderSettingsPage({ tab: 'email-signature' })

        expect(await screen.findByText('Organization Branding')).toBeInTheDocument()
        expect(screen.queryByText('Organization Info')).not.toBeInTheDocument()
        expect(screen.queryByText('Signature Branding')).not.toBeInTheDocument()
    })

    it('preserves an in-progress social link edit when equivalent signature data rerenders', async () => {
        const view = await renderSettingsPage({ tab: 'email-signature' })
        const urlInput = await screen.findByLabelText('Social URL 1')

        fireEvent.change(urlInput, { target: { value: 'https://linkedin.com/company/edited' } })
        expect(urlInput).toHaveValue('https://linkedin.com/company/edited')

        mockOrgSignature = {
            signature_social_links: [
                { platform: 'LinkedIn', url: 'https://linkedin.com/company/test' },
            ],
        }
        await act(async () => {
            view.rerender(<SettingsPage searchParams={Promise.resolve({ tab: 'email-signature' })} />)
            await Promise.resolve()
        })

        expect(screen.getByLabelText('Social URL 1')).toHaveValue('https://linkedin.com/company/edited')
    })

    it('shows a stored lowercase platform with its display label', async () => {
        mockOrgSignature = {
            signature_social_links: [{ platform: 'linkedin', url: 'https://linkedin.com/company/test' }],
        }

        await renderSettingsPage({ tab: 'email-signature' })

        expect(await screen.findByRole('combobox', { name: 'Social platform 1' })).toHaveTextContent('LinkedIn')
        expect(screen.queryByText('linkedin')).not.toBeInTheDocument()
    })

    it('saves branding and social links from one save bar', async () => {
        await renderSettingsPage({ tab: 'email-signature' })
        await screen.findByText('Organization Branding')

        expect(screen.queryByRole('button', { name: /save organization branding/i })).not.toBeInTheDocument()
        expect(screen.queryByRole('button', { name: /save social links/i })).not.toBeInTheDocument()
        expect(screen.queryByRole('region', { name: 'Unsaved changes' })).not.toBeInTheDocument()

        fireEvent.change(screen.getByLabelText('Website'), { target: { value: 'https://agency.example.com' } })
        fireEvent.change(screen.getByLabelText('Social URL 1'), {
            target: { value: 'https://linkedin.com/company/agency' },
        })

        const bar = screen.getByRole('region', { name: 'Unsaved changes' })
        expect(within(bar).getByText('2 unsaved changes')).toBeInTheDocument()

        fireEvent.click(within(bar).getByRole('button', { name: 'Save changes' }))

        await waitFor(() => expect(mockUpdateOrgSignature).toHaveBeenCalledTimes(1))
        expect(mockUpdateOrgSignature).toHaveBeenCalledWith(
            expect.objectContaining({
                signature_website: 'https://agency.example.com',
                signature_social_links: [{ platform: 'LinkedIn', url: 'https://linkedin.com/company/agency' }],
            })
        )
        await waitFor(() => expect(mockToastSuccess).toHaveBeenCalledWith('Email signature saved'))
    })

    it('blocks saving a social link without https and shows the field error', async () => {
        await renderSettingsPage({ tab: 'email-signature' })

        const urlInput = await screen.findByLabelText('Social URL 1')
        fireEvent.change(urlInput, { target: { value: 'linkedin.com/company/test' } })
        fireEvent.blur(urlInput)

        expect(urlInput).toHaveAttribute('aria-invalid', 'true')
        expect(screen.getByText('Enter a URL that starts with https://.')).toBeInTheDocument()
        const bar = screen.getByRole('region', { name: 'Unsaved changes' })
        expect(within(bar).getByRole('button', { name: 'Save changes' })).toBeDisabled()
        expect(mockUpdateOrgSignature).not.toHaveBeenCalled()
    })

    it('matches signature textareas to the input fill', async () => {
        await renderSettingsPage({ tab: 'email-signature' })

        expect(await screen.findByLabelText('Address')).toHaveClass('bg-transparent')
        expect(screen.getByLabelText('Address')).not.toHaveClass('bg-input/30')
    })

    it('clears Title and Phone by sending empty strings', async () => {
        await renderSettingsPage()

        expect(screen.queryByRole('region', { name: 'Unsaved changes' })).not.toBeInTheDocument()
        fireEvent.change(screen.getByLabelText('Title'), { target: { value: '' } })
        fireEvent.change(screen.getByLabelText('Phone'), { target: { value: '   ' } })
        const bar = screen.getByRole('region', { name: 'Unsaved changes' })
        expect(bar).toHaveTextContent('2 unsaved changes')
        fireEvent.click(within(bar).getByRole('button', { name: 'Save changes' }))

        await waitFor(() =>
            expect(mockUpdateProfile).toHaveBeenCalledWith({
                display_name: 'Dana Developer',
                phone: '',
                title: '',
            })
        )
        await waitFor(() => expect(mockToastSuccess).toHaveBeenCalledWith('Profile saved'))
        expect(screen.queryByRole('region', { name: 'Unsaved changes' })).not.toBeInTheDocument()
    })

    it('discards profile edits from the save bar', async () => {
        await renderSettingsPage()

        fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Director' } })
        const bar = screen.getByRole('region', { name: 'Unsaved changes' })
        expect(bar).toHaveTextContent('1 unsaved change')
        fireEvent.click(within(bar).getByRole('button', { name: 'Discard' }))

        expect(screen.getByLabelText('Title')).toHaveValue('Agency Director')
        expect(screen.queryByRole('region', { name: 'Unsaved changes' })).not.toBeInTheDocument()
    })

    it('requires a full name before saving the profile', async () => {
        await renderSettingsPage()

        const name = screen.getByLabelText('Full Name')
        fireEvent.change(name, { target: { value: '  ' } })
        expect(name).toHaveAttribute('aria-invalid', 'true')

        const bar = screen.getByRole('region', { name: 'Unsaved changes' })
        expect(within(bar).getByRole('button', { name: 'Save changes' })).toBeDisabled()
        fireEvent.click(within(bar).getByRole('button', { name: '1 error' }))

        expect(name).toHaveFocus()
        expect(name).toHaveAttribute('aria-invalid', 'true')
        expect(screen.getByText('Enter your full name.')).toBeInTheDocument()
        expect(mockUpdateProfile).not.toHaveBeenCalled()
    })

    it('shows an error toast when the profile save fails', async () => {
        mockUpdateProfile.mockRejectedValue(new ApiError(500, 'Internal Server Error', 'db down'))
        await renderSettingsPage()

        fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Director' } })
        const bar = screen.getByRole('region', { name: 'Unsaved changes' })
        fireEvent.click(within(bar).getByRole('button', { name: 'Save changes' }))

        await waitFor(() => expect(mockToastError).toHaveBeenCalledWith("Couldn't save your profile. Try again."))
        expect(screen.getByRole('region', { name: 'Unsaved changes' })).toBeInTheDocument()
    })

    it('confirms session revoke in an in-app dialog', async () => {
        const confirmSpy = vi.spyOn(window, 'confirm')
        mockSessions = [
            {
                id: 'session-current',
                device_info: 'Chrome on macOS',
                ip_address: '10.0.0.1',
                last_active_at: new Date().toISOString(),
                is_current: true,
            },
            {
                id: 'session-other',
                device_info: 'Safari on iPhone',
                ip_address: '10.0.0.2',
                last_active_at: new Date().toISOString(),
                is_current: false,
            },
        ]
        mockRevokeSession.mockResolvedValue(undefined)
        await renderSettingsPage()

        fireEvent.click(screen.getByRole('button', { name: 'Revoke session on Safari on iPhone' }))
        const dialog = await screen.findByRole('alertdialog')
        expect(within(dialog).getByText('Revoke the session on Safari on iPhone?')).toBeInTheDocument()
        fireEvent.click(within(dialog).getByRole('button', { name: 'Revoke session' }))

        await waitFor(() => expect(mockRevokeSession).toHaveBeenCalledWith('session-other'))
        expect(confirmSpy).not.toHaveBeenCalled()
        confirmSpy.mockRestore()
    })

    it('shows intelligent suggestions tab for admin roles', async () => {
        await renderSettingsPage()
        expect(screen.getByText('Intelligent Suggestions')).toBeInTheDocument()
    })

    // Note: Pipeline version history test removed - pipelines moved to dedicated /settings/pipelines page
})
