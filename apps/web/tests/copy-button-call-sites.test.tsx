import { act, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest"

import AppointmentsPage from "../app/(app)/appointments/page"
import SecuritySettingsPage from "../app/(app)/settings/security/page"
import DuoCallbackPage from "../app/auth/duo/callback/page.client"

const mocks = vi.hoisted(() => ({
    toastError: vi.fn(),
    useBookingLink: vi.fn(),
    useMFAStatus: vi.fn(),
    regenerateCodes: vi.fn(),
    useAuth: vi.fn(),
    verifyDuoCallback: vi.fn(),
    router: { replace: vi.fn(), push: vi.fn(), back: vi.fn(), prefetch: vi.fn() },
}))

vi.mock("@/components/ui/toast", () => ({
    toast: { error: mocks.toastError, success: vi.fn() },
}))

vi.mock("@/components/appointments/AppointmentsList", () => ({
    AppointmentsList: () => null,
}))

vi.mock("@/lib/hooks/use-appointments", () => ({
    useBookingLink: () => mocks.useBookingLink(),
}))

vi.mock("@/lib/hooks/use-mfa", () => ({
    useMFAStatus: () => mocks.useMFAStatus(),
    useDuoStatus: () => ({ data: { available: true, enrolled: true }, isLoading: false }),
    useInitiateDuoAuth: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRegenerateRecoveryCodes: () => ({ mutateAsync: mocks.regenerateCodes, isPending: false }),
    useDisableMFA: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mocks.useAuth(),
}))

vi.mock("@/lib/api/mfa", () => ({
    verifyDuoCallback: (...args: unknown[]) => mocks.verifyDuoCallback(...args),
}))

vi.mock("next/navigation", () => ({
    redirect: vi.fn(),
    useRouter: () => mocks.router,
}))

let writeText: MockInstance<(data: string) => Promise<void>>

beforeEach(() => {
    writeText = vi.spyOn(navigator.clipboard, "writeText")
    mocks.toastError.mockClear()
})

afterEach(() => {
    writeText.mockRestore()
})

describe("booking link copy on the appointments page", () => {
    beforeEach(() => {
        mocks.useBookingLink.mockReturnValue({
            data: { full_url: "https://example.com/book/abc", public_slug: "abc" },
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })
    })

    it("names the icon-only copy button and reports a failed write", async () => {
        writeText.mockRejectedValue(new Error("denied"))
        render(<AppointmentsPage />)

        fireEvent.click(screen.getByRole("button", { name: "Share booking link" }))
        const copyButton = await screen.findByRole("button", { name: "Copy booking link" })
        // The full URL stays readable and the dialog opens on the copy button, not the field.
        expect(screen.getByRole("textbox", { name: "Booking link" })).toHaveValue("https://example.com/book/abc")
        await vi.waitFor(() => expect(copyButton).toHaveFocus())
        expect(screen.getByRole("link", { name: "Scheduling settings" })).toHaveAttribute("href", "/settings/appointments")
        await act(async () => {
            fireEvent.click(copyButton)
        })

        expect(writeText).toHaveBeenCalledWith("https://example.com/book/abc")
        expect(copyButton).not.toHaveAttribute("data-copied")
        expect(mocks.toastError).toHaveBeenCalledWith("Failed to copy")
    })
})

describe("recovery code copy on the security settings page", () => {
    beforeEach(() => {
        mocks.useMFAStatus.mockReturnValue({
            data: { mfa_enabled: true, recovery_codes_remaining: 8 },
            isLoading: false,
        })
        mocks.regenerateCodes.mockResolvedValue({ codes: ["AAAA-1111", "BBBB-2222"] })
    })

    async function openRecoveryCodes() {
        render(<SecuritySettingsPage />)
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Regenerate recovery codes" }))
        })
        return screen.findByRole("button", { name: "Copy All" })
    }

    it("keeps the Copy All label after a successful copy", async () => {
        writeText.mockResolvedValue(undefined)
        const copyButton = await openRecoveryCodes()

        await act(async () => {
            fireEvent.click(copyButton)
        })

        expect(writeText).toHaveBeenCalledWith("AAAA-1111\nBBBB-2222")
        expect(copyButton).toHaveAccessibleName("Copy All")
        expect(copyButton).toHaveAttribute("data-copied")
        expect(screen.getByText("Copied")).toHaveClass("sr-only")
    })

    it("does not claim success when the write fails", async () => {
        writeText.mockRejectedValue(new Error("denied"))
        const copyButton = await openRecoveryCodes()

        await act(async () => {
            fireEvent.click(copyButton)
        })

        expect(copyButton).toHaveAccessibleName("Copy All")
        expect(copyButton).not.toHaveAttribute("data-copied")
        expect(screen.queryByText(/^Copied/)).not.toBeInTheDocument()
        expect(mocks.toastError).toHaveBeenCalledWith("Failed to copy")
    })
})

describe("recovery code copy on the Duo callback page", () => {
    beforeEach(() => {
        const search = "?duo_code=copy-code&state=copy-state"
        window.history.pushState({}, "", `/auth/duo/callback${search}`)
        try {
            // tests/setup.ts may replace window.location with a plain object that pushState does not update.
            window.location.search = search
        } catch {
            // Ignore if the environment uses a real Location object.
        }
        window.sessionStorage.clear()
        mocks.useAuth.mockReturnValue({ user: { role: "admin" }, isLoading: false, refetch: vi.fn() })
        mocks.verifyDuoCallback.mockResolvedValue({
            success: true,
            message: "ok",
            recovery_codes: ["CODE-1", "CODE-2"],
        })
    })

    it("keeps the Copy All label after a successful copy", async () => {
        writeText.mockResolvedValue(undefined)
        render(<DuoCallbackPage />)

        const copyButton = await screen.findByRole("button", { name: "Copy All" })
        await act(async () => {
            fireEvent.click(copyButton)
        })

        expect(writeText).toHaveBeenCalledWith("CODE-1\nCODE-2")
        expect(copyButton).toHaveAccessibleName("Copy All")
        expect(copyButton).toHaveAttribute("data-copied")
    })
})
