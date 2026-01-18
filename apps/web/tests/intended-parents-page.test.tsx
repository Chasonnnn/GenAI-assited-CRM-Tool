import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import IntendedParentsPage from '../app/(app)/intended-parents/page'

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

const mockSearchParams = new URLSearchParams()
const mockRouterReplace = vi.fn()

// Mock Next.js navigation
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

vi.mock('@/components/ui/date-range-picker', () => ({
    DateRangePicker: () => <div data-testid="date-range-picker" />,
}))

const mockUseIntendedParents = vi.fn()

vi.mock('@/lib/hooks/use-intended-parents', () => ({
    useIntendedParents: (filters: unknown) => mockUseIntendedParents(filters),
    useIntendedParentStats: () => ({
        data: { total: 1, by_status: { new: 1, ready_to_match: 0, matched: 0, delivered: 0 } },
    }),
    useCreateIntendedParent: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('IntendedParentsPage', () => {
    beforeEach(() => {
        mockSearchParams.delete('page')
        mockSearchParams.delete('status')
        mockSearchParams.delete('q')
        mockUseIntendedParents.mockReturnValue({
            data: {
                items: [
                    {
                        id: 'ip1',
                        full_name: 'Bob Parent',
                        email: 'bob@example.com',
                        phone: null,
                        state: 'CA',
                        budget: 50000,
                        status: 'new',
                        owner_type: null,
                        owner_id: null,
                        owner_name: null,
                        is_archived: false,
                        created_at: new Date().toISOString(),
                        updated_at: new Date().toISOString(),
                    },
                ],
                total: 1,
                per_page: 20,
                page: 1,
            },
            isLoading: false,
        })
    })

    it('renders stats and a list row', () => {
        render(<IntendedParentsPage />)
        expect(screen.getByText('Intended Parents')).toBeInTheDocument()
        expect(screen.getByText('Bob Parent')).toBeInTheDocument()
        expect(screen.getByText('bob@example.com')).toBeInTheDocument()
    })

    it('uses page from URL params', () => {
        mockSearchParams.set('page', '4')
        mockUseIntendedParents.mockReturnValue({
            data: {
                items: [],
                total: 0,
                per_page: 20,
                page: 4,
            },
            isLoading: false,
        })

        render(<IntendedParentsPage />)
        expect(mockUseIntendedParents).toHaveBeenCalledWith(
            expect.objectContaining({
                page: 4,
            })
        )
    })
})
