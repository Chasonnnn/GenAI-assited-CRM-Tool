import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import '@testing-library/jest-dom'
import MatchDetailPage from '../app/(app)/intended-parents/matches/[id]/page.client'
import { ApiError } from '@/lib/api'

const mockPush = vi.fn()
const mockReplace = vi.fn()
const mockInvalidateQueries = vi.fn()
const mockAcceptMatchMutateAsync = vi.fn()

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

vi.mock('next/navigation', () => ({
    useParams: () => ({ id: 'match1' }),
    useRouter: () => ({ push: mockPush, replace: mockReplace }),
    useSearchParams: () => ({
        get: (_key: string) => null,
        toString: () => '',
        keys: () => [] as string[],
    }),
}))

// Mock auth context
const DEFAULT_PERMISSIONS = ['view_matches', 'propose_matches']
let mockUserRole = 'admin'
let mockPermissions: string[] = DEFAULT_PERMISSIONS
vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({
        user: { role: mockUserRole, id: 'user1', user_id: 'user1', display_name: 'Test Admin' },
        isLoading: false,
    }),
}))

vi.mock('@/lib/hooks/use-permissions', () => ({
    useEffectivePermissions: () => ({
        data: { permissions: mockPermissions },
        isLoading: false,
        isError: false,
        isFetching: false,
        error: null,
        refetch: vi.fn(),
    }),
}))

beforeEach(() => {
    mockUserRole = 'admin'
    mockPermissions = DEFAULT_PERMISSIONS
})

// Mock react-query
vi.mock('@tanstack/react-query', async () => {
    const actual = await vi.importActual('@tanstack/react-query')
    return {
        ...actual,
        useQueryClient: () => ({
            invalidateQueries: mockInvalidateQueries,
        }),
    }
})

// Mock match hooks
const mockUseMatchAttempts = vi.fn()
const mockCompleteMatchMutateAsync = vi.fn()
const mockSaveAttemptMutateAsync = vi.fn()
const mockUseMatchWork = vi.fn()
const mockUseDonor = vi.fn()
const mockCreateMatchNote = vi.fn()
const mockUploadMatchFile = vi.fn()
const mockUseMatch = vi.fn()
const mockUseAcceptMatch = vi.fn()
const mockUseDeclineMatch = vi.fn()
const mockUseCancelMatch = vi.fn()
const mockUseUpdateMatchNotes = vi.fn()
const mockUseWithdrawMatchCancellation = vi.fn()

vi.mock('@/lib/hooks/use-matches', () => ({
    useMatch: (id: string) => mockUseMatch(id),
    useMatchWork: (id: string, attemptId?: string, page?: number) => mockUseMatchWork(id, attemptId, page),
    useMatchAttempts: () => mockUseMatchAttempts(),
    useCompleteMatch: () => ({ mutateAsync: mockCompleteMatchMutateAsync, isPending: false }),
    useSaveMatchAttempt: () => ({ mutateAsync: mockSaveAttemptMutateAsync, isPending: false }),
    useCreateMatchNote: () => ({ mutateAsync: mockCreateMatchNote, isPending: false }),
    useUploadMatchFile: () => ({ mutateAsync: mockUploadMatchFile, isPending: false }),
    matchWorkKeys: { all: (id: string) => ['matches', 'detail', id, 'work'] },
    useAcceptMatch: () => mockUseAcceptMatch(),
    useDeclineMatch: () => mockUseDeclineMatch(),
    useCancelMatch: () => mockUseCancelMatch(),
    useWithdrawMatchCancellation: () => mockUseWithdrawMatchCancellation(),
    useUpdateMatchNotes: () => mockUseUpdateMatchNotes(),
    matchKeys: { detail: (id: string) => ['matches', 'detail', id], lists: () => ['matches', 'list'] },
}))

vi.mock('@/lib/hooks/use-donors', () => ({
    useDonor: (id: string | null) => mockUseDonor(id),
    donorKeys: { detail: (id: string) => ['donors', 'detail', id] },
}))

// Mock surrogate hooks
const mockUseSurrogate = vi.fn()
const mockUseSurrogateActivity = vi.fn()
vi.mock('@/lib/hooks/use-surrogates', () => ({
    useSurrogate: (id: string) => mockUseSurrogate(id),
    useSurrogateActivity: (id: string) => mockUseSurrogateActivity(id),
    useChangeSurrogateStatus: () => ({ mutateAsync: vi.fn(), isPending: false }),
    surrogateKeys: {
        detail: (id: string) => ['surrogates', 'detail', id],
        lists: () => ['surrogates', 'list'],
        activity: (id: string) => ['surrogates', 'detail', id, 'activity'],
        history: (id: string) => ['surrogates', 'detail', id, 'history'],
    },
}))

// Mock notes hook
vi.mock('@/lib/hooks/use-notes', () => ({
    useNotes: () => ({ data: [], isLoading: false }),
    useCreateNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

// Mock IP hooks
const mockUseIntendedParent = vi.fn()
const mockUseIntendedParentHistory = vi.fn()
vi.mock('@/lib/hooks/use-intended-parents', () => ({
    useIntendedParent: (id: string) => mockUseIntendedParent(id),
    useIntendedParentNotes: () => ({ data: [] }),
    useIntendedParentHistory: (id: string) => mockUseIntendedParentHistory(id),
    useCreateIntendedParentNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
    intendedParentKeys: {
        detail: (id: string) => ['intended-parents', 'detail', id],
        lists: () => ['intended-parents', 'list'],
        history: (id: string) => ['intended-parents', 'history', id],
        notes: (id: string) => ['intended-parents', 'notes', id],
    },
}))

// Mock attachments hook
vi.mock('@/lib/hooks/use-attachments', () => ({
    useAttachments: () => ({ data: [], isLoading: false }),
    useIPAttachments: () => ({ data: [], isLoading: false }),
    useUploadAttachment: () => ({ mutateAsync: async () => ({}), isPending: false }),
    useUploadIPAttachment: () => ({ mutateAsync: async () => ({}), isPending: false }),
    useDeleteAttachment: () => ({ mutateAsync: async () => ({}), isPending: false }),
    useDownloadAttachment: () => ({ mutate: () => { }, isPending: false }),
    useAttachmentDownloadUrl: () => ({ mutateAsync: async () => ({ download_url: "" }), isPending: false }),
}))

// Mock tasks hook
const mockUseTasks = vi.fn()
const mockCreateTaskMutateAsync = vi.fn()
vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: unknown) => mockUseTasks(params),
    useCreateTask: () => ({ mutateAsync: mockCreateTaskMutateAsync, isPending: false }),
    taskKeys: { lists: () => ['tasks', 'list'] },
}))

// Mock pipelines hook
vi.mock('@/lib/hooks/use-pipelines', () => ({
    useDefaultPipeline: (entityType: string = 'surrogate') => ({
        data: entityType === 'intended_parent'
            ? {
                id: 'ip-pipeline',
                stages: [
                    { id: 'ipstage1', stage_key: 'new', label: 'New', order: 1, system_role: null },
                    { id: 'ipstage2', stage_key: 'ready_to_match', label: 'Ready to Match', order: 2, system_role: null },
                    { id: 'ipstage3', stage_key: 'matched', label: 'Matched', order: 3, system_role: 'matched' },
                ],
            }
            : {
                id: 'pipeline1',
                stages: [
                    { id: 'stage1', slug: 'ready_to_match', label: 'Ready to Match', color: '#888', stage_type: 'post_approval', order: 1, system_role: null },
                    { id: 'stage2', slug: 'matched', label: 'Matched', color: '#22c55e', stage_type: 'post_approval', order: 2, system_role: 'matched' },
                    { id: 'stage3', slug: 'medical_clearance_passed', label: 'Medical Clearance Passed', color: '#3b82f6', stage_type: 'post_approval', order: 3, system_role: null },
                ],
            },
        isLoading: false,
    }),
}))

// Mock toast
vi.mock('@/hooks/use-toast', () => ({
    useToast: () => ({ toast: vi.fn() }),
}))

describe('MatchDetailPage', () => {
    const mockMatch = {
        id: 'match1',
        match_number: 'M10001',
        surrogate_id: 'surrogate1',
        surrogate_name: 'Jane Doe',
        surrogate_number: 'S10001',
        ip_id: 'ip1',
        intended_parent_id: 'ip1',
        ip_name: 'John Smith',
        status: 'under_review' as const,
        proposed_at: '2024-01-15T10:00:00Z',
        proposed_by_user_id: 'user1',
        proposed_by_name: 'Admin User',
        notes_internal: 'Internal notes about the match',
        allowed_actions: ['accept', 'decline'],
        blocked_reasons: {},
        accept_eligibility_warnings: [],
        surrogate_has_accepted_match: false,
        pending_cancellation_request_id: null,
    }

    it.each(['completed', 'cancelled', 'cancellation_pending', 'declined'])('keeps %s case work readable without creation actions', async (status) => {
        mockUseMatch.mockReturnValue({ data: { ...mockMatch, status, outcome: 'Finished.', closed_at: '2026-09-05T12:00:00Z' }, isLoading: false })
        mockUseMatchWork.mockReturnValue({ data: { notes: [{ id: 'note1', content: 'Existing case note', source: 'match', created_at: '2026-09-05T12:00:00Z', author_name: 'Admin' }], files: [], tasks: [], activity: [] }, isLoading: false })
        render(<MatchDetailPage />)
        expect(screen.getByText('Existing case note')).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Add Note' })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('tab', { name: 'Files' }))
        expect(screen.queryByRole('button', { name: 'Upload File' })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('tab', { name: 'Tasks' }))
        expect(screen.queryByRole('button', { name: 'Add Task' })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('tab', { name: 'Calendar' }))
        expect(screen.queryByRole('button', { name: 'Add Task' })).not.toBeInTheDocument()
        expect(screen.getByText(/Finished\./).textContent).toContain('Finished. · ')
    })

    const mockSurrogate = {
        id: 'surrogate1',
        surrogate_number: 'S10001',
        full_name: 'Jane Doe',
        status_label: 'Matched',
        stage_id: 'stage2',
        stage_slug: 'matched',
        stage_type: 'post_approval',
        source: 'manual',
        email: 'jane@example.com',
        phone: '555-1234',
        state: 'CA',
        date_of_birth: '1990-05-15',
        race: null,
        height_ft: null,
        weight_lb: null,
        is_priority: false,
        is_archived: false,
        owner_type: 'user',
        owner_id: 'user1',
        owner_name: 'Test Admin',
        age: null,
        bmi: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-15T00:00:00Z',
    }

    const mockIP = {
        id: 'ip1',
        full_name: 'John Smith',
        email: 'john@example.com',
        phone: '555-5678',
        state: 'NY',
        budget: 100000,
        status: 'matched',
        is_archived: false,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-15T00:00:00Z',
    }

    beforeEach(() => {
        vi.clearAllMocks()
        mockUseMatchAttempts.mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() })
        mockUseDonor.mockReturnValue({ data: undefined, isLoading: false, isError: false })
        mockUseMatchWork.mockReturnValue({ data: { notes: [], files: [], tasks: [], activity: [] }, isLoading: false, error: null, refetch: vi.fn() })
        mockInvalidateQueries.mockReset()
        mockAcceptMatchMutateAsync.mockReset()

        mockUseMatch.mockReturnValue({
            data: mockMatch,
            isLoading: false,
            error: null,
        })
        mockUseCancelMatch.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseWithdrawMatchCancellation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })

        mockUseSurrogate.mockReturnValue({
            data: mockSurrogate,
            isLoading: false,
        })

        mockUseSurrogateActivity.mockReturnValue({ data: { items: [], total: 0 } })

        mockUseIntendedParent.mockReturnValue({
            data: mockIP,
            isLoading: false,
        })
        mockUseIntendedParentHistory.mockReturnValue({ data: [] })

        mockAcceptMatchMutateAsync.mockResolvedValue(mockMatch)
        mockUseAcceptMatch.mockReturnValue({ mutateAsync: mockAcceptMatchMutateAsync, isPending: false })
        mockUseDeclineMatch.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseCancelMatch.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseWithdrawMatchCancellation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseUpdateMatchNotes.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseTasks.mockReturnValue({ data: { items: [], total: 0 }, isLoading: false })
        mockCreateTaskMutateAsync.mockResolvedValue({})
    })

    it('renders match page tabs', () => {
        render(<MatchDetailPage />)
        expect(screen.getByRole('tab', { name: /overview/i })).toBeInTheDocument()
        expect(screen.getByRole('tab', { name: /calendar/i })).toBeInTheDocument()
    })

    it('shows loading state when match is loading', () => {
        mockUseMatch.mockReturnValue({
            data: null,
            isLoading: true,
            error: null,
        })
        render(<MatchDetailPage />)
        // Should show some loading indicator - check for spinner class or loading text
        const loadingIndicator = document.querySelector('.animate-spin')
        expect(loadingIndicator).toBeTruthy()
    })

    it('renders nothing when the route wrapper should own missing-match handling', () => {
        mockUseMatch.mockReturnValue({
            data: null,
            isLoading: false,
            error: new Error('Not found'),
        })
        const { container } = render(<MatchDetailPage />)
        expect(container).toBeEmptyDOMElement()
    })

    it('shows a permission message when the match detail is forbidden', () => {
        mockUseMatch.mockReturnValue({
            data: null,
            isLoading: false,
            isError: true,
            error: new ApiError(403, 'Forbidden', 'Forbidden'),
            refetch: vi.fn(),
        })

        render(<MatchDetailPage />)

        expect(screen.getByText('Permission required')).toBeInTheDocument()
        expect(screen.getByText(/account does not have permission to view this match/i)).toBeInTheDocument()
        // query-retry never retries a 403, so the denied state offers only the back link.
        expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    })

    it('shows upload button in files tab', () => {
        render(<MatchDetailPage />)
        fireEvent.click(screen.getByRole('tab', { name: /files/i }))
        expect(screen.getByRole('button', { name: /upload file/i })).toBeInTheDocument()
    })

    it('confirms file deletion in an app dialog that names the file', async () => {
        const confirmSpy = vi.spyOn(window, 'confirm')
        mockUseMatchWork.mockReturnValue({
            data: {
                notes: [],
                files: [{ id: 'file-1', filename: 'contract.pdf', file_size: 2048, created_at: '2026-09-05T12:00:00Z', source: 'match', scope: 'case' }],
                tasks: [],
                activity: [],
            },
            isLoading: false,
        })
        render(<MatchDetailPage />)

        fireEvent.click(screen.getByRole('tab', { name: /files/i }))
        fireEvent.click(screen.getByRole('button', { name: 'Delete contract.pdf' }))

        const dialog = await screen.findByRole('alertdialog', { name: 'Delete contract.pdf?' })
        expect(within(dialog).getByRole('button', { name: 'Delete file' })).toBeInTheDocument()
        fireEvent.click(within(dialog).getByRole('button', { name: 'Delete file' }))
        await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
        expect(confirmSpy).not.toHaveBeenCalled()
        confirmSpy.mockRestore()
    })

    it('shows add task button in overview tasks tab', () => {
        render(<MatchDetailPage />)
        fireEvent.click(screen.getByRole('tab', { name: /^tasks$/i }))
        expect(screen.getByRole('button', { name: /add task/i })).toBeInTheDocument()
    })

    it('defaults the add task dialog to match target', () => {
        render(<MatchDetailPage />)
        fireEvent.click(screen.getByRole('tab', { name: /^tasks$/i }))
        fireEvent.click(screen.getByRole('button', { name: /add task/i }))

        expect(screen.getByRole('radio', { name: /match \(both sides\)/i })).toBeChecked()
    })

    it('creates a match-scoped task from the overview tasks tab', async () => {
        render(<MatchDetailPage />)
        fireEvent.click(screen.getByRole('tab', { name: /^tasks$/i }))
        fireEvent.click(screen.getByRole('button', { name: /add task/i }))
        fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'Coordinate next steps' } })
        fireEvent.click(screen.getByRole('button', { name: /create task/i }))

        await waitFor(() =>
            expect(mockCreateTaskMutateAsync).toHaveBeenCalledWith({
                title: 'Coordinate next steps',
                task_type: 'other',
                match_id: 'match1',
                work_source: 'match',
            })
        )
    })

    it('renders dual-linked tasks once with a match badge', () => {
        const dualLinkedTask = {
            id: 'task-match-1',
            title: 'Coordinate next steps',
            due_date: '2026-03-07',
            is_completed: false,
            intended_parent_id: 'ip1',
        }

        mockUseMatchWork.mockReturnValue({ data: { notes: [], files: [], activity: [], tasks: [{ ...dualLinkedTask, source: 'match' }] }, isLoading: false })

        render(<MatchDetailPage />)
        fireEvent.click(screen.getByRole('tab', { name: /^tasks$/i }))

        expect(screen.getAllByText('Coordinate next steps')).toHaveLength(1)
        expect(screen.getByText('Match')).toBeInTheDocument()
    })

    it('loads only the exact case work endpoint and renders a donor participant safely', () => {
        mockUseMatch.mockReturnValue({ data: { ...mockMatch, match_kind: 'donor', surrogate_id: null, surrogate_name: null, donor_id: 'donor1', donor_name: 'Taylor Donor' }, isLoading: false })
        mockUseMatchAttempts.mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() })
        mockUseDonor.mockReturnValue({ data: { id: 'donor1', full_name: 'Taylor Donor', donor_number: 'D10001', email: 'donor@example.com', donor_type: 'egg', status_label: 'Ready' }, isLoading: false })
        render(<MatchDetailPage />)
        expect(mockUseMatchWork).toHaveBeenCalledWith('match1', undefined, 1)
        expect(mockUseSurrogate).toHaveBeenCalledWith('')
        expect(mockUseSurrogateActivity).not.toHaveBeenCalled()
        expect(mockUseIntendedParentHistory).not.toHaveBeenCalled()
        expect(screen.getByRole('heading', { name: 'Donor' })).toBeInTheDocument()
        expect(screen.getByRole('link', { name: 'Taylor Donor' })).toHaveAttribute('href', '/donors/donor1')
        expect(screen.queryByRole('button', { name: 'Parse Schedule' })).not.toBeInTheDocument()
    })

    it('shows a case work failure without presenting an empty history', () => {
        mockUseMatchWork.mockReturnValue({ data: undefined, error: new Error('Forbidden'), isLoading: false, refetch: vi.fn() })
        render(<MatchDetailPage />)
        expect(screen.getByRole('alert')).toHaveTextContent('Unable to load case work')
        expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
    })

    it('records completion outcome through the existing match action area', async () => {
        mockUseMatch.mockReturnValue({ data: { ...mockMatch, status: 'accepted', allowed_actions: ['complete', 'request_cancel'] }, isLoading: false })
        mockCompleteMatchMutateAsync.mockResolvedValue({ ...mockMatch, status: 'completed' })
        render(<MatchDetailPage />)
        fireEvent.click(screen.getByRole('button', { name: 'Complete Match' }))
        fireEvent.change(screen.getByLabelText('Outcome'), { target: { value: 'Relationship completed' } })
        fireEvent.click(screen.getAllByRole('button', { name: 'Complete Match' }).at(-1)!)
        await waitFor(() => expect(mockCompleteMatchMutateAsync).toHaveBeenCalledWith({ matchId: 'match1', data: { outcome: 'Relationship completed' } }))
    })

    it('shows work pagination and requests the next page without changing case identity', () => {
        mockUseMatchWork.mockReturnValue({ data: { notes: [], files: [], tasks: [], activity: [], has_more: true }, isLoading: false })
        render(<MatchDetailPage />)
        fireEvent.click(screen.getByRole('button', { name: 'Next' }))
        expect(mockUseMatchWork).toHaveBeenLastCalledWith('match1', undefined, 2)
    })

    it('keeps note permission denial distinct from an empty notes list', () => {
        mockUseMatchWork.mockReturnValue({ data: { notes: [], files: [], tasks: [], activity: [], can_view_notes: false }, isLoading: false })
        render(<MatchDetailPage />)
        expect(screen.getByText('You do not have permission to view these notes.')).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Add Note' })).not.toBeInTheDocument()
    })

    it('propagates selected attempt to case work and task creation', async () => {
        mockUseMatchAttempts.mockReturnValue({ data: [{ id: 'attempt2', match_id: 'match1', sequence: 2, attempt_type: 'embryo_transfer', status: 'planned', started_at: null, ended_at: null, outcome: null }], isLoading: false })
        render(<MatchDetailPage />)
        fireEvent.click(screen.getByRole('combobox', { name: 'Treatment attempt' }))
        fireEvent.mouseMove(screen.getByRole('option', { name: 'Attempt 2 · Embryo Transfer · Planned' }))
        fireEvent.click(screen.getByRole('option', { name: 'Attempt 2 · Embryo Transfer · Planned' }))
        expect(mockUseMatchWork).toHaveBeenLastCalledWith('match1', 'attempt2', 1)
        fireEvent.click(screen.getByRole('tab', { name: /^tasks$/i }))
        fireEvent.click(screen.getByRole('button', { name: /add task/i }))
        fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'Attempt follow-up' } })
        fireEvent.click(screen.getByRole('button', { name: /create task/i }))
        await waitFor(() => expect(mockCreateTaskMutateAsync).toHaveBeenCalledWith({ title: 'Attempt follow-up', task_type: 'other', match_id: 'match1', work_source: 'match', attempt_id: 'attempt2' }))
    })

    it('keeps a refused concurrent acceptance visible in the confirm dialog', async () => {
        mockAcceptMatchMutateAsync.mockRejectedValue(new ApiError(409, 'Conflict', 'Surrogate has an accepted match'))
        render(<MatchDetailPage />)
        fireEvent.click(screen.getByRole('button', { name: 'Accept Match' }))
        const dialog = await screen.findByRole('alertdialog')
        fireEvent.click(within(dialog).getByRole('button', { name: 'Accept Match' }))
        await waitFor(() => expect(within(dialog).getByRole('alert')).toHaveTextContent('Surrogate has an accepted match'))
        expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    })

    it('confirms acceptance with the stage changes the API applies', async () => {
        mockUseMatch.mockReturnValue({
            data: { ...mockMatch, surrogate_stage_id: 'stage1', surrogate_stage_label: 'Ready to Match' },
            isLoading: false,
        })
        mockUseIntendedParent.mockReturnValue({ data: { ...mockIP, stage_id: 'ipstage1' }, isLoading: false })
        render(<MatchDetailPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Accept Match' }))

        const dialog = await screen.findByRole('alertdialog', { name: 'Accept match M10001?' })
        const changes = within(dialog).getAllByRole('listitem').map((item) => item.textContent)
        expect(changes).toEqual([
            'Surrogate stage: Ready to Match → Matched',
            'Intended parent stage: New → Matched',
            "Other matches under review for this surrogate stay open but can't be accepted.",
        ])
        expect(mockAcceptMatchMutateAsync).not.toHaveBeenCalled()

        fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
        await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
        expect(mockAcceptMatchMutateAsync).not.toHaveBeenCalled()
    })

    it('uses the default variant for Accept and destructive-outline for Decline', () => {
        render(<MatchDetailPage />)
        const accept = screen.getByRole('button', { name: 'Accept Match' })
        const decline = screen.getByRole('button', { name: 'Decline' })
        expect(accept.className).toMatch(/bg-\[linear-gradient/)
        expect(accept).toHaveClass('h-8')
        expect(accept.className).not.toMatch(/bg-green|h-7|text-xs/)
        expect(decline).toHaveClass('border-destructive/40', 'text-destructive', 'h-8')
    })

    it('shows the decline reason on a declined match', () => {
        mockUseMatch.mockReturnValue({
            data: { ...mockMatch, status: 'declined', allowed_actions: [], decline_reason: 'Budget does not align', reviewed_at: '2026-09-05T12:00:00Z' },
            isLoading: false,
        })
        const { container } = render(<MatchDetailPage />)
        const row = container.querySelector('[data-slot="match-decline-reason"]')
        expect(row).not.toBeNull()
        expect(row).toHaveTextContent('Decline reason: Budget does not align')
    })

    it('shows attempt editing to a custom role that holds propose_matches', () => {
        mockUserRole = 'match_coordinator'
        mockPermissions = ['view_matches', 'propose_matches']
        mockUseMatch.mockReturnValue({ data: { ...mockMatch, status: 'accepted', allowed_actions: [] }, isLoading: false })
        render(<MatchDetailPage />)
        expect(screen.getByRole('button', { name: 'Add Attempt' })).toBeInTheDocument()
    })

    it('hides attempt editing from a listed role without propose_matches', () => {
        mockUserRole = 'admin'
        mockPermissions = ['view_matches']
        mockUseMatch.mockReturnValue({ data: { ...mockMatch, status: 'accepted', allowed_actions: [] }, isLoading: false })
        render(<MatchDetailPage />)
        expect(screen.queryByRole('button', { name: 'Add Attempt' })).not.toBeInTheDocument()
    })

    it('links a denied viewer without view_matches to the dashboard', () => {
        mockPermissions = []
        mockUseMatch.mockReturnValue({
            data: null,
            isLoading: false,
            isError: true,
            error: new ApiError(403, 'Forbidden', 'Forbidden'),
            refetch: vi.fn(),
        })
        render(<MatchDetailPage />)
        expect(screen.getByRole('link', { name: 'Go to Dashboard' })).toHaveAttribute('href', '/dashboard')
        expect(screen.queryByRole('link', { name: 'Back to matches' })).not.toBeInTheDocument()
    })

    it('spans case work below the participant cards until xl', () => {
        render(<MatchDetailPage />)
        const caseWork = screen.getByRole('tab', { name: /Activity/ }).closest('[data-slot="tabs"]') as HTMLElement
        const grid = caseWork.parentElement as HTMLElement
        expect(grid).toHaveClass('lg:grid-cols-2')
        expect(grid.className).toContain('xl:grid-cols-[minmax(0,35fr)_minmax(0,35fr)_minmax(0,30fr)]')
        expect(grid.className).not.toMatch(/(^|\s)lg:grid-cols-\[/)
        expect(caseWork).toHaveClass('lg:col-span-2', 'xl:col-span-1')
    })

    describe('match action controls', () => {
        it('renders only the controls the server allows', () => {
            mockUseMatch.mockReturnValue({ data: { ...mockMatch, allowed_actions: ['decline'] }, isLoading: false })
            render(<MatchDetailPage />)
            expect(screen.getByRole('button', { name: 'Decline' })).toBeEnabled()
            for (const name of ['Accept Match', 'Complete Match', 'Cancel Match', 'Withdraw Cancellation']) {
                expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
            }
        })

        it('renders no status controls when the server allows none, regardless of role', () => {
            mockUseMatch.mockReturnValue({ data: { ...mockMatch, allowed_actions: [], blocked_reasons: {} }, isLoading: false })
            render(<MatchDetailPage />)
            expect(screen.queryByRole('button', { name: 'Accept Match' })).not.toBeInTheDocument()
            expect(screen.queryByRole('button', { name: 'Decline' })).not.toBeInTheDocument()
        })

        it('renders a blocked control disabled with the server reason as its description', async () => {
            const reason = 'Surrogate has an accepted match'
            mockUseMatch.mockReturnValue({ data: { ...mockMatch, allowed_actions: ['decline'], blocked_reasons: { accept: reason } }, isLoading: false })
            render(<MatchDetailPage />)
            const accept = screen.getByRole('button', { name: 'Accept Match' })
            expect(accept).toHaveAttribute('aria-disabled', 'true')
            expect(accept).toHaveAccessibleDescription(reason)
            fireEvent.click(accept)
            expect(mockAcceptMatchMutateAsync).not.toHaveBeenCalled()
            fireEvent.focus(accept)
            await waitFor(() => expect(screen.getAllByText(reason)).toHaveLength(2))
        })

        it('renders accept eligibility warnings as a list', () => {
            mockUseMatch.mockReturnValue({ data: { ...mockMatch, accept_eligibility_warnings: ['Surrogate is at Screening, not Ready to Match', 'Intended parent is at New'] }, isLoading: false })
            render(<MatchDetailPage />)
            const list = screen.getByRole('list', { name: 'Accept warnings' })
            expect(list.querySelectorAll('li')).toHaveLength(2)
            expect(list).toHaveTextContent('Surrogate is at Screening, not Ready to Match')
            expect(list).toHaveTextContent('Intended parent is at New')
        })

        it('omits the warning list and conflict badge when absent', () => {
            render(<MatchDetailPage />)
            expect(screen.queryByRole('list', { name: 'Accept warnings' })).not.toBeInTheDocument()
            expect(screen.queryByText('Surrogate has an accepted match')).not.toBeInTheDocument()
        })

        it('flags a surrogate that already has an accepted match', () => {
            mockUseMatch.mockReturnValue({ data: { ...mockMatch, surrogate_has_accepted_match: true }, isLoading: false })
            render(<MatchDetailPage />)
            expect(screen.getByText('Surrogate has an accepted match')).toBeInTheDocument()
        })

        it('shows the pending label and disables sibling controls while an action runs', () => {
            mockUseAcceptMatch.mockReturnValue({ mutateAsync: mockAcceptMatchMutateAsync, isPending: true })
            render(<MatchDetailPage />)
            expect(screen.getByRole('button', { name: 'Accepting...' })).toBeDisabled()
            expect(screen.getByRole('button', { name: 'Decline' })).toBeDisabled()
        })

        it('withdraws the pending cancellation request by its id', async () => {
            const mutateAsync = vi.fn().mockResolvedValue({})
            mockUseWithdrawMatchCancellation.mockReturnValue({ mutateAsync, isPending: false })
            mockUseMatch.mockReturnValue({ data: { ...mockMatch, status: 'cancellation_pending', allowed_actions: ['withdraw_cancel'], pending_cancellation_request_id: 'request1' }, isLoading: false })
            render(<MatchDetailPage />)
            fireEvent.click(screen.getByRole('button', { name: 'Withdraw Cancellation' }))
            await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({ matchId: 'match1', requestId: 'request1' }))
        })

        it('shows the server detail when withdrawal fails', async () => {
            mockUseWithdrawMatchCancellation.mockReturnValue({ mutateAsync: vi.fn().mockRejectedValue(new ApiError(403, 'Forbidden', 'Only the requester can withdraw the cancellation request')), isPending: false })
            mockUseMatch.mockReturnValue({ data: { ...mockMatch, status: 'cancellation_pending', allowed_actions: ['withdraw_cancel'], pending_cancellation_request_id: 'request1' }, isLoading: false })
            render(<MatchDetailPage />)
            fireEvent.click(screen.getByRole('button', { name: 'Withdraw Cancellation' }))
            await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Only the requester can withdraw the cancellation request'))
        })

        it('opens the decline and cancellation reason dialogs from allowed controls', () => {
            mockUseMatch.mockReturnValue({ data: { ...mockMatch, allowed_actions: ['decline'] }, isLoading: false })
            const { unmount } = render(<MatchDetailPage />)
            fireEvent.click(screen.getByRole('button', { name: 'Decline' }))
            expect(screen.getByRole('dialog', { name: 'Decline Match' })).toBeInTheDocument()
            unmount()
            mockUseMatch.mockReturnValue({ data: { ...mockMatch, status: 'accepted', allowed_actions: ['request_cancel'] }, isLoading: false })
            render(<MatchDetailPage />)
            fireEvent.click(screen.getByRole('button', { name: 'Cancel Match' }))
            expect(screen.getByRole('dialog', { name: 'Cancel Match' })).toBeInTheDocument()
        })
    })

    it('displays surrogate name when loaded', () => {
        render(<MatchDetailPage />)
        // Should show surrogate name (full name from match data) - in the header which combines both names
        expect(screen.getAllByText(/Jane Doe/).length).toBeGreaterThan(0)
    })

    it('displays IP name when loaded', () => {
        render(<MatchDetailPage />)
        // Should show IP's name from match data
        expect(screen.getByText('John Smith')).toBeInTheDocument()
    })

    it('displays match status badge', () => {
        render(<MatchDetailPage />)
        expect(screen.getByText('Under Review')).toBeInTheDocument()
    })

    it('renders tabs for Overview and Calendar', () => {
        render(<MatchDetailPage />)
        const tabs = screen.getAllByRole('tab')
        expect(tabs.length).toBeGreaterThanOrEqual(2)
    })

    it('renders the intended parent status label instead of the raw status slug', () => {
        mockUseIntendedParent.mockReturnValue({
            data: {
                ...mockIP,
                status: 'matched',
                status_label: 'Connected',
            },
            isLoading: false,
        })

        render(<MatchDetailPage />)

        expect(screen.getByText('Connected')).toBeInTheDocument()
        expect(screen.queryByText(/^matched$/)).not.toBeInTheDocument()
    })

    it('refreshes source activity and history queries after accepting a match', async () => {
        render(<MatchDetailPage />)

        fireEvent.click(screen.getByRole('button', { name: /accept match/i }))
        const dialog = await screen.findByRole('alertdialog')
        fireEvent.click(within(dialog).getByRole('button', { name: /accept match/i }))

        await waitFor(() =>
            expect(mockAcceptMatchMutateAsync).toHaveBeenCalledWith({ matchId: 'match1' })
        )

        expect(mockInvalidateQueries).toHaveBeenCalledWith({
            queryKey: ['surrogates', 'detail', 'surrogate1', 'activity'],
        })
        expect(mockInvalidateQueries).toHaveBeenCalledWith({
            queryKey: ['surrogates', 'detail', 'surrogate1', 'history'],
        })
        expect(mockInvalidateQueries).toHaveBeenCalledWith({
            queryKey: ['intended-parents', 'history', 'ip1'],
        })
    })
})

describe('MatchDetailPage with different statuses', () => {
    beforeEach(() => {
        mockUseSurrogate.mockReturnValue({
            data: {
                id: 'surrogate1',
                surrogate_number: 'S10001',
                full_name: 'Jane Doe',
                status_label: 'Matched',
                stage_id: 'stage2',
                stage_slug: 'matched',
                stage_type: 'post_approval',
                source: 'manual',
                email: 'jane@example.com',
                phone: '555-1234',
                state: 'CA',
                date_of_birth: '1990-05-15',
                race: null,
                height_ft: null,
                weight_lb: null,
                is_priority: false,
                is_archived: false,
                owner_type: 'user',
                owner_id: 'user1',
                owner_name: 'Test Admin',
                age: null,
                bmi: null,
                created_at: '2024-01-01T00:00:00Z',
                updated_at: '2024-01-15T00:00:00Z',
            },
            isLoading: false,
        })

        mockUseSurrogateActivity.mockReturnValue({ data: { items: [], total: 0 } })

        mockUseIntendedParent.mockReturnValue({
            data: {
                id: 'ip1',
                full_name: 'John Smith',
                email: 'john@example.com',
                status: 'matched',
            },
            isLoading: false,
        })

        mockAcceptMatchMutateAsync.mockResolvedValue({
            id: 'match1',
            surrogate_id: 'surrogate1',
            intended_parent_id: 'ip1',
            status: 'accepted',
        })
        mockUseAcceptMatch.mockReturnValue({ mutateAsync: mockAcceptMatchMutateAsync, isPending: false })
        mockUseDeclineMatch.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseCancelMatch.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseWithdrawMatchCancellation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseUpdateMatchNotes.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    })

    it('shows accepted status badge for accepted matches', () => {
        mockUseMatch.mockReturnValue({
            data: {
                id: 'match1',
                surrogate_id: 'surrogate1',
                ip_id: 'ip1',
                intended_parent_id: 'ip1',
                surrogate_name: 'Jane Doe',
                ip_name: 'John Smith',
                status: 'accepted',
                allowed_actions: [],
                blocked_reasons: {},
                proposed_at: '2024-01-15T10:00:00Z',
                accepted_at: '2024-01-16T10:00:00Z',
            },
            isLoading: false,
            error: null,
        })
        render(<MatchDetailPage />)
        expect(screen.getByText('Accepted')).toBeInTheDocument()
    })

    it('shows declined status badge for declined matches', () => {
        mockUseMatch.mockReturnValue({
            data: {
                id: 'match1',
                surrogate_id: 'surrogate1',
                ip_id: 'ip1',
                intended_parent_id: 'ip1',
                surrogate_name: 'Jane Doe',
                ip_name: 'John Smith',
                status: 'declined',
                allowed_actions: [],
                blocked_reasons: {},
                proposed_at: '2024-01-15T10:00:00Z',
                rejected_at: '2024-01-16T10:00:00Z',
                decline_reason: 'Not compatible',
            },
            isLoading: false,
            error: null,
        })
        render(<MatchDetailPage />)
        expect(screen.getByText('Declined')).toBeInTheDocument()
    })
})
