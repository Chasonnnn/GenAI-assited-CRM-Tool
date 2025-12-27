/**
 * Example Integration Test - Permissions Page
 * 
 * Demonstrates how to use MSW + real QueryClient for integration testing.
 * This tests actual data flow rather than mocking hooks.
 */

import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../utils/integration-wrapper'
import { server } from '../mocks/server'
import { http, HttpResponse } from 'msw'
import { useQuery } from '@tanstack/react-query'

// Mock next/navigation
vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: vi.fn(),
        back: vi.fn(),
        refresh: vi.fn(),
    }),
    useParams: () => ({}),
    usePathname: () => '/settings/team',
}))

// Mock auth context with proper permissions
vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({
        user: {
            user_id: '550e8400-e29b-41d4-a716-446655440020',
            email: 'admin@example.com',
            display_name: 'Admin User',
            role: 'admin',
        },
        isLoading: false,
    }),
}))

// Simple test component that uses React Query
function PermissionsTestComponent() {
    const { data, isLoading, error } = useQuery({
        queryKey: ['permissions', 'available'],
        queryFn: async () => {
            const res = await fetch('http://localhost:8000/settings/permissions/available')
            if (!res.ok) throw new Error('Failed to fetch')
            return res.json()
        },
    })

    if (isLoading) return <div>Loading...</div>
    if (error) return <div>Error: {(error as Error).message}</div>

    return (
        <ul>
            {data?.map((p: { key: string; label: string }) => (
                <li key={p.key}>{p.label}</li>
            ))}
        </ul>
    )
}

describe('Integration: Permissions', () => {
    it('loads permissions from API via MSW', async () => {
        renderWithProviders(<PermissionsTestComponent />)

        // Initially shows loading
        expect(screen.getByText('Loading...')).toBeInTheDocument()

        // Wait for data to load
        await waitFor(() => {
            expect(screen.getByText('View Cases')).toBeInTheDocument()
        })

        // Verify all permissions are rendered
        expect(screen.getByText('Edit Cases')).toBeInTheDocument()
        expect(screen.getByText('View Tasks')).toBeInTheDocument()
    })

    it('handles API errors gracefully', async () => {
        // Override handler for this specific test
        server.use(
            http.get('http://localhost:8000/settings/permissions/available', () => {
                return new HttpResponse(null, { status: 500 })
            })
        )

        renderWithProviders(<PermissionsTestComponent />)

        // Wait for error state
        await waitFor(() => {
            expect(screen.getByText(/Error:/)).toBeInTheDocument()
        })
    })

    it('renders empty state for empty response', async () => {
        // Override handler to return empty array
        server.use(
            http.get('http://localhost:8000/settings/permissions/available', () => {
                return HttpResponse.json([])
            })
        )

        renderWithProviders(<PermissionsTestComponent />)

        await waitFor(() => {
            expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
        })

        // No list items should be rendered
        expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
    })
})
