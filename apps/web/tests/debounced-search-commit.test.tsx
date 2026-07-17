import { act, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { useDebouncedSearchCommit } from "@/lib/hooks/use-debounced-search-commit"

describe("useDebouncedSearchCommit", () => {
    afterEach(() => {
        vi.useRealTimers()
    })

    it("cancels pending commits when the URL scope changes or the owner unmounts", () => {
        vi.useFakeTimers()
        const firstCommit = vi.fn()
        const secondCommit = vi.fn()
        const view = renderHook(
            ({ scopeKey }) => useDebouncedSearchCommit(scopeKey),
            { initialProps: { scopeKey: "page=1" } }
        )

        act(() => {
            view.result.current.schedule(firstCommit, 300)
        })
        act(() => {
            view.rerender({ scopeKey: "page=2" })
        })
        act(() => {
            vi.advanceTimersByTime(300)
        })
        expect(firstCommit).not.toHaveBeenCalled()

        act(() => {
            view.result.current.schedule(secondCommit, 300)
            vi.advanceTimersByTime(300)
        })
        expect(secondCommit).toHaveBeenCalledTimes(1)

        const unmountedCommit = vi.fn()
        act(() => {
            view.result.current.schedule(unmountedCommit, 300)
        })
        act(() => {
            view.unmount()
        })
        act(() => {
            vi.advanceTimersByTime(300)
        })
        expect(unmountedCommit).not.toHaveBeenCalled()
    })
})
