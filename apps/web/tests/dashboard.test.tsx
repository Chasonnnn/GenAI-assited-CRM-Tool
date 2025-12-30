import type { PropsWithChildren } from "react"
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import DashboardPage from '../app/(app)/dashboard/page'

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { display_name: 'Test Manager', ai_enabled: true } }),
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

const mockUseCaseStats = vi.fn()
const mockUseTasks = vi.fn()
const mockUseCasesTrend = vi.fn()
const mockUseCasesByStatus = vi.fn()

vi.mock('@/lib/hooks/use-cases', () => ({
    useCaseStats: () => mockUseCaseStats(),
}))

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: unknown) => mockUseTasks(params),
    useCompleteTask: () => ({ mutateAsync: vi.fn() }),
    useUncompleteTask: () => ({ mutateAsync: vi.fn() }),
}))

vi.mock('@/lib/hooks/use-analytics', () => ({
    useCasesTrend: (params: unknown) => mockUseCasesTrend(params),
    useCasesByStatus: () => mockUseCasesByStatus(),
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

vi.mock('@/lib/hooks/use-dashboard-socket', () => ({
    useDashboardSocket: () => { },
}))

describe('DashboardPage', () => {
    beforeEach(() => {
        mockUseCaseStats.mockReturnValue({
            data: {
                total: 10,
                this_week: 2,
                pending_tasks: 1,
                this_month: 3,
                by_status: { new_unread: 4 },
            },
            isLoading: false,
        })

        mockUseTasks.mockReturnValue({
            data: { items: [] },
            isLoading: false,
        })

        mockUseCasesTrend.mockReturnValue({ data: [], isLoading: false })
        mockUseCasesByStatus.mockReturnValue({ data: [], isLoading: false })
    })

    it('renders stats cards with case data', () => {
        render(<DashboardPage />)

        // Check welcome header
        expect(screen.getByText(/Welcome back, Test/)).toBeInTheDocument()

        // Check stats cards
        expect(screen.getByText('Active Cases')).toBeInTheDocument()
        expect(screen.getByText('10')).toBeInTheDocument()
        expect(screen.getByText('Pending Tasks')).toBeInTheDocument()

        // Check chart sections exist
        expect(screen.getByText('Cases Trend')).toBeInTheDocument()
        expect(screen.getByText('Cases by Stage')).toBeInTheDocument()
    })
})
