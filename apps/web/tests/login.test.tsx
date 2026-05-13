import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import LoginPage from '../app/login/page'

type LoginSearchParams = Record<string, string | string[] | undefined>

async function renderLoginPage(searchParams: LoginSearchParams = {}) {
    const page = await LoginPage({ searchParams: Promise.resolve(searchParams) })
    return render(page)
}

describe('LoginPage', () => {
    it('renders the login screen', async () => {
        await renderLoginPage()

        expect(screen.getByText('Welcome Back')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument()
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
