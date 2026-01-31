import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, waitFor } from "@testing-library/react"
import DuoCallbackPage from "../app/auth/duo/callback/page"

const mockUseAuth = vi.fn()
const mockVerifyDuoCallback = vi.fn()
const mockReplace = vi.fn()

const mockSearchParams = {
    get: vi.fn((key: string) => {
        if (key === "duo_code") return "duo-code"
        if (key === "code") return null
        if (key === "state") return "state123"
        if (key === "return_to") return null
        return null
    }),
}

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
    useSearchParams: () => mockSearchParams,
}))

describe("DuoCallbackPage", () => {
    beforeEach(() => {
        authState = {
            user: { role: "admin" },
            isLoading: false,
            refetch: vi.fn(),
        }
        mockUseAuth.mockImplementation(() => authState)
        mockVerifyDuoCallback.mockReset()
        mockVerifyDuoCallback.mockResolvedValue({ success: true, message: "ok" })
        mockSearchParams.get.mockClear()
        mockSearchParams.get.mockImplementation((key: string) => {
            if (key === "duo_code") return "duo-code"
            if (key === "code") return null
            if (key === "state") return "state123"
            if (key === "return_to") return null
            return null
        })
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
