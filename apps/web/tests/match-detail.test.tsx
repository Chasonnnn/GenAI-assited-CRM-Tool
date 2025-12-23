import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import MatchDetailPage from '../app/(app)/intended-parents/matches/[id]/page'

const mockPush = vi.fn()

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

vi.mock('next/navigation', () => ({
    useParams: () => ({ id: 'match1' }),
    useRouter: () => ({ push: mockPush }),
}))

// Mock auth context
vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({
        user: { role: 'admin', id: 'user1', display_name: 'Test Admin' },
        isLoading: false,
    }),
}))

// Mock react-query
vi.mock('@tanstack/react-query', async () => {
    const actual = await vi.importActual('@tanstack/react-query')
    return {
        ...actual,
        useQueryClient: () => ({
            invalidateQueries: vi.fn(),
        }),
    }
})

// Mock match hooks
const mockUseMatch = vi.fn()
const mockUseAcceptMatch = vi.fn()
const mockUseRejectMatch = vi.fn()
const mockUseCancelMatch = vi.fn()
const mockUseUpdateMatchNotes = vi.fn()

vi.mock('@/lib/hooks/use-matches', () => ({
    useMatch: (id: string) => mockUseMatch(id),
    useAcceptMatch: () => mockUseAcceptMatch(),
    useRejectMatch: () => mockUseRejectMatch(),
    useCancelMatch: () => mockUseCancelMatch(),
    useUpdateMatchNotes: () => mockUseUpdateMatchNotes(),
    matchKeys: { detail: (id: string) => ['matches', 'detail', id] },
}))

// Mock case hooks
const mockUseCase = vi.fn()
vi.mock('@/lib/hooks/use-cases', () => ({
    useCase: (id: string) => mockUseCase(id),
    useChangeStatus: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCaseNotes: () => ({ data: [] }),
    useCaseHistory: () => ({ data: [] }),
    useCaseTasks: () => ({ data: { items: [], total: 0 } }),
    useCaseActivity: () => ({ data: { items: [], total: 0 } }),
    caseKeys: { detail: (id: string) => ['cases', 'detail', id], lists: () => ['cases', 'list'] },
}))

// Mock notes hook
vi.mock('@/lib/hooks/use-notes', () => ({
    useNotes: () => ({ data: [], isLoading: false }),
    useCreateNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

// Mock IP hooks
const mockUseIntendedParent = vi.fn()
vi.mock('@/lib/hooks/use-intended-parents', () => ({
    useIntendedParent: (id: string) => mockUseIntendedParent(id),
    useIntendedParentNotes: () => ({ data: [] }),
    useIntendedParentHistory: () => ({ data: [] }),
    useCreateIntendedParentNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
    intendedParentKeys: { detail: (id: string) => ['intended-parents', 'detail', id], lists: () => ['intended-parents', 'list'], notes: (id: string) => ['intended-parents', 'notes', id] },
}))

// Mock attachments hook
vi.mock('@/lib/hooks/use-attachments', () => ({
    useAttachments: () => ({ data: [], isLoading: false }),
    useIPAttachments: () => ({ data: [], isLoading: false }),
}))

// Mock tasks hook
vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: () => ({ data: { items: [], total: 0 }, isLoading: false }),
}))

// Mock pipelines hook
vi.mock('@/lib/hooks/use-pipelines', () => ({
    useDefaultPipeline: () => ({
        data: {
            id: 'pipeline1',
            stages: [
                { id: 'stage1', slug: 'pending_match', label: 'Pending Match', color: '#888', stage_type: 'intake' },
                { id: 'stage2', slug: 'matched', label: 'Matched', color: '#22c55e', stage_type: 'post_approval' },
                { id: 'stage3', slug: 'meds_started', label: 'Meds Started', color: '#3b82f6', stage_type: 'post_approval' },
            ],
        },
        isLoading: false,
    }),
}))

// Mock tasks
vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: () => ({ data: { items: [], total: 0 }, isLoading: false }),
}))

// Mock toast
vi.mock('@/hooks/use-toast', () => ({
    useToast: () => ({ toast: vi.fn() }),
}))

describe('MatchDetailPage', () => {
    const mockMatch = {
        id: 'match1',
        case_id: 'case1',
        case_name: 'Jane Doe',
        case_number: 'CASE-001',
        ip_id: 'ip1',
        ip_name: 'John Smith',
        status: 'proposed' as const,
        compatibility_score: 85,
        proposed_at: '2024-01-15T10:00:00Z',
        proposed_by_user_id: 'user1',
        proposed_by_name: 'Admin User',
        notes_internal: 'Internal notes about the match',
    }

    const mockCase = {
        id: 'case1',
        case_number: 'CASE-001',
        surrogate_first_name: 'Jane',
        surrogate_last_name: 'Doe',
        surrogate_email: 'jane@example.com',
        surrogate_phone: '555-1234',
        surrogate_dob: '1990-05-15',
        status: 'matched',
        state: 'CA',
        is_archived: false,
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

        mockUseMatch.mockReturnValue({
            data: mockMatch,
            isLoading: false,
            error: null,
        })

        mockUseCase.mockReturnValue({
            data: mockCase,
            isLoading: false,
        })

        mockUseIntendedParent.mockReturnValue({
            data: mockIP,
            isLoading: false,
        })

        mockUseAcceptMatch.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseRejectMatch.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseCancelMatch.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseUpdateMatchNotes.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
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

    it('shows error state when match not found', () => {
        mockUseMatch.mockReturnValue({
            data: null,
            isLoading: false,
            error: new Error('Not found'),
        })
        render(<MatchDetailPage />)
        expect(screen.getByText('Match not found')).toBeInTheDocument()
    })

    it('displays surrogate name when loaded', () => {
        render(<MatchDetailPage />)
        // Should show case name (surrogate's full name from match data) - in the header which combines both names
        expect(screen.getByText(/Jane Doe/)).toBeInTheDocument()
    })

    it('displays IP name when loaded', () => {
        render(<MatchDetailPage />)
        // Should show IP's name from match data
        expect(screen.getByText('John Smith')).toBeInTheDocument()
    })

    it('displays match status badge', () => {
        render(<MatchDetailPage />)
        expect(screen.getByText('Proposed')).toBeInTheDocument()
    })

    it('renders tabs for Overview and Calendar', () => {
        render(<MatchDetailPage />)
        const tabs = screen.getAllByRole('tab')
        expect(tabs.length).toBeGreaterThanOrEqual(2)
    })
})

describe('MatchDetailPage with different statuses', () => {
    beforeEach(() => {
        mockUseCase.mockReturnValue({
            data: {
                id: 'case1',
                case_number: 'CASE-001',
                surrogate_first_name: 'Jane',
                surrogate_last_name: 'Doe',
                surrogate_email: 'jane@example.com',
                status: 'matched',
            },
            isLoading: false,
        })

        mockUseIntendedParent.mockReturnValue({
            data: {
                id: 'ip1',
                full_name: 'John Smith',
                email: 'john@example.com',
                status: 'matched',
            },
            isLoading: false,
        })

        mockUseAcceptMatch.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseRejectMatch.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseCancelMatch.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseUpdateMatchNotes.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    })

    it('shows accepted status badge for accepted matches', () => {
        mockUseMatch.mockReturnValue({
            data: {
                id: 'match1',
                case_id: 'case1',
                ip_id: 'ip1',
                case_name: 'Jane Doe',
                ip_name: 'John Smith',
                status: 'accepted',
                compatibility_score: 90,
                proposed_at: '2024-01-15T10:00:00Z',
                accepted_at: '2024-01-16T10:00:00Z',
            },
            isLoading: false,
            error: null,
        })
        render(<MatchDetailPage />)
        expect(screen.getByText('Accepted')).toBeInTheDocument()
    })

    it('shows rejected status badge for rejected matches', () => {
        mockUseMatch.mockReturnValue({
            data: {
                id: 'match1',
                case_id: 'case1',
                ip_id: 'ip1',
                case_name: 'Jane Doe',
                ip_name: 'John Smith',
                status: 'rejected',
                compatibility_score: 70,
                proposed_at: '2024-01-15T10:00:00Z',
                rejected_at: '2024-01-16T10:00:00Z',
                rejection_reason: 'Not compatible',
            },
            isLoading: false,
            error: null,
        })
        render(<MatchDetailPage />)
        expect(screen.getByText('Rejected')).toBeInTheDocument()
    })
})
