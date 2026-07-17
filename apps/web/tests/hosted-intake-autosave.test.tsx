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
        const firstSave = vi.fn()
        const latestSave = vi.fn()
        const onSkipNextSave = vi.fn()
        const view = renderHook(
            ({ enabled, scopeKey, trigger, skipNextSave, onSave }) =>
                useHostedIntakeAutosave({
                    enabled,
                    scopeKey,
                    trigger,
                    skipNextSave,
                    onSkipNextSave,
                    onSave,
                }),
            {
                initialProps: {
                    enabled: false,
                    scopeKey: "event-1:session-1",
                    trigger: "empty",
                    skipNextSave: false,
                    onSave: firstSave,
                },
            }
        )

        view.rerender({
            enabled: true,
            scopeKey: "event-1:session-1",
            trigger: "first answers",
            skipNextSave: false,
            onSave: firstSave,
        })
        view.rerender({
            enabled: true,
            scopeKey: "event-1:session-1",
            trigger: "latest answers",
            skipNextSave: false,
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

        view.rerender({
            enabled: true,
            scopeKey: "event-1:session-1",
            trigger: "restored answers",
            skipNextSave: true,
            onSave: latestSave,
        })
        expect(onSkipNextSave).toHaveBeenCalledTimes(1)
        act(() => {
            vi.advanceTimersByTime(1500)
        })
        expect(latestSave).toHaveBeenCalledTimes(1)

        view.rerender({
            enabled: true,
            scopeKey: "event-2:session-2",
            trigger: "new session answers",
            skipNextSave: false,
            onSave: latestSave,
        })
        view.unmount()
        act(() => {
            vi.advanceTimersByTime(1500)
        })
        expect(latestSave).toHaveBeenCalledTimes(1)
    })
})
