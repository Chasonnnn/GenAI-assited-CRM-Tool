import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react'
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
const mockUseEffectivePermissions = vi.fn()
vi.mock('@/lib/hooks/use-permissions', () => ({
    useEffectivePermissions: () => mockUseEffectivePermissions(),
}))
const mockUseBulkChangeStage = vi.fn()
const mockToast = vi.hoisted(() => ({
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
}))
vi.mock('@/components/ui/toast', async (original) => {
    const actual = await original<typeof import('@/components/ui/toast')>()
    return { ...actual, toast: Object.assign(vi.fn(), actual.toast, mockToast) }
})

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
        onSubmit: (input: { stage_id: string; reason?: string }) => Promise<void> | void
    }) => {
        mockBulkChangeStageModal(props)
        if (!props.open) return null
        return (
            <dialog open aria-label="Bulk stage change">
                <button type="button" onClick={() => props.onSubmit({ stage_id: 's2', reason: 'Batch review' })}>
                    Mock submit bulk stage change
                </button>
            </dialog>
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
const mockUseAccessibleSurrogateOwners = vi.fn()
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
    useAccessibleSurrogateOwners: () => mockUseAccessibleSurrogateOwners(),
    useBulkAssign: () => mockUseBulkAssign(),
    useBulkArchive: () => mockUseBulkArchive(),
    useBulkChangeStage: () => mockUseBulkChangeStage(),
    useIntelligentSuggestionSummary: () => mockUseIntelligentSuggestionSummary(),
    useSurrogateCreatedDates: (...args: unknown[]) => mockUseSurrogateCreatedDates(...args),
}))

const mockShowUndoToast = vi.fn()
vi.mock('@/components/ui/undo-toast', () => ({
    showUndoToast: (...args: unknown[]) => mockShowUndoToast(...args),
}))

vi.mock('@/lib/hooks/use-queues', () => ({
    useQueues: (...args: unknown[]) => mockUseQueues(...args),
}))

// Mock Auth
vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

const mockGrantedPermissions = { value: ['archive_surrogates'] as string[] }
vi.mock('@/lib/hooks/use-permission-check', () => ({
    usePermissionCheck: () => ({
        isLoading: false,
        isError: false,
        retry: vi.fn(),
        isRetrying: false,
        can: (permission: string) => mockGrantedPermissions.value.includes(permission),
    }),
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
        mockUseEffectivePermissions.mockReturnValue({ data: { policy_version: 1, permissions: ["edit_surrogates"] } })
        // Reset mocks default return values
        mockSearchParams.delete('page')
        mockSearchParams.delete('stage')
        mockSearchParams.delete('source')
        mockSearchParams.delete('queue')
        mockSearchParams.delete('q')
        mockSearchParams.delete('owner_id')
        mockSearchParams.delete('dynamic_filter')
        mockSearchParams.delete('priority')
        mockSearchParams.delete('range')
        mockSearchParams.delete('from')
        mockSearchParams.delete('to')
        mockSearchParams.delete('search')
        mockSearchParams.delete('sort_by')
        mockSearchParams.delete('sort_order')
        mockUseSurrogates.mockReset()
        mockUseArchiveSurrogate.mockReset()
        mockUseRestoreSurrogate.mockReset()
        mockUseUpdateSurrogate.mockReset()
        mockUseCreateSurrogate.mockReset()
        mockUseAssignees.mockReset()
        mockUseAccessibleSurrogateOwners.mockReset()
        mockUseBulkAssign.mockReset()
        mockUseBulkArchive.mockReset()
        mockUseBulkChangeStage.mockReset()
        mockUseIntelligentSuggestionSummary.mockReset()
        mockUseSurrogateCreatedDates.mockReset()
        mockUseQueues.mockReset()
        mockRouterReplace.mockReset()
        mockShowUndoToast.mockReset()
        mockMassEditStageModal.mockReset()
        mockBulkChangeStageModal.mockReset()
        mockToast.success.mockReset()
        mockToast.warning.mockReset()
        mockToast.error.mockReset()
        mockUseAuth.mockReset()
        mockUseAuth.mockReturnValue({ user: { role: 'admin', user_id: 'admin-1' } })
        mockGrantedPermissions.value = ['archive_surrogates']
        mockUseArchiveSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseRestoreSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseUpdateSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseCreateSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseAssignees.mockReturnValue({ data: [] })
        mockUseAccessibleSurrogateOwners.mockReturnValue({ data: [] })
        mockUseBulkAssign.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseBulkArchive.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseBulkChangeStage.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseIntelligentSuggestionSummary.mockReturnValue({
            data: { total: 0, counts: {}, has_suggestions: false },
        })
        mockUseSurrogateCreatedDates.mockReturnValue({ data: [] })
        mockUseQueues.mockReturnValue({ data: [] })
    })

    it("uses Create independently of Edit under V2 and closes on revocation", async () => {
        mockUseSurrogates.mockReturnValue({ data: { items: [], total: 0, page: 1, per_page: 30 }, isLoading: false })
        mockUseEffectivePermissions.mockReturnValue({ data: { policy_version: 2, permissions: ["view_surrogates", "edit_surrogates"] } })
        const { rerender } = render(<SurrogatesPage />)
        expect(screen.queryByRole("button", { name: "New surrogate" })).not.toBeInTheDocument()
        mockUseEffectivePermissions.mockReturnValue({ data: { policy_version: 2, permissions: ["view_surrogates", "create_surrogates"] } })
        rerender(<SurrogatesPage />)
        fireEvent.click(screen.getByRole("button", { name: "New surrogate" }))
        expect(screen.getByRole("dialog")).toBeInTheDocument()
        mockUseEffectivePermissions.mockReturnValue({ data: { policy_version: 2, permissions: ["view_surrogates"] } })
        rerender(<SurrogatesPage />)
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    })

    it.each([{ data: undefined, isLoading: true }, { data: undefined, isError: true }])("hides Create until permissions load successfully", (result) => {
        mockUseSurrogates.mockReturnValue({ data: { items: [], total: 0, page: 1, per_page: 30 }, isLoading: false })
        mockUseEffectivePermissions.mockReturnValue(result)
        render(<SurrogatesPage />)
        expect(screen.queryByRole("button", { name: "New surrogate" })).not.toBeInTheDocument()
    })

    it('renders loading state', () => {
        mockUseSurrogates.mockReturnValue({
            data: null,
            isLoading: true,
            error: null,
        })

        const { container, rerender } = render(<SurrogatesPage />)

        expect(container.querySelector('.animate-spin')).toBeInTheDocument()
        expect(screen.queryByText('No surrogates yet')).not.toBeInTheDocument()
        expect(screen.queryByRole('table')).not.toBeInTheDocument()

        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })
        rerender(<SurrogatesPage />)

        expect(container.querySelector('.animate-spin')).not.toBeInTheDocument()
        expect(screen.getByText('No surrogates yet')).toBeInTheDocument()
    })

    it('renders empty state', () => {
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        const { container } = render(<SurrogatesPage />)
        expect(screen.getByText('No surrogates yet')).toBeInTheDocument()
        expect(screen.getByRole('heading', { level: 1, name: 'Surrogates' })).toBeInTheDocument()
        expect(container.querySelector('[data-slot="page-header-count"]')).toHaveTextContent('0 surrogates')
    })

    it('shows a load error with retry and never the server detail', async () => {
        const { ApiError } = await import('@/lib/api')
        const refetch = vi.fn()
        mockUseSurrogates.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            isFetching: false,
            error: new ApiError(500, 'Internal Server Error', 'boom'),
            refetch,
        })

        render(<SurrogatesPage />)

        expect(screen.getByRole('heading', { level: 2, name: "Couldn't load surrogates" })).toBeInTheDocument()
        expect(screen.queryByText('boom')).not.toBeInTheDocument()
        expect(screen.queryByText('No surrogates yet')).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
        expect(refetch).toHaveBeenCalledTimes(1)
    })

    it('shows the filtered count against the unfiltered total', () => {
        mockSearchParams.set('stage', 's2')
        mockUseSurrogates.mockImplementation((filters: { stage_id?: string }) => ({
            data: filters.stage_id
                ? { items: [buildSurrogateListItem({ stage_id: 's2' })], total: 8, pages: 1 }
                : { items: [], total: 151, pages: 8 },
            isLoading: false,
            error: null,
        }))

        const { container } = render(<SurrogatesPage />)

        expect(container.querySelector('[data-slot="page-header-count"]')).toHaveTextContent('8 of 151')
        expect(screen.queryByText(/total surrogates/)).not.toBeInTheDocument()
    })

    it('offers every surrogate source in the Source filter, using the badge labels', async () => {
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        fireEvent.click(screen.getByRole('button', { name: 'More Filters' }))
        fireEvent.click(screen.getByRole('combobox', { name: 'Filter by source' }))

        const listbox = await screen.findByRole('listbox')
        const labels = within(listbox).getAllByRole('option').map((option) => option.textContent)
        expect(labels).toEqual(expect.arrayContaining(['All Sources', 'Agency', 'Import', 'Other']))
        expect(labels).not.toContain('Others')
    })

    it('confirms a bulk archive by count and offers undo for the archived records', async () => {
        const bulkArchive = vi.fn().mockResolvedValue({ archived: 2, failed: [] })
        const restore = vi.fn().mockResolvedValue({})
        mockUseBulkArchive.mockReturnValue({ mutateAsync: bulkArchive, isPending: false })
        mockUseRestoreSurrogate.mockReturnValue({ mutateAsync: restore, isPending: false })
        mockUseSurrogates.mockReturnValue({
            data: {
                items: [
                    buildSurrogateListItem({ id: '1', full_name: 'Jane Doe' }),
                    buildSurrogateListItem({ id: '2', full_name: 'Mia Ross', surrogate_number: 'S12346' }),
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
        fireEvent.click(screen.getByRole('button', { name: /^archive$/i }))

        const dialog = await screen.findByRole('alertdialog')
        expect(within(dialog).getByText('Archive 2 surrogates?')).toBeInTheDocument()
        expect(bulkArchive).not.toHaveBeenCalled()
        fireEvent.click(within(dialog).getByRole('button', { name: 'Archive' }))

        await waitFor(() => expect(bulkArchive).toHaveBeenCalledWith(['1', '2']))
        expect(mockShowUndoToast).toHaveBeenCalledWith('Archived 2 surrogates', expect.any(Function))
        await mockShowUndoToast.mock.calls[0]?.[1]()
        expect(restore).toHaveBeenCalledWith('1')
        expect(restore).toHaveBeenCalledWith('2')
    })

    it('hides row and bulk Archive without the archive_surrogates permission', async () => {
        // Case managers can still bulk assign, so rows stay selectable.
        mockUseAuth.mockReturnValue({ user: { role: 'case_manager', user_id: 'cm-1' } })
        mockGrantedPermissions.value = []
        mockUseSurrogates.mockReturnValue({
            data: {
                items: [
                    buildSurrogateListItem({ id: '1', full_name: 'Jane Doe' }),
                    buildSurrogateListItem({ id: '2', full_name: 'Mia Ross', surrogate_number: 'S12346' }),
                ],
                total: 2,
                pages: 1,
            },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        fireEvent.click(screen.getByRole('button', { name: 'Actions for Jane Doe' }))
        expect(await screen.findByRole('menuitem', { name: 'View Details' })).toBeInTheDocument()
        expect(screen.queryByRole('menuitem', { name: /archive/i })).not.toBeInTheDocument()
        fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' })

        fireEvent.click(screen.getByLabelText('Select Jane Doe'))
        fireEvent.click(screen.getByLabelText('Select Mia Ross'))
        expect(screen.getByText('2 surrogates selected')).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: /^archive$/i })).not.toBeInTheDocument()
    })

    it('confirms a row archive and offers undo that restores the surrogate', async () => {
        const archive = vi.fn().mockResolvedValue({ id: '1', surrogate_number: 'S12345' })
        const restore = vi.fn().mockResolvedValue({ id: '1' })
        mockUseArchiveSurrogate.mockReturnValue({ mutateAsync: archive, isPending: false })
        mockUseRestoreSurrogate.mockReturnValue({ mutateAsync: restore, isPending: false })
        mockUseSurrogates.mockReturnValue({
            data: { items: [buildSurrogateListItem()], total: 1, pages: 1 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        fireEvent.click(screen.getByRole('button', { name: 'Actions for John Doe' }))
        fireEvent.click(await screen.findByRole('menuitem', { name: /archive/i }))

        const dialog = await screen.findByRole('alertdialog')
        expect(within(dialog).getByText('Archive S12345?')).toBeInTheDocument()
        expect(archive).not.toHaveBeenCalled()
        fireEvent.click(within(dialog).getByRole('button', { name: 'Archive' }))

        await waitFor(() => expect(archive).toHaveBeenCalledWith('1'))
        expect(mockShowUndoToast).toHaveBeenCalledWith('S12345 archived', expect.any(Function))
        await mockShowUndoToast.mock.calls[0]?.[1]()
        expect(restore).toHaveBeenCalledWith('1')
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
            .flatMap((header) => {
                const label = header.textContent?.replace(/\s+/g, ' ').trim() ?? ''
                return label ? [label] : []
            })

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

    it('hydrates legacy search params as canonical q filters without mount-time navigation', () => {
        mockSearchParams.set('search', 'Local Warning')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        expect(screen.getByRole('textbox', { name: 'Search surrogates' })).toHaveValue('Local Warning')
        expect(mockUseSurrogates).toHaveBeenCalledWith(expect.objectContaining({ q: 'Local Warning' }))
        expect(mockRouterReplace).not.toHaveBeenCalled()
    })

    it('derives filters from the current URL on rerender', () => {
        mockSearchParams.set('stage', 's1')
        mockSearchParams.set('q', 'alpha')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        const { rerender } = render(<SurrogatesPage />)

        expect(mockUseSurrogates).toHaveBeenLastCalledWith(
            expect.objectContaining({
                stage_id: 's1',
                q: 'alpha',
            })
        )

        mockSearchParams.set('stage', 's2')
        mockSearchParams.set('q', 'beta')
        mockUseSurrogates.mockClear()

        rerender(<SurrogatesPage />)

        expect(mockUseSurrogates).toHaveBeenLastCalledWith(
            expect.objectContaining({
                stage_id: 's2',
                q: 'beta',
            })
        )
        expect(screen.getByRole('textbox', { name: 'Search surrogates' })).toHaveValue('beta')
    })

    it('cancels pending search commits when the URL changes before debounce', () => {
        vi.useFakeTimers()
        try {
            mockSearchParams.set('stage', 's1')
            mockSearchParams.set('q', 'alpha')
            mockUseSurrogates.mockReturnValue({
                data: { items: [], total: 0, pages: 0 },
                isLoading: false,
                error: null,
            })

            const { rerender } = render(<SurrogatesPage />)

            fireEvent.change(screen.getByRole('textbox', { name: 'Search surrogates' }), {
                target: { value: 'draft' },
            })
            expect(screen.getByRole('textbox', { name: 'Search surrogates' })).toHaveValue('draft')

            mockSearchParams.set('stage', 's2')
            mockSearchParams.set('q', 'beta')
            rerender(<SurrogatesPage />)

            expect(screen.getByRole('textbox', { name: 'Search surrogates' })).toHaveValue('beta')

            act(() => {
                vi.advanceTimersByTime(300)
            })

            expect(mockRouterReplace).not.toHaveBeenCalled()
        } finally {
            vi.clearAllTimers()
            vi.useRealTimers()
        }
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

    it('uses the v2 assign action for selected records instead of the role', () => {
        mockUseSurrogates.mockReturnValue({ data: { items: [buildSurrogateListItem()], total: 1, pages: 1 }, isLoading: false, error: null })
        mockUseAuth.mockReturnValue({ user: { role: 'case_manager', user_id: 'cm-1' } })
        mockUseEffectivePermissions.mockReturnValue({ data: { policy_version: 2, permissions: ['view_surrogates'] } })
        const view = render(<SurrogatesPage />)
        fireEvent.click(screen.getByLabelText('Select John Doe'))
        expect(screen.queryByRole('button', { name: 'Assign to user' })).not.toBeInTheDocument()
        mockUseAuth.mockReturnValue({ user: { role: 'intake_specialist', user_id: 'is-1' } })
        mockUseEffectivePermissions.mockReturnValue({ data: { policy_version: 2, permissions: ['view_surrogates', 'assign_surrogates'] } })
        view.rerender(<SurrogatesPage />)
        expect(screen.getByRole('button', { name: 'Assign to user' })).toBeInTheDocument()
    })

    it('shows Change stage in the floating selection bar only for admin and developer users', () => {
        mockUseSurrogates.mockReturnValue({
            data: { items: [buildSurrogateListItem()], total: 1, pages: 1 },
            isLoading: false,
            error: null,
        })

        const adminView = render(<SurrogatesPage />)
        fireEvent.click(screen.getByLabelText('Select John Doe'))
        expect(screen.getByRole('button', { name: 'Change stage' })).toBeInTheDocument()
        adminView.unmount()

        mockUseAuth.mockReturnValue({ user: { role: 'case_manager', user_id: 'cm-1' } })
        const caseManagerView = render(<SurrogatesPage />)
        fireEvent.click(screen.getByLabelText('Select John Doe'))
        expect(screen.queryByRole('button', { name: 'Change stage' })).not.toBeInTheDocument()
        caseManagerView.unmount()

        mockUseAuth.mockReturnValue({ user: { role: 'intake_specialist', user_id: 'is-1' } })
        render(<SurrogatesPage />)
        fireEvent.click(screen.getByLabelText('Select John Doe'))
        expect(screen.queryByRole('button', { name: 'Change stage' })).not.toBeInTheDocument()
    })

    it('keeps the floating selection bar inside a 16px side gutter on narrow screens', () => {
        mockUseSurrogates.mockReturnValue({
            data: { items: [buildSurrogateListItem()], total: 1, pages: 1 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        fireEvent.click(screen.getByLabelText('Select John Doe'))

        const bar = screen.getByText('1 surrogate selected').parentElement as HTMLElement
        const container = bar.parentElement as HTMLElement
        // A left-1/2 anchor limits the bar to half the viewport, so it overflowed at 390px.
        expect(container).toHaveClass('fixed', 'inset-x-4', 'flex', 'justify-center', 'pointer-events-none')
        expect(container).not.toHaveClass('left-1/2')
        expect(bar).toHaveClass('flex-wrap', 'pointer-events-auto')
    })

    it('keeps the stage and date filters visible at phone width', () => {
        mockUseSurrogates.mockReturnValue({ data: { items: [], total: 0, pages: 0 }, isLoading: false, error: null })
        render(<SurrogatesPage />)

        const stageFilter = screen.getByRole('combobox', { name: 'Filter by stage' })
        const dateFilter = screen.getByTestId('date-picker')
        for (const control of [stageFilter, dateFilter]) {
            expect(control.closest('.hidden')).toBeNull()
        }
    })

    it('does not offer row selection when the viewer has no bulk action', () => {
        mockUseSurrogates.mockReturnValue({
            data: { items: [buildSurrogateListItem()], total: 1, pages: 1 },
            isLoading: false,
            error: null,
        })
        mockUseAuth.mockReturnValue({ user: { role: 'intake_specialist', user_id: 'is-1' } })
        mockGrantedPermissions.value = []

        render(<SurrogatesPage />)

        expect(screen.getByText('John Doe')).toBeInTheDocument()
        expect(screen.queryByLabelText('Select all surrogates')).not.toBeInTheDocument()
        expect(screen.queryByLabelText('Select John Doe')).not.toBeInTheDocument()
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
        fireEvent.click(screen.getByRole('button', { name: 'Change stage' }))

        const modalProps = mockBulkChangeStageModal.mock.lastCall?.[0] as { surrogates: unknown[] }
        expect(modalProps.surrogates).toEqual([
            { id: '1', full_name: 'Jane Doe', stage_id: 's1', paused_from_stage_id: null },
            { id: '2', full_name: 'Mia Ross', stage_id: 's1', paused_from_stage_id: null },
        ])
        fireEvent.click(screen.getByRole('button', { name: 'Mock submit bulk stage change' }))

        await waitFor(() =>
            expect(mutateAsync).toHaveBeenCalledWith({
                surrogate_ids: ['1', '2'],
                stage_id: 's2',
                reason: 'Batch review',
            })
        )
        expect(mockToast.success).toHaveBeenCalledWith('Changed stage for 2 surrogates.')
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
        fireEvent.click(screen.getByRole('button', { name: 'Change stage' }))
        fireEvent.click(screen.getByRole('button', { name: 'Mock submit bulk stage change' }))

        await waitFor(() => expect(screen.getByText('1 surrogate selected')).toBeInTheDocument())
        expect(screen.getByLabelText('Select Jane Doe')).not.toBeChecked()
        expect(screen.getByLabelText('Select Mia Ross')).toBeChecked()

        const [title, options] = mockToast.warning.mock.lastCall as [
            string,
            { description: React.ReactNode; duration?: number },
        ]
        expect(title).toBe('Changed stage for 1 of 2 surrogates; 1 failed.')
        // Failure reasons are shown only here, so the toast stays until dismissed.
        expect(options.duration).toBe(0)
        render(<>{options.description}</>)
        expect(screen.getByText('Mia Ross: Target stage is same as current stage')).toBeInTheDocument()
    })

    it('reports a failed title when no surrogate changed stage', async () => {
        const mutateAsync = vi.fn().mockResolvedValue({
            requested: 2,
            applied: 0,
            pending_approval: 0,
            failed: [
                { surrogate_id: '1', reason: 'Cannot set to Matched without an accepted Match.' },
                { surrogate_id: '2', reason: 'Cannot set to Matched without an accepted Match.' },
            ],
        })
        mockUseBulkChangeStage.mockReturnValue({ mutateAsync, isPending: false })
        mockUseSurrogates.mockReturnValue({
            data: {
                items: [
                    buildSurrogateListItem({ id: '1', surrogate_number: 'S10001', full_name: 'Jane Doe' }),
                    buildSurrogateListItem({ id: '2', surrogate_number: 'S10002', full_name: 'Mia Ross' }),
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
        fireEvent.click(screen.getByRole('button', { name: 'Change stage' }))
        fireEvent.click(screen.getByRole('button', { name: 'Mock submit bulk stage change' }))

        await waitFor(() => expect(mockToast.error).toHaveBeenCalled())
        const [title, options] = mockToast.error.mock.lastCall as [
            string,
            { description: React.ReactNode; duration?: number },
        ]
        expect(title).toBe('Stage change failed for 2 surrogates.')
        expect(options.duration).toBe(0)
        expect(mockToast.warning).not.toHaveBeenCalled()
        expect(screen.getByText('2 surrogates selected')).toBeInTheDocument()
    })

    it('opens the New surrogate dialog without descriptive copy', () => {
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        fireEvent.click(screen.getByRole('button', { name: 'New surrogate' }))
        expect(screen.getByRole('heading', { name: 'New surrogate' })).toBeInTheDocument()
        expect(screen.queryByText('Add a new surrogate to the system')).not.toBeInTheDocument()
        expect(screen.getByRole('link', { name: 'Import CSV' })).toBeInTheDocument()
    })

    it('validates the email inline before calling the API', async () => {
        const create = vi.fn()
        mockUseCreateSurrogate.mockReturnValue({ mutateAsync: create, isPending: false })
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        fireEvent.click(screen.getByRole('button', { name: 'New surrogate' }))
        fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Jane Doe' } })
        const email = screen.getByLabelText(/email/i)
        fireEvent.change(email, { target: { value: 'not-an-email' } })
        fireEvent.click(screen.getByRole('button', { name: 'Create' }))

        await waitFor(() => expect(email).toHaveAttribute('aria-invalid', 'true'))
        expect(create).not.toHaveBeenCalled()
    })

    it('maps a 422 email error from the API onto the email field', async () => {
        const { ApiError } = await import('@/lib/api')
        const create = vi.fn().mockRejectedValue(
            new ApiError(422, 'Unprocessable Entity', 'Validation failed', [
                { path: 'email', message: 'value is not a valid email address: An email address must have an @-sign.' },
            ]),
        )
        mockUseCreateSurrogate.mockReturnValue({ mutateAsync: create, isPending: false })
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        fireEvent.click(screen.getByRole('button', { name: 'New surrogate' }))
        fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Jane Doe' } })
        const email = screen.getByLabelText(/email/i)
        fireEvent.change(email, { target: { value: 'jane@example.com' } })
        fireEvent.click(screen.getByRole('button', { name: 'Create' }))

        await waitFor(() => expect(email).toHaveAttribute('aria-invalid', 'true'))
        expect(screen.queryByText(/pydantic|@-sign/i)).not.toBeInTheDocument()
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

    it('ignores owner_id URL params for intake users', () => {
        mockUseAuth.mockReturnValue({ user: { role: 'intake_specialist', user_id: 'is-1' } })
        mockSearchParams.set('owner_id', 'user-123')
        mockUseSurrogates.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)

        const latestSurrogateFilters = mockUseSurrogates.mock.calls.at(-1)?.[0] as Record<string, unknown>
        expect(latestSurrogateFilters).not.toHaveProperty('owner_id')

        const latestCreatedDateFilters = mockUseSurrogateCreatedDates.mock.calls.at(-1)?.[0] as Record<string, unknown>
        expect(latestCreatedDateFilters).not.toHaveProperty('owner_id')
        expect(mockMassEditStageModal).not.toHaveBeenCalled()
    })

    it('keeps v2 Intake assignee filters for scoped records and calendar dates', () => {
        mockUseAuth.mockReturnValue({ user: { role: 'intake_specialist', user_id: 'is-1' } })
        mockUseEffectivePermissions.mockReturnValue({ data: { policy_version: 2, permissions: ['view_surrogates'] } })
        mockSearchParams.set('owner_id', 'case-manager-1')
        mockUseSurrogates.mockReturnValue({ data: { items: [], total: 0, pages: 0 }, isLoading: false, error: null })
        render(<SurrogatesPage />)
        expect(mockUseSurrogates.mock.calls.at(-1)?.[0]).toHaveProperty('owner_id', 'case-manager-1')
        expect(mockUseSurrogateCreatedDates.mock.calls.at(-1)?.[0]).toHaveProperty('owner_id', 'case-manager-1')
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

    it('reads a stage outside the pipeline as All Stages instead of sending it to the API', () => {
        mockSearchParams.set('stage', 'not-a-stage')
        mockUseSurrogates.mockReturnValue({ data: { items: [], total: 0, pages: 0 }, isLoading: false, error: null })

        render(<SurrogatesPage />)

        for (const call of mockUseSurrogates.mock.calls) {
            expect(call[0]).not.toHaveProperty('stage_id')
        }
        expect(mockUseSurrogateCreatedDates.mock.calls.at(-1)?.[0]).not.toHaveProperty('stage_id')
        expect(screen.getByRole('combobox', { name: 'Filter by stage' })).toHaveTextContent('All Stages')
    })

    it('combines assignee and dynamic filters with other filters using AND semantics', () => {
        mockSearchParams.set('owner_id', 'user-123')
        mockSearchParams.set('dynamic_filter', 'attention_unreached')
        mockSearchParams.set('stage', 's1')
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
                stage_id: 's1',
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
                stage_id: 's1',
                source: 'manual',
                queue_id: 'queue-1',
                q: 'alpha',
            }),
            { enabled: true },
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
        fireEvent.click(screen.getByRole('checkbox', { name: 'Priority only' }))

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
            { enabled: true },
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

        const { rerender } = render(<SurrogatesPage />)
        fireEvent.click(screen.getByRole('columnheader', { name: /last modified/i }))

        expect(mockRouterReplace).toHaveBeenCalledWith(
            '/surrogates?sort_by=last_modified_at&sort_order=desc',
            { scroll: false },
        )

        mockSearchParams.set('sort_by', 'last_modified_at')
        mockSearchParams.set('sort_order', 'desc')
        mockUseSurrogates.mockClear()

        rerender(<SurrogatesPage />)

        expect(mockUseSurrogates).toHaveBeenLastCalledWith(
            expect.objectContaining({
                sort_by: 'last_modified_at',
                sort_order: 'desc',
            }),
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
