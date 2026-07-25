import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import AIBuilderPage from "../app/(app)/automation/ai-builder/page"

const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()
const mockUseSearchParams = vi.fn()

const mockGenerateWorkflow = vi.fn()
const mockSaveAIWorkflow = vi.fn()
const mockGenerateEmailTemplate = vi.fn()
const mockCreateEmailTemplateDraft = vi.fn()
const mockRouterPush = vi.fn()

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => mockUseEffectivePermissions(),
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: mockRouterPush,
        replace: vi.fn(),
        back: vi.fn(),
    }),
    useSearchParams: () => mockUseSearchParams(),
}))

vi.mock("@/lib/api/ai", () => ({
    generateWorkflow: (...args: unknown[]) => mockGenerateWorkflow(...args),
    saveAIWorkflow: (...args: unknown[]) => mockSaveAIWorkflow(...args),
    generateEmailTemplate: (...args: unknown[]) => mockGenerateEmailTemplate(...args),
}))

vi.mock("@/lib/hooks/use-email-templates", () => ({
    useEmailTemplateVariables: () => ({
        data: [
            { name: "first_name", description: "", category: "Recipient", required: false, value_type: "text", html_safe: false },
            { name: "unsubscribe_url", description: "", category: "Compliance", required: false, value_type: "url", html_safe: false },
        ],
        isLoading: false,
        error: null,
    }),
}))

vi.mock("@/lib/hooks/use-email-template-drafts", () => ({
    useCreateEmailTemplateDraft: () => ({
        mutateAsync: mockCreateEmailTemplateDraft,
        isPending: false,
    }),
}))

describe("AIBuilderPage", () => {
    beforeEach(() => {
        mockUseSearchParams.mockReturnValue({ get: () => null })
        mockUseAuth.mockReturnValue({ user: { ai_enabled: true, user_id: "user-1" } })
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: ["use_ai_assistant"] } })
        mockGenerateWorkflow.mockReset()
        mockSaveAIWorkflow.mockReset()
        mockGenerateEmailTemplate.mockReset()
        mockCreateEmailTemplateDraft.mockReset()
        mockRouterPush.mockReset()
    })

    it("shows disabled state when AI permission is missing", () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: [] } })
        render(<AIBuilderPage />)
        expect(screen.getByText(/ai builder is disabled/i)).toBeInTheDocument()
    })

    it("renders variable suggestions for generated email template", async () => {
        mockUseSearchParams.mockReturnValue({
            get: (key: string) => (key === "mode" ? "email_template" : null),
        })
        mockGenerateEmailTemplate.mockResolvedValue({
            success: true,
            template: {
                name: "Welcome",
                subject: "Hello {{first_name}}",
                body_html: "<p>Hi {{first_name}}</p><p>{{unsubscribe_url}}</p>",
                variables_used: ["first_name", "unsubscribe_url"],
            },
            warnings: [],
            validation_errors: [],
            explanation: null,
        })

        render(<AIBuilderPage />)
        fireEvent.change(screen.getByRole("textbox"), { target: { value: "Welcome email" } })
        fireEvent.click(screen.getByRole("button", { name: /generate template/i }))

        expect(await screen.findByText(/variables detected/i)).toBeInTheDocument()
        expect(screen.getByText("first_name")).toBeInTheDocument()
        expect(screen.getByText("unsubscribe_url")).toBeInTheDocument()
    })

    it("saves generated personal templates as isolated Studio drafts", async () => {
        mockUseSearchParams.mockReturnValue({
            get: (key: string) => (key === "mode" ? "email_template" : null),
        })
        mockGenerateEmailTemplate.mockResolvedValue({
            success: true,
            template: {
                name: "Welcome",
                subject: "Hello {{first_name}}",
                body_html: "<p>Hi {{first_name}}</p>",
                variables_used: ["first_name"],
            },
            warnings: [],
            validation_errors: [],
            explanation: null,
        })
        mockCreateEmailTemplateDraft.mockResolvedValue({
            id: "draft-ai-personal",
        })

        render(<AIBuilderPage />)
        fireEvent.change(screen.getByRole("textbox"), {
            target: { value: "Welcome email" },
        })
        fireEvent.click(screen.getByRole("button", { name: /generate template/i }))
        fireEvent.click(
            await screen.findByRole("button", { name: "Save Template" }),
        )

        await waitFor(() => {
            expect(mockCreateEmailTemplateDraft).toHaveBeenCalledWith({
                name: "Welcome",
                subject: "Hello {{first_name}}",
                body: "<p>Hi {{first_name}}</p>",
                scope: "personal",
            })
        })
        expect(mockRouterPush).toHaveBeenCalledWith(
            "/automation/email-templates/personal/draft-ai-personal",
        )
    })
})
