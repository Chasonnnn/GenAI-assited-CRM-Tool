import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest'
import { render, screen, act, fireEvent } from '@testing-library/react'
import { SearchCommandDialog } from '@/components/search-command'
import * as reactQuery from '@tanstack/react-query'

// Mock dependencies
vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn() }),
}))

// Note: useQuery is globally mocked in apps/web/tests/setup.ts
// This allows us to inspect calls without wrapping in QueryClientProvider

describe('SearchCommandDialog Debounce', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        vi.clearAllMocks()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it('debounces search input by 400ms', async () => {
        // Verify that useQuery is indeed mocked
        if (!vi.isMockFunction(reactQuery.useQuery)) {
            throw new Error('useQuery is not mocked! Check apps/web/tests/setup.ts')
        }

        // Mock onOpenChange
        const onOpenChange = vi.fn()

        render(<SearchCommandDialog open={true} onOpenChange={onOpenChange} />)

        const input = screen.getByPlaceholderText(/Search surrogates/i)

        // Type 'test'
        fireEvent.change(input, { target: { value: 'test' } })

        const useQueryMock = reactQuery.useQuery as Mock

        const isCalledWithTest = () => {
            return useQueryMock.mock.calls.some(call => {
                const options = call[0] as { queryKey: unknown[] }
                // The query key is ['search-command', debouncedQuery]
                return Array.isArray(options.queryKey) &&
                       options.queryKey[0] === 'search-command' &&
                       options.queryKey[1] === 'test'
            })
        }

        // Initially not called with 'test'
        expect(isCalledWithTest()).toBe(false)

        // Fast forward 399ms
        act(() => {
            vi.advanceTimersByTime(399)
        })

        expect(isCalledWithTest()).toBe(false)

        // Fast forward another 2ms (total > 400ms)
        act(() => {
            vi.advanceTimersByTime(2)
        })

        expect(isCalledWithTest()).toBe(true)
    })
})
