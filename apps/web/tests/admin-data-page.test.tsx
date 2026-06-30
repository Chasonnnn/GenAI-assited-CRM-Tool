import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import AdminDataPage from "../app/(app)/settings/admin/page"

const mocks = vi.hoisted(() => ({
    useAuth: vi.fn(),
    toastSuccess: vi.fn(),
    toastError: vi.fn(),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mocks.useAuth(),
}))

vi.mock("@/lib/csrf", () => ({
    getCsrfHeaders: () => ({ "X-CSRF-Token": "test-token" }),
}))

vi.mock("sonner", () => ({
    toast: {
        success: mocks.toastSuccess,
        error: mocks.toastError,
    },
}))

function jsonResponse(body: unknown, init?: ResponseInit) {
    return new Response(JSON.stringify(body), {
        headers: { "Content-Type": "application/json" },
        ...init,
    })
}

describe("AdminDataPage", () => {
    beforeEach(() => {
        mocks.useAuth.mockReturnValue({ user: { role: "developer" } })
        mocks.toastSuccess.mockReset()
        mocks.toastError.mockReset()
    })

    afterEach(() => {
        vi.unstubAllGlobals()
        vi.restoreAllMocks()
    })

    it("blocks non-developer users", () => {
        mocks.useAuth.mockReturnValue({ user: { role: "admin" } })

        render(<AdminDataPage />)

        expect(screen.getByText(/only accessible to developers/i)).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /export surrogates csv/i })).not.toBeInTheDocument()
    })

    it("exports completed jobs and re-enables export controls", async () => {
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(jsonResponse({ job_id: "job-1", status: "completed" }))
            .mockResolvedValueOnce(jsonResponse({
                download_url: "https://example.test/surrogates.csv",
                filename: "surrogates.csv",
            }))
        const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {})
        vi.stubGlobal("fetch", fetchMock)

        render(<AdminDataPage />)
        const exportButton = screen.getByRole("button", { name: /export surrogates csv/i })

        fireEvent.click(exportButton)

        await waitFor(() => {
            expect(mocks.toastSuccess).toHaveBeenCalledWith(
                "Export complete",
                { description: "Downloaded surrogates.csv" }
            )
        })
        expect(fetchMock).toHaveBeenNthCalledWith(
            1,
            "http://localhost:8000/admin/exports/surrogates",
            expect.objectContaining({
                method: "POST",
                credentials: "include",
                headers: { "X-CSRF-Token": "test-token" },
            })
        )
        expect(clickSpy).toHaveBeenCalled()
        expect(exportButton).toBeEnabled()
    })

    it("re-enables export controls after a failed export", async () => {
        const fetchMock = vi.fn().mockResolvedValueOnce(new Response(null, { status: 500 }))
        vi.stubGlobal("fetch", fetchMock)

        render(<AdminDataPage />)
        const exportButton = screen.getByRole("button", { name: /export config zip/i })

        fireEvent.click(exportButton)

        await waitFor(() => {
            expect(mocks.toastError).toHaveBeenCalledWith(
                "Export failed",
                { description: "Export failed: 500" }
            )
        })
        expect(exportButton).toBeEnabled()
    })
})
