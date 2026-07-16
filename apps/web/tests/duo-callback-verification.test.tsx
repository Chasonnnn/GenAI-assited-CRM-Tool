import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useDuoCallbackVerification } from "@/lib/hooks/use-duo-callback-verification"

const mockVerifyDuoCallback = vi.fn()
let callbackAttempt = 0
let callbackCode = ""
let callbackState = ""

vi.mock("@/lib/api/mfa", () => ({
    verifyDuoCallback: (...args: unknown[]) => mockVerifyDuoCallback(...args),
}))

describe("useDuoCallbackVerification", () => {
    beforeEach(() => {
        callbackAttempt += 1
        callbackCode = `hook-code-${callbackAttempt}`
        callbackState = `hook-state-${callbackAttempt}`
        const search = `?duo_code=${callbackCode}&state=${callbackState}`
        try {
            window.history.pushState({}, "", `/auth/duo/callback${search}`)
        } catch {
            // Some test setups replace window.location with a plain object not linked to history.
        }
        try {
            // @ts-expect-error - window.location may be a test stub.
            window.location.search = search
        } catch {
            // Ignore if the environment uses a real Location object.
        }
        mockVerifyDuoCallback.mockReset()
        mockVerifyDuoCallback.mockResolvedValue({ success: true, message: "ok" })
    })

    it("verifies one callback attempt, refreshes auth, and completes app navigation", async () => {
        const refreshAuth = vi.fn().mockResolvedValue(undefined)
        const replace = vi.fn()

        const { rerender } = renderHook(() =>
            useDuoCallbackVerification({
                enabled: true,
                refreshAuth,
                replace,
                returnTo: "app",
            }),
        )

        await waitFor(() => {
            expect(mockVerifyDuoCallback).toHaveBeenCalledWith(
                callbackCode,
                callbackState,
                "app",
            )
        })
        await waitFor(() => expect(refreshAuth).toHaveBeenCalledTimes(1))
        await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"))

        rerender()

        expect(mockVerifyDuoCallback).toHaveBeenCalledTimes(1)
    })

    it("does not refresh auth or navigate after its owner unmounts", async () => {
        let resolveVerification!: (result: { success: boolean; message: string }) => void
        const verification = new Promise<{ success: boolean; message: string }>((resolve) => {
            resolveVerification = resolve
        })
        mockVerifyDuoCallback.mockReturnValue(verification)
        const refreshAuth = vi.fn().mockResolvedValue(undefined)
        const replace = vi.fn()

        const { unmount } = renderHook(() =>
            useDuoCallbackVerification({
                enabled: true,
                refreshAuth,
                replace,
                returnTo: "app",
            }),
        )

        await waitFor(() => expect(mockVerifyDuoCallback).toHaveBeenCalledTimes(1))
        unmount()

        await act(async () => {
            resolveVerification({ success: true, message: "ok" })
            await verification
        })

        expect(refreshAuth).not.toHaveBeenCalled()
        expect(replace).not.toHaveBeenCalled()
    })
})
