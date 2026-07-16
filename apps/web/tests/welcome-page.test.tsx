import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { renderToString } from 'react-dom/server'
import WelcomePage from '../app/(app)/welcome/page'

const mocks = vi.hoisted(() => ({
    redirect: vi.fn(),
    replace: vi.fn(),
    push: vi.fn(),
    useAuth: vi.fn(),
    patchProfile: vi.fn(),
}))

vi.mock('next/navigation', () => ({
    redirect: (path: string) => mocks.redirect(path),
    useRouter: () => ({
        replace: mocks.replace,
        push: mocks.push,
    }),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mocks.useAuth(),
}))

vi.mock('@/lib/api', () => ({
    default: {
        patch: mocks.patchProfile,
    },
}))

vi.mock('@/components/ui/toast', () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
    },
}))

describe('WelcomePage', () => {
    beforeEach(() => {
        mocks.redirect.mockReset()
        mocks.replace.mockReset()
        mocks.push.mockReset()
        mocks.patchProfile.mockReset()
        mocks.useAuth.mockReset()
    })

    it('redirects to dashboard during the initial render when profile is complete', () => {
        mocks.useAuth.mockReturnValue({
            user: {
                profile_complete: true,
                display_name: 'Test User',
                title: 'Case Manager',
                phone: null,
            },
            refetch: vi.fn(),
        })

        renderToString(<WelcomePage />)

        expect(mocks.redirect).toHaveBeenCalledWith('/dashboard')
        expect(mocks.replace).not.toHaveBeenCalled()
    })

    it('renders the profile completion form when profile is incomplete', () => {
        mocks.useAuth.mockReturnValue({
            user: {
                profile_complete: false,
                display_name: '',
                title: '',
                phone: null,
            },
            refetch: vi.fn(),
        })

        render(<WelcomePage />)

        expect(screen.getByText('Welcome to Surrogacy Force')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /complete profile/i })).toBeInTheDocument()
    })

    it('submits a valid title entered after the profile reset', async () => {
        const refetch = vi.fn().mockResolvedValue(undefined)
        mocks.patchProfile.mockResolvedValue({})
        mocks.useAuth.mockReturnValue({
            user: {
                profile_complete: false,
                display_name: 'Test Intake',
                title: '',
                phone: null,
            },
            refetch,
        })

        render(<WelcomePage />)

        fireEvent.input(screen.getByLabelText(/job title/i), {
            target: { value: 'Intake Specialist' },
        })
        fireEvent.click(screen.getByRole('button', { name: /complete profile/i }))

        await waitFor(() => {
            expect(mocks.patchProfile).toHaveBeenCalledWith('/auth/me', {
                display_name: 'Test Intake',
                title: 'Intake Specialist',
                phone: null,
            })
        })
        expect(refetch).toHaveBeenCalledTimes(1)
        expect(mocks.push).toHaveBeenCalledWith('/dashboard')
        expect(screen.queryByText('Title must be at least 2 characters')).not.toBeInTheDocument()
    })

    it('preserves profile edits when equivalent auth data rerenders', async () => {
        const user = {
            user_id: 'user-1',
            profile_complete: false,
            display_name: 'Test Intake',
            title: '',
            phone: null,
        }
        let authState = { user, refetch: vi.fn() }
        mocks.useAuth.mockImplementation(() => authState)

        const view = render(<WelcomePage />)
        fireEvent.input(screen.getByLabelText(/job title/i), {
            target: { value: 'Intake Specialist' },
        })

        authState = { user: { ...user }, refetch: authState.refetch }
        await act(async () => {
            view.rerender(<WelcomePage />)
            await Promise.resolve()
        })

        expect(screen.getByLabelText(/job title/i)).toHaveValue('Intake Specialist')
    })
})
