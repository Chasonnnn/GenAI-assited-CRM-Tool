import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import InvitePage from '../app/invite/[id]/page'

const mockApiGet = vi.fn()

vi.mock('next/navigation', () => ({
    useParams: () => ({ id: 'inv-123' }),
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

vi.mock('@/lib/api', () => ({
    default: {
        get: (...args: unknown[]) => mockApiGet(...args),
    },
}))

describe('InvitePage', () => {
    const originalApiBase = process.env.NEXT_PUBLIC_API_BASE_URL

    beforeEach(() => {
        mockApiGet.mockResolvedValue({
            id: 'inv-123',
            organization_name: 'Test Org',
            role: 'member',
            inviter_name: 'Test User',
            expires_at: null,
            status: 'pending',
        })
        process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.example.com'
    })

    afterEach(() => {
        process.env.NEXT_PUBLIC_API_BASE_URL = originalApiBase
        mockApiGet.mockReset()
    })

    it('redirects to backend Google login when continuing', async () => {
        render(<InvitePage />)

        await waitFor(() => {
            expect(screen.getByText("You're Invited")).toBeInTheDocument()
        })

        const button = screen.getByRole('button', { name: /continue with google/i })
        fireEvent.click(button)

        expect(window.location.assign).toHaveBeenCalledWith(
            'https://api.example.com/auth/google/login?return_to=app'
        )
    })
})
