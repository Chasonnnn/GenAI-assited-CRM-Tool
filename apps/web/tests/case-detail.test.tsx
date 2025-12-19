import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import CaseDetailPage from '../app/(app)/cases/[id]/page'

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
const mockClaimCase = vi.fn()
const mockReleaseCase = vi.fn()

vi.mock('@/lib/hooks/use-queues', () => ({
    useQueues: () => mockUseQueues(),
    useClaimCase: () => ({ mutateAsync: mockClaimCase, isPending: false }),
    useReleaseCase: () => ({ mutateAsync: mockReleaseCase, isPending: false }),
}))

const mockUseCase = vi.fn()
const mockUseCaseActivity = vi.fn()
const mockUseNotes = vi.fn()
const mockUseTasks = vi.fn()

const mockChangeStatus = vi.fn()
const mockArchive = vi.fn()
const mockRestore = vi.fn()
const mockUpdateCase = vi.fn()
const mockCreateNote = vi.fn()
const mockDeleteNote = vi.fn()
const mockCompleteTask = vi.fn()
const mockUncompleteTask = vi.fn()

vi.mock('@/lib/hooks/use-cases', () => ({
    useCase: (id: string) => mockUseCase(id),
    useCaseActivity: (id: string) => mockUseCaseActivity(id),
    useChangeStatus: () => ({ mutateAsync: mockChangeStatus }),
    useArchiveCase: () => ({ mutateAsync: mockArchive }),
    useRestoreCase: () => ({ mutateAsync: mockRestore }),
    useUpdateCase: () => ({ mutateAsync: mockUpdateCase }),
    useSendCaseEmail: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/hooks/use-notes', () => ({
    useNotes: (caseId: string) => mockUseNotes(caseId),
    useCreateNote: () => ({ mutateAsync: mockCreateNote }),
    useDeleteNote: () => ({ mutateAsync: mockDeleteNote }),
}))

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: unknown) => mockUseTasks(params),
    useCompleteTask: () => ({ mutateAsync: mockCompleteTask }),
    useUncompleteTask: () => ({ mutateAsync: mockUncompleteTask }),
}))

vi.mock('@/lib/hooks/use-ai', () => ({
    useSummarizeCase: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDraftEmail: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useAISettings: () => ({ data: { is_enabled: false } }),
}))

vi.mock('@/lib/hooks/use-email-templates', () => ({
    useEmailTemplates: () => ({ data: [], isLoading: false }),
    useEmailTemplate: () => ({ data: null, isLoading: false }),  // singular for detail
    useSendEmail: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('CaseDetailPage', () => {
    beforeEach(() => {
        mockUseCase.mockReturnValue({
            data: {
                id: 'c1',
                case_number: '12345',
                full_name: 'Jane Applicant',
                status: 'new_unread',
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

        mockUseCaseActivity.mockReturnValue({ data: { items: [] } })
        mockUseNotes.mockReturnValue({ data: [] })
        mockUseTasks.mockReturnValue({ data: { items: [] } })
        mockUseQueues.mockReturnValue({ data: [] })

        mockPush.mockReset()
        mockClaimCase.mockReset()
        mockReleaseCase.mockReset()
            ; (navigator.clipboard.writeText as any).mockClear?.()
    })

    it('renders case header and allows copying email', () => {
        render(<CaseDetailPage />)

        expect(screen.getByText('Case #12345')).toBeInTheDocument()
        expect(screen.getByText('Jane Applicant')).toBeInTheDocument()
        expect(screen.getByText('jane@example.com')).toBeInTheDocument()

        const emailRow = screen.getByText('Email:').parentElement
        const copyButton = emailRow?.querySelector('button')
        expect(copyButton).toBeTruthy()

        fireEvent.click(copyButton!)
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith('jane@example.com')
    })

    it('shows Claim Case for queue-owned cases', () => {
        mockUseCase.mockReturnValueOnce({
            data: {
                id: 'c1',
                case_number: '12345',
                full_name: 'Jane Applicant',
                status: 'new_unread',
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

        render(<CaseDetailPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Claim Case' }))
        expect(mockClaimCase).toHaveBeenCalledWith('c1')
    })
})
