import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import MatchesPage from '../app/(app)/intended-parents/matches/page'
import { ApiError } from '@/lib/api'

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

const mockSearchParams = new URLSearchParams()
const mockRouterReplace = vi.fn()

vi.mock('next/navigation', () => ({
    useSearchParams: () => ({
        get: (key: string) => mockSearchParams.get(key),
        toString: () => mockSearchParams.toString(),
    }),
    useRouter: () => ({
        push: vi.fn(),
        replace: mockRouterReplace,
    }),
}))

const mockUseMatches = vi.fn()
const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()

vi.mock('@/lib/hooks/use-matches', () => ({
    useMatches: (filters: unknown) => mockUseMatches(filters),
    useMatchStats: () => ({
        data: {
            total: 42,
            by_status: { under_review: 17, accepted: 8, cancellation_pending: 1, declined: 9, cancelled: 4, completed: 3 },
        },
        isLoading: false,
    }),
    useCreateMatch: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock('@/lib/hooks/use-permissions', () => ({
    useEffectivePermissions: (userId: string | null) => mockUseEffectivePermissions(userId),
}))

function setPermissions(permissions: string[], policyVersion?: number) {
    mockUseEffectivePermissions.mockReturnValue({
        data: { permissions, ...(policyVersion ? { policy_version: policyVersion } : {}) },
        isLoading: false,
        isError: false,
    })
}

const emptyMatches = { data: { items: [], total: 0, per_page: 20, page: 1 }, isLoading: false }

describe('MatchesPage', () => {
    const mockMatchData = {
        items: [
            {
                id: 'match1',
                match_number: 'M10001',
                surrogate_id: 'surrogate1',
                surrogate_name: 'Jane Doe',
                surrogate_number: 'S10001',
                ip_id: 'ip1',
                ip_name: 'John Smith',
                status: 'under_review' as const,
                proposed_at: '2024-01-15T10:00:00Z',
                proposed_by_user_id: 'user1',
                proposed_by_name: 'Admin User',
            },
            {
                id: 'match2',
                match_number: 'M10002',
                surrogate_id: 'surrogate2',
                surrogate_name: 'Mary Johnson',
                surrogate_number: 'S10002',
                ip_id: 'ip2',
                ip_name: 'Bob Williams',
                status: 'accepted' as const,
                proposed_at: '2024-01-10T14:00:00Z',
                proposed_by_user_id: 'user1',
                proposed_by_name: 'Admin User',
                accepted_at: '2024-01-12T09:00:00Z',
            },
        ],
        total: 2,
        per_page: 20,
        page: 1,
    }

    beforeEach(() => {
        vi.clearAllMocks()
        mockSearchParams.delete('page')
        mockSearchParams.delete('status')
        mockSearchParams.delete('q')
        mockSearchParams.delete('match_kind')
        mockSearchParams.delete('range')
        mockSearchParams.delete('from')
        mockSearchParams.delete('to')
        mockRouterReplace.mockReset()
        mockUseAuth.mockReturnValue({ user: { user_id: 'user-1', role: 'case_manager' }, isLoading: false })
        setPermissions(['view_matches', 'propose_matches'])
        mockUseMatches.mockReturnValue({
            data: mockMatchData,
            isLoading: false,
        })
    })

    it.each(['pending_legacy', 'constructor'])('labels the filter and preserves unknown status %s', (unknownStatus) => {
        mockUseMatches.mockReturnValue({data: {...mockMatchData, items: [{...mockMatchData.items[0], status: unknownStatus}]}, isLoading: false})
        render(<MatchesPage />)
        expect(screen.getByRole('combobox', { name: 'Filter by stage' })).toHaveTextContent('All Stages')
        expect(screen.getByText(unknownStatus)).toBeInTheDocument()
        expect(screen.queryByText('Under Review')).not.toBeInTheDocument()
    })

    it('renders page header and title', () => {
        render(<MatchesPage />)
        expect(screen.getByRole('heading', { level: 1, name: 'Matches' })).toBeInTheDocument()
    })

    it('shows the count in the header instead of stat cards', () => {
        render(<MatchesPage />)
        expect(document.querySelector('[data-slot="page-header-count"]')).toHaveTextContent('2')
        expect(screen.queryByText('Total')).not.toBeInTheDocument()
    })

    it('shows filtered and unfiltered counts when a filter is active', () => {
        mockSearchParams.set('status', 'accepted')
        render(<MatchesPage />)
        expect(document.querySelector('[data-slot="page-header-count"]')).toHaveTextContent('2 of 42')
    })

    it('orders the toolbar Stage, Date, More Filters, then search', () => {
        render(<MatchesPage />)
        const stage = screen.getByRole('combobox', { name: 'Filter by stage' })
        const date = screen.getByRole('button', { name: 'Proposed date range' })
        const more = screen.getByRole('button', { name: 'More Filters' })
        const search = screen.getByRole('textbox', { name: 'Search matches' })
        expect(stage).toHaveTextContent('All Stages')
        expect(stage.compareDocumentPosition(date) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
        expect(date.compareDocumentPosition(more) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
        expect(more.compareDocumentPosition(search) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
        expect(search).toHaveAttribute('placeholder', 'Search matches')
    })

    it('shows New Match only with propose_matches', () => {
        const { unmount } = render(<MatchesPage />)
        expect(screen.getByRole('button', { name: 'New Match' })).toBeInTheDocument()
        unmount()

        setPermissions(['view_matches'])
        render(<MatchesPage />)
        expect(screen.queryByRole('button', { name: 'New Match' })).not.toBeInTheDocument()
    })

    it('also requires view_intended_parents for New Match under policy v2', () => {
        setPermissions(['view_matches', 'propose_matches'], 2)
        const { unmount } = render(<MatchesPage />)
        expect(screen.queryByRole('button', { name: 'New Match' })).not.toBeInTheDocument()
        unmount()

        setPermissions(['view_matches', 'propose_matches', 'view_intended_parents'], 2)
        render(<MatchesPage />)
        expect(screen.getByRole('button', { name: 'New Match' })).toBeInTheDocument()
    })

    it('gates the page on view_matches before loading matches', () => {
        mockUseAuth.mockReturnValue({ user: { user_id: 'intake-1', role: 'intake_specialist' }, isLoading: false })
        setPermissions([])
        render(<MatchesPage />)

        expect(screen.getByRole('heading', { level: 1, name: 'Matches' })).toBeInTheDocument()
        expect(screen.getByRole('heading', { level: 2, name: 'Permission required' })).toBeInTheDocument()
        expect(screen.getByRole('link', { name: 'Go to Dashboard' })).toHaveAttribute('href', '/dashboard')
        expect(screen.queryByRole('button', { name: 'New Match' })).not.toBeInTheDocument()
        expect(screen.queryByRole('textbox', { name: 'Search matches' })).not.toBeInTheDocument()
        expect(mockUseMatches).not.toHaveBeenCalled()
    })

    it('renders chips through the label helpers and resets every filter', () => {
        mockSearchParams.set('status', 'accepted')
        mockSearchParams.set('match_kind', 'donor')
        mockSearchParams.set('q', 'smith')
        mockSearchParams.set('page', '2')
        render(<MatchesPage />)

        expect(screen.getByRole('button', { name: 'Remove filter: Stage: Accepted' })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Remove filter: Kind: Donor' })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Remove filter: Search: smith' })).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: 'Remove filter: Kind: Donor' }))
        expect(mockRouterReplace).toHaveBeenLastCalledWith(
            '/intended-parents/matches?status=accepted&q=smith',
            { scroll: false },
        )

        fireEvent.click(screen.getByRole('button', { name: 'Reset' }))
        expect(mockRouterReplace).toHaveBeenLastCalledWith('/intended-parents/matches', { scroll: false })
    })

    it('sends a custom proposed date range and shows it as a chip', () => {
        mockSearchParams.set('range', 'custom')
        mockSearchParams.set('from', '2026-09-01')
        mockSearchParams.set('to', '2026-09-26')
        render(<MatchesPage />)

        expect(mockUseMatches).toHaveBeenCalledWith(
            expect.objectContaining({ proposed_from: '2026-09-01', proposed_to: '2026-09-26' })
        )
        expect(
            screen.getByRole('button', { name: 'Remove filter: Proposed: Sep 1, 2026 - Sep 26, 2026' })
        ).toBeInTheDocument()
    })

    it('moves Kind into More Filters', async () => {
        render(<MatchesPage />)
        expect(screen.queryByRole('combobox', { name: 'Filter by kind' })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: 'More Filters' }))
        const kind = await screen.findByRole('combobox', { name: 'Filter by kind' })
        expect(kind).toHaveTextContent('All Kinds')
    })

    it('renders match table with data', () => {
        render(<MatchesPage />)
        // Table headers
        expect(screen.getByText('Participant')).toBeInTheDocument()
        expect(screen.getByText('Participant #')).toBeInTheDocument()
        expect(screen.getByText('Intended Parents')).toBeInTheDocument()
        expect(screen.queryByText('Compatibility')).not.toBeInTheDocument()
        expect(screen.getByText('Match Stage')).toBeInTheDocument()
        expect(screen.getByText('Participant Stage')).toBeInTheDocument()

        // Match data
        expect(screen.getByText('Jane Doe')).toBeInTheDocument()
        expect(screen.getByText('S10001')).toBeInTheDocument()
        expect(screen.getByText('John Smith')).toBeInTheDocument()

        expect(screen.getByText('Mary Johnson')).toBeInTheDocument()
        expect(screen.getByText('S10002')).toBeInTheDocument()
        expect(screen.getByText('Bob Williams')).toBeInTheDocument()
    })

    it('shows loading state', () => {
        mockUseMatches.mockReturnValue({
            data: null,
            isLoading: true,
        })
        render(<MatchesPage />)
        expect(screen.getByText('Loading…')).toBeInTheDocument()
    })

    it('shows the first-run empty state when no filter is active', () => {
        mockUseMatches.mockReturnValue(emptyMatches)
        render(<MatchesPage />)
        expect(screen.getByRole('heading', { level: 2, name: 'No matches yet' })).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Clear filters' })).not.toBeInTheDocument()
    })

    it.each([
        ['stage', 'status', 'accepted'],
        ['kind', 'match_kind', 'donor'],
        ['search', 'q', 'nobody'],
        ['proposed date', 'range', 'month'],
    ])('shows the filtered empty state with Clear filters for the %s filter', (_label, param, value) => {
        mockSearchParams.set(param, value)
        mockUseMatches.mockReturnValue(emptyMatches)
        render(<MatchesPage />)

        expect(screen.getByRole('heading', { level: 2, name: 'No matches found' })).toBeInTheDocument()
        expect(screen.queryByText('No matches yet')).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
        expect(mockRouterReplace).toHaveBeenLastCalledWith('/intended-parents/matches', { scroll: false })
    })

    it('shows the permission state when the list API returns 403', () => {
        mockUseMatches.mockReturnValue({
            data: null,
            isLoading: false,
            isError: true,
            error: new ApiError(403, 'Forbidden', 'Forbidden'),
            refetch: vi.fn(),
        })

        render(<MatchesPage />)

        expect(screen.getByText('Permission required')).toBeInTheDocument()
        expect(screen.getByText(/Matches need the View Matches permission/)).toBeInTheDocument()
        expect(screen.queryByText("Couldn't load matches")).not.toBeInTheDocument()
    })

    it('shows a retryable error without the raw message on other failures', () => {
        const refetch = vi.fn()
        mockUseMatches.mockReturnValue({
            data: null,
            isLoading: false,
            isError: true,
            error: new ApiError(500, 'Internal Server Error', 'boom'),
            refetch,
        })

        render(<MatchesPage />)

        expect(screen.getByRole('heading', { level: 2, name: "Couldn't load matches" })).toBeInTheDocument()
        expect(screen.queryByText('boom')).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
        expect(refetch).toHaveBeenCalled()
    })

    it('links match names to detail pages', () => {
        render(<MatchesPage />)
        const janeLink = screen.getByText('Jane Doe').closest('a')
        expect(janeLink).toHaveAttribute('href', '/intended-parents/matches/match1')

        const maryLink = screen.getByText('Mary Johnson').closest('a')
        expect(maryLink).toHaveAttribute('href', '/intended-parents/matches/match2')
    })

    it('calls useMatches with correct filter params', () => {
        render(<MatchesPage />)
        expect(mockUseMatches).toHaveBeenCalledWith({
            status: undefined,
            page: 1,
            per_page: 20,
            sort_by: 'match_number',
            sort_order: 'desc',
        })
    })

    it('uses page from URL params', () => {
        mockSearchParams.set('page', '2')
        mockUseMatches.mockReturnValue({
            data: { items: [], total: 0, per_page: 20, page: 2 },
            isLoading: false,
        })

        render(<MatchesPage />)
        expect(mockUseMatches).toHaveBeenCalledWith(
            expect.objectContaining({
                page: 2,
            })
        )
    })

    it('derives committed filters from URL params', () => {
        mockSearchParams.set('page', '3')
        mockSearchParams.set('status', 'accepted')
        mockSearchParams.set('q', 'smith')

        render(<MatchesPage />)

        expect(screen.getByPlaceholderText(/search match/i)).toHaveValue('smith')
        expect(mockUseMatches).toHaveBeenCalledWith(
            expect.objectContaining({
                page: 3,
                status: 'accepted',
                q: 'smith',
            })
        )
    })

    it('debounces search URL updates while preserving sibling filters and resetting page', () => {
        vi.useFakeTimers()
        mockSearchParams.set('page', '4')
        mockSearchParams.set('status', 'under_review')
        mockSearchParams.set('q', 'old')

        render(<MatchesPage />)

        fireEvent.change(screen.getByPlaceholderText(/search match/i), {
            target: { value: 'alice' },
        })

        expect(mockRouterReplace).not.toHaveBeenCalled()
        act(() => {
            vi.advanceTimersByTime(300)
        })

        expect(mockRouterReplace).toHaveBeenCalledWith(
            '/intended-parents/matches?status=under_review&q=alice',
            { scroll: false },
        )
        vi.useRealTimers()
    })

    it('shows pagination when needed', () => {
        mockUseMatches.mockReturnValue({
            data: {
                items: mockMatchData.items,
                total: 50,
                per_page: 20,
                page: 1,
            },
            isLoading: false,
        })
        render(<MatchesPage />)
        expect(screen.getByText('Showing 1 to 20 of 50')).toBeInTheDocument()
    })

    it('hides pagination when not needed', () => {
        render(<MatchesPage />)
        expect(screen.queryByText(/Showing/)).not.toBeInTheDocument()
    })
    it('renders donor cases without surrogate fields and restores the kind filter from URL', () => {
        mockSearchParams.set('match_kind', 'donor')
        mockUseMatches.mockReturnValue({ data: { ...mockMatchData, items: [{ ...mockMatchData.items[0], match_kind: 'donor', donor_id: 'donor1', donor_name: 'Taylor Donor', donor_number: 'D10001', donor_stage_label: 'Ready', surrogate_id: null, surrogate_name: null, surrogate_number: null, status: 'completed' }] }, isLoading: false })
        render(<MatchesPage />)
        expect(mockUseMatches).toHaveBeenCalledWith(expect.objectContaining({ match_kind: 'donor' }))
        expect(screen.getByText('Taylor Donor')).toBeInTheDocument()
        expect(screen.getByText('D10001')).toBeInTheDocument()
        expect(screen.getByText('Completed')).toBeInTheDocument()
        expect(screen.getByText('Ready')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Remove filter: Kind: Donor' })).toBeInTheDocument()
    })

})
