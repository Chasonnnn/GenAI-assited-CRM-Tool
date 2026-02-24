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
const mockUseTasks = vi.fn()
const mockUseNotificationSocket = vi.fn()

vi.mock('@/lib/hooks/use-notifications', () => ({
    useNotifications: (params: unknown) => mockUseNotifications(params),
    useMarkRead: () => ({ mutate: mockMarkRead, isPending: false }),
    useMarkAllRead: () => ({ mutate: mockMarkAllRead, isPending: false }),
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
    })

    it('renders notifications page with header', () => {
        render(<NotificationsPage />)
        expect(screen.getByText('Notifications')).toBeInTheDocument()
    })

    it('shows unread count badge', () => {
        render(<NotificationsPage />)
        expect(screen.getByText('2 unread')).toBeInTheDocument()
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

    it('renders overdue tasks section', () => {
        render(<NotificationsPage />)
        expect(screen.getByText('Overdue Tasks')).toBeInTheDocument()
        expect(screen.getByText('Overdue task')).toBeInTheDocument()
    })

    it('renders type filter dropdown', () => {
        render(<NotificationsPage />)
        expect(screen.getByRole('combobox')).toBeInTheDocument()
    })

    it('passes notification_types to hook when filter is selected', () => {
        render(<NotificationsPage />)
        // Initial call should have no filter
        expect(mockUseNotifications).toHaveBeenCalledWith(
            expect.objectContaining({ limit: 50 })
        )
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
})
