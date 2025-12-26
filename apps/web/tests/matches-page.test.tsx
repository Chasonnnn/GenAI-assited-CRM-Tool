import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import MatchesPage from '../app/(app)/intended-parents/matches/page'

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
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
            },
            {
                id: 'match2',
                case_id: 'case2',
                case_name: 'Mary Johnson',
                case_number: 'CASE-002',
                ip_id: 'ip2',
                ip_name: 'Bob Williams',
                status: 'accepted' as const,
                compatibility_score: 92,
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
        expect(screen.getByText('Case #')).toBeInTheDocument()
        expect(screen.getByText('Intended Parents')).toBeInTheDocument()
        expect(screen.getByText('Compatibility')).toBeInTheDocument()
        expect(screen.getByText('Match Stage')).toBeInTheDocument()
        expect(screen.getByText('Case Stage')).toBeInTheDocument()

        // Match data
        expect(screen.getByText('Jane Doe')).toBeInTheDocument()
        expect(screen.getByText('CASE-001')).toBeInTheDocument()
        expect(screen.getByText('John Smith')).toBeInTheDocument()
        expect(screen.getByText('85%')).toBeInTheDocument()

        expect(screen.getByText('Mary Johnson')).toBeInTheDocument()
        expect(screen.getByText('CASE-002')).toBeInTheDocument()
        expect(screen.getByText('Bob Williams')).toBeInTheDocument()
        expect(screen.getByText('92%')).toBeInTheDocument()
    })

    it('shows loading state', () => {
        mockUseMatches.mockReturnValue({
            data: null,
            isLoading: true,
        })
        render(<MatchesPage />)
        expect(screen.getByText('Loading...')).toBeInTheDocument()
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
        })
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
