import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { MatchTasksCalendar } from '../components/matches/MatchTasksCalendar'
import { format, addMonths, subMonths } from 'date-fns'

const mockUseTasks = vi.fn()
const mockUseAppointments = vi.fn()

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: unknown) => mockUseTasks(params),
}))

vi.mock('@/lib/hooks/use-appointments', () => ({
    useAppointments: (params: unknown) => mockUseAppointments(params),
}))

describe('MatchTasksCalendar', () => {
    const mockTasks = {
        items: [
            {
                id: 'task1',
                title: 'Medical Appointment',
                description: 'Scheduled checkup',
                task_type: 'medical_appointment',
                case_id: 'case1',
                due_date: format(new Date(), 'yyyy-MM-dd'),
                due_time: '10:00:00',
                is_completed: false,
                owner_type: 'user',
                owner_id: 'user1',
                created_at: '2024-01-01T00:00:00Z',
            },
            {
                id: 'task2',
                title: 'Contract Review',
                description: 'Review legal documents',
                task_type: 'contract',
                case_id: 'case1',
                due_date: format(new Date(), 'yyyy-MM-dd'),
                due_time: '14:00:00',
                is_completed: false,
                owner_type: 'user',
                owner_id: 'user1',
                created_at: '2024-01-02T00:00:00Z',
            },
        ],
        total: 2,
        per_page: 100,
        page: 1,
    }

    beforeEach(() => {
        vi.clearAllMocks()
        mockUseTasks.mockReturnValue({
            data: mockTasks,
            isLoading: false,
        })
        mockUseAppointments.mockReturnValue({
            data: { items: [], total: 0, page: 1, per_page: 100, pages: 0 },
            isLoading: false,
        })
    })

    it('renders calendar header with current month', () => {
        render(<MatchTasksCalendar caseId="case1" />)
        const currentMonthYear = format(new Date(), 'MMMM yyyy')
        expect(screen.getByText(currentMonthYear)).toBeInTheDocument()
    })

    it('renders navigation buttons', () => {
        render(<MatchTasksCalendar caseId="case1" />)
        expect(screen.getByText('Today')).toBeInTheDocument()
    })

    it('renders filter buttons', () => {
        render(<MatchTasksCalendar caseId="case1" />)
        expect(screen.getByText('All')).toBeInTheDocument()
        expect(screen.getByText('Surrogate')).toBeInTheDocument()
    })

    it('renders day of week headers in month view', () => {
        render(<MatchTasksCalendar caseId="case1" />)
        expect(screen.getByText('Sun')).toBeInTheDocument()
        expect(screen.getByText('Mon')).toBeInTheDocument()
        expect(screen.getByText('Tue')).toBeInTheDocument()
        expect(screen.getByText('Wed')).toBeInTheDocument()
        expect(screen.getByText('Thu')).toBeInTheDocument()
        expect(screen.getByText('Fri')).toBeInTheDocument()
        expect(screen.getByText('Sat')).toBeInTheDocument()
    })

    it('renders legend with color indicators', () => {
        render(<MatchTasksCalendar caseId="case1" />)
        expect(screen.getByText('Surrogate Tasks')).toBeInTheDocument()
        expect(screen.getByText('IP Tasks')).toBeInTheDocument()
    })

    it('shows loading spinner when loading', () => {
        mockUseTasks.mockReturnValue({
            data: null,
            isLoading: true,
        })
        render(<MatchTasksCalendar caseId="case1" />)
        expect(document.querySelector('.animate-spin')).toBeInTheDocument()
    })

    it('calls useTasks with correct case_id', () => {
        render(<MatchTasksCalendar caseId="case1" />)
        expect(mockUseTasks).toHaveBeenCalledWith({
            case_id: 'case1',
            is_completed: false,
            per_page: 100,
            exclude_approvals: true,
            intended_parent_id: undefined,
        })
    })

    it('displays tasks on calendar', () => {
        render(<MatchTasksCalendar caseId="case1" />)
        expect(screen.getByText(/Medical Appointment/)).toBeInTheDocument()
    })

    it('navigates to previous month', () => {
        render(<MatchTasksCalendar caseId="case1" />)
        const prevButton = screen.getAllByRole('button')[0] // First button is prev
        fireEvent.click(prevButton)
        // Should now show previous month
        const previousMonth = format(subMonths(new Date(), 1), 'MMMM yyyy')
        expect(screen.getByText(previousMonth)).toBeInTheDocument()
    })

    it('navigates to next month', () => {
        render(<MatchTasksCalendar caseId="case1" />)
        const buttons = screen.getAllByRole('button')
        const nextButton = buttons[1] // Second button is next
        fireEvent.click(nextButton)
        // Should now show next month
        const nextMonth = format(addMonths(new Date(), 1), 'MMMM yyyy')
        expect(screen.getByText(nextMonth)).toBeInTheDocument()
    })

    it('returns to today when Today button clicked', () => {
        render(<MatchTasksCalendar caseId="case1" />)

        // Navigate away first
        const nextButton = screen.getAllByRole('button')[1]
        fireEvent.click(nextButton)

        // Click today button
        const todayButton = screen.getByText('Today')
        fireEvent.click(todayButton)

        // Should show current month again
        const currentMonthYear = format(new Date(), 'MMMM yyyy')
        expect(screen.getByText(currentMonthYear)).toBeInTheDocument()
    })

    it('filters tasks when Surrogate filter is clicked', () => {
        render(<MatchTasksCalendar caseId="case1" />)

        // Click Surrogate filter
        const surrogateButton = screen.getByText('Surrogate')
        fireEvent.click(surrogateButton)

        // Tasks should still be visible (all are surrogate tasks in our mock)
        expect(screen.getByText(/Medical Appointment/)).toBeInTheDocument()
    })

    it('filters tasks when All filter is clicked', () => {
        render(<MatchTasksCalendar caseId="case1" />)

        // First click surrogate, then All
        const surrogateButton = screen.getByText('Surrogate')
        fireEvent.click(surrogateButton)

        const allButton = screen.getByText('All')
        fireEvent.click(allButton)

        // Tasks should still be visible
        expect(screen.getByText(/Medical Appointment/)).toBeInTheDocument()
    })
})

describe('MatchTasksCalendar with empty state', () => {
    beforeEach(() => {
        mockUseTasks.mockReturnValue({
            data: { items: [], total: 0, per_page: 100, page: 1 },
            isLoading: false,
        })
        mockUseAppointments.mockReturnValue({
            data: { items: [], total: 0, page: 1, per_page: 100, pages: 0 },
            isLoading: false,
        })
    })

    it('renders calendar even with no tasks', () => {
        render(<MatchTasksCalendar caseId="case1" />)
        // Should still show day headers
        expect(screen.getByText('Sun')).toBeInTheDocument()
        expect(screen.getByText('Mon')).toBeInTheDocument()
    })

    it('still shows filter buttons when no tasks', () => {
        render(<MatchTasksCalendar caseId="case1" />)
        expect(screen.getByText('All')).toBeInTheDocument()
        expect(screen.getByText('Surrogate')).toBeInTheDocument()
    })
})
