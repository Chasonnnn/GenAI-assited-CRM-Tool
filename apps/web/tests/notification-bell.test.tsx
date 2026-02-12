import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { NotificationBell } from '../components/notification-bell'

// Mock hooks
const mockUseNotifications = vi.fn()
const mockUseUnreadCount = vi.fn()
const mockMarkRead = vi.fn()
const mockMarkAllRead = vi.fn()
const mockUseNotificationSocket = vi.fn()
const mockUseBrowserNotifications = vi.fn()
const mockPush = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: mockPush }),
}))

vi.mock('@/lib/hooks/use-notifications', () => ({
    useNotifications: (params: unknown) => mockUseNotifications(params),
    useUnreadCount: () => mockUseUnreadCount(),
    useMarkRead: () => ({ mutate: mockMarkRead }),
    useMarkAllRead: () => ({ mutate: mockMarkAllRead }),
}))

vi.mock('@/lib/hooks/use-notification-socket', () => ({
    useNotificationSocket: () => mockUseNotificationSocket(),
}))

vi.mock('@/lib/hooks/use-browser-notifications', () => ({
    useBrowserNotifications: () => mockUseBrowserNotifications(),
}))

describe('NotificationBell', () => {
    beforeEach(() => {
        mockUseNotifications.mockReturnValue({
            data: { items: [] },
        })
        mockUseUnreadCount.mockReturnValue({
            data: { count: 0 },
        })
        mockUseNotificationSocket.mockReturnValue({
            lastNotification: null,
            unreadCount: null,
        })
        mockUseBrowserNotifications.mockReturnValue({
            permission: 'default',
            showNotification: vi.fn(),
        })
    })

    it('renders with default aria-label when no unread notifications', () => {
        render(<NotificationBell />)
        const trigger = screen.getByRole('button', { name: /notifications/i })
        expect(trigger).toBeInTheDocument()
        expect(trigger).toHaveAttribute('aria-label', 'Notifications')
    })

    it('renders with dynamic aria-label when there are unread notifications', () => {
        mockUseUnreadCount.mockReturnValue({
            data: { count: 5 },
        })
        render(<NotificationBell />)
        // This expectation will fail until we implement the fix
        const trigger = screen.getByRole('button', { name: /notifications, 5 unread/i })
        expect(trigger).toBeInTheDocument()
    });
})
