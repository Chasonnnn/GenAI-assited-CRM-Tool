import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import MFAPage from "../app/mfa/page"

const mockUseAuth = vi.fn()
const mockUseMFAStatus = vi.fn()
const mockUseDuoStatus = vi.fn()
const mockUseSetupTOTP = vi.fn()
const mockUseVerifyTOTPSetup = vi.fn()
const mockUseCompleteMFAChallenge = vi.fn()
const mockUseInitiateDuoAuth = vi.fn()
const mockReplace = vi.fn()

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-mfa", () => ({
    useMFAStatus: () => mockUseMFAStatus(),
    useDuoStatus: () => mockUseDuoStatus(),
    useSetupTOTP: () => mockUseSetupTOTP(),
    useVerifyTOTPSetup: () => mockUseVerifyTOTPSetup(),
    useCompleteMFAChallenge: () => mockUseCompleteMFAChallenge(),
    useInitiateDuoAuth: () => mockUseInitiateDuoAuth(),
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        replace: mockReplace,
        push: vi.fn(),
        back: vi.fn(),
        prefetch: vi.fn(),
    }),
}))

describe("MFAPage", () => {
    beforeEach(() => {
        window.sessionStorage.clear()
        mockReplace.mockReset()
        mockUseAuth.mockReturnValue({
            user: {
                email: "user@example.com",
                mfa_required: true,
                mfa_verified: false,
            },
            isLoading: false,
            refetch: vi.fn(),
        })
        mockUseMFAStatus.mockReturnValue({
            data: {
                mfa_enabled: false,
                totp_enabled: false,
            },
            isLoading: false,
        })
        mockUseDuoStatus.mockReturnValue({
            data: {
                available: true,
                enrolled: false,
            },
            isLoading: false,
        })
        mockUseSetupTOTP.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })
        mockUseVerifyTOTPSetup.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })
        mockUseCompleteMFAChallenge.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })
        mockUseInitiateDuoAuth.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })
    })

    it("does not offer Duo when the user is not enrolled", () => {
        render(<MFAPage />)

        expect(screen.queryByRole("button", { name: /continue with duo/i })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /set up duo/i })).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: /set up authenticator/i })).toBeInTheDocument()
    })
})
