import { describe, it, expect, vi, beforeEach } from "vitest"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import MFAPage from "../app/mfa/page"

const mockUseAuth = vi.fn()
const mockUseMFAStatus = vi.fn()
const mockUseDuoStatus = vi.fn()
const mockUseCompleteMFAChallenge = vi.fn()
const mockUseInitiateDuoAuth = vi.fn()
const mockReplace = vi.fn()

type Deferred<T> = {
    promise: Promise<T>
    resolve: (value: T) => void
}

function deferred<T>(): Deferred<T> {
    let resolve!: (value: T) => void
    const promise = new Promise<T>((res) => {
        resolve = res
    })
    return { promise, resolve }
}

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-mfa", () => ({
    useMFAStatus: () => mockUseMFAStatus(),
    useDuoStatus: () => mockUseDuoStatus(),
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
        mockUseCompleteMFAChallenge.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })
        mockUseInitiateDuoAuth.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })
    })

    it("offers Duo setup when the user is not enrolled", () => {
        render(<MFAPage />)

        expect(screen.queryByRole("button", { name: /continue with duo/i })).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: /set up duo/i })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /set up authenticator/i })).not.toBeInTheDocument()
        expect(screen.queryByText(/google authenticator/i)).not.toBeInTheDocument()
    })

    it("redirects app users to dashboard after completing MFA", async () => {
        const refetch = vi.fn()
        const mutateAsync = vi.fn().mockResolvedValue({ success: true })

        mockUseAuth.mockReturnValue({
            user: {
                email: "user@example.com",
                mfa_required: true,
                mfa_verified: false,
            },
            isLoading: false,
            refetch,
        })
        mockUseMFAStatus.mockReturnValue({
            data: {
                mfa_enabled: true,
                totp_enabled: false,
            },
            isLoading: false,
        })
        mockUseDuoStatus.mockReturnValue({
            data: {
                available: false,
                enrolled: false,
            },
            isLoading: false,
        })
        mockUseCompleteMFAChallenge.mockReturnValue({
            mutateAsync,
            isPending: false,
        })

        render(<MFAPage />)

        fireEvent.change(screen.getByLabelText(/recovery code/i), {
            target: { value: "RECOVERYCODE" },
        })
        fireEvent.click(screen.getByRole("button", { name: /verify code/i }))

        await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith("RECOVERYCODE"))
        await waitFor(() => expect(refetch).toHaveBeenCalled())
        await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/dashboard"))
    })

    it("redirects ops users after completing MFA and refreshing auth", async () => {
        const challenge = deferred<{ success: boolean }>()
        const authRefresh = deferred<void>()
        const refetch = vi.fn(() => authRefresh.promise)
        const mutateAsync = vi.fn(() => challenge.promise)
        window.sessionStorage.setItem("auth_return_to", "ops")

        mockUseAuth.mockReturnValue({
            user: {
                email: "ops@example.com",
                mfa_required: true,
                mfa_verified: false,
            },
            isLoading: false,
            refetch,
        })
        mockUseMFAStatus.mockReturnValue({
            data: {
                mfa_enabled: true,
                totp_enabled: false,
            },
            isLoading: false,
        })
        mockUseDuoStatus.mockReturnValue({
            data: {
                available: false,
                enrolled: false,
            },
            isLoading: false,
        })
        mockUseCompleteMFAChallenge.mockReturnValue({
            mutateAsync,
            isPending: false,
        })

        render(<MFAPage />)

        fireEvent.change(screen.getByLabelText(/recovery code/i), {
            target: { value: "RECOVERYCODE" },
        })
        fireEvent.click(screen.getByRole("button", { name: /verify code/i }))

        await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith("RECOVERYCODE"))
        expect(mockReplace).not.toHaveBeenCalled()

        await act(async () => {
            challenge.resolve({ success: true })
        })

        await waitFor(() => expect(refetch).toHaveBeenCalled())
        expect(mockReplace).not.toHaveBeenCalled()

        await act(async () => {
            authRefresh.resolve()
        })

        await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/ops"))
        expect(window.sessionStorage.getItem("auth_return_to")).toBeNull()
    })

    it("redirects verified app users away from MFA to dashboard", async () => {
        mockUseAuth.mockReturnValue({
            user: {
                email: "user@example.com",
                mfa_required: true,
                mfa_verified: true,
            },
            isLoading: false,
            refetch: vi.fn(),
        })

        render(<MFAPage />)

        await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/dashboard"))
    })
})
