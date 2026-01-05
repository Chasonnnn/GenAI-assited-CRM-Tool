import type { PropsWithChildren } from "react"
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ReportsPage from '../app/(app)/reports/page'

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { ai_enabled: true } }),
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
    useAnalyticsSummary: () => ({ data: { total_cases: 42, new_this_period: 5, qualified_rate: 10 }, isLoading: false }),
    useCasesByStatus: () => ({ data: [{ status: 'new_unread', count: 1 }], isLoading: false }),
    useCasesByAssignee: () => ({ data: [{ user_email: 'alice@example.com', count: 2 }], isLoading: false }),
    useCasesTrend: () => ({ data: [{ date: '2025-01-01', count: 1 }], isLoading: false }),
    useMetaPerformance: () => ({ data: { conversion_rate: 20, leads_converted: 2, leads_received: 10 }, isLoading: false }),
    useMetaSpend: () => ({ data: { total_spend: 1000, cost_per_lead: 12.34 }, isLoading: false }),
    useFunnelCompare: () => ({ data: null, isLoading: false }),
    useCasesByStateCompare: () => ({ data: null, isLoading: false }),
    useCampaigns: () => ({ data: [], isLoading: false }),
    usePerformanceByUser: () => ({ data: { data: [], unassigned: { total_cases: 0 } }, isLoading: false }),
}))

describe('ReportsPage', () => {
    it('renders report summary cards', () => {
        render(<ReportsPage />)
        expect(screen.getByText('Reports')).toBeInTheDocument()
        expect(screen.getByText('42')).toBeInTheDocument()
        expect(screen.getByText('$1,000')).toBeInTheDocument()
    })
})
