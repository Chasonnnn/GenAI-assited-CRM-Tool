import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SurrogateDetailPage from '../app/(app)/surrogates/[id]/page'

const mockPush = vi.fn()
const mockCreateZoomMeeting = vi.fn()
const mockSendZoomInvite = vi.fn()

vi.mock('next/navigation', () => ({
    useParams: () => ({ id: 'c1' }),
    useRouter: () => ({ push: mockPush }),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { role: 'developer' } }),
}))

vi.mock('@/components/rich-text-editor', () => ({
    RichTextEditor: () => <div data-testid="rich-text-editor" />,
}))

vi.mock('@/lib/hooks/use-user-integrations', () => ({
    useZoomStatus: () => ({ data: { connected: false, account_email: null } }),
    useCreateZoomMeeting: () => ({ mutateAsync: mockCreateZoomMeeting, isPending: false }),
    useSendZoomInvite: () => ({ mutateAsync: mockSendZoomInvite, isPending: false }),
}))

const mockUseQueues = vi.fn()
const mockClaimSurrogate = vi.fn()
const mockReleaseSurrogate = vi.fn()

vi.mock('@/lib/hooks/use-queues', () => ({
    useQueues: () => mockUseQueues(),
    useClaimSurrogate: () => ({ mutateAsync: mockClaimSurrogate, isPending: false }),
    useReleaseSurrogate: () => ({ mutateAsync: mockReleaseSurrogate, isPending: false }),
}))

const mockUseSurrogate = vi.fn()
const mockUseSurrogateActivity = vi.fn()
const mockUseNotes = vi.fn()
const mockUseTasks = vi.fn()

const mockChangeStatus = vi.fn()
const mockArchive = vi.fn()
const mockRestore = vi.fn()
const mockUpdateSurrogate = vi.fn()
const mockAssignSurrogate = vi.fn()
const mockUseAssignees = vi.fn()
const mockCreateNote = vi.fn()
const mockDeleteNote = vi.fn()
const mockCompleteTask = vi.fn()
const mockUncompleteTask = vi.fn()
const mockUpdateTask = vi.fn()
const mockCreateTask = vi.fn()
const mockDeleteTask = vi.fn()

vi.mock('@/lib/hooks/use-surrogates', () => ({
    useSurrogate: (id: string) => mockUseSurrogate(id),
    useSurrogateActivity: (id: string) => mockUseSurrogateActivity(id),
    useChangeSurrogateStatus: () => ({ mutateAsync: mockChangeStatus }),
    useArchiveSurrogate: () => ({ mutateAsync: mockArchive }),
    useRestoreSurrogate: () => ({ mutateAsync: mockRestore }),
    useUpdateSurrogate: () => ({ mutateAsync: mockUpdateSurrogate }),
    useAssignSurrogate: () => ({ mutateAsync: mockAssignSurrogate }),
    useAssignees: () => mockUseAssignees(),
    useSendSurrogateEmail: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCreateContactAttempt: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useContactAttempts: () => ({ data: null, isLoading: false }),
}))

vi.mock('@/lib/hooks/use-notes', () => ({
    useNotes: (surrogateId: string) => mockUseNotes(surrogateId),
    useCreateNote: () => ({ mutateAsync: mockCreateNote }),
    useDeleteNote: () => ({ mutateAsync: mockDeleteNote }),
}))

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: unknown) => mockUseTasks(params),
    useCompleteTask: () => ({ mutateAsync: mockCompleteTask }),
    useUncompleteTask: () => ({ mutateAsync: mockUncompleteTask }),
    useUpdateTask: () => ({ mutateAsync: mockUpdateTask }),
    useCreateTask: () => ({ mutateAsync: mockCreateTask, isPending: false }),
    useDeleteTask: () => ({ mutateAsync: mockDeleteTask, isPending: false }),
}))

vi.mock('@/lib/hooks/use-ai', () => ({
    useSummarizeSurrogate: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDraftEmail: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useAISettings: () => ({ data: { is_enabled: false } }),
}))

vi.mock('@/lib/hooks/use-pipelines', () => ({
    useDefaultPipeline: () => ({
        data: {
            id: 'p1',
            stages: [
                { id: 's1', slug: 'new_unread', label: 'New Unread', color: '#3b82f6', stage_type: 'intake', is_active: true },
            ],
        },
        isLoading: false,
    }),
}))

vi.mock('@/lib/hooks/use-email-templates', () => ({
    useEmailTemplates: () => ({ data: [], isLoading: false }),
    useEmailTemplate: () => ({ data: null, isLoading: false }),  // singular for detail
    useSendEmail: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/hooks/use-intended-parents', () => ({
    useIntendedParents: () => ({ data: { items: [] }, isLoading: false }),
}))

vi.mock('@/lib/hooks/use-matches', () => ({
    useCreateMatch: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('SurrogateDetailPage', () => {
    beforeEach(() => {
        mockUseAssignees.mockReturnValue({ data: [] })
        mockUseSurrogate.mockReturnValue({
            data: {
                id: 'c1',
                surrogate_number: 'SUR-12345',
                full_name: 'Jane Applicant',
                status_label: 'New Unread',
                stage_id: 's1',
                stage_slug: 'new_unread',
                stage_type: 'intake',
                source: 'manual',
                email: 'jane@example.com',
                phone: null,
                state: null,
                is_priority: false,
                is_archived: false,
                owner_type: 'user',
                owner_id: 'u1',
                owner_name: null,
                age: null,
                bmi: null,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                created_by_user_id: null,
                date_of_birth: null,
                race: null,
                height_ft: null,
                weight_lb: null,
                is_age_eligible: null,
                is_citizen_or_pr: null,
                has_child: null,
                is_non_smoker: null,
                has_surrogate_experience: null,
                num_deliveries: null,
                num_csections: null,
                archived_at: null,
            },
            isLoading: false,
            error: null,
        })

        mockUseSurrogateActivity.mockReturnValue({ data: { items: [] } })
        mockUseNotes.mockReturnValue({ data: [] })
        mockUseTasks.mockReturnValue({ data: { items: [] } })
        mockUseQueues.mockReturnValue({ data: [] })

        mockPush.mockReset()
        mockClaimSurrogate.mockReset()
        mockReleaseSurrogate.mockReset()
        const clipboardWriteText = navigator.clipboard.writeText as unknown as { mockClear?: () => void }
        clipboardWriteText.mockClear?.()
    })

    it('renders surrogate header and allows copying email', () => {
        render(<SurrogateDetailPage />)

        expect(screen.getByText('Surrogate #SUR-12345')).toBeInTheDocument()
        expect(screen.getByText('Jane Applicant')).toBeInTheDocument()
        expect(screen.getByText('jane@example.com')).toBeInTheDocument()

        const emailRow = screen.getByText('Email:').parentElement
        const copyButton = emailRow?.querySelector('button')
        expect(copyButton).toBeTruthy()

        fireEvent.click(copyButton!)
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith('jane@example.com')
    })

    it('shows Claim Surrogate for queue-owned surrogates', () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                id: 'c1',
                surrogate_number: 'SUR-12345',
                full_name: 'Jane Applicant',
                status_label: 'New Unread',
                stage_id: 's1',
                stage_slug: 'new_unread',
                stage_type: 'intake',
                source: 'manual',
                email: 'jane@example.com',
                phone: null,
                state: null,
                is_priority: false,
                is_archived: false,
                owner_type: 'queue',
                owner_id: 'q1',
                owner_name: null,
                age: null,
                bmi: null,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                created_by_user_id: null,
                date_of_birth: null,
                race: null,
                height_ft: null,
                weight_lb: null,
                is_age_eligible: null,
                is_citizen_or_pr: null,
                has_child: null,
                is_non_smoker: null,
                has_surrogate_experience: null,
                num_deliveries: null,
                num_csections: null,
                archived_at: null,
            },
            isLoading: false,
            error: null,
        })

        render(<SurrogateDetailPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Claim Surrogate' }))
        expect(mockClaimSurrogate).toHaveBeenCalledWith('c1')
    })
})
