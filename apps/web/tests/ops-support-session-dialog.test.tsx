import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom"

import { SupportSessionDialog } from "@/components/ops/agencies/SupportSessionDialog"

const mockCreateSupportSession = vi.fn()

vi.mock("@/lib/api/platform", () => ({
    createSupportSession: (data: unknown) => mockCreateSupportSession(data),
}))

vi.mock("sonner", () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
    },
}))

function createPopupStub() {
    const bodyStyle: Record<string, string> = {}
    const body = {
        innerHTML: "",
        style: bodyStyle,
        appendChild: vi.fn(),
    }
    const doc = {
        title: "",
        body,
        createElement: vi.fn(() => ({
            textContent: "",
            style: {} as Record<string, string>,
        })),
    }
    const popup = {
        opener: null as unknown,
        document: doc,
        location: { href: "" },
        close: vi.fn(),
    }
    return popup as unknown as Window
}

describe("SupportSessionDialog", () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it("creates a support session and opens the portal", async () => {
        const popup = createPopupStub()
        vi.spyOn(window, "open").mockReturnValue(popup)

        mockCreateSupportSession.mockResolvedValueOnce({
            id: "sess_1",
            org_id: "org_1",
            role: "admin",
            mode: "write",
            reason_code: "bug_repro",
            reason_text: null,
            expires_at: new Date().toISOString(),
            created_at: new Date().toISOString(),
        })

        render(
            <SupportSessionDialog
                orgId="org_1"
                orgName="Test Org"
                portalBaseUrl="https://test.example.com"
            />
        )

        fireEvent.click(screen.getByRole("button", { name: "View as role" }))

        fireEvent.click(await screen.findByRole("button", { name: /start session/i }))

        await waitFor(() =>
            expect(mockCreateSupportSession).toHaveBeenCalledWith({
                org_id: "org_1",
                role: "admin",
                mode: "write",
                reason_code: "bug_repro",
                reason_text: null,
            })
        )

        await waitFor(() => expect(popup.location.href).toBe("https://test.example.com"))
        expect((popup as unknown as { close: () => void }).close).not.toHaveBeenCalled()
    })

    it("closes the placeholder tab if creating the support session fails", async () => {
        const popup = createPopupStub()
        vi.spyOn(window, "open").mockReturnValue(popup)

        mockCreateSupportSession.mockRejectedValueOnce(new Error("Nope"))

        render(
            <SupportSessionDialog
                orgId="org_1"
                orgName="Test Org"
                portalBaseUrl="https://test.example.com"
            />
        )

        fireEvent.click(screen.getByRole("button", { name: "View as role" }))
        fireEvent.click(await screen.findByRole("button", { name: /start session/i }))

        await waitFor(() => expect((popup as unknown as { close: () => void }).close).toHaveBeenCalled())
    })
})

