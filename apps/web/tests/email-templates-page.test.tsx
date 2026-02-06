import { describe, it, beforeEach, vi, expect } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import * as React from "react"
import EmailTemplatesPage from "../app/(app)/automation/email-templates/page"

const mockUseAuth = vi.fn()

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => ({ data: { permissions: ["manage_email_templates"] } }),
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
        back: vi.fn(),
        prefetch: vi.fn(),
    }),
    useSearchParams: () => ({
        get: vi.fn(() => null),
    }),
}))

vi.mock("@/lib/hooks/use-email-templates", () => ({
    useEmailTemplates: (params?: { scope?: string | null }) => {
        if (params?.scope === "org") {
            return {
                data: [
                    {
                        id: "tpl_org_1",
                        name: "Org Template",
                        subject: "Your Surrogacy Journey Starts with EWI Family Global",
                        from_email: null,
                        is_active: true,
                        scope: "org",
                        owner_user_id: null,
                        owner_name: null,
                        is_system_template: false,
                        created_at: new Date().toISOString(),
                        updated_at: new Date().toISOString(),
                    },
                ],
                isLoading: false,
            }
        }
        return { data: [], isLoading: false }
    },
    useEmailTemplate: () => ({ data: null, isLoading: false }),
    useEmailTemplateLibrary: () => ({
        data: [
            {
                id: "lib_tpl_1",
                name: "Library Template",
                subject: "Hello {{full_name}}",
                category: null,
            },
        ],
        isLoading: false,
    }),
    useEmailTemplateLibraryItem: (id: string | null) => ({
        data:
            id === "lib_tpl_1"
                ? {
                      id: "lib_tpl_1",
                      name: "Library Template",
                      subject: "Hello {{full_name}}",
                      body: "<p>Hi there</p>",
                  }
                : null,
        isLoading: false,
    }),
    useEmailTemplateVariables: () => ({ data: [], isLoading: false }),
    useCreateEmailTemplate: () => ({ mutate: vi.fn(), isPending: false }),
    useUpdateEmailTemplate: () => ({ mutate: vi.fn(), isPending: false }),
    useDeleteEmailTemplate: () => ({ mutate: vi.fn(), isPending: false }),
    useCopyTemplateToPersonal: () => ({ mutate: vi.fn(), isPending: false }),
    useShareTemplateWithOrg: () => ({ mutate: vi.fn(), isPending: false }),
    useCopyTemplateFromLibrary: () => ({ mutate: vi.fn(), isPending: false }),
    useSendTestEmailTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/lib/hooks/use-signature", () => ({
    useUserSignature: () => ({ data: null, refetch: vi.fn() }),
    useUpdateUserSignature: () => ({ mutate: vi.fn(), isPending: false }),
    useSignaturePreview: () => ({ data: { html: "<div>Personal Signature</div>" }, isLoading: false }),
    useUploadSignaturePhoto: () => ({ mutate: vi.fn(), isPending: false }),
    useDeleteSignaturePhoto: () => ({ mutate: vi.fn(), isPending: false }),
    useOrgSignature: () => ({ data: { signature_company_name: "Org", available_templates: [] }, isLoading: false }),
    useOrgSignaturePreview: () => ({ data: { html: "<div>Org Signature</div>" }, isLoading: false }),
}))

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: React.forwardRef(() => <div data-testid="rich-text-editor" />),
}))

describe("EmailTemplatesPage", () => {
    beforeEach(() => {
        document.documentElement.classList.remove("dark")
        mockUseAuth.mockReturnValue({
            user: {
                user_id: "user_1",
                role: "admin",
                email: "admin@example.com",
                display_name: "Admin",
                org_name: "Test Org",
                ai_enabled: false,
            },
        })
    })

    it("renders updated tabs", () => {
        render(<EmailTemplatesPage />)
        expect(screen.getByRole("tab", { name: "My Email Templates" })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: "Organization Templates" })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: "My Signature" })).toBeInTheDocument()
    })

    it("shows send test email action and opens dialog", async () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))

        const triggers = document.querySelectorAll('[data-slot="dropdown-menu-trigger"]')
        expect(triggers.length).toBeGreaterThan(0)
        fireEvent.click(triggers[0] as HTMLElement)

        expect(await screen.findByText("Send test email")).toBeInTheDocument()
        fireEvent.click(screen.getByText("Send test email"))

        expect(await screen.findByLabelText("To email")).toBeInTheDocument()
    })

    it("truncates long subjects on template cards", () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))

        expect(screen.getByText("Your Surrogacy Journey Starts with EWI Fam....")).toBeInTheDocument()
    })

    it("renders a readable email preview on a white background (dark theme)", async () => {
        document.documentElement.classList.add("dark")

        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Platform Templates" }))
        fireEvent.click(screen.getByRole("button", { name: "Preview" }))

        expect(await screen.findByText("Email Preview")).toBeInTheDocument()

        const bodyText = await screen.findByText("Hi there")
        const proseContainer = bodyText.closest(".prose")
        expect(proseContainer).toHaveClass("prose-stone")

        expect(screen.getByText("Org Signature")).toBeInTheDocument()
        expect(screen.getByText("Unsubscribe")).toBeInTheDocument()
    })
})
