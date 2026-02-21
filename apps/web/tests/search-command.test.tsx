import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { SearchCommandDialog } from '@/components/search-command'
import * as searchApi from '@/lib/api/search'

// Mock useRouter
vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: vi.fn(),
    }),
}))

// Mock globalSearch
vi.mock('@/lib/api/search', () => ({
    globalSearch: vi.fn(),
}))

// Override useQuery mock to execute queryFn so we can verify globalSearch is called
vi.mock('@tanstack/react-query', async (importOriginal) => {
    const actual = await importOriginal<typeof import('@tanstack/react-query')>()
    return {
        ...actual,
        useQuery: vi.fn((options: any) => {
            // Check enabled flag from options
            if (options.enabled !== false && typeof options.queryFn === 'function') {
                options.queryFn()
            }
            return {
                data: null,
                isLoading: false,
                error: null,
                refetch: vi.fn(),
            }
        }),
    }
})

describe('SearchCommandDialog Debounce', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        vi.clearAllMocks()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it('debounces the search query by 400ms', async () => {
        const onOpenChange = vi.fn()
        render(<SearchCommandDialog open={true} onOpenChange={onOpenChange} />)

        const input = screen.getByPlaceholderText('Search surrogates, intended parents, notes, files...')

        // Type "test"
        fireEvent.change(input, { target: { value: 'test' } })

        // Initial render (empty query) might call globalSearch if enabled logic allows.
        // In component: enabled: open && debouncedQuery.length >= 2
        // Initial debouncedQuery is "", length < 2, so NOT enabled.
        // So globalSearch should NOT be called initially.
        expect(searchApi.globalSearch).not.toHaveBeenCalled()

        // Advance by 200ms
        await act(async () => {
            vi.advanceTimersByTime(200)
        })

        // Should NOT be called yet (since we increased to 400ms)
        expect(searchApi.globalSearch).not.toHaveBeenCalled()

        // Advance by another 150ms (total 350ms)
        await act(async () => {
            vi.advanceTimersByTime(150)
        })

        // Still should NOT be called
        expect(searchApi.globalSearch).not.toHaveBeenCalled()

        // Advance by 100ms (total 450ms > 400ms)
        await act(async () => {
            vi.advanceTimersByTime(100)
        })

        // Now it should have been called with { q: "test", limit: 10 }
        expect(searchApi.globalSearch).toHaveBeenCalledWith({ q: "test", limit: 10 })
    })
})
