import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { cookies } from 'next/headers'
import LoginPage from '../app/login/page'

vi.mock('next/headers', () => ({
    cookies: vi.fn(),
}))

type LoginSearchParams = Record<string, string | string[] | undefined>

function mockAuthHint(value?: string) {
    vi.mocked(cookies).mockResolvedValue({
        get: (name: string) =>
            name === 'auth_error_account_hint' && value ? { value } : undefined,
    } as Awaited<ReturnType<typeof cookies>>)
}

async function renderLoginPage(searchParams: LoginSearchParams = {}) {
    mockAuthHint()
    const page = await LoginPage({ searchParams: Promise.resolve(searchParams) })
    return render(page)
}

describe('LoginPage', () => {
    it('renders the login screen', async () => {
        await renderLoginPage()

        expect(screen.getByText('Welcome Back')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument()
        expect(screen.getByRole('link', { name: /privacy policy/i })).toHaveAttribute(
            'href',
            '/privacy'
        )
        expect(screen.getByRole('link', { name: /terms/i })).toHaveAttribute('href', '/terms')
        expect(screen.queryByText('Other sign-in methods')).not.toBeInTheDocument()
    })

    it('shows a clear no-membership failure state', async () => {
        await renderLoginPage({ error: 'no_membership' })

        const alert = screen.getByRole('alert')
        expect(alert).toHaveTextContent('Access not available')
        expect(alert).toHaveTextContent('selected by your browser')
        expect(alert).toHaveTextContent('team membership')
        expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument()
    })

    it('shows the selected Google account hint when one is available', async () => {
        mockAuthHint('mem...@example.com')
        const page = await LoginPage({ searchParams: Promise.resolve({ error: 'no_membership' }) })
        render(page)

        const alert = screen.getByRole('alert')
        expect(alert).toHaveTextContent('Google selected')
        expect(alert).toHaveTextContent('mem...@example.com')
    })

    it('offers a normal login link when an auth error is shown', async () => {
        await renderLoginPage({ error: 'no_membership' })

        const normalLoginLink = screen.getByRole('link', { name: /back to login/i })
        expect(normalLoginLink).toHaveAttribute('href', '/login')
    })

    it('shows an expired invite failure state', async () => {
        await renderLoginPage({ error: 'invite_expired' })

        expect(screen.getByRole('alert')).toHaveTextContent('Invite expired')
    })

    it('shows a generic failure state for unknown login errors', async () => {
        await renderLoginPage({ error: 'unexpected_error' })

        expect(screen.getByRole('alert')).toHaveTextContent('Sign-in could not continue')
    })

    it('shows loading state for Google sign-in button', async () => {
        vi.useFakeTimers()

        await renderLoginPage()

        const button = screen.getByRole('button', { name: /sign in with google/i })
        fireEvent.click(button)

        expect(button).toBeDisabled()
        expect(button).toHaveTextContent('Signing In...')

        vi.useRealTimers()
    })
})
