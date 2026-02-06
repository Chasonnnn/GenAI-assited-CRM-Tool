import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, waitFor } from "@testing-library/react"
import DuoCallbackPage from "../app/auth/duo/callback/page"

const mockUseAuth = vi.fn()
const mockVerifyDuoCallback = vi.fn()
const mockReplace = vi.fn()

let authState: { user: Record<string, unknown> | null; isLoading: boolean; refetch: () => void }

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/api/mfa", () => ({
    verifyDuoCallback: (...args: unknown[]) => mockVerifyDuoCallback(...args),
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        replace: mockReplace,
        push: vi.fn(),
        back: vi.fn(),
        prefetch: vi.fn(),
    }),
}))

describe("DuoCallbackPage", () => {
    beforeEach(() => {
        try {
            window.history.pushState({}, "", "/auth/duo/callback?duo_code=duo-code&state=state123")
        } catch {
            // Some test setups replace window.location with a plain object not linked to history.
        }

        try {
            // @ts-expect-error - window.location may be a test stub.
            window.location.search = "?duo_code=duo-code&state=state123"
        } catch {
            // Ignore if the environment uses a real Location object.
        }
        window.sessionStorage.clear()

        authState = {
            user: { role: "admin" },
            isLoading: false,
            refetch: vi.fn(),
        }
        mockUseAuth.mockImplementation(() => authState)
        mockVerifyDuoCallback.mockReset()
        mockVerifyDuoCallback.mockResolvedValue({ success: true, message: "ok" })
        mockReplace.mockClear()
    })

    it("verifies duo callback once per code/state", async () => {
        const { unmount } = render(<DuoCallbackPage />)

        await waitFor(() => expect(mockVerifyDuoCallback).toHaveBeenCalledTimes(1))

        unmount()
        authState.user = { role: "admin", mfa_verified: true }
        render(<DuoCallbackPage />)

        await waitFor(() => expect(mockVerifyDuoCallback).toHaveBeenCalledTimes(1))
    })
})
