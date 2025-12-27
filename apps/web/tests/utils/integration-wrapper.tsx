/**
 * Integration Test Wrapper
 * 
 * Provides real QueryClientProvider for integration tests.
 * Use this instead of the global mock when testing data flow.
 */

import React, { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

interface WrapperProps {
    children: ReactNode
}

/**
 * Creates a fresh QueryClient for each test to prevent state leakage.
 */
export function createTestQueryClient() {
    return new QueryClient({
        defaultOptions: {
            queries: {
                retry: false, // Don't retry on failure in tests
                gcTime: Infinity, // Don't garbage collect during test
                staleTime: 0, // Always refetch
            },
            mutations: {
                retry: false,
            },
        },
    })
}

/**
 * Provider wrapper for integration tests.
 * 
 * Usage:
 * ```tsx
 * import { renderWithProviders } from '@/tests/utils/integration-wrapper'
 * 
 * test('loads cases', async () => {
 *   renderWithProviders(<CasesPage />)
 *   await screen.findByText('Jane Doe')
 * })
 * ```
 */
export function IntegrationWrapper({ children }: WrapperProps) {
    const queryClient = createTestQueryClient()

    return (
        <QueryClientProvider client={queryClient}>
            {children}
        </QueryClientProvider>
    )
}

/**
 * Custom render function for integration tests.
 * Wraps component with real QueryClientProvider.
 */
import { render, RenderOptions } from '@testing-library/react'

export function renderWithProviders(
    ui: React.ReactElement,
    options?: Omit<RenderOptions, 'wrapper'>
) {
    return render(ui, {
        wrapper: IntegrationWrapper,
        ...options,
    })
}

// Re-export everything from testing-library
export * from '@testing-library/react'
export { renderWithProviders as render }
