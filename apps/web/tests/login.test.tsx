import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import LoginPage from '../app/login/page'

describe('LoginPage', () => {
    it('renders and can reveal other sign-in form', () => {
        render(<LoginPage />)

        expect(screen.getByText('Welcome Back')).toBeInTheDocument()

        fireEvent.click(screen.getByText('Other sign-in methods'))
        expect(screen.getByLabelText('Email (optional)')).toBeInTheDocument()
    })

    it('shows loading state for Google sign-in button', () => {
        vi.useFakeTimers()

        render(<LoginPage />)

        const button = screen.getByRole('button', { name: /sign in with google/i })
        fireEvent.click(button)

        expect(button).toBeDisabled()
        expect(button).toHaveTextContent('Signing In...')

        vi.useRealTimers()
    })
})
