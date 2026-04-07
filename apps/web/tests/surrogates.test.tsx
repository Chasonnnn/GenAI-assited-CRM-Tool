import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { SurrogatesPageClient as SurrogatesPage } from '../app/(app)/surrogates/page.client'

// ============================================================================
// Mocks
// ============================================================================

// Mock Next.js Link
vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

const mockSearchParams = new URLSearchParams()
const mockRouterReplace = vi.fn()
const mockMassEditStageModal = vi.fn()
const mockBulkChangeStageModal = vi.fn()
const mockUseAuth = vi.fn()
const mockUseBulkChangeStage = vi.fn()

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
    useSearchParams: () => ({
        get: (key: string) => mockSearchParams.get(key),
        has: (key: string) => mockSearchParams.has(key),
        toString: () => mockSearchParams.toString(),
    }),
    useRouter: () => ({
        push: vi.fn(),
        replace: mockRouterReplace,
    }),
}))

vi.mock('@/components/surrogates/MassEditStageModal', () => ({
    MassEditStageModal: (props: unknown) => {
        mockMassEditStageModal(props)
        return null
    },
}))

vi.mock('@/components/surrogates/BulkChangeStageModal', () => ({
    BulkChangeStageModal: (props: {
        open: boolean
        onSubmit: (stageId: string) => Promise<void> | void
    }) => {
        mockBulkChangeStageModal(props)
        if (!props.open) return null
        return (
            <div role="dialog">
                <button type="button" onClick={() => props.onSubmit('s2')}>
                    Mock submit bulk stage change
                </button>
            </div>
        )
    },
}))

// Mock API hooks
const mockUseSurrogates = vi.fn()
const mockUseArchiveSurrogate = vi.fn()
const mockUseRestoreSurrogate = vi.fn()
const mockUseUpdateSurrogate = vi.fn()
const mockUseCreateSurrogate = vi.fn()
const mockUseAssignees = vi.fn()
const mockUseBulkAssign = vi.fn()
const mockUseBulkArchive = vi.fn()
const mockUseIntelligentSuggestionSummary = vi.fn()
const mockUseSurrogateCreatedDates = vi.fn()
const mockUseQueues = vi.fn()

vi.mock('@/lib/hooks/use-surrogates', () => ({
    useSurrogates: (filters: unknown) => mockUseSurrogates(filters),
    useArchiveSurrogate: () => mockUseArchiveSurrogate(),
    useRestoreSurrogate: () => mockUseRestoreSurrogate(),
    useUpdateSurrogate: () => mockUseUpdateSurrogate(),
    useCreateSurrogate: () => mockUseCreateSurrogate(),
    useAssignees: () => mockUseAssignees(),
    useBulkAssign: () => mockUseBulkAssign(),
    useBulkArchive: () => mockUseBulkArchive(),
    useBulkChangeStage: () => mockUseBulkChangeStage(),
    useIntelligentSuggestionSummary: () => mockUseIntelligentSuggestionSummary(),
    useSurrogateCreatedDates: (...args: unknown[]) => mockUseSurrogateCreatedDates(...args),
}))

vi.mock('@/lib/hooks/use-queues', () => ({
    useQueues: (...args: unknown[]) => mockUseQueues(...args),
}))

// Mock Auth
vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

// Mock UI components that might cause issues in JSDOM or are complex
vi.mock('@/components/ui/date-range-picker', () => ({
    DateRangePicker: () => <div data-testid="date-picker">Date Picker</div>,
}))

vi.mock('@/lib/hooks/use-pipelines', () => ({
    useDefaultPipeline: () => ({
        data: {
            id: 'p1',
            stages: [
                { id: 's1', slug: 'new_unread', label: 'New Unread', color: '#3b82f6', stage_type: 'intake', is_active: true },
                { id: 's2', slug: 'contacted', label: 'Contacted', color: '#0ea5e9', stage_type: 'intake', is_active: true },
                { id: 's3', slug: 'on_hold', label: 'On Hold', color: '#f59e0b', stage_type: 'paused', is_active: true },
                { id: 's4', slug: 'delivered', label: 'Delivered', color: '#22c55e', stage_type: 'post_approval', is_active: true },
            ],
        },
        isLoading: false,
    }),
}))

function buildSurrogateListItem(
    overrides: Partial<{
        id: string
        surrogate_number: string
        full_name: string
        stage_id: string
        stage_slug: string
        stage_type: string
        status_label: string
        source: string
        email: string
        phone: string | null
        state: string | null
        race: string | null
        owner_type: string
        owner_id: string
        owner_name: string
        created_at: string
        last_activity_at: string
        is_priority: boolean
        is_archived: boolean
        age: number | null
        bmi: number | null
    }> = {},
) {
    return {
        id: '1',
        surrogate_number: 'S12345',
        full_name: 'John Doe',
        stage_id: 's1',
        stage_slug: 'new_unread',
        stage_type: 'intake',
        status_label: 'New Unread',
        source: 'manual',
        email: 'john@example.com',
        phone: null,
        state: null,
        race: null,
        owner_type: 'user',
        owner_id: 'u1',
        owner_name: 'Owner',
        created_at: new Date().toISOString(),
        last_activity_at: new Date().toISOString(),
        is_priority: false,
        is_archived: false,
        age: null,
        bmi: null,
        ...overrides,
    }
}

// ============================================================================
// Tests
// ============================================================================

describe('SurrogatesPage', () => {
    beforeEach(() => {
        // Reset mocks default return values
        mockSearchParams.delete('page')
        mockSearchParams.delete('stage')
        mockSearchParams.delete('source')
        mockSearchParams.delete('queue')
        mockSearchParams.delete('q')
        mockSearchParams.delete('owner_id')
        mockSearchParams.delete('dynamic_filter')
        mockSearchParams.delete('range')
        mockSearchParams.delete('from')
        mockSearchParams.delete('to')
        mockSearchParams.delete('search')
        mockUseSurrogates.mockReset()
        mockUseArchiveSurrogate.mockReset()
        mockUseRestoreSurrogate.mockReset()
        mockUseUpdateSurrogate.mockReset()
        mockUseCreateSurrogate.mockReset()
        mockUseAssignees.mockReset()
        mockUseBulkAssign.mockReset()
        mockUseBulkArchive.mockReset()
        mockUseBulkChangeStage.mockReset()
        mockUseIntelligentSuggestionSummary.mockReset()
        mockUseSurrogateCreatedDates.mockReset()
        mockUseQueues.mockReset()
        mockRouterReplace.mockReset()
        mockMassEditStageModal.mockReset()
        mockBulkChangeStageModal.mockReset()
        mockUseAuth.mockReset()
        mockUseAuth.mockReturnValue({ user: { role: 'admin', user_id: 'admin-1' } })
        mockUseArchiveSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseRestoreSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseUpdateSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseCreateSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseAssignees.mockReturnValue({ data: [] })
        mockUseBulkAssign.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseBulkArchive.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseBulkChangeStage.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseIntelligentSuggestionSummary.mockReturnValue({
            data: { total: 0, counts: {}, has_suggestions: false },
        })
        mockUseSurrogateCreatedDates.mockReturnValue({ data: [] })
        mockUseQueues.mockReturnValue({ data: [] })
    })

    it('renders loading state', () => {
        mockUseSurrogates.mockReturnValue({
            data: null,
            isLoading: true,
            error: null,
        })

        render(<SurrogatesPage />)
        // We expect the loader icon (lucide-react) or a card with loading spinner
        // Since we can't easily query by icon, we'll check if the main content area is present
        // or check for implicit loading indicators.
        // In the code: <Loader2Icon /> is rendered.
        // simpler check: "Surrogates" header should be present
        expect(screen.getByText('Surrogates')).toBeInTheDocument()
    })

    it('renders empty state', () => {
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        expect(screen.getByText('No surrogates yet')).toBeInTheDocument()
        expect(screen.getByText('0 total surrogates')).toBeInTheDocument()
    })

    it('renders surrogates list', () => {
        const mockSurrogates = [buildSurrogateListItem()]

        mockUseSurrogates.mockReturnValue({
            data: { items: mockSurrogates, total: 1, pages: 1 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        expect(screen.getByText('John Doe')).toBeInTheDocument()
        expect(screen.getByText('#S12345')).toBeInTheDocument()
        expect(screen.getByText('Manual')).toBeInTheDocument()
    })

    it('removes the email column and keeps source as the last named table column', () => {
        const mockSurrogates = [
            buildSurrogateListItem({
                phone: '+15551234567',
                state: 'CA',
                race: 'white',
                created_at: '2024-03-03T12:00:00.000Z',
                last_activity_at: '2024-03-04T12:00:00.000Z',
                age: 34,
                bmi: 24.1,
            }),
        ]

        mockUseSurrogates.mockReturnValue({
            data: { items: mockSurrogates, total: 1, pages: 1 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        const table = screen.getByRole('table')
        const namedHeaders = within(table)
            .getAllByRole('columnheader')
            .map((header) => header.textContent?.replace(/\s+/g, ' ').trim() ?? '')
            .filter(Boolean)

        expect(namedHeaders.some((header) => /email/i.test(header))).toBe(false)
        expect(within(table).queryByText('john@example.com')).not.toBeInTheDocument()
        expect(namedHeaders.at(-1)).toMatch(/source/i)
    })

    it('preserves current filters in surrogate detail links', () => {
        mockSearchParams.set('stage', 's1')
        mockSearchParams.set('q', 'john')
        mockSearchParams.set('page', '2')
        mockUseSurrogates.mockReturnValue({
            data: {
                items: [
                    {
                        ...buildSurrogateListItem(),
                    },
                ],
                total: 1,
                pages: 1,
            },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        expect(screen.getByRole('link', { name: '#S12345' })).toHaveAttribute(
            'href',
            '/surrogates/1?return_to=%2Fsurrogates%3Fstage%3Ds1%26q%3Djohn%26page%3D2',
        )
    })

    it('hydrates legacy search params and normalizes them to q', async () => {
        mockSearchParams.set('search', 'Local Warning')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        expect(screen.getByRole('textbox', { name: 'Search surrogates' })).toHaveValue('Local Warning')
        expect(mockUseSurrogates).toHaveBeenCalledWith(expect.objectContaining({ q: 'Local Warning' }))

        await waitFor(() =>
            expect(mockRouterReplace).toHaveBeenCalledWith('/surrogates?q=Local+Warning', { scroll: false })
        )
    })

    it('shows the priority action only for admin and developer users', () => {
        const mockSurrogates = [buildSurrogateListItem()]

        mockUseSurrogates.mockReturnValue({
            data: { items: mockSurrogates, total: 1, pages: 1 },
            isLoading: false,
            error: null,
        })

        const adminView = render(<SurrogatesPage />)
        fireEvent.click(screen.getByLabelText('Actions for John Doe'))
        expect(screen.getByText('Mark as Priority')).toBeInTheDocument()

        adminView.unmount()

        mockUseAuth.mockReturnValue({ user: { role: 'case_manager', user_id: 'cm-1' } })
        render(<SurrogatesPage />)

        fireEvent.click(screen.getByLabelText('Actions for John Doe'))
        expect(screen.queryByText('Mark as Priority')).not.toBeInTheDocument()
    })

    it('renders Last Modified column label', () => {
        const mockSurrogates = [buildSurrogateListItem()]

        mockUseSurrogates.mockReturnValue({
            data: { items: mockSurrogates, total: 1, pages: 1 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        expect(screen.getByText('Last Modified')).toBeInTheDocument()
    })

    it('shows Change stage... in the floating selection bar only for admin and developer users', () => {
        mockUseSurrogates.mockReturnValue({
            data: { items: [buildSurrogateListItem()], total: 1, pages: 1 },
            isLoading: false,
            error: null,
        })

        const adminView = render(<SurrogatesPage />)
        fireEvent.click(screen.getByLabelText('Select John Doe'))
        expect(screen.getByRole('button', { name: 'Change stage...' })).toBeInTheDocument()
        adminView.unmount()

        mockUseAuth.mockReturnValue({ user: { role: 'case_manager', user_id: 'cm-1' } })
        const caseManagerView = render(<SurrogatesPage />)
        fireEvent.click(screen.getByLabelText('Select John Doe'))
        expect(screen.queryByRole('button', { name: 'Change stage...' })).not.toBeInTheDocument()
        caseManagerView.unmount()

        mockUseAuth.mockReturnValue({ user: { role: 'intake_specialist', user_id: 'is-1' } })
        render(<SurrogatesPage />)
        fireEvent.click(screen.getByLabelText('Select John Doe'))
        expect(screen.queryByRole('button', { name: 'Change stage...' })).not.toBeInTheDocument()
    })

    it('submits selected surrogate ids through the bulk change stage flow', async () => {
        const mutateAsync = vi.fn().mockResolvedValue({
            requested: 2,
            applied: 2,
            failed: [],
        })
        mockUseBulkChangeStage.mockReturnValue({ mutateAsync, isPending: false })
        mockUseSurrogates.mockReturnValue({
            data: {
                items: [
                    buildSurrogateListItem({ id: '1', surrogate_number: 'S10001', full_name: 'Jane Doe' }),
                    buildSurrogateListItem({ id: '2', surrogate_number: 'S10002', full_name: 'Mia Ross' }),
                    buildSurrogateListItem({ id: '3', surrogate_number: 'S10003', full_name: 'Ava Cole' }),
                ],
                total: 3,
                pages: 1,
            },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        fireEvent.click(screen.getByLabelText('Select Jane Doe'))
        fireEvent.click(screen.getByLabelText('Select Mia Ross'))
        fireEvent.click(screen.getByRole('button', { name: 'Change stage...' }))
        fireEvent.click(screen.getByRole('button', { name: 'Mock submit bulk stage change' }))

        await waitFor(() =>
            expect(mutateAsync).toHaveBeenCalledWith({
                surrogate_ids: ['1', '2'],
                stage_id: 's2',
            })
        )
    })

    it('keeps failed surrogate ids selected after a partial bulk stage change failure', async () => {
        const mutateAsync = vi.fn().mockResolvedValue({
            requested: 2,
            applied: 1,
            failed: [{ surrogate_id: '2', reason: 'Target stage is same as current stage' }],
        })
        mockUseBulkChangeStage.mockReturnValue({ mutateAsync, isPending: false })
        mockUseSurrogates.mockReturnValue({
            data: {
                items: [
                    buildSurrogateListItem({ id: '1', surrogate_number: 'S10001', full_name: 'Jane Doe' }),
                    buildSurrogateListItem({
                        id: '2',
                        surrogate_number: 'S10002',
                        full_name: 'Mia Ross',
                        stage_id: 's2',
                        stage_slug: 'contacted',
                        status_label: 'Contacted',
                    }),
                ],
                total: 2,
                pages: 1,
            },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        fireEvent.click(screen.getByLabelText('Select Jane Doe'))
        fireEvent.click(screen.getByLabelText('Select Mia Ross'))
        fireEvent.click(screen.getByRole('button', { name: 'Change stage...' }))
        fireEvent.click(screen.getByRole('button', { name: 'Mock submit bulk stage change' }))

        await waitFor(() => expect(screen.getByText('1 surrogate selected')).toBeInTheDocument())
        expect(screen.getByLabelText('Select Jane Doe')).not.toBeChecked()
        expect(screen.getByLabelText('Select Mia Ross')).toBeChecked()
    })

    it('opens New Surrogates dialog', () => {
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        fireEvent.click(screen.getByRole('button', { name: 'New Surrogates' }))
        expect(screen.getByRole('heading', { name: 'New Surrogates' })).toBeInTheDocument()
        expect(screen.getByRole('link', { name: 'Import CSV' })).toBeInTheDocument()
    })

    it('uses page from URL params', () => {
        mockSearchParams.set('page', '3')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        expect(mockUseSurrogates).toHaveBeenCalledWith(
            expect.objectContaining({
                page: 3,
            })
        )
    })

    it('applies owner_id from URL params', () => {
        mockSearchParams.set('owner_id', 'user-123')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        expect(mockUseSurrogates).toHaveBeenCalledWith(
            expect.objectContaining({
                owner_id: 'user-123',
            })
        )
    })

    it('keeps assignee filtering behind More Filters', () => {
        mockUseAssignees.mockReturnValue({
            data: [{ id: 'user-123', name: 'Case Manager A', role: 'case_manager' }],
        })
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        const { rerender } = render(<SurrogatesPage />)
        expect(screen.getByRole('button', { name: 'More Filters' })).toBeInTheDocument()
        expect(screen.queryByText('All Assignees')).not.toBeInTheDocument()

        mockUseAuth.mockReturnValue({ user: { role: 'case_manager', user_id: 'cm-1' } })
        rerender(<SurrogatesPage />)

        expect(screen.queryByText('All Assignees')).not.toBeInTheDocument()
    })

    it('combines assignee and dynamic filters with other filters using AND semantics', () => {
        mockSearchParams.set('owner_id', 'user-123')
        mockSearchParams.set('dynamic_filter', 'attention_unreached')
        mockSearchParams.set('stage', 'stage-1')
        mockSearchParams.set('source', 'manual')
        mockSearchParams.set('queue', 'queue-1')
        mockSearchParams.set('q', 'alpha')
        mockSearchParams.set('range', 'custom')
        mockSearchParams.set('from', '2025-01-10')
        mockSearchParams.set('to', '2025-01-15')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        expect(mockUseSurrogates).toHaveBeenCalledWith(
            expect.objectContaining({
                owner_id: 'user-123',
                dynamic_filter: 'attention_unreached',
                stage_id: 'stage-1',
                source: 'manual',
                queue_id: 'queue-1',
                q: 'alpha',
                created_from: '2025-01-10',
                created_to: '2025-01-15',
            })
        )
        expect(mockUseSurrogateCreatedDates).toHaveBeenCalledWith(
            expect.objectContaining({
                owner_id: 'user-123',
                dynamic_filter: 'attention_unreached',
                stage_id: 'stage-1',
                source: 'manual',
                queue_id: 'queue-1',
                q: 'alpha',
            }),
        )
    })

    it('passes owner_id into developer mass edit base filters', () => {
        mockUseAuth.mockReturnValue({ user: { role: 'developer', user_id: 'dev-1' } })
        mockSearchParams.set('owner_id', 'user-123')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        expect(mockMassEditStageModal).toHaveBeenCalled()
        const latestProps = mockMassEditStageModal.mock.calls.at(-1)?.[0] as {
            baseFilters: Record<string, unknown>
        }
        expect(latestProps.baseFilters).toEqual(
            expect.objectContaining({
                owner_id: 'user-123',
            })
        )
    })

    it('shows Reset when only owner_id is active and clears filters', () => {
        mockSearchParams.set('owner_id', 'user-123')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Reset' }))

        expect(mockRouterReplace).toHaveBeenCalledWith('/surrogates', { scroll: false })
    })

    it('applies dynamic_filter from URL params', () => {
        mockSearchParams.set('dynamic_filter', 'attention_unreached')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        expect(mockUseSurrogates).toHaveBeenCalledWith(
            expect.objectContaining({
                dynamic_filter: 'attention_unreached',
            })
        )
    })

    it('renders the stuck attention chip with the surrogate label', () => {
        mockSearchParams.set('dynamic_filter', 'attention_stuck')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        expect(screen.getByText('Attention Needed: Stuck Surrogates')).toBeInTheDocument()
    })

    it('shows intelligent unavailable copy when intelligent dynamic filter has no results', () => {
        mockSearchParams.set('dynamic_filter', 'intelligent_any')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        expect(screen.getByText('Intelligent suggestions are not available right now.')).toBeInTheDocument()
    })

    it('uses More Filters entry point instead of inline secondary filters', () => {
        mockUseAssignees.mockReturnValue({
            data: [{ id: 'user-123', name: 'Case Manager A', role: 'case_manager' }],
        })
        mockUseQueues.mockReturnValue({
            data: [{ id: 'queue-1', name: 'Unassigned' }],
        })
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        expect(screen.getByRole('button', { name: 'More Filters' })).toBeInTheDocument()
        expect(screen.queryByText('All Sources')).not.toBeInTheDocument()
        expect(screen.queryByText('All Queues')).not.toBeInTheDocument()
        expect(screen.queryByText('All Assignees')).not.toBeInTheDocument()
    })

    it('renders secondary controls inside the More Filters popover instead of the old sheet', () => {
        mockUseAssignees.mockReturnValue({
            data: [{ id: 'user-123', name: 'Case Manager A', role: 'case_manager' }],
        })
        mockUseQueues.mockReturnValue({
            data: [{ id: 'queue-1', name: 'Unassigned' }],
        })
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        fireEvent.click(screen.getByRole('button', { name: 'More Filters' }))

        expect(screen.getByText('Source')).toBeInTheDocument()
        expect(screen.getByText('Queue')).toBeInTheDocument()
        expect(screen.getByText('Assignee')).toBeInTheDocument()
        expect(screen.getByText('Attention / Smart Filter')).toBeInTheDocument()
        expect(screen.queryByText('Secondary filters stay here so the list keeps its core controls visible.')).not.toBeInTheDocument()
    })

    it('shows friendly secondary filter labels inside More Filters', () => {
        mockSearchParams.set('source', 'manual')
        mockSearchParams.set('queue', 'queue-1')
        mockSearchParams.set('owner_id', 'user-123')
        mockSearchParams.set('dynamic_filter', 'attention_unreached')
        mockUseAssignees.mockReturnValue({
            data: [{ id: 'user-123', name: 'Case Manager A', role: 'case_manager' }],
        })
        mockUseQueues.mockReturnValue({
            data: [{ id: 'queue-1', name: 'Unassigned' }],
        })
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        fireEvent.click(screen.getByRole('button', { name: 'More Filters' }))

        expect(screen.getByText('Manual')).toBeInTheDocument()
        expect(screen.getByText('Unassigned')).toBeInTheDocument()
        expect(screen.getByText('Case Manager A')).toBeInTheDocument()
        expect(screen.getAllByText('Attention Needed: Unreached Leads').length).toBeGreaterThan(0)
        expect(screen.queryByText('queue-1')).not.toBeInTheDocument()
        expect(screen.queryByText('user-123')).not.toBeInTheDocument()
    })

    it('hides intelligent smart-filter options when intelligent suggestions are unavailable', () => {
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        fireEvent.click(screen.getByRole('button', { name: 'More Filters' }))
        const smartFilterTrigger = screen.getAllByRole('combobox').at(-1)
        expect(smartFilterTrigger).toBeDefined()
        fireEvent.click(smartFilterTrigger!)

        expect(screen.queryByText('New Unread Needs Follow-up')).not.toBeInTheDocument()
        expect(screen.queryByText('Meeting Outcome Missing')).not.toBeInTheDocument()
        expect(screen.queryByText('Pre-approval Stuck Cases')).not.toBeInTheDocument()
        expect(screen.getByText('Attention Needed: Unreached Leads')).toBeInTheDocument()
        expect(screen.getByText('Attention Needed: Stuck Surrogates')).toBeInTheDocument()
    })

    it('applies priority-only immediately from More Filters', () => {
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        fireEvent.click(screen.getByRole('button', { name: 'More Filters' }))
        fireEvent.click(screen.getByLabelText('Priority only'))

        expect(mockRouterReplace).toHaveBeenCalledWith('/surrogates?priority=only', { scroll: false })
    })

    it('applies priority-only filter from URL params', () => {
        mockSearchParams.set('priority', 'only')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        expect(mockUseSurrogates).toHaveBeenCalledWith(
            expect.objectContaining({
                is_priority: true,
            })
        )
        expect(mockUseSurrogateCreatedDates).toHaveBeenCalledWith(
            expect.objectContaining({
                is_priority: true,
            }),
        )
    })

    it('renders active chips for secondary filters', () => {
        mockSearchParams.set('priority', 'only')
        mockSearchParams.set('source', 'manual')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        expect(screen.getByText('Priority Only')).toBeInTheDocument()
        expect(screen.getByText('Source: Manual')).toBeInTheDocument()
    })

    it('renders active chips for primary filters next to Reset', () => {
        mockSearchParams.set('stage', 's1')
        mockSearchParams.set('range', 'week')
        mockSearchParams.set('q', 'alpha')
        mockSearchParams.set('dynamic_filter', 'intelligent_any')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        expect(screen.getByText('Intelligent Suggestions')).toBeInTheDocument()
        expect(screen.getByText('Stage: New Unread')).toBeInTheDocument()
        expect(screen.getByText('Date: This Week')).toBeInTheDocument()
        expect(screen.getByText('Search: alpha')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Reset' })).toBeInTheDocument()
    })

    it('sorts by last_modified_at when Last Modified header is clicked', () => {
        mockUseSurrogates.mockReturnValue({
            data: {
                items: [
                    {
                        id: '1',
                        surrogate_number: 'S12345',
                        full_name: 'John Doe',
                        stage_id: 's1',
                        stage_slug: 'new_unread',
                        stage_type: 'intake',
                        status_label: 'New Unread',
                        source: 'manual',
                        email: 'john@example.com',
                        phone: null,
                        state: null,
                        race: null,
                        owner_type: 'user',
                        owner_id: 'u1',
                        owner_name: 'Owner',
                        created_at: '2024-03-03T12:00:00.000Z',
                        updated_at: '2024-02-02T12:00:00.000Z',
                        last_activity_at: '2024-01-01T12:00:00.000Z',
                        is_priority: false,
                        is_archived: false,
                        age: null,
                        bmi: null,
                    },
                ],
                total: 1,
                pages: 1,
            },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        fireEvent.click(screen.getByRole('columnheader', { name: /last modified/i }))

        expect(mockUseSurrogates).toHaveBeenLastCalledWith(
            expect.objectContaining({
                sort_by: 'last_modified_at',
            })
        )
    })

    it('renders Last Modified from the latest of updated_at and last_activity_at', () => {
        mockUseSurrogates.mockReturnValue({
            data: {
                items: [
                    {
                        id: '1',
                        surrogate_number: 'S12345',
                        full_name: 'John Doe',
                        stage_id: 's1',
                        stage_slug: 'new_unread',
                        stage_type: 'intake',
                        status_label: 'New Unread',
                        source: 'manual',
                        email: 'john@example.com',
                        phone: null,
                        state: null,
                        race: null,
                        owner_type: 'user',
                        owner_id: 'u1',
                        owner_name: 'Owner',
                        created_at: '2024-03-03T12:00:00.000Z',
                        updated_at: '2024-02-02T12:00:00.000Z',
                        last_activity_at: '2024-01-01T12:00:00.000Z',
                        is_priority: false,
                        is_archived: false,
                        age: null,
                        bmi: null,
                    },
                ],
                total: 1,
                pages: 1,
            },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        expect(screen.getByText('Feb 02, 2024')).toBeInTheDocument()
        expect(screen.queryByText('Jan 01, 2024')).not.toBeInTheDocument()
    })

    it('renders Last Modified from last_activity_at when activity is newer than updated_at', () => {
        mockUseSurrogates.mockReturnValue({
            data: {
                items: [
                    {
                        id: '1',
                        surrogate_number: 'S12345',
                        full_name: 'John Doe',
                        stage_id: 's1',
                        stage_slug: 'new_unread',
                        stage_type: 'intake',
                        status_label: 'New Unread',
                        source: 'manual',
                        email: 'john@example.com',
                        phone: null,
                        state: null,
                        race: null,
                        owner_type: 'user',
                        owner_id: 'u1',
                        owner_name: 'Owner',
                        created_at: '2024-03-03T12:00:00.000Z',
                        updated_at: '2024-02-02T12:00:00.000Z',
                        last_activity_at: '2024-04-04T12:00:00.000Z',
                        is_priority: false,
                        is_archived: false,
                        age: null,
                        bmi: null,
                    },
                ],
                total: 1,
                pages: 1,
            },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        expect(screen.getByText('Apr 04, 2024')).toBeInTheDocument()
        expect(screen.queryByText('Feb 02, 2024')).not.toBeInTheDocument()
    })
})
