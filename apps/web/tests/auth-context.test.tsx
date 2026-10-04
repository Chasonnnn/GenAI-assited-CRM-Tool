import { act, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { AuthProvider, useAuth } from '@/lib/auth-context'

const getSpy = vi.fn()

vi.mock('@/lib/api', () => ({
    default: {
        get: (...args: unknown[]) => getSpy(...args),
    },
    ApiError: class ApiError extends Error {
        status: number
        constructor(status: number, statusText: string, message?: string) {
            super(message || `${status} ${statusText}`)
            this.status = status
        }
    },
}))

function setLocation(pathname: string, hostname: string) {
    Object.defineProperty(window, 'location', {
        writable: true,
        value: {
            ...window.location,
            pathname,
            hostname,
        },
    })
}

function AuthProbe({ onAuth }: { onAuth: (auth: ReturnType<typeof useAuth>) => void }) {
    const auth = useAuth()
    onAuth(auth)
    return <div>{auth.isLoading ? 'loading' : auth.user?.user_id ?? 'signed out'}</div>
}

describe('AuthProvider', () => {
    beforeEach(() => {
        getSpy.mockReset()
        getSpy.mockResolvedValue({ user_id: '1' })
    })

    afterEach(() => {
        getSpy.mockReset()
    })

    it('skips auth fetch on ops routes', async () => {
        setLocation('/ops', 'ops.surrogacyforce.com')
        render(
            <AuthProvider>
                <div>child</div>
            </AuthProvider>
        )

        await new Promise((resolve) => setTimeout(resolve, 0))
        expect(getSpy).not.toHaveBeenCalled()
    })

    it('fetches auth on mfa route even on ops host', async () => {
        setLocation('/mfa', 'ops.surrogacyforce.com')
        render(
            <AuthProvider>
                <div>child</div>
            </AuthProvider>
        )

        await waitFor(() => expect(getSpy).toHaveBeenCalled())
    })

    it('refreshes the user without returning to the loading state', async () => {
        setLocation('/settings', 'app.surrogacyforce.com')
        let auth: ReturnType<typeof useAuth> | undefined
        render(
            <AuthProvider>
                <AuthProbe onAuth={(value) => { auth = value }} />
            </AuthProvider>
        )
        expect(await screen.findByText('1')).toBeInTheDocument()

        let resolveMe: (user: { user_id: string }) => void = () => {}
        getSpy.mockReturnValueOnce(new Promise((resolve) => { resolveMe = resolve }))
        let refreshing: Promise<void> = Promise.resolve()
        act(() => { refreshing = auth!.refresh() })
        expect(screen.getByText('1')).toBeInTheDocument()

        await act(async () => {
            resolveMe({ user_id: '2' })
            await refreshing
        })
        expect(screen.getByText('2')).toBeInTheDocument()
    })

    it('keeps the user when a background refresh fails, and signs out on 401', async () => {
        setLocation('/settings', 'app.surrogacyforce.com')
        let auth: ReturnType<typeof useAuth> | undefined
        render(
            <AuthProvider>
                <AuthProbe onAuth={(value) => { auth = value }} />
            </AuthProvider>
        )
        expect(await screen.findByText('1')).toBeInTheDocument()

        getSpy.mockRejectedValueOnce(Object.assign(new Error('Server error'), { status: 500 }))
        await act(() => auth!.refresh())
        expect(screen.getByText('1')).toBeInTheDocument()
        expect(auth!.error?.message).toBe('Server error')

        getSpy.mockRejectedValueOnce(Object.assign(new Error('Unauthorized'), { status: 401 }))
        await act(() => auth!.refresh())
        expect(screen.getByText('signed out')).toBeInTheDocument()
        expect(auth!.error).toBeNull()
    })
})
