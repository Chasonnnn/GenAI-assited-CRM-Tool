import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import WelcomePage from '../app/(app)/welcome/page'

const replace = vi.fn()
const mockUseAuth = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        replace,
    }),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock('@/lib/api', () => ({
    default: {
        patch: vi.fn(),
    },
}))

vi.mock('sonner', () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
    },
}))

describe('WelcomePage', () => {
    beforeEach(() => {
        replace.mockReset()
        mockUseAuth.mockReset()
    })

    it('redirects to dashboard when profile is complete', async () => {
        mockUseAuth.mockReturnValue({
            user: {
                profile_complete: true,
                display_name: 'Test User',
                title: 'Case Manager',
                phone: null,
            },
            refetch: vi.fn(),
        })

        render(<WelcomePage />)

        await waitFor(() => {
            expect(replace).toHaveBeenCalledWith('/dashboard')
        })
    })

    it('renders the profile completion form when profile is incomplete', () => {
        mockUseAuth.mockReturnValue({
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
})
