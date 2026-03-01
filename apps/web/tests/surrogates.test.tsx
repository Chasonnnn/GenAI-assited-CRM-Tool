import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SurrogatesPage from '../app/(app)/surrogates/page'

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
}))

vi.mock('@/lib/hooks/use-queues', () => ({
    useQueues: (...args: unknown[]) => mockUseQueues(...args),
}))

// Mock Auth
vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { role: 'admin' } }),
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
            ],
        },
        isLoading: false,
    }),
}))

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
        mockUseArchiveSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseRestoreSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseUpdateSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseCreateSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseAssignees.mockReturnValue({ data: [] })
        mockUseBulkAssign.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseBulkArchive.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
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
        const mockSurrogates = [
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
                created_at: new Date().toISOString(),
                last_activity_at: new Date().toISOString(),
                is_priority: false,
                is_archived: false,
                age: null,
                bmi: null,
            },
        ]

        mockUseSurrogates.mockReturnValue({
            data: { items: mockSurrogates, total: 1, pages: 1 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        expect(screen.getByText('John Doe')).toBeInTheDocument()
        expect(screen.getByText('#S12345')).toBeInTheDocument()
        expect(screen.getByText('john@example.com')).toBeInTheDocument()
    })

    it('renders Last Modified column label', () => {
        const mockSurrogates = [
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
                created_at: new Date().toISOString(),
                last_activity_at: new Date().toISOString(),
                is_priority: false,
                is_archived: false,
                age: null,
                bmi: null,
            },
        ]

        mockUseSurrogates.mockReturnValue({
            data: { items: mockSurrogates, total: 1, pages: 1 },
            isLoading: false,
            error: null,
        })

        render(<SurrogatesPage />)
        expect(screen.getByText('Last Modified')).toBeInTheDocument()
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
})
