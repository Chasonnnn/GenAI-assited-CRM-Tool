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
                        subject: "Hello {{full_name}}",
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
    useEmailTemplateLibrary: () => ({ data: [], isLoading: false }),
    useEmailTemplateLibraryItem: () => ({ data: null, isLoading: false }),
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
    useSignaturePreview: () => ({ data: { html: "" }, isLoading: false }),
    useUploadSignaturePhoto: () => ({ mutate: vi.fn(), isPending: false }),
    useDeleteSignaturePhoto: () => ({ mutate: vi.fn(), isPending: false }),
    useOrgSignature: () => ({ data: { signature_company_name: "Org", available_templates: [] }, isLoading: false }),
    useOrgSignaturePreview: () => ({ data: { html: "" }, isLoading: false }),
}))

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: React.forwardRef(() => <div data-testid="rich-text-editor" />),
}))

describe("EmailTemplatesPage", () => {
    beforeEach(() => {
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
        expect(screen.getByRole("tab", { name: "Email Templates" })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: "My Signature" })).toBeInTheDocument()
    })

    it("shows send test email action and opens dialog", async () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Email Templates" }))

        const triggers = document.querySelectorAll('[data-slot="dropdown-menu-trigger"]')
        expect(triggers.length).toBeGreaterThan(0)
        fireEvent.click(triggers[0] as HTMLElement)

        expect(await screen.findByText("Send test email")).toBeInTheDocument()
        fireEvent.click(screen.getByText("Send test email"))

        expect(await screen.findByLabelText("To email")).toBeInTheDocument()
    })
})
