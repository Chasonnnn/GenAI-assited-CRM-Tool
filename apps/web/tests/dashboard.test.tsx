import type { PropsWithChildren } from "react"
import * as React from "react"
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { ApiError } from '@/lib/api'
import { formatLocalDate } from '@/lib/utils/date'
import DashboardPage from '../app/(app)/dashboard/page'

const mockUseSearchParams = vi.fn()
const mockUseAuth = vi.fn()

type DynamicComponent = React.ComponentType<Record<string, unknown>>
type DynamicModule = DynamicComponent | { default: DynamicComponent }

const resolveDynamicModule = (mod: DynamicModule): DynamicComponent => {
    if (typeof mod === "function") {
        return mod
    }
    return mod.default
}

vi.mock("next/dynamic", () => ({
    __esModule: true,
    default: (loader: () => Promise<DynamicModule>) => {
        return function DynamicComponentWrapper(props: Record<string, unknown>) {
            const [Component, setComponent] = React.useState<DynamicComponent | null>(null)

            React.useEffect(() => {
                let mounted = true
                loader().then((mod) => {
                    const Resolved = resolveDynamicModule(mod)
                    if (mounted) {
                        setComponent(() => Resolved)
                    }
                })
                return () => {
                    mounted = false
                }
            }, [])

            if (!Component) return null
            return <Component {...props} />
        }
    },
}))

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
    useAuth: () => mockUseAuth(),
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
    useSurrogateStats: (params: unknown) => mockUseSurrogateStats(params),
    useAssignees: () => ({ data: [] }),
}))

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: unknown) => mockUseTasks(params),
    useCompleteTask: () => ({ mutateAsync: vi.fn() }),
    useUncompleteTask: () => ({ mutateAsync: vi.fn() }),
}))

vi.mock('@/lib/hooks/use-analytics', () => ({
    useSurrogatesTrend: (params: unknown) => mockUseSurrogatesTrend(params),
    useSurrogatesByStatus: (params: unknown) => mockUseSurrogatesByStatus(params),
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
        mockUseAuth.mockReturnValue({
            user: {
                display_name: 'Test Manager',
                ai_enabled: true,
                role: 'admin',
                user_id: 'user-1',
            },
        })
        mockUseSurrogateStats.mockReturnValue({
            data: {
                total: 10,
                this_week: 2,
                pending_tasks: 1,
                new_leads_24h: 3,
                by_status: { new_unread: 4 },
                last_week: 1,
                week_change_pct: 10,
                new_leads_prev_24h: 2,
                new_leads_change_pct: 50,
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

    it('renders stats cards with surrogate data', async () => {
        render(<DashboardPage />)

        // Check welcome header
        expect(screen.getByText(/Welcome back, Test/)).toBeInTheDocument()
        expect(screen.getByText('Portfolio health')).toBeInTheDocument()
        expect(screen.getByRole('link', { name: /review attention queue/i })).toBeInTheDocument()

        // Check stats cards
        const activeCard = screen.getByText('Active Surrogates').closest('[data-slot="card"]')
        expect(activeCard).not.toBeNull()
        expect(within(activeCard as HTMLElement).getByText('10')).toBeInTheDocument()
        expect(screen.getByText('My Tasks')).toBeInTheDocument()

        // Check chart sections exist
        expect(await screen.findByText('Surrogates Trend')).toBeInTheDocument()
        expect(await screen.findByText('Pipeline Distribution')).toBeInTheDocument()
    })

    it('shows restricted state for charts without reports access', async () => {
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

        const unavailable = await screen.findAllByText('Analytics unavailable')
        expect(unavailable.length).toBeGreaterThan(0)
    })

    it('shows contextual empty state when trend has no new surrogates', async () => {
        render(<DashboardPage />)

        expect(await screen.findByText('No new surrogates in the last 30 days')).toBeInTheDocument()
        expect(await screen.findByText('View surrogates')).toBeInTheDocument()
    })

    it('links attention surrogate cards to dynamic filters', async () => {
        mockUseAttention.mockReturnValue({
            data: {
                unreached_leads: [{ id: 's1', surrogate_number: 'S10001', stage_label: 'New', days_since_contact: 9, created_at: new Date().toISOString() }],
                unreached_count: 1,
                overdue_tasks: [],
                overdue_count: 0,
                stuck_surrogates: [{ id: 's2', surrogate_number: 'S10002', stage_label: 'Contacted', days_in_stage: 35, last_stage_change: new Date().toISOString() }],
                stuck_count: 1,
                total_count: 2,
            },
            isLoading: false,
            isError: false,
        })

        render(<DashboardPage />)

        const unreachedLink = await screen.findByText('Unreached leads (7+ days)')
        expect(unreachedLink.closest('a')).toHaveAttribute('href', '/surrogates?dynamic_filter=attention_unreached')

        const stuckLink = await screen.findByText('Stuck surrogates (30+ days)')
        expect(stuckLink.closest('a')).toHaveAttribute('href', '/surrogates?dynamic_filter=attention_stuck')
    })

    it('shows filter-empty state for pipeline distribution when range filters exclude all', async () => {
        mockUseSearchParams.mockReturnValue(new URLSearchParams('range=week'))

        render(<DashboardPage />)

        expect(await screen.findByText('No surrogates match your filters')).toBeInTheDocument()
        expect(await screen.findByText('Reset filters')).toBeInTheDocument()
    })

    it('uses consistent dashboard filters for all trend queries', async () => {
        mockUseSearchParams.mockReturnValue(new URLSearchParams('range=week&assignee=user-1'))
        mockUseSurrogatesTrend.mockClear()

        render(<DashboardPage />)

        await screen.findByText('Surrogates Trend')

        const trendCalls = mockUseSurrogatesTrend.mock.calls.map((call) => call[0] as Record<string, unknown>)
        expect(trendCalls.length).toBeGreaterThan(0)

        for (const params of trendCalls) {
            expect(params.owner_id).toBe('user-1')
            expect(typeof params.timezone).toBe('string')
            expect((params.timezone as string).length).toBeGreaterThan(0)
        }

        const fromDates = new Set(trendCalls.map((params) => params.from_date))
        const toDates = new Set(trendCalls.map((params) => params.to_date))
        expect(fromDates.size).toBe(1)
        expect(toDates.size).toBe(1)
    })

    it('scopes stale assignee filters back to the current non-admin user', async () => {
        mockUseAuth.mockReturnValue({
            user: {
                display_name: 'Case Manager',
                ai_enabled: true,
                role: 'case_manager',
                user_id: 'user-1',
            },
        })
        mockUseSearchParams.mockReturnValue(new URLSearchParams('range=week&assignee=user-2'))
        mockUseSurrogatesTrend.mockClear()
        mockUseSurrogatesByStatus.mockClear()
        mockUseSurrogateStats.mockClear()
        mockUseAttention.mockClear()
        mockUseUpcoming.mockClear()

        render(<DashboardPage />)

        await screen.findByText('Surrogates Trend')

        const trendCalls = mockUseSurrogatesTrend.mock.calls.map((call) => call[0] as Record<string, unknown>)
        expect(trendCalls.length).toBeGreaterThan(0)
        for (const params of trendCalls) {
            expect(params.owner_id).toBe('user-1')
        }

        const statusCalls = mockUseSurrogatesByStatus.mock.calls.map((call) => call[0] as Record<string, unknown>)
        expect(statusCalls.length).toBeGreaterThan(0)
        for (const params of statusCalls) {
            expect(params.owner_id).toBe('user-1')
        }

        const statsCalls = mockUseSurrogateStats.mock.calls.map((call) => call[0] as Record<string, unknown>)
        expect(statsCalls.length).toBeGreaterThan(0)
        expect(statsCalls[0].owner_id).toBe('user-1')

        const attentionCalls = mockUseAttention.mock.calls.map((call) => call[0] as Record<string, unknown>)
        expect(attentionCalls.length).toBeGreaterThan(0)
        expect(attentionCalls[0].assignee_id).toBe('user-1')

        const upcomingCalls = mockUseUpcoming.mock.calls.map((call) => call[0] as Record<string, unknown>)
        expect(upcomingCalls.length).toBeGreaterThan(0)
        expect(upcomingCalls[0].assignee_id).toBe('user-1')
    })

    it('formats KPI deltas without percent when values drop to zero', () => {
        mockUseSurrogateStats.mockReturnValue({
            data: {
                total: 10,
                this_week: 0,
                pending_tasks: 1,
                new_leads_24h: 0,
                by_status: { new_unread: 4 },
                last_week: 1,
                week_change_pct: -100,
                new_leads_prev_24h: 7,
                new_leads_change_pct: -100,
            },
            isLoading: false,
            isError: false,
        })

        render(<DashboardPage />)

        expect(screen.queryByText('-100%')).not.toBeInTheDocument()
        expect(screen.getByText('0 vs 7 last 24h')).toBeInTheDocument()
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

        fireEvent.click(screen.getByRole('button', { name: /Upcoming This Week/i }))

        expect(screen.getByText('Overdue tasks')).toBeInTheDocument()
        expect(screen.queryByText('Overdue Task 1')).not.toBeInTheDocument()
        expect(screen.queryByText('Week Task 1')).not.toBeInTheDocument()
    })
})
