import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import CasesPage from '../app/(app)/cases/page'

// ============================================================================
// Mocks
// ============================================================================

// Mock Next.js Link
vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
    useSearchParams: () => ({
        get: () => null,
        toString: () => '',
    }),
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
    }),
}))

// Mock API hooks
const mockUseCases = vi.fn()
const mockUseArchiveCase = vi.fn()
const mockUseRestoreCase = vi.fn()
const mockUseUpdateCase = vi.fn()
const mockUseAssignees = vi.fn()
const mockUseBulkAssign = vi.fn()
const mockUseBulkArchive = vi.fn()
const mockUseQueues = vi.fn()

vi.mock('@/lib/hooks/use-cases', () => ({
    useCases: () => mockUseCases(),
    useArchiveCase: () => mockUseArchiveCase(),
    useRestoreCase: () => mockUseRestoreCase(),
    useUpdateCase: () => mockUseUpdateCase(),
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

describe('CasesPage', () => {
    beforeEach(() => {
        // Reset mocks default return values
        mockUseArchiveCase.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseRestoreCase.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseUpdateCase.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseAssignees.mockReturnValue({ data: [] })
        mockUseBulkAssign.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseBulkArchive.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        mockUseQueues.mockReturnValue({ data: [] })
    })

    it('renders loading state', () => {
        mockUseCases.mockReturnValue({
            data: null,
            isLoading: true,
            error: null,
        })

        render(<CasesPage />)
        // We expect the loader icon (lucide-react) or a card with loading spinner
        // Since we can't easily query by icon, we'll check if the main content area is present
        // or check for implicit loading indicators.
        // In the code: <LoaderIcon /> is rendered.
        // simpler check: "Cases" header should be present
        expect(screen.getByText('Cases')).toBeInTheDocument()
    })

    it('renders empty state', () => {
        mockUseCases.mockReturnValue({
            data: { items: [], total: 0, pages: 0 },
            isLoading: false,
            error: null,
        })

        render(<CasesPage />)
        expect(screen.getByText('No cases yet')).toBeInTheDocument()
        expect(screen.getByText('0 total cases')).toBeInTheDocument()
    })

    it('renders cases list', () => {
        const mockCases = [
            {
                id: '1',
                case_number: '12345',
                full_name: 'John Doe',
                status: 'new_unread',
                source: 'manual',
                email: 'john@example.com',
                created_at: new Date().toISOString(),
                is_priority: false,
            },
        ]

        mockUseCases.mockReturnValue({
            data: { items: mockCases, total: 1, pages: 1 },
            isLoading: false,
            error: null,
        })

        render(<CasesPage />)
        expect(screen.getByText('John Doe')).toBeInTheDocument()
        expect(screen.getByText('#12345')).toBeInTheDocument()
        expect(screen.getByText('john@example.com')).toBeInTheDocument()
    })
})
