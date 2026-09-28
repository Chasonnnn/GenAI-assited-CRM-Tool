import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import InvitePage from '../app/invite/[id]/page'

const mockApiGet = vi.fn()
const navigationState = vi.hoisted(() => ({ inviteId: 'inv-123' }))

vi.unmock('@tanstack/react-query')

vi.mock('next/navigation', () => ({
    useParams: () => ({ id: navigationState.inviteId }),
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

vi.mock('@/lib/api', async (importOriginal) => ({
    ...(await importOriginal<typeof import('@/lib/api')>()),
    default: {
        get: (...args: unknown[]) => mockApiGet(...args),
    },
}))

describe('InvitePage', () => {
    const originalApiBase = process.env.NEXT_PUBLIC_API_BASE_URL

    beforeEach(() => {
        navigationState.inviteId = 'inv-123'
        mockApiGet.mockImplementation((path: string) => {
            if (path === '/auth/me') return Promise.reject(new Error('Unauthenticated'))
            return Promise.resolve({
                id: 'inv-123',
                organization_id: 'org-123',
                organization_name: 'Test Org',
                role: 'intake_specialist',
                inviter_name: 'Test User',
                expires_at: null,
                status: 'pending',
            })
        })
        process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.example.com'
    })

    function renderInvitePage() {
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false } },
        })
        return render(
            <QueryClientProvider client={queryClient}>
                <InvitePage />
            </QueryClientProvider>
        )
    }

    afterEach(() => {
        process.env.NEXT_PUBLIC_API_BASE_URL = originalApiBase
        mockApiGet.mockReset()
    })

    it('redirects to backend Google login when continuing', async () => {
        renderInvitePage()

        await waitFor(() => {
            expect(screen.getByText("You're Invited")).toBeInTheDocument()
        })

        const button = screen.getByRole('button', { name: /continue with google/i })
        fireEvent.click(button)

        expect(window.location.assign).toHaveBeenCalledWith(
            'https://api.example.com/auth/google/login?return_to=app&invite_id=inv-123'
        )
    })

    it('shows one safe message for a malformed invite id instead of the validation text', async () => {
        const { ApiError } = await import('@/lib/api')
        navigationState.inviteId = 'not-a-uuid'
        mockApiGet.mockImplementation((path: string) => {
            if (path === '/auth/me') return Promise.reject(new Error('Unauthenticated'))
            return Promise.reject(
                new ApiError(422, 'Unprocessable Entity', 'invite_id: Input should be a valid UUID, invalid character'),
            )
        })

        renderInvitePage()

        expect(await screen.findByText('This invitation is invalid or has expired.')).toBeInTheDocument()
        expect(screen.getByText('Invitation not found')).toBeInTheDocument()
        expect(screen.queryByText("You're Invited")).not.toBeInTheDocument()
        expect(screen.queryByText(/valid UUID/)).not.toBeInTheDocument()
    })

    it('shows the same message for an unknown invite id', async () => {
        const { ApiError } = await import('@/lib/api')
        mockApiGet.mockImplementation((path: string) => {
            if (path === '/auth/me') return Promise.reject(new Error('Unauthenticated'))
            return Promise.reject(new ApiError(404, 'Not Found', 'Invite not found'))
        })

        renderInvitePage()

        expect(await screen.findByText('This invitation is invalid or has expired.')).toBeInTheDocument()
    })

    it('hides server error details for other failures', async () => {
        const { ApiError } = await import('@/lib/api')
        mockApiGet.mockImplementation((path: string) => {
            if (path === '/auth/me') return Promise.reject(new Error('Unauthenticated'))
            return Promise.reject(new ApiError(500, 'Internal Server Error', 'psycopg OperationalError'))
        })

        renderInvitePage()

        expect(await screen.findByText("Couldn't load invitation")).toBeInTheDocument()
        expect(screen.queryByText(/psycopg/)).not.toBeInTheDocument()
    })

    it('keeps the newest invitation visible when an older request finishes last', async () => {
        let resolveFirst: (value: unknown) => void = () => undefined
        let resolveSecond: (value: unknown) => void = () => undefined
        const firstRequest = new Promise((resolve) => { resolveFirst = resolve })
        const secondRequest = new Promise((resolve) => { resolveSecond = resolve })
        mockApiGet.mockImplementation((path: string) => {
            if (path === '/auth/me') return Promise.reject(new Error('Unauthenticated'))
            if (path.endsWith('/invite-first')) return firstRequest
            if (path.endsWith('/invite-second')) return secondRequest
            return Promise.reject(new Error(`Unexpected path: ${path}`))
        })

        navigationState.inviteId = 'invite-first'
        const view = renderInvitePage()
        navigationState.inviteId = 'invite-second'
        view.rerender(
            <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
                <InvitePage />
            </QueryClientProvider>
        )

        await act(async () => {
            resolveSecond({
                id: 'invite-second',
                organization_id: 'org-second',
                organization_name: 'Second Organization',
                role: 'case_manager',
                inviter_name: null,
                expires_at: null,
                status: 'pending',
            })
        })
        expect(await screen.findByText('Second Organization')).toBeInTheDocument()

        await act(async () => {
            resolveFirst({
                id: 'invite-first',
                organization_id: 'org-first',
                organization_name: 'First Organization',
                role: 'case_manager',
                inviter_name: null,
                expires_at: null,
                status: 'pending',
            })
            await Promise.resolve()
        })

        expect(screen.getByText('Second Organization')).toBeInTheDocument()
        expect(screen.queryByText('First Organization')).not.toBeInTheDocument()
    })
})
