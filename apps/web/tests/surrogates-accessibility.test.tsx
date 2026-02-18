import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SurrogatesPage from '../app/(app)/surrogates/page'
import { SurrogateOverviewTab } from '../components/surrogates/detail/tabs/SurrogateOverviewTab'
import { InlineEditField } from '../components/inline-edit-field'
import { InlineDateField } from '../components/inline-date-field'
import { Tabs } from '@/components/ui/tabs'

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
    useParams: () => ({ id: '1' }),
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
    useSurrogateActivity: () => ({ data: { items: [] } }),
    useSurrogateHistory: () => ({ data: [] }),
}))

vi.mock('@/lib/hooks/use-queues', () => ({
    useQueues: (...args: unknown[]) => mockUseQueues(...args),
}))

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: () => ({ data: { items: [] } }),
}))

// Mock Auth
vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { role: 'case_manager' } }), // Ensure role allows assign
}))

// Mock UI components
vi.mock('@/components/ui/date-range-picker', () => ({
    DateRangePicker: () => <div data-testid="date-picker">Date Picker</div>,
}))

vi.mock('@/lib/hooks/use-pipelines', () => ({
    useDefaultPipeline: () => ({
        data: {
            id: 'p1',
            stages: [
                { id: 's1', slug: 'new_unread', label: 'New Unread', color: '#3b82f6', stage_type: 'intake', is_active: true },
            ],
        },
        isLoading: false,
    }),
}))

// Mock Context for Tab
const mockSurrogateContext = {
    surrogate: {
        id: '1',
        full_name: 'Jane Doe',
        email: 'jane@example.com',
        created_at: new Date().toISOString(),
        stage_id: 's1',
        source: 'manual',
    },
}

vi.mock('@/components/surrogates/detail/SurrogateDetailContext', () => ({
    useSurrogateDetailContext: () => mockSurrogateContext,
}))

describe('SurrogatesPage Accessibility', () => {
    beforeEach(() => {
        // Reset mocks default return values
        mockSearchParams.delete('page')
        mockUseSurrogates.mockReturnValue({
            data: {
                items: [
                    {
                        id: '1',
                        surrogate_number: 'S12345',
                        full_name: 'John Doe',
                        stage_id: 's1',
                        status_label: 'New Unread',
                        source: 'manual',
                        email: 'john@example.com',
                        created_at: new Date().toISOString(),
                        is_priority: false,
                        is_archived: false,
                    }
                ],
                total: 1,
                pages: 1
            },
            isLoading: false,
            error: null,
        })
        mockUseAssignees.mockReturnValue({ data: [{ id: 'u1', name: 'User 1' }] })
        mockUseBulkAssign.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseBulkArchive.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseQueues.mockReturnValue({ data: [] })
        mockUseCreateSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseUpdateSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseArchiveSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseRestoreSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    })

    it('renders search input with aria-label', () => {
        render(<SurrogatesPage />)
        expect(screen.getByLabelText('Search surrogates')).toBeInTheDocument()
    })

    it('renders table checkboxes with aria-labels', () => {
        render(<SurrogatesPage />)
        expect(screen.getByLabelText('Select all surrogates')).toBeInTheDocument()
        expect(screen.getByLabelText('Select John Doe')).toBeInTheDocument()
    })

    it('renders assign dropdown with aria-label when items selected', async () => {
        render(<SurrogatesPage />)

        // Select one item to show floating bar
        const checkbox = screen.getByLabelText('Select John Doe')
        fireEvent.click(checkbox)

        // Now floating bar should appear
        expect(screen.getByText('1 surrogate selected')).toBeInTheDocument()

        // Check for Assign button aria-label
        expect(screen.getByLabelText('Assign to user')).toBeInTheDocument()
    })
})

describe('SurrogateOverviewTab Accessibility', () => {
    it('renders copy email button with aria-label', () => {
        render(
            <Tabs defaultValue="overview">
                <SurrogateOverviewTab />
            </Tabs>
        )
        expect(screen.getByLabelText('Copy email')).toBeInTheDocument()
    })
})

describe('Inline Field Accessibility', () => {
    it('adds contextual labels to InlineEditField save/cancel icon buttons', () => {
        render(
            <InlineEditField
                value="test@example.com"
                label="Email"
                onSave={vi.fn().mockResolvedValue(undefined)}
            />
        )

        fireEvent.click(screen.getByRole("button"))

        expect(screen.getByRole("button", { name: "Save Email" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Cancel Email" })).toBeInTheDocument()
    })

    it('adds contextual labels to InlineEditField trigger/input with placeholder fallback', () => {
        render(
            <InlineEditField
                value="Acme Health"
                placeholder="Insurance Company"
                onSave={vi.fn().mockResolvedValue(undefined)}
            />
        )

        const trigger = screen.getByRole("button", { name: "Edit Insurance Company" })
        fireEvent.click(trigger)

        expect(screen.getByRole("textbox", { name: "Insurance Company" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Save Insurance Company" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Cancel Insurance Company" })).toBeInTheDocument()
    })

    it('adds contextual labels to InlineDateField save/cancel icon buttons', () => {
        render(
            <InlineDateField
                value="2026-01-05"
                label="Start Date"
                onSave={vi.fn().mockResolvedValue(undefined)}
            />
        )

        fireEvent.click(screen.getByRole("button"))

        expect(screen.getByRole("button", { name: "Save Start Date" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Cancel Start Date" })).toBeInTheDocument()
    })
})
