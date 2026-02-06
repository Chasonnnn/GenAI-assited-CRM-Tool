import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import AIBuilderPage from "../app/(app)/automation/ai-builder/page"

const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()
const mockUseSearchParams = vi.fn()

const mockGenerateWorkflow = vi.fn()
const mockSaveAIWorkflow = vi.fn()
const mockGenerateEmailTemplate = vi.fn()

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => mockUseEffectivePermissions(),
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: vi.fn(),
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
    useCreateEmailTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useEmailTemplateVariables: () => ({
        data: [
            { name: "first_name", description: "", category: "Recipient", required: false, value_type: "text", html_safe: false },
            { name: "unsubscribe_url", description: "", category: "Compliance", required: true, value_type: "url", html_safe: false },
        ],
        isLoading: false,
        error: null,
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
})
