import type { PropsWithChildren } from "react"
import * as React from "react"
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { ApiError } from '@/lib/api'
import { formatLocalDate } from '@/lib/utils/date'
import DashboardPage from '../app/(app)/dashboard/page'

const mockUseSearchParams = vi.fn()
const mockUseAuth = vi.fn()
const mockPush = vi.fn()

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
    useRouter: () => ({ replace: vi.fn(), push: mockPush }),
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
    Tooltip: () => <div />,
    LabelList: () => <div />,
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
const mockUseDonorsByStatus = vi.fn()
const mockUseAttention = vi.fn()
const mockUseUpcoming = vi.fn()
const mockUseEffectivePermissions = vi.fn()

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
    useDonorsByStatus: (params: unknown, options: unknown) => mockUseDonorsByStatus(params, options),
}))

vi.mock('@/lib/hooks/use-permissions', () => ({
    useEffectivePermissions: () => mockUseEffectivePermissions(),
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
        mockPush.mockClear()
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
        mockUseDonorsByStatus.mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() })
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ['view_dashboard', 'view_donors'] },
            isLoading: false,
        })
        mockUseAttention.mockReturnValue({
            data: {
                unreached_leads: [],
                unreached_count: 0,
                overdue_tasks: [],
                overdue_count: 0,
                stuck_surrogates: [],
                stuck_count: 0,
                stuck_donors: [],
                stuck_donor_count: 0,
                stuck_donor_counts: { egg: 0, sperm: 0 },
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

        // Check stats cards
        expect(screen.getByText('Active Surrogates')).toBeInTheDocument()
        expect(screen.getByText('10')).toBeInTheDocument()
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
                stuck_surrogates: [{ id: 's2', surrogate_number: 'S10002', stage_label: 'Contacted', days_in_stage: 100, last_stage_change: new Date().toISOString() }],
                stuck_count: 1,
                total_count: 2,
            },
            isLoading: false,
            isError: false,
        })

        render(<DashboardPage />)

        const unreachedLink = await screen.findByText('Unreached leads (7+ days)')
        expect(unreachedLink.closest('a')).toHaveAttribute('href', '/surrogates?dynamic_filter=attention_unreached')

        const stuckLink = await screen.findByText('Stuck surrogates (90+ days)')
        expect(stuckLink.closest('a')).toHaveAttribute('href', '/surrogates?dynamic_filter=attention_stuck')
        expect(screen.getByText('In stage for 90+ days')).toBeInTheDocument()

        const attentionCalls = mockUseAttention.mock.calls.map((call) => call[0] as Record<string, unknown>)
        expect(attentionCalls.length).toBeGreaterThan(0)
        for (const params of attentionCalls) {
            expect(params.days_stuck).toBe(90)
        }
    })

    it('shows filter-empty state for pipeline distribution when range filters exclude all', async () => {
        mockUseSearchParams.mockReturnValue(new URLSearchParams('range=week'))

        render(<DashboardPage />)

        expect(await screen.findByText('No surrogates match your filters')).toBeInTheDocument()
        expect(await screen.findByText('Reset filters')).toBeInTheDocument()
    })

    it('adds focus-visible styles to dashboard section toggles', () => {
        render(<DashboardPage />)

        expect(screen.getByRole('button', { name: /Attention Needed/i })).toHaveClass(
            'focus-visible:ring-2',
            'focus-visible:ring-ring',
            'focus-visible:ring-offset-2'
        )
        expect(screen.getByRole('button', { name: /Upcoming This Week/i })).toHaveClass(
            'focus-visible:ring-2',
            'focus-visible:ring-ring',
            'focus-visible:ring-offset-2'
        )
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

    it('uses browser-navigation assignee filters before issuing new dashboard requests', async () => {
        mockUseSearchParams.mockReturnValue(new URLSearchParams('assignee=user-1'))

        const { rerender } = render(<DashboardPage />)
        await screen.findByText('Surrogates Trend')

        mockUseSurrogateStats.mockClear()
        mockUseSurrogatesTrend.mockClear()
        mockUseSurrogatesByStatus.mockClear()
        mockUseAttention.mockClear()
        mockUseUpcoming.mockClear()
        mockUseSearchParams.mockReturnValue(new URLSearchParams('assignee=user-2'))

        rerender(<DashboardPage />)

        await waitFor(() => {
            const calls = mockUseSurrogateStats.mock.calls
                .map((call) => call[0] as Record<string, unknown> | undefined)
                .filter((params): params is Record<string, unknown> => params !== undefined)
            expect(calls.some((params) => params.owner_id === 'user-2')).toBe(true)
        })

        for (const [params] of mockUseSurrogateStats.mock.calls) {
            if (!params) continue
            expect((params as Record<string, unknown>).owner_id).toBe('user-2')
        }
        for (const [params] of mockUseSurrogatesTrend.mock.calls) {
            if (!params) continue
            expect((params as Record<string, unknown>).owner_id).toBe('user-2')
        }
        for (const [params] of mockUseSurrogatesByStatus.mock.calls) {
            if (!params) continue
            expect((params as Record<string, unknown>).owner_id).toBe('user-2')
        }
        for (const [params] of mockUseAttention.mock.calls) {
            if (!params) continue
            expect((params as Record<string, unknown>).assignee_id).toBe('user-2')
        }
        for (const [params] of mockUseUpcoming.mock.calls) {
            if (!params) continue
            expect((params as Record<string, unknown>).assignee_id).toBe('user-2')
        }
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

    it('shows the donor number for donor-linked upcoming tasks', async () => {
        const today = formatLocalDate(new Date())
        mockUseUpcoming.mockReturnValue({
            data: {
                tasks: [
                    {
                        id: 'donor-task-1',
                        type: 'task',
                        title: 'Review donor application',
                        time: null,
                        surrogate_id: null,
                        surrogate_number: null,
                        donor_id: 'donor-1',
                        donor_number: 'D10001',
                        donor_type: 'egg',
                        date: today,
                        is_overdue: false,
                        task_type: 'other',
                    },
                ],
                meetings: [],
            },
            isLoading: false,
            isError: false,
        })

        render(<DashboardPage />)
        fireEvent.click(screen.getByRole('button', { name: /Upcoming This Week/i }))

        expect(await screen.findByText('D10001')).toBeInTheDocument()
    })

    it('hides donor pipeline selectors when donor access is revoked', async () => {
        mockUseAuth.mockReturnValue({
            user: {
                display_name: 'Test Manager',
                role: 'admin',
                user_id: 'user-1',
            },
        })
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ['view_dashboard'] },
            isLoading: false,
        })

        render(<DashboardPage />)

        expect(await screen.findByText('Pipeline Distribution')).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Egg Donors' })).not.toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Sperm Donors' })).not.toBeInTheDocument()
    })

    it('links egg donor stage bars to the egg donor tab and stage filter', async () => {
        mockUseDonorsByStatus.mockImplementation((params: { donor_type: string }) => ({
            data: params.donor_type === 'egg'
                ? [{ status: 'New', stage_id: 'egg-stage', count: 3, order: 1 }]
                : [],
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        }))

        render(<DashboardPage />)
        fireEvent.click(await screen.findByRole('button', { name: 'Egg Donors' }))

        const link = await screen.findByRole('link', { name: 'View New egg donors' })
        expect(link).toHaveAttribute('href', '/donors?type=egg&stage=egg-stage')
    })

    it('carries the dashboard week boundaries into donor stage drilldowns', async () => {
        mockUseSearchParams.mockReturnValue(new URLSearchParams('range=week'))
        mockUseDonorsByStatus.mockImplementation((params: { donor_type: string }) => ({
            data: params.donor_type === 'egg'
                ? [{ status: 'New', stage_id: 'egg-stage', count: 3, order: 1 }]
                : [],
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        }))
        const today = new Date()
        const sunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay())

        render(<DashboardPage />)
        fireEvent.click(await screen.findByRole('button', { name: 'Egg Donors' }))

        const link = await screen.findByRole('link', { name: 'View New egg donors' })
        expect(link).toHaveAttribute(
            'href',
            `/donors?type=egg&stage=egg-stage&range=week&from=${formatLocalDate(sunday)}&to=${formatLocalDate(today)}`,
        )
    })

    it('shows the donor empty state instead of a zero-value stage chart', async () => {
        mockUseDonorsByStatus.mockImplementation((params: { donor_type: string }) => ({
            data: params.donor_type === 'egg'
                ? Array.from({ length: 10 }, (_, index) => ({
                    status: `Stage ${index + 1}`,
                    stage_id: `egg-stage-${index + 1}`,
                    count: 0,
                    order: index + 1,
                }))
                : [],
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        }))

        render(<DashboardPage />)
        fireEvent.click(await screen.findByRole('button', { name: 'Egg Donors' }))

        expect(await screen.findByText('No egg donors yet')).toBeInTheDocument()
        expect(screen.queryByRole('link', { name: 'View Stage 1 egg donors' })).not.toBeInTheDocument()
    })

    it('uses donor detail and subtype-filtered links for stuck donors', async () => {
        mockUseAttention.mockReturnValue({
            data: {
                unreached_leads: [],
                unreached_count: 0,
                overdue_tasks: [],
                overdue_count: 0,
                stuck_surrogates: [],
                stuck_count: 0,
                stuck_donors: [{
                    id: 'donor-1',
                    donor_number: 'D10001',
                    donor_type: 'egg',
                    stage_label: 'Contacted',
                    days_in_stage: 100,
                    last_stage_change: new Date().toISOString(),
                }],
                stuck_donor_count: 3,
                stuck_donor_counts: { egg: 1, sperm: 2 },
                total_count: 3,
            },
            isLoading: false,
            isError: false,
        })

        render(<DashboardPage />)

        const eggDonorLink = await screen.findByText('Stuck egg donors (90+ days)')
        expect(eggDonorLink.closest('a')).toHaveAttribute('href', '/donors/donor-1')
        const spermDonorLink = await screen.findByText('Stuck sperm donors (90+ days)')
        expect(spermDonorLink.closest('a')).toHaveAttribute(
            'href',
            '/donors?type=sperm&dynamic_filter=attention_stuck',
        )

        const attentionSection = screen.getByText('Attention Needed').closest('section')
        expect(attentionSection).not.toBeNull()
        fireEvent.click(within(attentionSection!).getByRole('button', { name: 'View all' }))
        expect(await screen.findByRole('link', { name: 'Stuck egg donors' })).toHaveAttribute(
            'href',
            '/donors?type=egg&dynamic_filter=attention_stuck',
        )
        expect(screen.getByRole('link', { name: 'Stuck sperm donors' })).toHaveAttribute(
            'href',
            '/donors?type=sperm&dynamic_filter=attention_stuck',
        )
    })

    it('hides stuck donor rows and View all links without donor permission', async () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ['view_dashboard'] },
            isLoading: false,
        })
        mockUseAttention.mockReturnValue({
            data: {
                unreached_leads: [],
                unreached_count: 0,
                overdue_tasks: [],
                overdue_count: 0,
                stuck_surrogates: [],
                stuck_count: 0,
                stuck_donors: [{
                    id: 'donor-1',
                    donor_number: 'D10001',
                    donor_type: 'egg',
                    stage_label: 'Contacted',
                    days_in_stage: 100,
                    last_stage_change: new Date().toISOString(),
                }],
                stuck_donor_count: 1,
                stuck_donor_counts: { egg: 1, sperm: 0 },
                total_count: 1,
            },
            isLoading: false,
            isError: false,
        })

        render(<DashboardPage />)

        expect(screen.queryByText('Stuck egg donors (90+ days)')).not.toBeInTheDocument()
        const attentionSection = screen.getByText('Attention Needed').closest('section')
        fireEvent.click(within(attentionSection!).getByRole('button', { name: 'View all' }))
        expect(screen.queryByRole('link', { name: 'Stuck egg donors' })).not.toBeInTheDocument()
        expect(screen.queryByRole('link', { name: 'Stuck sperm donors' })).not.toBeInTheDocument()
    })
})
