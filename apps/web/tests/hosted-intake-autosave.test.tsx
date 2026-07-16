import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useHostedIntakeAutosave } from "@/lib/hooks/use-hosted-intake-autosave"

describe("useHostedIntakeAutosave", () => {
    beforeEach(() => {
        vi.useFakeTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("debounces the latest save, consumes restoration skips, and cancels on unmount", () => {
        const skipNextSaveRef = { current: false }
        const firstSave = vi.fn()
        const latestSave = vi.fn()
        const view = renderHook(
            ({ enabled, scopeKey, trigger, onSave }) =>
                useHostedIntakeAutosave({
                    enabled,
                    scopeKey,
                    trigger,
                    skipNextSaveRef,
                    onSave,
                }),
            {
                initialProps: {
                    enabled: false,
                    scopeKey: "event-1:session-1",
                    trigger: "empty",
                    onSave: firstSave,
                },
            }
        )

        view.rerender({
            enabled: true,
            scopeKey: "event-1:session-1",
            trigger: "first answers",
            onSave: firstSave,
        })
        view.rerender({
            enabled: true,
            scopeKey: "event-1:session-1",
            trigger: "latest answers",
            onSave: latestSave,
        })

        act(() => {
            vi.advanceTimersByTime(1499)
        })
        expect(firstSave).not.toHaveBeenCalled()
        expect(latestSave).not.toHaveBeenCalled()

        act(() => {
            vi.advanceTimersByTime(1)
        })
        expect(latestSave).toHaveBeenCalledTimes(1)

        skipNextSaveRef.current = true
        view.rerender({
            enabled: true,
            scopeKey: "event-1:session-1",
            trigger: "restored answers",
            onSave: latestSave,
        })
        expect(skipNextSaveRef.current).toBe(false)
        act(() => {
            vi.advanceTimersByTime(1500)
        })
        expect(latestSave).toHaveBeenCalledTimes(1)

        view.rerender({
            enabled: true,
            scopeKey: "event-2:session-2",
            trigger: "new session answers",
            onSave: latestSave,
        })
        view.unmount()
        act(() => {
            vi.advanceTimersByTime(1500)
        })
        expect(latestSave).toHaveBeenCalledTimes(1)
    })
})
