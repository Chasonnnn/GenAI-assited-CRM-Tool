import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import TemplatesPage from "../app/ops/templates/page"

const mockPush = vi.fn()
const mockReplace = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: mockPush,
        replace: mockReplace,
    }),
    useSearchParams: () => ({
        get: (key: string) => (key === "tab" ? "system" : null),
    }),
}))

vi.mock("@/lib/hooks/use-platform-templates", () => ({
    usePlatformEmailTemplates: () => ({ data: [], isLoading: false }),
    usePlatformFormTemplates: () => ({ data: [], isLoading: false }),
    usePlatformWorkflowTemplates: () => ({ data: [], isLoading: false }),
    usePlatformSystemEmailTemplates: () => ({ data: [], isLoading: false }),
}))

describe("Templates Studio (Ops)", () => {
    it("shows a create button for system email templates", () => {
        render(<TemplatesPage />)

        const button = screen.getByRole("button", { name: /new system email/i })
        fireEvent.click(button)

        expect(mockPush).toHaveBeenCalledWith("/ops/templates/system/new")
    })
})

