import type { PropsWithChildren } from "react"
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ApiError } from '@/lib/api'
import { formatLocalDate } from '@/lib/utils/date'
import DashboardPage from '../app/(app)/dashboard/page'

const mockUseSearchParams = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
    useSearchParams: () => mockUseSearchParams(),
}))

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({
        user: {
            display_name: 'Test Manager',
            ai_enabled: true,
            role: 'admin',
            user_id: 'user-1',
        },
    }),
}))

vi.mock('recharts', () => ({
    Area: ({ children }: PropsWithChildren) => <div>{children}</div>,
    AreaChart: ({ children }: PropsWithChildren) => <div>{children}</div>,
    Bar: ({ children }: PropsWithChildren) => <div>{children}</div>,
    BarChart: ({ children }: PropsWithChildren) => <div>{children}</div>,
    CartesianGrid: () => <div />,
    XAxis: () => <div />,
    YAxis: () => <div />,
    Cell: () => <div />,
}))

vi.mock('@/components/ui/chart', () => ({
    ChartContainer: ({ children }: PropsWithChildren) => <div>{children}</div>,
    ChartTooltip: ({ children }: PropsWithChildren) => <div>{children}</div>,
    ChartTooltipContent: () => <div />,
}))

const mockUseSurrogateStats = vi.fn()
const mockUseTasks = vi.fn()
const mockUseSurrogatesTrend = vi.fn()
const mockUseSurrogatesByStatus = vi.fn()
const mockUseAttention = vi.fn()
const mockUseUpcoming = vi.fn()

vi.mock('@/lib/hooks/use-surrogates', () => ({
    useSurrogateStats: () => mockUseSurrogateStats(),
    useAssignees: () => ({ data: [] }),
}))

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: unknown) => mockUseTasks(params),
    useCompleteTask: () => ({ mutateAsync: vi.fn() }),
    useUncompleteTask: () => ({ mutateAsync: vi.fn() }),
}))

vi.mock('@/lib/hooks/use-analytics', () => ({
    useSurrogatesTrend: (params: unknown) => mockUseSurrogatesTrend(params),
    useSurrogatesByStatus: () => mockUseSurrogatesByStatus(),
}))

vi.mock('@/lib/hooks/use-dashboard', () => ({
    useAttention: (params: unknown) => mockUseAttention(params),
    useUpcoming: (params: unknown) => mockUseUpcoming(params),
}))

vi.mock('@/lib/hooks/use-pipelines', () => ({
    usePipelines: () => ({
        data: [
            { id: 'p1', name: 'Default Pipeline', is_default: true },
        ],
        isLoading: false,
    }),
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

vi.mock('@/lib/hooks/use-dashboard-socket', () => ({
    useDashboardSocket: () => { },
}))

describe('DashboardPage', () => {
    beforeEach(() => {
        mockUseSearchParams.mockReturnValue(new URLSearchParams())
        mockUseSurrogateStats.mockReturnValue({
            data: {
                total: 10,
                this_week: 2,
                pending_tasks: 1,
                this_month: 3,
                by_status: { new_unread: 4 },
                last_week: 1,
                week_change_pct: 10,
                last_month: 2,
                month_change_pct: 50,
            },
            isLoading: false,
        })

        mockUseTasks.mockReturnValue({
            data: { items: [], total: 0 },
            isLoading: false,
        })

        mockUseSurrogatesTrend.mockReturnValue({ data: [], isLoading: false, isError: false })
        mockUseSurrogatesByStatus.mockReturnValue({ data: [], isLoading: false, isError: false })
        mockUseAttention.mockReturnValue({
            data: {
                unreached_leads: [],
                unreached_count: 0,
                overdue_tasks: [],
                overdue_count: 0,
                stuck_surrogates: [],
                stuck_count: 0,
                total_count: 0,
            },
            isLoading: false,
            isError: false,
        })
        mockUseUpcoming.mockReturnValue({
            data: { tasks: [], meetings: [] },
            isLoading: false,
            isError: false,
        })
    })

    it('renders stats cards with surrogate data', () => {
        render(<DashboardPage />)

        // Check welcome header
        expect(screen.getByText(/Welcome back, Test/)).toBeInTheDocument()

        // Check stats cards
        expect(screen.getByText('Active Surrogates')).toBeInTheDocument()
        expect(screen.getByText('10')).toBeInTheDocument()
        expect(screen.getByText('My Tasks')).toBeInTheDocument()

        // Check chart sections exist
        expect(screen.getByText('Surrogates Trend')).toBeInTheDocument()
        expect(screen.getByText('Pipeline Distribution')).toBeInTheDocument()
    })

    it('shows restricted state for charts without reports access', () => {
        mockUseSurrogatesTrend.mockReturnValue({
            data: [],
            isLoading: false,
            isError: true,
            error: new ApiError(403, 'Forbidden'),
        })
        mockUseSurrogatesByStatus.mockReturnValue({
            data: [],
            isLoading: false,
            isError: true,
            error: new ApiError(403, 'Forbidden'),
        })

        render(<DashboardPage />)

        expect(screen.getAllByText('Analytics unavailable').length).toBeGreaterThan(0)
    })

    it('shows contextual empty state when trend has no new surrogates', () => {
        render(<DashboardPage />)

        expect(screen.getByText('No new surrogates in this period')).toBeInTheDocument()
        expect(screen.getByText('View surrogates')).toBeInTheDocument()
        expect(screen.getByText('Adjust date range')).toBeInTheDocument()
    })

    it('shows filter-empty state for pipeline distribution when range filters exclude all', () => {
        mockUseSearchParams.mockReturnValue(new URLSearchParams('range=week'))

        render(<DashboardPage />)

        expect(screen.getByText('No surrogates match your filters')).toBeInTheDocument()
        expect(screen.getByText('Reset filters')).toBeInTheDocument()
    })

    it('formats KPI deltas without percent when values drop to zero', () => {
        mockUseSurrogateStats.mockReturnValue({
            data: {
                total: 10,
                this_week: 0,
                pending_tasks: 1,
                this_month: 0,
                by_status: { new_unread: 4 },
                last_week: 1,
                week_change_pct: -100,
                last_month: 7,
                month_change_pct: -100,
            },
            isLoading: false,
            isError: false,
        })

        render(<DashboardPage />)

        expect(screen.queryByText('-100%')).not.toBeInTheDocument()
        expect(screen.getByText('0 vs 7 last month')).toBeInTheDocument()
    })

    it('limits upcoming list and collapses overdue items', () => {
        const today = new Date()
        const tomorrow = new Date(today)
        tomorrow.setDate(today.getDate() + 1)
        const later = new Date(today)
        later.setDate(today.getDate() + 3)
        const yesterday = new Date(today)
        yesterday.setDate(today.getDate() - 1)

        mockUseUpcoming.mockReturnValue({
            data: {
                tasks: [
                    { id: 'o1', type: 'task', title: 'Overdue Task 1', time: null, surrogate_id: null, surrogate_number: null, date: formatLocalDate(yesterday), is_overdue: true, task_type: 'other' },
                    { id: 'o2', type: 'task', title: 'Overdue Task 2', time: null, surrogate_id: null, surrogate_number: null, date: formatLocalDate(yesterday), is_overdue: true, task_type: 'other' },
                    { id: 'o3', type: 'task', title: 'Overdue Task 3', time: null, surrogate_id: null, surrogate_number: null, date: formatLocalDate(yesterday), is_overdue: true, task_type: 'other' },
                    { id: 'o4', type: 'task', title: 'Overdue Task 4', time: null, surrogate_id: null, surrogate_number: null, date: formatLocalDate(yesterday), is_overdue: true, task_type: 'other' },
                    { id: 't1', type: 'task', title: 'Today Task 1', time: null, surrogate_id: null, surrogate_number: null, date: formatLocalDate(today), is_overdue: false, task_type: 'other' },
                    { id: 't2', type: 'task', title: 'Today Task 2', time: null, surrogate_id: null, surrogate_number: null, date: formatLocalDate(today), is_overdue: false, task_type: 'other' },
                    { id: 'tm1', type: 'task', title: 'Tomorrow Task 1', time: null, surrogate_id: null, surrogate_number: null, date: formatLocalDate(tomorrow), is_overdue: false, task_type: 'other' },
                    { id: 'tm2', type: 'task', title: 'Tomorrow Task 2', time: null, surrogate_id: null, surrogate_number: null, date: formatLocalDate(tomorrow), is_overdue: false, task_type: 'other' },
                    { id: 'w1', type: 'task', title: 'Week Task 1', time: null, surrogate_id: null, surrogate_number: null, date: formatLocalDate(later), is_overdue: false, task_type: 'other' },
                ],
                meetings: [],
            },
            isLoading: false,
            isError: false,
        })

        render(<DashboardPage />)

        expect(screen.getByText('Overdue tasks')).toBeInTheDocument()
        expect(screen.queryByText('Overdue Task 1')).not.toBeInTheDocument()
        expect(screen.queryByText('Week Task 1')).not.toBeInTheDocument()
    })
})
