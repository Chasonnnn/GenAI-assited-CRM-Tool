import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import NotificationsPage from '../app/(app)/notifications/page'

const mockPush = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: mockPush }),
}))

const mockUseNotifications = vi.fn()
const mockMarkRead = vi.fn()
const mockMarkAllRead = vi.fn()
const mockUseMarkAllRead = vi.fn()
const mockUseTasks = vi.fn()
const mockUseNotificationSocket = vi.fn()

vi.mock('@/lib/hooks/use-notifications', () => ({
    useNotifications: (params: unknown) => mockUseNotifications(params),
    useMarkRead: () => ({ mutate: mockMarkRead, isPending: false }),
    useMarkAllRead: () => mockUseMarkAllRead(),
}))

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: unknown) => mockUseTasks(params),
}))

vi.mock('@/lib/hooks/use-notification-socket', () => ({
    useNotificationSocket: () => mockUseNotificationSocket(),
}))

describe('NotificationsPage', () => {
    beforeEach(() => {
        mockUseNotificationSocket.mockReturnValue({
            isConnected: false,
            lastNotification: null,
            unreadCount: null,
        })
        mockUseNotifications.mockReturnValue({
            data: {
                unread_count: 2,
                items: [
                    {
                        id: 'n1',
                        type: 'surrogate_assigned',
                        title: 'Surrogate assigned',
                        body: 'You have been assigned a surrogate.',
                        entity_type: 'surrogate',
                        entity_id: 's1',
                        read_at: null,
                        created_at: new Date().toISOString(),
                    },
                    {
                        id: 'n2',
                        type: 'task_assigned',
                        title: 'Task assigned',
                        body: 'You have a new task.',
                        entity_type: 'task',
                        entity_id: 't1',
                        read_at: new Date().toISOString(),
                        created_at: new Date().toISOString(),
                    },
                ],
            },
            isLoading: false,
        })

        // Mock overdue tasks (one day old)
        const yesterday = new Date()
        yesterday.setDate(yesterday.getDate() - 2)
        mockUseTasks.mockReturnValue({
            data: {
                items: [
                    {
                        id: 'task1',
                        title: 'Overdue task',
                        due_date: yesterday.toISOString().split('T')[0],
                        owner_name: 'John Doe',
                        surrogate_id: 's1',
                        surrogate_number: 'S10042',
                    },
                ],
            },
            isLoading: false,
        })

        mockPush.mockReset()
        mockMarkRead.mockReset()
        mockMarkAllRead.mockReset()
        mockUseMarkAllRead.mockReturnValue({ mutate: mockMarkAllRead, isPending: false })
    })

    it('renders notification counts, overdue tasks, and default filters', () => {
        render(<NotificationsPage />)
        expect(screen.getByText('Notifications')).toBeInTheDocument()
        expect(screen.getByText('2 unread')).toBeInTheDocument()
        expect(screen.getByText('Overdue Tasks')).toBeInTheDocument()
        expect(screen.getByText('Overdue task')).toBeInTheDocument()
        expect(mockUseNotifications).toHaveBeenCalledWith(
            expect.objectContaining({ limit: 50 })
        )
    })

    it('can mark all as read', () => {
        render(<NotificationsPage />)
        fireEvent.click(screen.getByRole('button', { name: /mark all read/i }))
        expect(mockMarkAllRead).toHaveBeenCalled()
    })

    it('marks a notification as read and navigates', () => {
        render(<NotificationsPage />)
        fireEvent.click(screen.getByText('Surrogate assigned'))
        expect(mockMarkRead).toHaveBeenCalledWith('n1')
        expect(mockPush).toHaveBeenCalledWith('/surrogates/s1')
    })

    it("enables polling fallback when websocket is disconnected", () => {
        mockUseNotificationSocket.mockReturnValue({
            isConnected: false,
            lastNotification: null,
            unreadCount: null,
        })

        render(<NotificationsPage />)

        expect(mockUseNotifications).toHaveBeenCalledWith(
            expect.objectContaining({ limit: 50, refetch_interval_ms: 30_000 })
        )
    })

    it('routes approval-needed notifications to tasks', () => {
        mockUseNotifications.mockReturnValue({
            data: {
                unread_count: 1,
                items: [
                    {
                        id: 'n3',
                        type: 'status_change_requested',
                        title: 'Approval needed',
                        body: 'A status change requires approval.',
                        entity_type: 'surrogate',
                        entity_id: 's2',
                        read_at: null,
                        created_at: new Date().toISOString(),
                    },
                ],
            },
            isLoading: false,
        })
        mockUseTasks.mockReturnValue({ data: { items: [] }, isLoading: false })

        render(<NotificationsPage />)
        fireEvent.click(screen.getByText('Approval needed'))
        expect(mockMarkRead).toHaveBeenCalledWith('n3')
        expect(mockPush).toHaveBeenCalledWith('/tasks?filter=my_tasks&focus=approvals')
    })

    it('routes overdue task notifications to the overdue section', () => {
        mockUseNotifications.mockReturnValue({
            data: {
                unread_count: 1,
                items: [
                    {
                        id: 'n4',
                        type: 'task_overdue',
                        title: 'Task overdue',
                        body: 'A task is overdue.',
                        entity_type: 'task',
                        entity_id: 't2',
                        read_at: null,
                        created_at: new Date().toISOString(),
                    },
                ],
            },
            isLoading: false,
        })
        mockUseTasks.mockReturnValue({ data: { items: [] }, isLoading: false })

        render(<NotificationsPage />)
        fireEvent.click(screen.getByText('Task overdue'))
        expect(mockMarkRead).toHaveBeenCalledWith('n4')
        expect(mockPush).toHaveBeenCalledWith('/tasks?filter=my_tasks&focus=overdue')
    })

    it('shows empty state when no notifications', () => {
        mockUseNotifications.mockReturnValue({
            data: { unread_count: 0, items: [] },
            isLoading: false,
        })
        mockUseTasks.mockReturnValue({ data: { items: [] }, isLoading: false })

        render(<NotificationsPage />)
        expect(screen.getByText("You're all caught up!")).toBeInTheDocument()
    })

    it("shows progress and prevents duplicate mark-all requests until the mutation settles", () => {
        mockUseMarkAllRead.mockReturnValue({ mutate: mockMarkAllRead, isPending: true })
        const { rerender } = render(<NotificationsPage />)
        const button = screen.getByRole("button", { name: "Mark all read" })

        expect(button).toBeDisabled()
        expect(button).toHaveAttribute("aria-busy", "true")
        expect(button.querySelector("svg")).toHaveClass("animate-spin")
        fireEvent.click(button)
        expect(mockMarkAllRead).not.toHaveBeenCalled()

        // A rejected request leaves unread items available for retry.
        mockUseMarkAllRead.mockReturnValue({ mutate: mockMarkAllRead, isPending: false, isError: true })
        rerender(<NotificationsPage />)
        expect(button).toBeEnabled()
        expect(button).toHaveAttribute("aria-busy", "false")
        expect(button.querySelector("svg")).toBeNull()
        fireEvent.click(button)
        expect(mockMarkAllRead).toHaveBeenCalledTimes(1)
    })

    it('applies match and appointment filters and restores All', async () => {
        render(<NotificationsPage />)
        expect(mockUseNotifications.mock.lastCall?.[0]).not.toHaveProperty('notification_types')
        fireEvent.click(screen.getByRole('combobox'))
        const option = await screen.findByRole('option', { name: 'Match Updates' })
        fireEvent.mouseMove(option)
        fireEvent.click(option)
        expect(mockUseNotifications).toHaveBeenLastCalledWith(
            expect.objectContaining({ notification_types: ['match_conflict'] })
        )
        expect(screen.getByRole('combobox')).toHaveTextContent('Match Updates')

        fireEvent.click(screen.getByRole('combobox'))
        const appointments = await screen.findByRole('option', { name: 'Appointments' })
        fireEvent.mouseMove(appointments)
        fireEvent.click(appointments)
        expect(screen.getByRole('combobox')).toHaveTextContent('Appointments')
        expect(mockUseNotifications).toHaveBeenLastCalledWith(
            expect.objectContaining({
                notification_types: [
                    'appointment_requested',
                    'appointment_confirmed',
                    'appointment_cancelled',
                    'appointment_reminder',
                ],
            })
        )

        fireEvent.click(screen.getByRole('combobox'))
        const all = await screen.findByRole('option', { name: 'All', exact: true })
        fireEvent.mouseMove(all)
        fireEvent.click(all)
        expect(screen.getByRole('combobox')).toHaveTextContent('All')
        expect(mockUseNotifications.mock.lastCall?.[0]).not.toHaveProperty('notification_types')
    })

    it('routes match conflict notifications to the match detail with the match icon', () => {
        mockUseNotifications.mockReturnValue({
            data: {
                unread_count: 1,
                items: [
                    {
                        id: 'n4',
                        type: 'match_conflict',
                        title: 'Surrogate has an accepted match',
                        body: 'M10001 remains under review.',
                        entity_type: 'match',
                        entity_id: 'match-1',
                        read_at: null,
                        created_at: new Date().toISOString(),
                    },
                ],
            },
            isLoading: false,
        })
        mockUseTasks.mockReturnValue({ data: { items: [] }, isLoading: false })
        render(<NotificationsPage />)
        const item = screen.getByText('Surrogate has an accepted match').closest('button')!
        expect(item.querySelector('svg.lucide-heart-handshake')).not.toBeNull()
        fireEvent.click(item)
        expect(mockMarkRead).toHaveBeenCalledWith('n4')
        expect(mockPush).toHaveBeenCalledWith('/intended-parents/matches/match-1')
    })
})
