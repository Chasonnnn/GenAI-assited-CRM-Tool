import { beforeEach, describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen, within } from "@testing-library/react"

import ZoomSettingsPage from "../app/(app)/settings/integrations/zoom/page"
import { ApiError } from "@/lib/api"

const mockDisconnect = vi.fn()
const mockToast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))

vi.mock("@/components/ui/toast", () => ({ toast: mockToast }))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
    usePathname: () => "/settings/integrations/zoom",
    useSearchParams: () => new URLSearchParams(),
}))

vi.mock("@/lib/hooks/use-user-integrations", () => ({
    useZoomStatus: () => ({
        data: {
            connected: true,
            account_email: "host@test.com",
            connected_at: null,
            token_expires_at: null,
        },
        isLoading: false,
    }),
    useZoomMeetings: () => ({ data: [], isLoading: false }),
    useConnectZoom: () => ({ mutate: vi.fn(), isPending: false }),
    useDisconnectIntegration: () => ({ mutateAsync: mockDisconnect, isPending: false }),
}))

describe("ZoomSettingsPage", () => {
    beforeEach(() => {
        mockDisconnect.mockReset()
        mockToast.success.mockReset()
    })

    it("disconnects Zoom only after a destructive confirmation", async () => {
        mockDisconnect.mockResolvedValue(undefined)

        render(<ZoomSettingsPage />)
        fireEvent.click(screen.getByRole("button", { name: "Disconnect…" }))
        expect(mockDisconnect).not.toHaveBeenCalled()

        const dialog = await screen.findByRole("alertdialog", { name: "Disconnect Zoom?" })
        const confirm = within(dialog).getByRole("button", { name: "Disconnect" })
        expect(confirm).toHaveClass("bg-destructive")
        await act(async () => {
            fireEvent.click(confirm)
        })

        expect(mockDisconnect).toHaveBeenCalledWith("zoom")
        expect(mockToast.success).toHaveBeenCalledWith("Zoom disconnected")
    })

    it("keeps the confirmation open with a sanitized error when disconnect fails", async () => {
        mockDisconnect.mockRejectedValue(new ApiError(500, "Internal Server Error", "zoom token revoke failed"))

        render(<ZoomSettingsPage />)
        fireEvent.click(screen.getByRole("button", { name: "Disconnect…" }))
        const dialog = await screen.findByRole("alertdialog", { name: "Disconnect Zoom?" })
        await act(async () => {
            fireEvent.click(within(dialog).getByRole("button", { name: "Disconnect" }))
        })

        expect(within(dialog).getByText("Couldn't disconnect Zoom. Try again.")).toBeInTheDocument()
        expect(within(dialog).queryByText(/revoke failed/)).not.toBeInTheDocument()
    })
})
