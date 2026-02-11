import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { NotificationBell } from '../components/notification-bell'

// Mock dependencies
const mockPush = vi.fn()
vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: mockPush }),
}))

const mockUseNotifications = vi.fn()
const mockUseUnreadCount = vi.fn()
const mockMarkRead = vi.fn()
const mockMarkAllRead = vi.fn()
const mockUseNotificationSocket = vi.fn()
const mockUseBrowserNotifications = vi.fn()

vi.mock('@/lib/hooks/use-notifications', () => ({
    useNotifications: (opts: unknown) => mockUseNotifications(opts),
    useUnreadCount: () => mockUseUnreadCount(),
    useMarkRead: () => ({ mutate: mockMarkRead, isPending: false }),
    useMarkAllRead: () => ({ mutate: mockMarkAllRead, isPending: false }),
}))

vi.mock('@/lib/hooks/use-notification-socket', () => ({
    useNotificationSocket: () => mockUseNotificationSocket(),
}))

vi.mock('@/lib/hooks/use-browser-notifications', () => ({
    useBrowserNotifications: () => mockUseBrowserNotifications(),
}))

describe('NotificationBell', () => {
    beforeEach(() => {
        // Default mocks
        mockUseNotifications.mockReturnValue({
            data: { items: [] },
            isLoading: false,
        })
        mockUseUnreadCount.mockReturnValue({
            data: { count: 0 },
            isLoading: false,
        })
        mockUseNotificationSocket.mockReturnValue({
            lastNotification: null,
            unreadCount: null,
        })
        mockUseBrowserNotifications.mockReturnValue({
            permission: 'default',
            showNotification: vi.fn(),
        })

        mockPush.mockReset()
        mockMarkRead.mockReset()
        mockMarkAllRead.mockReset()
    })

    it('renders with correct aria-label when no notifications', () => {
        render(<NotificationBell />)
        const trigger = screen.getByRole('button', { name: /notifications/i })
        expect(trigger).toBeInTheDocument()
        expect(trigger).toHaveAttribute('aria-label', 'Notifications (no unread)')
    })

    it('renders with correct aria-label when unread notifications exist', () => {
        mockUseUnreadCount.mockReturnValue({
            data: { count: 3 },
            isLoading: false,
        })

        render(<NotificationBell />)
        const trigger = screen.getByRole('button', { name: /notifications/i })
        expect(trigger).toHaveAttribute('aria-label', 'Notifications (3 unread)')
    })

    it('shows loading state when fetching count', () => {
        mockUseUnreadCount.mockReturnValue({
            data: undefined,
            isLoading: true,
        })

        render(<NotificationBell />)
        const trigger = screen.getByRole('button')
        expect(trigger).toBeInTheDocument()
        // Once implemented, we can test for specific loading state behavior
    })

    it('shows empty state with icon when no notifications', () => {
        render(<NotificationBell />)
        fireEvent.click(screen.getByRole('button', { name: /notifications/i }))

        expect(screen.getByText('No notifications')).toBeInTheDocument()
    })

    it('navigates to notification page on "View all"', () => {
        render(<NotificationBell />)
        fireEvent.click(screen.getByRole('button', { name: /notifications/i }))
        fireEvent.click(screen.getByText('View all notifications'))

        expect(mockPush).toHaveBeenCalledWith('/notifications')
    })
})
