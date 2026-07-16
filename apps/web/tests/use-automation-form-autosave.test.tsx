import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useAutomationFormAutosave } from "@/lib/forms/use-automation-form-autosave"

describe("useAutomationFormAutosave", () => {
    beforeEach(() => {
        vi.useFakeTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("saves an active draft only after the debounce interval", async () => {
        const save = vi.fn().mockResolvedValue({ id: "form-1" })
        const onSaving = vi.fn()
        const onSaved = vi.fn()
        const onError = vi.fn()

        renderHook(() =>
            useAutomationFormAutosave({
                enabled: true,
                fingerprint: "draft-1",
                savedFingerprint: "draft-0",
                save,
                onSaving,
                onSaved,
                onError,
            }),
        )

        await act(async () => {
            await vi.advanceTimersByTimeAsync(1199)
        })
        expect(save).not.toHaveBeenCalled()

        await act(async () => {
            await vi.advanceTimersByTimeAsync(1)
        })

        expect(onSaving).toHaveBeenCalledTimes(1)
        expect(save).toHaveBeenCalledTimes(1)
        expect(onSaved).toHaveBeenCalledWith({ id: "form-1" })
        expect(onError).not.toHaveBeenCalled()
    })
})
