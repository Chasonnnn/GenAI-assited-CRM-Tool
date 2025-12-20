import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
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
    Area: ({ children }: any) => <div>{children}</div>,
    AreaChart: ({ children }: any) => <div>{children}</div>,
    Bar: ({ children }: any) => <div>{children}</div>,
    BarChart: ({ children }: any) => <div>{children}</div>,
    CartesianGrid: () => <div />,
    XAxis: () => <div />,
    YAxis: () => <div />,
}))

vi.mock('@/components/ui/chart', () => ({
    ChartContainer: ({ children }: any) => <div>{children}</div>,
    ChartTooltip: ({ children }: any) => <div>{children}</div>,
    ChartTooltipContent: () => <div />,
}))

const mockUseCaseStats = vi.fn()
const mockUseTasks = vi.fn()
const mockCompleteTask = vi.fn()
const mockUncompleteTask = vi.fn()
const mockUseCasesTrend = vi.fn()
const mockUseCasesByStatus = vi.fn()

vi.mock('@/lib/hooks/use-cases', () => ({
    useCaseStats: () => mockUseCaseStats(),
}))

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: unknown) => mockUseTasks(params),
    useCompleteTask: () => ({ mutateAsync: mockCompleteTask }),
    useUncompleteTask: () => ({ mutateAsync: mockUncompleteTask }),
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
            data: {
                items: [
                    {
                        id: 't1',
                        title: 'Call lead',
                        is_completed: false,
                        due_date: null,
                        case_id: 'c1',
                        case_number: '12345',
                    },
                ],
            },
            isLoading: false,
        })

        mockUseCasesTrend.mockReturnValue({ data: [], isLoading: false })
        mockUseCasesByStatus.mockReturnValue({ data: [], isLoading: false })

        mockCompleteTask.mockReset()
        mockUncompleteTask.mockReset()
    })

    it('renders stats and allows completing a task', () => {
        render(<DashboardPage />)

        expect(screen.getByText('Active Cases')).toBeInTheDocument()
        expect(screen.getByText('10')).toBeInTheDocument()
        expect(screen.getByText('Call lead')).toBeInTheDocument()

        fireEvent.click(screen.getByLabelText('Call lead'))
        expect(mockCompleteTask).toHaveBeenCalledWith('t1')
    })
})
