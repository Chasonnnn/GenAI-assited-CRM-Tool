import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import TemplatesPage from "../app/ops/templates/page"

const mockPush = vi.fn()
const mockReplace = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: mockPush,
        replace: mockReplace,
    }),
}))

vi.mock("@/lib/hooks/use-platform-templates", () => ({
    usePlatformEmailTemplates: () => ({ data: [], isLoading: false }),
    usePlatformFormTemplates: () => ({ data: [], isLoading: false }),
    usePlatformWorkflowTemplates: () => ({ data: [], isLoading: false }),
    usePlatformSystemEmailTemplates: () => ({ data: [], isLoading: false }),
}))

describe("Templates Studio (Ops)", () => {
    beforeEach(() => {
        mockPush.mockClear()
        mockReplace.mockClear()
        try {
            window.history.pushState({}, "", "/ops/templates?tab=system")
        } catch {
            // Some test setups replace window.location with a plain object not linked to history.
            // In that case, pushState won't update window.location.search, so set it directly.
        }

        try {
            // @ts-expect-error - window.location may be a test stub.
            window.location.search = "?tab=system"
        } catch {
            // Ignore if the environment uses a real Location object.
        }
    })

    it("shows a create button for system email templates", async () => {
        render(<TemplatesPage />)

        const button = await screen.findByRole("button", { name: /new system email/i })
        fireEvent.click(button)

        expect(mockPush).toHaveBeenCalledWith("/ops/templates/system/new")
    })
})
