import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import IntendedParentsPage from '../app/(app)/intended-parents/page'
import { ApiError } from '@/lib/api'

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
const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()
const mockToastError = vi.fn()
const mockToastSuccess = vi.fn()

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock('@/lib/hooks/use-permissions', () => ({
    useEffectivePermissions: (userId: string | null) => mockUseEffectivePermissions(userId),
}))

vi.mock('@/components/ui/toast', () => ({
    toast: {
        error: (...args: unknown[]) => mockToastError(...args),
        success: (...args: unknown[]) => mockToastSuccess(...args),
    },
}))

function setPermissions(permissions: string[]) {
    mockUseEffectivePermissions.mockReturnValue({ data: { permissions }, isLoading: false, isError: false })
}

const emptyList = { data: { items: [], total: 0, per_page: 20, page: 1 }, isLoading: false }

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
        mockSearchParams.delete('range')
        mockSearchParams.delete('from')
        mockSearchParams.delete('to')
        mockRouterReplace.mockReset()
        mockCreateIntendedParent.mockReset()
        mockCreateIntendedParent.mockResolvedValue({})
        mockToastError.mockReset()
        mockToastSuccess.mockReset()
        mockUseIntendedParents.mockClear()
        mockUseAuth.mockReturnValue({ user: { user_id: 'user-1', role: 'case_manager' }, isLoading: false })
        setPermissions(['view_intended_parents', 'edit_intended_parents'])
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

    it('renders the header count, toolbar and a list row without stat cards', () => {
        render(<IntendedParentsPage />)
        expect(screen.getByRole('heading', { level: 1, name: 'Intended Parents' })).toBeInTheDocument()
        expect(document.querySelector('[data-slot="page-header-count"]')).toHaveTextContent('1')
        expect(screen.queryByText('Total')).not.toBeInTheDocument()
        expect(screen.getByText('Bob Parent')).toBeInTheDocument()
        expect(screen.getByText('bob@example.com')).toBeInTheDocument()
        expect(screen.getByRole('columnheader', { name: 'Stage' })).toBeInTheDocument()
        expect(screen.queryByRole('columnheader', { name: 'Status' })).not.toBeInTheDocument()
        const stage = screen.getByRole('combobox', { name: 'Filter by stage' })
        const date = screen.getByTestId('date-range-picker')
        const search = screen.getByRole('textbox', { name: 'Search intended parents' })
        expect(stage).toHaveTextContent('All Stages')
        expect(stage.compareDocumentPosition(date) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
        expect(date.compareDocumentPosition(search) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })

    it('gates the page on view_intended_parents before loading the list', () => {
        mockUseAuth.mockReturnValue({ user: { user_id: 'intake-1', role: 'intake_specialist' }, isLoading: false })
        setPermissions(['view_surrogates'])
        render(<IntendedParentsPage />)

        expect(screen.getByRole('heading', { level: 1, name: 'Intended Parents' })).toBeInTheDocument()
        expect(screen.getByRole('heading', { level: 2, name: 'Permission required' })).toBeInTheDocument()
        expect(screen.getByRole('link', { name: 'Go to Dashboard' })).toHaveAttribute('href', '/dashboard')
        expect(screen.queryByRole('button', { name: /new intended parent/i })).not.toBeInTheDocument()
        expect(screen.queryByRole('combobox', { name: 'Filter by stage' })).not.toBeInTheDocument()
        expect(mockUseIntendedParents).not.toHaveBeenCalled()
    })

    it('hides New Intended Parent without edit_intended_parents', () => {
        setPermissions(['view_intended_parents'])
        render(<IntendedParentsPage />)
        expect(screen.getByText('Bob Parent')).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: /new intended parent/i })).not.toBeInTheDocument()
    })

    it('shows filter chips with stage labels and resets them', () => {
        mockSearchParams.set('status', 'ready_to_match')
        mockSearchParams.set('q', 'smith')
        mockSearchParams.set('range', 'month')
        render(<IntendedParentsPage />)

        expect(document.querySelector('[data-slot="page-header-count"]')).toHaveTextContent('1')
        expect(screen.getByRole('button', { name: 'Remove filter: Stage: Ready to Match' })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Remove filter: Date: This Month' })).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Remove filter: Search: smith' }))
        expect(mockRouterReplace).toHaveBeenLastCalledWith(
            '/intended-parents?status=ready_to_match&range=month',
            { scroll: false },
        )

        fireEvent.click(screen.getByRole('button', { name: 'Reset' }))
        expect(mockRouterReplace).toHaveBeenLastCalledWith('/intended-parents', { scroll: false })
    })

    it('shows the first-run empty state with a create action', () => {
        mockUseIntendedParents.mockReturnValue(emptyList)
        render(<IntendedParentsPage />)
        expect(screen.getByRole('heading', { level: 2, name: 'No intended parents yet' })).toBeInTheDocument()
        expect(screen.getAllByRole('button', { name: 'New Intended Parent' })).toHaveLength(2)
    })

    it('shows the filtered empty state with Clear filters', () => {
        mockSearchParams.set('q', 'nobody')
        mockUseIntendedParents.mockReturnValue(emptyList)
        render(<IntendedParentsPage />)
        expect(screen.getByRole('heading', { level: 2, name: 'No intended parents found' })).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
        expect(mockRouterReplace).toHaveBeenLastCalledWith('/intended-parents', { scroll: false })
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

    it('derives committed filters from URL params', () => {
        mockSearchParams.set('page', '3')
        mockSearchParams.set('status', 'ready_to_match')
        mockSearchParams.set('q', 'smith')
        mockSearchParams.set('range', 'custom')
        mockSearchParams.set('from', '2026-02-01')
        mockSearchParams.set('to', '2026-02-14')

        render(<IntendedParentsPage />)

        expect(screen.getByPlaceholderText('Search intended parents')).toHaveValue('smith')
        expect(mockUseIntendedParents).toHaveBeenCalledWith(
            expect.objectContaining({
                page: 3,
                q: 'smith',
                status: ['ready_to_match'],
                created_after: '2026-02-01',
                created_before: '2026-02-14',
            })
        )
    })

    it('debounces search URL updates while preserving sibling filters and resetting page', () => {
        vi.useFakeTimers()
        mockSearchParams.set('page', '4')
        mockSearchParams.set('status', 'new')
        mockSearchParams.set('q', 'old')
        mockSearchParams.set('range', 'month')

        render(<IntendedParentsPage />)

        fireEvent.change(screen.getByPlaceholderText('Search intended parents'), {
            target: { value: 'alice' },
        })

        expect(mockRouterReplace).not.toHaveBeenCalled()
        act(() => {
            vi.advanceTimersByTime(300)
        })

        expect(mockRouterReplace).toHaveBeenCalledWith(
            '/intended-parents?status=new&q=alice&range=month',
            { scroll: false },
        )
        vi.useRealTimers()
    })

    it('shows a permission message when the intended parent list is forbidden', () => {
        mockUseIntendedParents.mockReturnValue({
            data: null,
            isLoading: false,
            isError: true,
            error: new ApiError(403, 'Forbidden', 'Forbidden'),
            refetch: vi.fn(),
        })

        render(<IntendedParentsPage />)

        expect(screen.getByText('Permission required')).toBeInTheDocument()
        expect(screen.getByText(/Intended Parents need the View Intended Parents permission/)).toBeInTheDocument()
        expect(screen.queryByText("Couldn't load intended parents")).not.toBeInTheDocument()
    })

    function openCreateDialog() {
        render(<IntendedParentsPage />)
        fireEvent.click(screen.getByRole('button', { name: /new intended parent/i }))
        fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Jordan Smith' } })
    }

    it('validates email inline before calling the API', async () => {
        openCreateDialog()
        const email = screen.getByLabelText(/^email \*/i)
        fireEvent.change(email, { target: { value: 'jordan-at-example' } })
        fireEvent.click(screen.getByRole('button', { name: /^create$/i }))

        expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument()
        expect(email).toHaveAttribute('aria-invalid', 'true')
        expect(mockCreateIntendedParent).not.toHaveBeenCalled()
        expect(mockToastError).not.toHaveBeenCalled()
    })

    it('maps a 422 email error to the field instead of a raw toast', async () => {
        mockCreateIntendedParent.mockRejectedValue(
            new ApiError(422, 'Unprocessable Entity', 'email: value is not a valid email address', [
                { path: 'email', message: 'value is not a valid email address: An email address must have an @-sign.' },
            ]),
        )
        openCreateDialog()
        fireEvent.change(screen.getByLabelText(/^email \*/i), { target: { value: 'jordan@example.test' } })
        fireEvent.click(screen.getByRole('button', { name: /^create$/i }))

        expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument()
        expect(screen.getByLabelText(/^email \*/i)).toHaveAttribute('aria-invalid', 'true')
        expect(mockToastError).not.toHaveBeenCalled()
    })

    it('shows a sanitized toast when create fails on the server', async () => {
        mockCreateIntendedParent.mockRejectedValue(new ApiError(500, 'Internal Server Error'))
        openCreateDialog()
        fireEvent.change(screen.getByLabelText(/^email \*/i), { target: { value: 'jordan@example.com' } })
        fireEvent.click(screen.getByRole('button', { name: /^create$/i }))

        await waitFor(() => {
            expect(mockToastError).toHaveBeenCalledWith("Couldn't create intended parent. Try again.")
        })
        expect(screen.getByRole('dialog', { name: 'New Intended Parent' })).toBeInTheDocument()
    })

    it('creates an intended parent without requiring address or IVF clinic details', async () => {
        render(<IntendedParentsPage />)

        fireEvent.click(screen.getByRole('button', { name: /new intended parent/i }))

        expect(screen.queryByText(/budget/i)).not.toBeInTheDocument()
        expect(screen.getByLabelText(/partner email/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/partner pronouns/i)).toBeInTheDocument()
        expect(screen.queryByLabelText(/date of birth/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/marital status/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/number of embryos/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/pgs tested/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/egg source/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/sperm source/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/trust info/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/trust provider/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/primary contact/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/funding status/i)).not.toBeInTheDocument()
        expect(screen.queryByLabelText(/portal url/i)).not.toBeInTheDocument()
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
        expect(payload).not.toHaveProperty('date_of_birth')
        expect(payload).not.toHaveProperty('partner_date_of_birth')
        expect(payload).not.toHaveProperty('marital_status')
        expect(payload).not.toHaveProperty('embryo_count')
        expect(payload).not.toHaveProperty('pgs_tested')
        expect(payload).not.toHaveProperty('egg_source')
        expect(payload).not.toHaveProperty('sperm_source')
        expect(payload).not.toHaveProperty('trust_provider_name')
        expect(payload).not.toHaveProperty('trust_primary_contact_name')
        expect(payload).not.toHaveProperty('trust_email')
        expect(payload).not.toHaveProperty('trust_phone')
        expect(payload).not.toHaveProperty('trust_address_line1')
        expect(payload).not.toHaveProperty('trust_address_line2')
        expect(payload).not.toHaveProperty('trust_city')
        expect(payload).not.toHaveProperty('trust_state')
        expect(payload).not.toHaveProperty('trust_postal')
        expect(payload).not.toHaveProperty('trust_case_reference')
        expect(payload).not.toHaveProperty('trust_funding_status')
        expect(payload).not.toHaveProperty('trust_portal_url')
        expect(payload).not.toHaveProperty('trust_notes')
    })
})
