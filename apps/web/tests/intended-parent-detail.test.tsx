import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import IntendedParentDetailPage from '../app/(app)/intended-parents/[id]/page'

const mockPush = vi.fn()

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

vi.mock('next/navigation', () => ({
    useParams: () => ({ id: 'ip1' }),
    useRouter: () => ({ push: mockPush }),
}))

const mockUseIntendedParent = vi.fn()

vi.mock('@/lib/hooks/use-intended-parents', () => ({
    useIntendedParent: (id: string) => mockUseIntendedParent(id),
    useIntendedParentHistory: () => ({ data: [] }),
    useIntendedParentNotes: () => ({ data: [] }),
    useUpdateIntendedParent: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateIntendedParentStatus: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useArchiveIntendedParent: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRestoreIntendedParent: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteIntendedParent: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCreateIntendedParentNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteIntendedParentNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('IntendedParentDetailPage', () => {
    beforeEach(() => {
        mockUseIntendedParent.mockReturnValue({
            data: {
                id: 'ip1',
                full_name: 'Bob Parent',
                email: 'bob@example.com',
                phone: null,
                state: 'CA',
                budget: 50000,
                notes_internal: null,
                status: 'new',
                assigned_to_user_id: null,
                assigned_to_name: null,
                is_archived: false,
                archived_at: null,
                last_activity: new Date().toISOString(),
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
            isLoading: false,
            error: null,
        })
    })

    it('renders primary details', () => {
        render(<IntendedParentDetailPage />)
        expect(screen.getByText('Bob Parent')).toBeInTheDocument()
        expect(screen.getAllByText('bob@example.com').length).toBeGreaterThan(0)
    })
})
