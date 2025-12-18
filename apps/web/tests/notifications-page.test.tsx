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

vi.mock('@/lib/hooks/use-notifications', () => ({
    useNotifications: (params: unknown) => mockUseNotifications(params),
    useMarkRead: () => ({ mutate: mockMarkRead, isPending: false }),
    useMarkAllRead: () => ({ mutate: mockMarkAllRead, isPending: false }),
}))

describe('NotificationsPage', () => {
    beforeEach(() => {
        mockUseNotifications.mockReturnValue({
            data: {
                unread_count: 1,
                items: [
                    {
                        id: 'n1',
                        type: 'case_assigned',
                        title: 'Case assigned',
                        body: 'You have been assigned a case.',
                        entity_type: 'case',
                        entity_id: 'c1',
                        read_at: null,
                        created_at: new Date().toISOString(),
                    },
                ],
            },
            isLoading: false,
        })

        mockPush.mockReset()
        mockMarkRead.mockReset()
        mockMarkAllRead.mockReset()
    })

    it('can mark all as read', () => {
        render(<NotificationsPage />)
        fireEvent.click(screen.getByRole('button', { name: /mark all read/i }))
        expect(mockMarkAllRead).toHaveBeenCalled()
    })

    it('marks a notification as read and navigates', () => {
        render(<NotificationsPage />)

        fireEvent.click(screen.getByText('Case assigned'))

        expect(mockMarkRead).toHaveBeenCalledWith('n1')
        expect(mockPush).toHaveBeenCalledWith('/cases/c1')
    })
})

