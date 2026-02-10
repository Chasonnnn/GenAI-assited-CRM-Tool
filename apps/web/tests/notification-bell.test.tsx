import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { NotificationBell } from '../components/notification-bell'

// Mock next/navigation
const mockPush = vi.fn()
vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: mockPush }),
}))

// Mock use-notifications
const mockUseNotifications = vi.fn()
const mockUnreadCount = vi.fn()
const mockMarkRead = vi.fn()
const mockMarkAllRead = vi.fn()

vi.mock('@/lib/hooks/use-notifications', () => ({
    useNotifications: (params: unknown) => mockUseNotifications(params),
    useUnreadCount: () => mockUnreadCount(),
    useMarkRead: () => ({ mutate: mockMarkRead, isPending: false }),
    useMarkAllRead: () => ({ mutate: mockMarkAllRead, isPending: false }),
}))

// Mock use-notification-socket
const mockUseNotificationSocket = vi.fn()
vi.mock('@/lib/hooks/use-notification-socket', () => ({
    useNotificationSocket: () => mockUseNotificationSocket(),
}))

// Mock use-browser-notifications
const mockShowNotification = vi.fn()
vi.mock('@/lib/hooks/use-browser-notifications', () => ({
    useBrowserNotifications: () => ({
        permission: 'granted',
        showNotification: mockShowNotification,
        isSupported: true,
        requestPermission: vi.fn(),
    }),
}))

describe('NotificationBell', () => {
    beforeEach(() => {
        vi.resetAllMocks()

        mockUseNotifications.mockReturnValue({
            data: { items: [] },
            isLoading: false,
        })
        mockUnreadCount.mockReturnValue({
            data: { count: 0 },
            isLoading: false,
        })
        mockUseNotificationSocket.mockReturnValue({
            lastNotification: null,
            unreadCount: null,
        })
    })

    it('has accessible label indicating unread count', () => {
        mockUnreadCount.mockReturnValue({
            data: { count: 5 },
            isLoading: false,
        })

        render(<NotificationBell />)

        // This should fail before the fix as it is currently just "Notifications"
        const button = screen.getByRole('button', { name: /notifications, 5 unread/i })
        expect(button).toBeInTheDocument()
    })

    it('has accessible label when no unread messages', () => {
        mockUnreadCount.mockReturnValue({
            data: { count: 0 },
            isLoading: false,
        })

        render(<NotificationBell />)

        const button = screen.getByRole('button', { name: /notifications, no unread messages/i })
        expect(button).toBeInTheDocument()
    })

    it('shows accessible unread indicator for unread notifications', () => {
        mockUseNotifications.mockReturnValue({
            data: {
                items: [
                    {
                        id: 'n1',
                        read_at: null,
                        title: 'Unread Notification',
                        created_at: new Date().toISOString()
                    }
                ]
            },
            isLoading: false,
        })

        render(<NotificationBell />)

        // Open the menu to see notifications
        const button = screen.getByRole('button')
        fireEvent.click(button)

        expect(screen.getByText('Unread')).toHaveClass('sr-only')
    })
})
