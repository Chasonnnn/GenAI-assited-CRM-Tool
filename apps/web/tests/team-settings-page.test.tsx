import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { ApiError } from '@/lib/api'
import TeamSettingsPage from '../app/(app)/settings/team/page'

const mockUseInvites = vi.fn()
const mockUseMembers = vi.fn()
const mockCan = vi.fn()
const mockCreateInvite = vi.fn()
const mockRemoveMember = vi.fn()
const mockRevokeInvite = vi.fn()

vi.mock('@/lib/hooks/use-permission-check', () => ({
    usePermissionCheck: () => ({
        isLoading: false,
        isError: false,
        retry: vi.fn(),
        isRetrying: false,
        can: (permission: string) => mockCan(permission),
    }),
}))

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
    useCreateInvite: () => ({ mutateAsync: mockCreateInvite, isPending: false }),
    useResendInvite: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRevokeInvite: () => ({ mutateAsync: mockRevokeInvite, isPending: false }),
}))

vi.mock('@/lib/hooks/use-permissions', () => ({
    useMembers: () => mockUseMembers(),
    useRemoveMember: () => ({ mutateAsync: mockRemoveMember, isPending: false }),
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

vi.mock('@/components/ui/toast', () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
    },
}))

const TEAM_MEMBERS = [
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
]

describe('TeamSettingsPage invitations tab', () => {
    beforeEach(() => {
        mockCan.mockReset()
        mockCan.mockImplementation((permission: string) => permission === 'manage_team')
        mockCreateInvite.mockReset()
        mockRemoveMember.mockReset()
        mockRevokeInvite.mockReset()
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

    it('uses the Team header with a member count and wrapping actions', () => {
        mockUseMembers.mockReturnValue({ data: TEAM_MEMBERS, isLoading: false })

        render(<TeamSettingsPage />)

        expect(screen.getByRole('heading', { level: 1, name: 'Team' })).toBeInTheDocument()
        const countBadge = document.querySelector('[data-slot="page-header-count"]')
        expect(countBadge).toHaveTextContent('2 members')
        expect(screen.getByRole('link', { name: /role permissions/i })).toHaveClass('flex-1', 'sm:flex-none')
        expect(screen.getByRole('button', { name: /invite member/i })).toHaveClass('flex-1', 'sm:flex-none')
    })

    it('shows the denied state and loads no members without manage_team', () => {
        mockCan.mockReturnValue(false)
        mockUseMembers.mockClear()

        render(<TeamSettingsPage />)

        expect(screen.getByText('Permission required')).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: /invite member/i })).not.toBeInTheDocument()
        expect(mockUseMembers).not.toHaveBeenCalled()
    })

    it('shows a load error instead of an empty team when members fail to load', () => {
        mockUseMembers.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(500, 'Internal Server Error', 'boom'),
            refetch: vi.fn(),
            isFetching: false,
        })

        render(<TeamSettingsPage />)

        expect(screen.getByText("Couldn't load team members")).toBeInTheDocument()
        expect(screen.queryByText('No team members')).not.toBeInTheDocument()
        expect(screen.queryByText(/boom/)).not.toBeInTheDocument()
        expect(screen.getByRole('tab', { name: 'Members' })).toBeInTheDocument()
        expect(screen.queryByText('Members (0)')).not.toBeInTheDocument()
    })

    it('confirms member removal in an in-app dialog', async () => {
        const confirmSpy = vi.spyOn(window, 'confirm')
        mockUseMembers.mockReturnValue({ data: TEAM_MEMBERS, isLoading: false })
        mockRemoveMember.mockResolvedValue(undefined)

        render(<TeamSettingsPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Remove case@example.com' }))
        const dialog = await screen.findByRole('alertdialog')
        expect(within(dialog).getByText('Remove case@example.com?')).toBeInTheDocument()
        expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus()

        fireEvent.click(within(dialog).getByRole('button', { name: 'Remove member' }))

        await waitFor(() => expect(mockRemoveMember).toHaveBeenCalledWith('member-2'))
        await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
        expect(confirmSpy).not.toHaveBeenCalled()
        confirmSpy.mockRestore()
    })

    it('confirms invitation revoke in an in-app dialog', async () => {
        mockRevokeInvite.mockResolvedValue(undefined)

        render(<TeamSettingsPage />)

        fireEvent.click(screen.getByRole('tab', { name: /invitations/i }))
        fireEvent.click(screen.getByRole('button', { name: 'Revoke invitation for pending@example.com' }))
        const dialog = await screen.findByRole('alertdialog')
        expect(within(dialog).getByText('Revoke the invitation for pending@example.com?')).toBeInTheDocument()

        fireEvent.click(within(dialog).getByRole('button', { name: 'Revoke invitation' }))

        await waitFor(() => expect(mockRevokeInvite).toHaveBeenCalledWith('inv-pending'))
    })

    it('keeps Send disabled until the invite email is valid and shows the field error', async () => {
        mockCreateInvite.mockResolvedValue({})

        render(<TeamSettingsPage />)

        fireEvent.click(screen.getByRole('button', { name: /invite member/i }))
        const dialog = await screen.findByRole('dialog')
        const send = within(dialog).getByRole('button', { name: 'Send Invitation' })
        const email = within(dialog).getByLabelText('Email address')

        expect(send).toBeDisabled()
        expect(within(dialog).queryByText(/will receive an email/i)).not.toBeInTheDocument()

        fireEvent.change(email, { target: { value: 'not-an-email' } })
        fireEvent.blur(email)
        expect(send).toBeDisabled()
        expect(email).toHaveAttribute('aria-invalid', 'true')
        expect(within(dialog).getByText(/valid email/i)).toBeInTheDocument()

        fireEvent.change(email, { target: { value: 'new.person@example.com' } })
        expect(send).toBeEnabled()
        fireEvent.click(send)

        await waitFor(() =>
            expect(mockCreateInvite).toHaveBeenCalledWith({ email: 'new.person@example.com', role: 'intake_specialist' })
        )
    })
})
