import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useFormBuilderAutosave } from "@/lib/forms/use-form-builder-autosave"

async function advance(ms: number) {
    await act(async () => {
        await vi.advanceTimersByTimeAsync(ms)
    })
}

describe("useFormBuilderAutosave", () => {
    beforeEach(() => {
        vi.useFakeTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("saves the active draft only after the debounce interval", async () => {
        const save = vi.fn()

        renderHook(() =>
            useFormBuilderAutosave({
                enabled: true,
                fingerprint: "draft-1",
                savedFingerprint: "draft-0",
                failedFingerprint: "",
                save,
            }),
        )

        await advance(1199)
        expect(save).not.toHaveBeenCalled()

        await advance(1)
        expect(save).toHaveBeenCalledTimes(1)
    })

    it("waits while disabled and skips a draft that is already saved or failed", async () => {
        const save = vi.fn()
        type Props = { enabled: boolean; savedFingerprint: string; failedFingerprint: string }
        const { rerender } = renderHook(
            ({ enabled, savedFingerprint, failedFingerprint }: Props) =>
                useFormBuilderAutosave({ enabled, fingerprint: "draft-1", savedFingerprint, failedFingerprint, save }),
            { initialProps: { enabled: false, savedFingerprint: "draft-0", failedFingerprint: "" } },
        )

        await advance(5000)
        expect(save).not.toHaveBeenCalled()

        rerender({ enabled: true, savedFingerprint: "draft-1", failedFingerprint: "" })
        await advance(5000)
        expect(save).not.toHaveBeenCalled()

        rerender({ enabled: true, savedFingerprint: "draft-0", failedFingerprint: "draft-1" })
        await advance(5000)
        expect(save).not.toHaveBeenCalled()

        rerender({ enabled: true, savedFingerprint: "draft-0", failedFingerprint: "" })
        await advance(1200)
        expect(save).toHaveBeenCalledTimes(1)
    })
})
