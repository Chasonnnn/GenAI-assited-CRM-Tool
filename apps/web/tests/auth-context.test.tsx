import { render, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { AuthProvider } from '@/lib/auth-context'

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
})
