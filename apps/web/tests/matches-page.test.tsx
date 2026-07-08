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

vi.mock('@/lib/hooks/use-matches', () => ({
    useMatches: (filters: unknown) => mockUseMatches(filters),
    useMatchStats: () => ({
        data: { proposed: 1, reviewing: 0, accepted: 1, rejected: 0, cancelled: 0, total: 2 },
        isLoading: false,
    }),
}))

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
                status: 'proposed' as const,
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
        mockRouterReplace.mockReset()
        mockUseMatches.mockReturnValue({
            data: mockMatchData,
            isLoading: false,
        })
    })

    it('renders page header and title', () => {
        render(<MatchesPage />)
        expect(screen.getByText('Matches')).toBeInTheDocument()
    })

    it('renders stats cards', () => {
        render(<MatchesPage />)
        expect(screen.getByText('Total')).toBeInTheDocument()
        // Use getAllByText to handle multiple instances
        expect(screen.getAllByText('Proposed').length).toBeGreaterThan(0)
        expect(screen.getAllByText('Accepted').length).toBeGreaterThan(0)
    })

    it('renders match table with data', () => {
        render(<MatchesPage />)
        // Table headers
        expect(screen.getByText('Surrogate')).toBeInTheDocument()
        expect(screen.getByText('Surrogate #')).toBeInTheDocument()
        expect(screen.getByText('Intended Parents')).toBeInTheDocument()
        expect(screen.queryByText('Compatibility')).not.toBeInTheDocument()
        expect(screen.getByText('Match Stage')).toBeInTheDocument()
        expect(screen.getByText('Surrogate Stage')).toBeInTheDocument()

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

    it('shows empty state when no matches', () => {
        mockUseMatches.mockReturnValue({
            data: { items: [], total: 0, per_page: 20, page: 1 },
            isLoading: false,
        })
        render(<MatchesPage />)
        expect(screen.getByText('No matches found')).toBeInTheDocument()
        expect(screen.getByText('Matches will appear here when surrogates are paired with intended parents')).toBeInTheDocument()
    })

    it('shows a permission message when matches are forbidden', () => {
        mockUseMatches.mockReturnValue({
            data: null,
            isLoading: false,
            isError: true,
            error: new ApiError(403, 'Forbidden', 'Forbidden'),
            refetch: vi.fn(),
        })

        render(<MatchesPage />)

        expect(screen.getByText('Permission required')).toBeInTheDocument()
        expect(screen.getByText(/account does not have permission to view matches/i)).toBeInTheDocument()
        expect(screen.queryByText('Unable to load matches')).not.toBeInTheDocument()
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

        expect(screen.getByPlaceholderText(/search case/i)).toHaveValue('smith')
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
        mockSearchParams.set('status', 'proposed')
        mockSearchParams.set('q', 'old')

        render(<MatchesPage />)

        fireEvent.change(screen.getByPlaceholderText(/search case/i), {
            target: { value: 'alice' },
        })

        expect(mockRouterReplace).not.toHaveBeenCalled()
        act(() => {
            vi.advanceTimersByTime(300)
        })

        expect(mockRouterReplace).toHaveBeenCalledWith(
            '/intended-parents/matches?status=proposed&q=alice',
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
})
