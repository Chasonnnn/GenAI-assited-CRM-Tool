import type { PropsWithChildren } from "react"
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

const dynamicState = vi.hoisted(() => ({
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

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { ai_enabled: true } }),
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
    useAnalyticsSummary: () => ({
        data: {
            total_surrogates: 42,
            new_this_period: 5,
            qualification_rate: 10,
            qualification_stage_key: 'pre_qualified',
            avg_time_to_qualification_hours: 48,
        },
        isLoading: false,
    }),
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
}))

describe('ReportsPage', () => {
    it('lazy loads report visualizations', () => {
        expect(dynamicState.calls.length).toBeGreaterThan(0)
        expect(dynamicState.calls.some((call) => call.options?.ssr === false)).toBe(true)
    })

    it('renders report summary cards', () => {
        render(<ReportsPage />)
        expect(screen.getByText('Reports')).toBeInTheDocument()
        expect(screen.getByText('42')).toBeInTheDocument()
        expect(screen.getAllByText('$1,000').length).toBeGreaterThan(0)
    })
})
