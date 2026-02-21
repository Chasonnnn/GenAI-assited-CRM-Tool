import { describe, it, beforeEach, vi, expect } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import * as React from "react"
import EmailTemplatesPage from "../app/(app)/automation/email-templates/page"

const mockUseAuth = vi.fn()
const mockRichTextEditorProps = vi.fn()
const mockUseEmailTemplates = vi.fn()
const FIXED_TIMESTAMP = "2026-01-01T00:00:00.000Z"
const TEMPLATE_VARIABLES = [
    {
        name: "full_name",
        description: "Recipient full name",
        category: "Recipient",
        required: false,
        value_type: "text",
        html_safe: false,
    },
]

const ORG_TEMPLATE = {
    id: "tpl_org_1",
    name: "Org Template",
    subject: "Your Surrogacy Journey Starts with EWI Family Global",
    from_email: null,
    is_active: true,
    scope: "org",
    owner_user_id: null,
    owner_name: null,
    is_system_template: false,
    created_at: FIXED_TIMESTAMP,
    updated_at: FIXED_TIMESTAMP,
} as const

const PERSONAL_TEMPLATE = {
    id: "tpl_personal_1",
    name: "Personal Template",
    subject: "Hi {{full_name}}",
    from_email: null,
    is_active: true,
    scope: "personal",
    owner_user_id: "user_1",
    owner_name: "Admin",
    is_system_template: false,
    created_at: FIXED_TIMESTAMP,
    updated_at: FIXED_TIMESTAMP,
} as const

const OTHER_USER_PERSONAL_TEMPLATE = {
    ...PERSONAL_TEMPLATE,
    id: "tpl_personal_2",
    name: "Other User Personal Template",
    owner_user_id: "user_2",
    owner_name: "Maegan Fee",
} as const

const TEMPLATE_DETAIL_BY_ID = {
    tpl_personal_1: {
        id: "tpl_personal_1",
        organization_id: "org_1",
        created_by_user_id: "user_1",
        name: "Personal Template",
        subject: "Hi {{full_name}}",
        from_email: null,
        body: "<p>Personal Body</p>",
        is_active: true,
        scope: "personal",
        owner_user_id: "user_1",
        owner_name: "Admin",
        source_template_id: null,
        is_system_template: false,
        current_version: 1,
        created_at: FIXED_TIMESTAMP,
        updated_at: FIXED_TIMESTAMP,
    },
    tpl_org_1: {
        id: "tpl_org_1",
        organization_id: "org_1",
        created_by_user_id: "user_1",
        name: "Org Template",
        subject: "Your Surrogacy Journey Starts with EWI Family Global",
        from_email: null,
        body: "<p>Org Body</p>",
        is_active: true,
        scope: "org",
        owner_user_id: null,
        owner_name: null,
        source_template_id: null,
        is_system_template: false,
        current_version: 1,
        created_at: FIXED_TIMESTAMP,
        updated_at: FIXED_TIMESTAMP,
    },
} as const

const LIBRARY_TEMPLATE = {
    id: "lib_tpl_1",
    name: "Library Template",
    subject: "Hello {{full_name}}",
    category: null,
} as const

const LIBRARY_TEMPLATE_DETAIL = {
    id: "lib_tpl_1",
    name: "Library Template",
    subject: "Hello {{full_name}}",
    body: "<p>Hi there</p>",
} as const

let personalTemplatesFixture = [PERSONAL_TEMPLATE]
let orgTemplatesFixture = [ORG_TEMPLATE]

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
    useEmailTemplates: (params?: { scope?: string | null; activeOnly?: boolean }) => {
        mockUseEmailTemplates(params)

        if (params?.scope === "org") {
            return {
                data: params?.activeOnly === false
                    ? orgTemplatesFixture
                    : orgTemplatesFixture.filter((template) => template.is_active),
                isLoading: false,
            }
        }
        if (params?.scope === "personal") {
            return {
                data: params?.activeOnly === false
                    ? personalTemplatesFixture
                    : personalTemplatesFixture.filter((template) => template.is_active),
                isLoading: false,
            }
        }
        return { data: [], isLoading: false }
    },
    useEmailTemplate: (id: string | null) => {
        const templateDetail = id
            ? TEMPLATE_DETAIL_BY_ID[id as keyof typeof TEMPLATE_DETAIL_BY_ID] ?? null
            : null
        return { data: templateDetail, isLoading: false }
    },
    useEmailTemplateLibrary: () => ({
        data: [LIBRARY_TEMPLATE],
        isLoading: false,
    }),
    useEmailTemplateLibraryItem: (id: string | null) => ({
        data: id === "lib_tpl_1" ? LIBRARY_TEMPLATE_DETAIL : null,
        isLoading: false,
    }),
    useEmailTemplateVariables: () => ({ data: TEMPLATE_VARIABLES, isLoading: false }),
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
    RichTextEditor: React.forwardRef((props: Record<string, unknown>, _ref) => {
        mockRichTextEditorProps(props)
        return <div data-testid="rich-text-editor" />
    }),
}))

describe("EmailTemplatesPage", () => {
    beforeEach(() => {
        document.documentElement.classList.remove("dark")
        mockRichTextEditorProps.mockClear()
        mockUseEmailTemplates.mockClear()
        personalTemplatesFixture = [PERSONAL_TEMPLATE]
        orgTemplatesFixture = [ORG_TEMPLATE]
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

    it("clamps long subjects on template cards", () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))

        const subject = screen.getByText("Your Surrogacy Journey Starts with EWI Family Global")
        expect(subject).toHaveClass("line-clamp-2")
        expect(subject).toHaveAttribute("title", "Your Surrogacy Journey Starts with EWI Family Global")
    })

    it("clamps long template names to two lines to protect actions area", () => {
        orgTemplatesFixture = [
            {
                ...ORG_TEMPLATE,
                id: "tpl_org_long_name",
                name: "Gift Card Email-Completed the interview and waiting for GC to process through the payroll team",
            },
        ]

        render(<EmailTemplatesPage />)
        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))

        const title = screen.getByText(
            "Gift Card Email-Completed the interview and waiting for GC to process through the payroll team"
        )
        expect(title).toHaveClass("line-clamp-2")
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

    it("enables emoji picker for visual template editing", () => {
        render(<EmailTemplatesPage />)
        fireEvent.click(screen.getByRole("button", { name: /Create Template/i }))

        expect(mockRichTextEditorProps).toHaveBeenCalled()
        const hasEmojiEnabledCall = mockRichTextEditorProps.mock.calls.some(
            ([props]) => Boolean((props as { enableEmojiPicker?: boolean }).enableEmojiPicker)
        )
        expect(hasEmojiEnabledCall).toBe(true)
    })

    it("uses personal signature in preview for personal templates", async () => {
        render(<EmailTemplatesPage />)

        const triggers = document.querySelectorAll('[data-slot="dropdown-menu-trigger"]')
        expect(triggers.length).toBeGreaterThan(0)
        fireEvent.click(triggers[0] as HTMLElement)

        fireEvent.click(await screen.findByText("Edit"))
        fireEvent.click(await screen.findByRole("button", { name: "Preview" }))

        expect(await screen.findByText("Email Preview")).toBeInTheDocument()
        expect(screen.getByText("Personal Signature")).toBeInTheDocument()
        expect(screen.queryByText("Org Signature")).not.toBeInTheDocument()
    })

    it("uses org signature in preview for organization templates", async () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))

        const triggers = document.querySelectorAll('[data-slot="dropdown-menu-trigger"]')
        expect(triggers.length).toBeGreaterThan(0)
        fireEvent.click(triggers[0] as HTMLElement)

        fireEvent.click(await screen.findByText("Edit"))
        fireEvent.click(await screen.findByRole("button", { name: "Preview" }))

        expect(await screen.findByText("Email Preview")).toBeInTheDocument()
        expect(screen.getByText("Org Signature")).toBeInTheDocument()
        expect(screen.queryByText("Personal Signature")).not.toBeInTheDocument()
    })

    it.each(["admin", "developer"] as const)(
        "allows %s to edit non-owned personal templates",
        async (role) => {
            mockUseAuth.mockReturnValue({
                user: {
                    user_id: "user_1",
                    role,
                    email: "admin@example.com",
                    display_name: "Admin",
                    org_name: "Test Org",
                    ai_enabled: false,
                },
            })
            personalTemplatesFixture = [OTHER_USER_PERSONAL_TEMPLATE]

            render(<EmailTemplatesPage />)

            expect(screen.queryByText("View Only")).not.toBeInTheDocument()

            const triggers = document.querySelectorAll('[data-slot="dropdown-menu-trigger"]')
            expect(triggers.length).toBeGreaterThan(0)
            fireEvent.click(triggers[0] as HTMLElement)

            expect(await screen.findByText("Edit")).toBeInTheDocument()
        }
    )

    it("does not show inactive personal templates", () => {
        personalTemplatesFixture = [{
            ...PERSONAL_TEMPLATE,
            id: "tpl_personal_deleted",
            name: "Deleted Personal Template",
            is_active: false,
        }]

        render(<EmailTemplatesPage />)

        expect(screen.queryByText("Deleted Personal Template")).not.toBeInTheDocument()
        expect(screen.getByText("You don't have any personal templates yet")).toBeInTheDocument()
    })

    it("does not insert variables into hidden HTML field after switching to visual mode", async () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("button", { name: /Create Template/i }))
        fireEvent.change(screen.getByLabelText("Template Name"), { target: { value: "My Template" } })
        fireEvent.change(screen.getByLabelText("Subject Line"), { target: { value: "Hello" } })

        fireEvent.click(screen.getByRole("button", { name: "HTML" }))

        const htmlTextarea = screen.getByLabelText("Email Body") as HTMLTextAreaElement
        fireEvent.change(htmlTextarea, { target: { value: "<p>Body</p>" } })
        htmlTextarea.focus()

        fireEvent.click(screen.getByRole("button", { name: "Visual" }))
        fireEvent.click(screen.getByRole("button", { name: "Insert Variable" }))
        fireEvent.click(await screen.findByText("{{full_name}}"))

        fireEvent.click(screen.getByRole("button", { name: "HTML" }))
        const htmlTextareaAfter = screen.getByLabelText("Email Body") as HTMLTextAreaElement
        expect(htmlTextareaAfter.value).toBe("<p>Body</p>")
    })
})
