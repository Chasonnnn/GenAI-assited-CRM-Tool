import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import CaseDetailPage from '../app/(app)/cases/[id]/page'

const mockPush = vi.fn()

vi.mock('next/navigation', () => ({
    useParams: () => ({ id: 'c1' }),
    useRouter: () => ({ push: mockPush }),
}))

vi.mock('@/components/rich-text-editor', () => ({
    RichTextEditor: () => <div data-testid="rich-text-editor" />,
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
                assigned_to_name: null,
                is_priority: false,
                is_archived: false,
                age: null,
                bmi: null,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                assigned_to_user_id: null,
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

        mockPush.mockReset()
        ;(navigator.clipboard.writeText as any).mockClear?.()
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
})

