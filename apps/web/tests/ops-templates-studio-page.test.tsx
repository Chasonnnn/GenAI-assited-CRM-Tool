import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { renderToString } from "react-dom/server"
import TemplatesPage from "../app/ops/templates/page.client"

const mockPush = vi.fn()
const mockReplace = vi.fn()
const templateMocks = vi.hoisted(() => ({
    emailTemplates: [] as unknown[],
    formTemplates: [] as unknown[],
    workflowTemplates: [] as unknown[],
    systemTemplates: [] as unknown[],
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: mockPush,
        replace: mockReplace,
    }),
}))

vi.mock("@/lib/hooks/use-platform-templates", () => ({
    usePlatformEmailTemplates: () => ({ data: templateMocks.emailTemplates, isLoading: false }),
    usePlatformFormTemplates: () => ({ data: templateMocks.formTemplates, isLoading: false }),
    usePlatformWorkflowTemplates: () => ({ data: templateMocks.workflowTemplates, isLoading: false }),
    usePlatformSystemEmailTemplates: () => ({ data: templateMocks.systemTemplates, isLoading: false }),
}))

describe("Templates Studio (Ops)", () => {
    beforeEach(() => {
        mockPush.mockClear()
        mockReplace.mockClear()
        templateMocks.emailTemplates = []
        templateMocks.formTemplates = []
        templateMocks.workflowTemplates = []
        templateMocks.systemTemplates = []
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

    it("server-renders template timestamps as deterministic UTC fallback labels", () => {
        templateMocks.emailTemplates = [
            {
                id: "email_template_1",
                status: "published",
                published_version: 1,
                is_published_globally: true,
                published_at: "2026-06-03T00:30:00.000Z",
                updated_at: "2026-06-04T00:30:00.000Z",
                draft: {
                    name: "Welcome email",
                    subject: "Welcome",
                },
            },
        ]

        const html = renderToString(<TemplatesPage />)

        expect(html).toContain("Jun 3, 2026")
        expect(html).toContain("Jun 4, 2026")
        expect(html).not.toContain("ago")
        expect(html).not.toContain("in ")
    })
})
