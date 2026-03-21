import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import TeamSettingsPage from '../app/(app)/settings/team/page'

const mockUseInvites = vi.fn()
const mockUseMembers = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
    }),
}))

vi.mock('next/link', () => ({
    default: ({
        href,
        children,
        prefetch: _prefetch,
        ...props
    }: {
        href: string
        children: ReactNode
        prefetch?: boolean
    }) => (
        <a href={href} {...props}>{children}</a>
    ),
}))

vi.mock('@/lib/hooks/use-invites', () => ({
    useInvites: () => mockUseInvites(),
    useCreateInvite: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useResendInvite: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRevokeInvite: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/hooks/use-permissions', () => ({
    useMembers: () => mockUseMembers(),
    useRemoveMember: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useBulkUpdateRoles: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({
        user: {
            user_id: 'user-1',
            role: 'admin',
        },
    }),
}))

vi.mock('sonner', () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
    },
}))

describe('TeamSettingsPage invitations tab', () => {
    beforeEach(() => {
        mockUseMembers.mockReturnValue({ data: [], isLoading: false })
        mockUseInvites.mockReturnValue({
            data: {
                invites: [
                    {
                        id: 'inv-pending',
                        email: 'pending@example.com',
                        role: 'case_manager',
                        status: 'pending',
                        invited_by_user_id: 'user-1',
                        expires_at: '2099-01-01T00:00:00Z',
                        resend_count: 0,
                        can_resend: true,
                        resend_cooldown_seconds: null,
                        created_at: '2026-01-01T00:00:00Z',
                    },
                    {
                        id: 'inv-expired',
                        email: 'expired@example.com',
                        role: 'admin',
                        status: 'expired',
                        invited_by_user_id: 'user-1',
                        expires_at: '2025-01-01T00:00:00Z',
                        resend_count: 1,
                        can_resend: true,
                        resend_cooldown_seconds: null,
                        created_at: '2025-01-01T00:00:00Z',
                    },
                    {
                        id: 'inv-accepted',
                        email: 'accepted@example.com',
                        role: 'admin',
                        status: 'accepted',
                        invited_by_user_id: 'user-1',
                        expires_at: null,
                        resend_count: 0,
                        can_resend: false,
                        resend_cooldown_seconds: null,
                        created_at: '2025-01-01T00:00:00Z',
                    },
                ],
                pending_count: 1,
            },
            isLoading: false,
        })
    })

    it('shows pending and expired invites in Invitations tab', () => {
        render(<TeamSettingsPage />)

        fireEvent.click(screen.getByRole('tab', { name: /invitations/i }))

        expect(screen.getByText('pending@example.com')).toBeInTheDocument()
        expect(screen.getByText('expired@example.com')).toBeInTheDocument()
        expect(screen.queryByText('accepted@example.com')).not.toBeInTheDocument()
    })

    it('moves the current user badge into the action slot so the name column stays centered', () => {
        mockUseMembers.mockReturnValue({
            data: [
                {
                    id: 'member-1',
                    user_id: 'user-1',
                    display_name: 'Test Admin',
                    email: 'admin@example.com',
                    role: 'admin',
                    last_login_at: null,
                },
                {
                    id: 'member-2',
                    user_id: 'user-2',
                    display_name: 'Test Case Manager',
                    email: 'case@example.com',
                    role: 'case_manager',
                    last_login_at: null,
                },
            ],
            isLoading: false,
        })

        render(<TeamSettingsPage />)

        const selfRow = screen.getByText('Test Admin').closest('tr')
        expect(selfRow).not.toBeNull()

        const selfNameCell = screen.getByText('Test Admin').closest('td')
        expect(selfNameCell).not.toBeNull()
        expect(within(selfNameCell as HTMLElement).queryByText('You')).not.toBeInTheDocument()

        expect(screen.getByText('Test Admin')).toHaveClass('text-center')
        expect(screen.getByText('Test Case Manager')).toHaveClass('text-center')

        const actionCell = within(selfRow as HTMLElement).getByRole('link', { name: /manage/i }).closest('td')
        expect(actionCell).not.toBeNull()

        const actionLayout = actionCell?.firstElementChild
        expect(actionLayout).toHaveClass('grid', 'grid-cols-[auto_3.5rem]', 'items-center', 'justify-center')

        const youBadge = within(actionCell as HTMLElement).getByText('You')
        expect(youBadge.parentElement).toHaveClass('flex', 'w-14', 'justify-center')
    })
})
