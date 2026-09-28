import type { PropsWithChildren } from "react"
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

const dynamicState = vi.hoisted(() => ({
    policyVersion: 1,
    canViewOrgReports: true,
    calls: [] as Array<{ options?: { ssr?: boolean } }>,
}))

vi.mock('next/dynamic', () => ({
    __esModule: true,
    default: (_loader: unknown, options: { ssr?: boolean; loading?: () => unknown } = {}) => {
        dynamicState.calls.push({ options })
        return () => (options.loading ? options.loading() : null)
    },
}))

import ReportsPage from '../app/(app)/reports/page'
import { ReportsChartsGrid } from '../app/(app)/reports/components/ReportsChartsGrid'

const MAX_CARD_ENTRANCE_DELAY_MS = 300

// Reads both inline animation-delay and delay-* utilities so the cap holds for either styling approach.
function getEntranceDelayMs(card: HTMLElement) {
    const inlineDelay = card.style.animationDelay
    const inlineDelayMs = inlineDelay
        ? parseFloat(inlineDelay) * (inlineDelay.endsWith('ms') ? 1 : 1000)
        : 0
    const classDelaysMs = Array.from(card.classList).flatMap((name) => {
        const match = /^delay-(?:\[(\d+)ms\]|(\d+))$/.exec(name)
        return match ? [Number(match[1] ?? match[2])] : []
    })
    return Math.max(inlineDelayMs, ...classDelaysMs)
}

function expectHeldCardEntrances(container: HTMLElement) {
    const animatedCards = Array.from(
        container.querySelectorAll<HTMLElement>('[data-slot="card"].animate-in'),
    )
    expect(animatedCards.length).toBeGreaterThan(0)
    for (const card of animatedCards) {
        // Without a backwards fill, delayed cards render at full opacity and then drop to the start opacity.
        expect(card.className).toMatch(/\bfill-mode-(backwards|both)\b/)
        expect(getEntranceDelayMs(card)).toBeLessThanOrEqual(MAX_CARD_ENTRANCE_DELAY_MS)
    }
}

const accessState = vi.hoisted(() => ({
    role: 'admin',
    permissions: ['view_reports', 'view_donors'] as string[],
    summaryCalls: 0,
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { ai_enabled: true, user_id: 'user-1', role: accessState.role }, isLoading: false }),
}))

// The denied state's Dashboard link is an AppLink, which needs the app router.
vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}))

vi.mock('@/lib/hooks/use-permissions', () => ({
    useEffectivePermissions: () => ({
        data: {
            permissions: accessState.permissions,
            policy_version: dynamicState.policyVersion,
            capabilities: { can_view_org_reports: dynamicState.canViewOrgReports },
        },
        isLoading: false,
    }),
}))

vi.mock('@/lib/hooks/use-pipelines', () => ({
    useDefaultPipeline: () => ({
        data: {
            id: 'pipeline-1',
            stages: [
                {
                    id: 'stage-1',
                    stage_key: 'new_unread',
                    slug: 'new_unread',
                    label: 'New Unread',
                    color: '#3B82F6',
                    order: 1,
                    stage_type: 'intake',
                    is_active: true,
                },
            ],
        },
        isLoading: false,
    }),
}))

vi.mock('recharts', () => ({
    Bar: ({ children }: PropsWithChildren) => <div>{children}</div>,
    BarChart: ({ children }: PropsWithChildren) => <div>{children}</div>,
    CartesianGrid: () => <div />,
    XAxis: () => <div />,
    YAxis: () => <div />,
    Line: ({ children }: PropsWithChildren) => <div>{children}</div>,
    LineChart: ({ children }: PropsWithChildren) => <div>{children}</div>,
    Pie: ({ children }: PropsWithChildren) => <div>{children}</div>,
    PieChart: ({ children }: PropsWithChildren) => <div>{children}</div>,
}))

vi.mock('@/components/ui/chart', () => ({
    ChartContainer: ({ children }: PropsWithChildren) => <div>{children}</div>,
    ChartTooltip: ({ children }: PropsWithChildren) => <div>{children}</div>,
    ChartTooltipContent: () => <div />,
    ChartLegend: ({ children }: PropsWithChildren) => <div>{children}</div>,
    ChartLegendContent: () => <div />,
}))

vi.mock('@/components/charts/funnel-chart', () => ({
    FunnelChart: () => <div data-testid="funnel-chart" />,
}))

vi.mock('@/components/charts/us-map-chart', () => ({
    USMapChart: () => <div data-testid="us-map-chart" />,
}))

vi.mock('@/components/reports/TeamPerformanceTable', () => ({
    TeamPerformanceTable: () => <div data-testid="team-performance-table" />,
}))

vi.mock('@/components/reports/TeamPerformanceChart', () => ({
    TeamPerformanceChart: () => <div data-testid="team-performance-chart" />,
}))

vi.mock('@/components/ui/date-range-picker', () => ({
    DateRangePicker: () => <div data-testid="date-range-picker" />,
}))

vi.mock('@/lib/hooks/use-analytics', () => ({
    useAnalyticsSummary: () => {
        accessState.summaryCalls += 1
        return {
            data: {
                total_surrogates: 42,
                new_this_period: 5,
                qualification_rate: 10,
                qualification_stage_key: 'pre_qualified',
                avg_time_to_qualification_hours: 48,
            },
            isLoading: false,
        }
    },
    useSurrogatesByStatus: () => ({ data: [{ status: 'new_unread', count: 1 }], isLoading: false }),
    useSurrogatesByAssignee: () => ({ data: [{ user_email: 'alice@example.com', count: 2 }], isLoading: false }),
    useSurrogatesTrend: () => ({ data: [{ date: '2025-01-01', count: 1 }], isLoading: false }),
    useMetaPerformance: () => ({
        data: {
            qualified_rate: 40,
            qualification_stage_key: 'pre_qualified',
            conversion_rate: 20,
            conversion_stage_key: 'application_submitted',
            leads_qualified: 4,
            leads_converted: 2,
            leads_received: 10,
            avg_time_to_convert_hours: 72,
        },
        isLoading: false,
    }),
    useMetaAdAccounts: () => ({ data: [{ id: 'ad-1', ad_account_name: 'Test Account' }], isLoading: false }),
    useSpendTotals: () => ({
        data: {
            total_spend: 1000,
            total_impressions: 5000,
            total_clicks: 250,
            total_leads: 20,
            cost_per_lead: 12.34,
            sync_status: 'synced',
            last_synced_at: null,
            ad_accounts_configured: 1,
        },
        isLoading: false,
    }),
    useSpendByCampaign: () => ({ data: [], isLoading: false }),
    useSpendByBreakdown: () => ({ data: [], isLoading: false }),
    useSpendTrend: () => ({ data: [], isLoading: false }),
    useFormPerformance: () => ({ data: [], isLoading: false }),
    useFunnelCompare: () => ({ data: null, isLoading: false }),
    useSurrogatesByStateCompare: () => ({ data: null, isLoading: false }),
    useCampaigns: () => ({ data: [], isLoading: false }),
    usePerformanceByUser: () => ({
        data: {
            from_date: '2025-01-01',
            to_date: '2025-01-31',
            mode: 'cohort',
            as_of: '2025-01-31T00:00:00Z',
            pipeline_id: 'pipeline-1',
            columns: [
                { stage_key: 'contacted', label: 'Contacted', color: '#10B981', order: 1 },
                { stage_key: 'matched', label: 'Matched', color: '#3B82F6', order: 2 },
            ],
            match_stage_key: 'matched',
            conversion_stage_key: 'application_submitted',
            data: [],
            unassigned: { total_surrogates: 0, archived_count: 0, stage_counts: {} },
        },
        isLoading: false,
    }),
    useDonorAnalyticsSummary: () => ({
        data: {
            donor_type: 'egg',
            total_donors: 7,
            new_this_period: 2,
            qualification_rate: 25,
            qualification_stage_key: 'ready_to_match',
            avg_time_to_qualification_hours: 96,
        },
        isLoading: false,
        isError: false,
    }),
    useDonorsByStatus: () => ({
        data: [{ status: 'New', stage_id: 'stage-1', count: 7, order: 1 }],
        isLoading: false,
        isError: false,
    }),
    useDonorsTrend: () => ({
        data: [{ date: '2025-01-01', count: 2 }],
        isLoading: false,
        isError: false,
    }),
}))

describe('ReportsPage', () => {
    beforeEach(() => {
        accessState.role = 'admin'
        accessState.permissions = ['view_reports', 'view_donors']
        accessState.summaryCalls = 0
        dynamicState.policyVersion = 1
        dynamicState.canViewOrgReports = true
    })

    it('lazy loads report visualizations', () => {
        expect(dynamicState.calls.length).toBeGreaterThan(0)
        expect(dynamicState.calls.some((call) => call.options?.ssr === false)).toBe(true)
    })

    it('renders report summary cards', () => {
        render(<ReportsPage />)
        expect(screen.getByRole('heading', { level: 1, name: 'Reports' })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Export PDF' })).toBeInTheDocument()
        expect(screen.getByRole('combobox', { name: 'Filter by campaign' })).toHaveTextContent('All campaigns')
        expect(screen.getByText('42')).toBeInTheDocument()
        expect(screen.getAllByText('$1,000').length).toBeGreaterThan(0)
        expect(screen.getByRole('heading', { name: 'Donors' })).toBeInTheDocument()
        expect(screen.getByText('Egg Donors by Stage')).toBeInTheDocument()
        expect(screen.getByText('Egg Donors Creation Trend')).toBeInTheDocument()
        expect(screen.getAllByText('7').length).toBeGreaterThan(0)
    })

    it('holds the start state of staggered summary cards through a capped delay', () => {
        const { container } = render(<ReportsPage />)
        expectHeldCardEntrances(container)
    })

    it('holds the start state of staggered chart cards through a capped delay', () => {
        const { container } = render(
            <ReportsChartsGrid
                aiEnabled
                statusChartData={[{ status: 'New Unread', count: 1, fill: '#3B82F6' }]}
                trendChartData={[{ date: '2025-01-01', count: 1 }]}
                assigneeChartData={[{ member: 'Alice', count: 2 }]}
                topStatus={{ status: 'New Unread', count: 1, fill: '#3B82F6' }}
                topPerformer={{ member: 'Alice', count: 2 }}
                totalSurrogatesInPeriod={1}
                computeTrendPercentage={null}
                metaPerf={null}
                byStatusLoading={false}
                byStatusError={false}
                trendLoading={false}
                trendError={false}
                byAssigneeLoading={false}
                byAssigneeError={false}
                metaLoading={false}
                metaError={false}
            />,
        )
        expect(container.querySelectorAll('[data-slot="card"].animate-in')).toHaveLength(4)
        expectHeldCardEntrances(container)
    })

    it('keeps chart cards inside a single shrinkable column below md', () => {
        // Without an explicit column the auto track grows to the chart width and clips cards at 390px.
        const { container } = render(
            <ReportsChartsGrid
                aiEnabled={false}
                statusChartData={[]}
                trendChartData={[]}
                assigneeChartData={[]}
                topStatus={null}
                topPerformer={null}
                totalSurrogatesInPeriod={0}
                computeTrendPercentage={null}
                metaPerf={null}
                byStatusLoading={false}
                byStatusError={false}
                trendLoading={false}
                trendError={false}
                byAssigneeLoading={false}
                byAssigneeError={false}
                metaLoading={false}
                metaError={false}
            />,
        )
        const grid = container.querySelector('[data-slot="card"]')?.parentElement
        expect(grid).toHaveClass('grid', 'grid-cols-1', 'md:grid-cols-2', '[&>*]:min-w-0')
    })

    it('keeps individual performance cards inside a single shrinkable column below lg', () => {
        render(<ReportsPage />)
        const grid = screen.getByTestId('team-performance-table').parentElement
        expect(grid).toHaveClass('grid', 'grid-cols-1', 'lg:grid-cols-2', '[&>*]:min-w-0')
    })

    it('shows the denied state without report queries or Export PDF when view_reports is missing', () => {
        accessState.role = 'case_manager'
        accessState.permissions = ['view_dashboard']
        render(<ReportsPage />)

        expect(screen.getByRole('heading', { level: 1, name: 'Reports' })).toBeInTheDocument()
        expect(screen.getByRole('heading', { level: 2, name: 'Permission required' })).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Export PDF' })).not.toBeInTheDocument()
        expect(screen.queryByText('Unable to load')).not.toBeInTheDocument()
        expect(accessState.summaryCalls).toBe(0)
    })

    it('shows the denied state to intake specialists under policy v1, whose reports API rejects them', () => {
        accessState.role = 'intake_specialist'
        accessState.permissions = ['view_dashboard', 'view_reports']
        render(<ReportsPage />)

        expect(screen.getByRole('heading', { level: 2, name: 'Permission required' })).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Export PDF' })).not.toBeInTheDocument()
        expect(accessState.summaryCalls).toBe(0)
    })

    it('shows reports to intake specialists with view_reports under policy v2', () => {
        dynamicState.policyVersion = 2
        accessState.role = 'intake_specialist'
        accessState.permissions = ['view_dashboard', 'view_reports']
        render(<ReportsPage />)

        expect(screen.queryByRole('heading', { level: 2, name: 'Permission required' })).not.toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Export PDF' })).toBeInTheDocument()
    })

    it('hides organization ad spend for a scoped report viewer', () => {
        dynamicState.policyVersion = 2
        dynamicState.canViewOrgReports = false
        const view = render(<ReportsPage />)
        expect(screen.queryByText('Ad Spend')).not.toBeInTheDocument()
        view.unmount()
        dynamicState.canViewOrgReports = true
        render(<ReportsPage />)
        expect(screen.getByText('Ad Spend')).toBeInTheDocument()
    })
})
