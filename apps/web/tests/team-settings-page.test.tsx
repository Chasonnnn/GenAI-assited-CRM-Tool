import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
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
})
