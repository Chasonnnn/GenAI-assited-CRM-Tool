import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import SecuritySettingsPage from "../app/(app)/settings/security/page"

const mockUseMFAStatus = vi.fn()
const mockUseDuoStatus = vi.fn()
const mockUseInitiateDuoAuth = vi.fn()
const mockUseRegenerateRecoveryCodes = vi.fn()
const mockUseDisableMFA = vi.fn()

vi.mock("@/lib/hooks/use-mfa", () => ({
    useMFAStatus: () => mockUseMFAStatus(),
    useDuoStatus: () => mockUseDuoStatus(),
    useInitiateDuoAuth: () => mockUseInitiateDuoAuth(),
    useRegenerateRecoveryCodes: () => mockUseRegenerateRecoveryCodes(),
    useDisableMFA: () => mockUseDisableMFA(),
}))

describe("SecuritySettingsPage", () => {
    beforeEach(() => {
        mockUseMFAStatus.mockReturnValue({
            data: {
                mfa_enabled: false,
                recovery_codes_remaining: 0,
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
        mockUseInitiateDuoAuth.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })
        mockUseRegenerateRecoveryCodes.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })
        mockUseDisableMFA.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })
    })

    it("shows Duo setup and removes authenticator setup copy", () => {
        render(<SecuritySettingsPage />)

        expect(screen.getByRole("button", { name: /set up duo/i })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /set up authenticator/i })).not.toBeInTheDocument()
        expect(screen.queryByText(/google authenticator/i)).not.toBeInTheDocument()
    })
})
