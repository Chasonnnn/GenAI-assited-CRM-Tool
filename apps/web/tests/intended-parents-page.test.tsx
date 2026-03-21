import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import IntendedParentsPage from '../app/(app)/intended-parents/page'

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

const mockSearchParams = new URLSearchParams()
const mockRouterReplace = vi.fn()
const mockCreateIntendedParent = vi.fn()

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
const mockUseIntendedParentCreatedDates = vi.fn()

vi.mock('@/lib/hooks/use-intended-parents', () => ({
    useIntendedParents: (filters: unknown) => mockUseIntendedParents(filters),
    useIntendedParentCreatedDates: (filters: unknown) => mockUseIntendedParentCreatedDates(filters),
    useIntendedParentStats: () => ({
        data: { total: 1, by_status: { new: 1, ready_to_match: 0, matched: 0, delivered: 0 } },
    }),
    useCreateIntendedParent: () => ({ mutateAsync: mockCreateIntendedParent, isPending: false }),
}))

vi.mock('@/lib/hooks/use-metadata', () => ({
    useIntendedParentStatuses: () => ({
        data: {
            statuses: [
                {
                    id: 'stage-new',
                    value: 'new',
                    label: 'New',
                    stage_key: 'new',
                    stage_slug: 'new',
                    stage_type: 'intake',
                    color: '#3B82F6',
                    order: 1,
                },
                {
                    id: 'stage-ready',
                    value: 'ready_to_match',
                    label: 'Ready to Match',
                    stage_key: 'ready_to_match',
                    stage_slug: 'ready_to_match',
                    stage_type: 'post_approval',
                    color: '#F59E0B',
                    order: 2,
                },
                {
                    id: 'stage-matched',
                    value: 'matched',
                    label: 'Matched',
                    stage_key: 'matched',
                    stage_slug: 'matched',
                    stage_type: 'post_approval',
                    color: '#10B981',
                    order: 3,
                },
                {
                    id: 'stage-delivered',
                    value: 'delivered',
                    label: 'Delivered',
                    stage_key: 'delivered',
                    stage_slug: 'delivered',
                    stage_type: 'post_approval',
                    color: '#14B8A6',
                    order: 4,
                },
            ],
        },
    }),
}))

describe('IntendedParentsPage', () => {
    beforeEach(() => {
        mockSearchParams.delete('page')
        mockSearchParams.delete('status')
        mockSearchParams.delete('q')
        mockCreateIntendedParent.mockReset()
        mockCreateIntendedParent.mockResolvedValue({})
        mockUseIntendedParentCreatedDates.mockReturnValue({ data: [] })
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
                        stage_id: 'stage-new',
                        stage_key: 'new',
                        stage_slug: 'new',
                        status_label: 'New',
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

    it('creates an intended parent without requiring address or IVF clinic details', async () => {
        render(<IntendedParentsPage />)

        fireEvent.click(screen.getByRole('button', { name: /new intended parent/i }))

        expect(screen.queryByText(/budget/i)).not.toBeInTheDocument()
        expect(screen.getByLabelText(/partner email/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/partner pronouns/i)).toBeInTheDocument()
        expect(screen.queryByLabelText(/address line 1/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/address line 2/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/^city$/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/zip/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/ivf clinic name/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/ivf clinic email/i)).not.toBeInTheDocument()

        fireEvent.change(screen.getByLabelText(/full name/i), {
            target: { value: 'Jordan and Casey Smith' },
        })
        fireEvent.change(screen.getByLabelText(/^email \*/i), {
            target: { value: 'jordan@example.com' },
        })
        fireEvent.change(screen.getByLabelText(/partner name/i), {
            target: { value: 'Casey Smith' },
        })
        fireEvent.change(screen.getByLabelText(/partner email/i), {
            target: { value: 'casey@example.com' },
        })

        fireEvent.click(screen.getByRole('button', { name: /^create$/i }))

        await waitFor(() => {
            expect(mockCreateIntendedParent).toHaveBeenCalledWith(
                expect.objectContaining({
                    full_name: 'Jordan and Casey Smith',
                    email: 'jordan@example.com',
                    partner_name: 'Casey Smith',
                    partner_email: 'casey@example.com',
                }),
            )
        })

        const payload = mockCreateIntendedParent.mock.calls[0]?.[0]
        expect(payload).not.toHaveProperty('address_line1')
        expect(payload).not.toHaveProperty('address_line2')
        expect(payload).not.toHaveProperty('city')
        expect(payload).not.toHaveProperty('postal')
        expect(payload).not.toHaveProperty('ip_clinic_name')
        expect(payload).not.toHaveProperty('ip_clinic_email')
    })
})
