import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest'
import { SearchCommandDialog } from '@/components/search-command'
import * as searchApi from '@/lib/api/search'
import { useQuery } from '@tanstack/react-query'

// Mock dependencies
vi.mock('@/lib/api/search', () => ({
    globalSearch: vi.fn(),
}))

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: vi.fn(),
    }),
}))

// Override the global useQuery mock for this test file
vi.mock('@tanstack/react-query', async () => {
    // We need to partially mock it, but we can't use importOriginal inside vi.mock factory easily
    // if we want to change implementation per test, so we just mock the function we need.
    return {
        useQuery: vi.fn(),
    }
})

describe('SearchCommandDialog Debounce', () => {
    beforeEach(() => {
        vi.useFakeTimers();

        // Setup useQuery to execute the queryFn when called
        // We simulate the behavior where useQuery calls the queryFn when enabled is true
        // and keys change.
        (useQuery as Mock).mockImplementation(({ queryFn, enabled }) => {
            if (enabled) {
                queryFn()
            }
            return {
                data: null,
                isLoading: false,
            }
        })
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it('triggers search after 500ms debounce (optimized)', async () => {
        render(<SearchCommandDialog open={true} onOpenChange={() => {}} />)

        const input = screen.getByPlaceholderText(/Search surrogates/i)

        // Type 'test'
        fireEvent.change(input, { target: { value: 'test' } })

        // At 0ms, useDebouncedValue hasn't updated yet.
        expect(searchApi.globalSearch).not.toHaveBeenCalled()

        // Advance 250ms (previous debounce time + buffer)
        // With 500ms debounce, this should NO LONGER trigger search
        act(() => {
            vi.advanceTimersByTime(250)
        })
        expect(searchApi.globalSearch).not.toHaveBeenCalled()

        // Advance another 300ms (total 550ms)
        // This should trigger the search now
        act(() => {
            vi.advanceTimersByTime(300)
        })

        expect(searchApi.globalSearch).toHaveBeenCalledWith(expect.objectContaining({
            q: 'test'
        }))
    })
})
