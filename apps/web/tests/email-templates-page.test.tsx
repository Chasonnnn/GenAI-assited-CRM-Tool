import { describe, it, beforeEach, vi, expect } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import * as React from "react"
import EmailTemplatesPage from "../app/(app)/automation/email-templates/page"
import type {
    EmailTemplate,
    EmailTemplateLibraryDetail,
    EmailTemplateLibraryItem,
    EmailTemplateListItem,
} from "@/lib/api/email-templates"

const mockUseAuth = vi.fn()
const mockRichTextEditorProps = vi.fn()
const mockUseEmailTemplates = vi.fn()
const mockCreateEmailTemplate = vi.fn()
const mockUpdateEmailTemplate = vi.fn()
const mockSendTestEmailTemplate = vi.fn()
let userSignatureData: Record<string, string | null> | null = null
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

const ORG_TEMPLATE: EmailTemplateListItem = {
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
}

const PERSONAL_TEMPLATE: EmailTemplateListItem = {
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
}

const OTHER_USER_PERSONAL_TEMPLATE: EmailTemplateListItem = {
    ...PERSONAL_TEMPLATE,
    id: "tpl_personal_2",
    name: "Other User Personal Template",
    owner_user_id: "user_2",
    owner_name: "Maegan Fee",
}

const TEMPLATE_DETAIL_BY_ID: Record<string, EmailTemplate> = {
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
}

const LIBRARY_TEMPLATE: EmailTemplateLibraryItem = {
    id: "lib_tpl_1",
    name: "Library Template",
    subject: "Hello {{full_name}}",
    from_email: null,
    category: null,
    published_at: null,
    updated_at: FIXED_TIMESTAMP,
}

const LIBRARY_TEMPLATE_DETAIL: EmailTemplateLibraryDetail = {
    id: "lib_tpl_1",
    name: "Library Template",
    subject: "Hello {{full_name}}",
    from_email: null,
    category: null,
    published_at: null,
    updated_at: FIXED_TIMESTAMP,
    body: "<p>Hi there</p>",
}

let personalTemplatesFixture: EmailTemplateListItem[] = [PERSONAL_TEMPLATE]
let orgTemplatesFixture: EmailTemplateListItem[] = [ORG_TEMPLATE]
let libraryTemplateDetailFixture: EmailTemplateLibraryDetail | null = LIBRARY_TEMPLATE_DETAIL

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
        data: id === "lib_tpl_1" ? libraryTemplateDetailFixture : null,
        isLoading: false,
    }),
    useEmailTemplateVariables: () => ({ data: TEMPLATE_VARIABLES, isLoading: false }),
    useCreateEmailTemplate: () => ({ mutate: mockCreateEmailTemplate, isPending: false }),
    useUpdateEmailTemplate: () => ({ mutate: mockUpdateEmailTemplate, isPending: false }),
    useDeleteEmailTemplate: () => ({ mutate: vi.fn(), isPending: false }),
    useCopyTemplateToPersonal: () => ({ mutate: vi.fn(), isPending: false }),
    useShareTemplateWithOrg: () => ({ mutate: vi.fn(), isPending: false }),
    useCopyTemplateFromLibrary: () => ({ mutate: vi.fn(), isPending: false }),
    useSendTestEmailTemplate: () => ({ mutateAsync: mockSendTestEmailTemplate, isPending: false }),
}))

vi.mock("@/lib/hooks/use-signature", () => ({
    useUserSignature: () => ({ data: userSignatureData, refetch: vi.fn() }),
    useUpdateUserSignature: () => ({ mutate: vi.fn(), isPending: false }),
    useSignaturePreview: () => ({ data: { html: "<div>Personal Signature</div>" }, isLoading: false }),
    useUploadSignaturePhoto: () => ({ mutate: vi.fn(), isPending: false }),
    useDeleteSignaturePhoto: () => ({ mutate: vi.fn(), isPending: false }),
    useOrgSignature: () => ({ data: { signature_company_name: "Org", available_templates: [] }, isLoading: false }),
    useOrgSignaturePreview: () => ({ data: { html: "<div>Org Signature</div>" }, isLoading: false }),
}))

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: function MockRichTextEditor(props: Record<string, unknown>) {
        mockRichTextEditorProps(props)
        return <div data-testid="rich-text-editor" />
    },
}))

describe("EmailTemplatesPage", () => {
    beforeEach(() => {
        document.documentElement.classList.remove("dark")
        mockRichTextEditorProps.mockClear()
        mockUseEmailTemplates.mockClear()
        mockCreateEmailTemplate.mockReset()
        mockUpdateEmailTemplate.mockReset()
        mockSendTestEmailTemplate.mockReset()
        mockSendTestEmailTemplate.mockResolvedValue({ provider_used: "resend" })
        userSignatureData = null
        personalTemplatesFixture = [PERSONAL_TEMPLATE]
        orgTemplatesFixture = [ORG_TEMPLATE]
        libraryTemplateDetailFixture = LIBRARY_TEMPLATE_DETAIL
        TEMPLATE_DETAIL_BY_ID.tpl_personal_1.body = "<p>Personal Body</p>"
        TEMPLATE_DETAIL_BY_ID.tpl_org_1.body = "<p>Org Body</p>"
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

        fireEvent.click(await screen.findByRole("button", { name: "Actions for Org Template" }))

        const sendTestAction = await screen.findByRole("menuitem", { name: "Send test email" })
        expect(sendTestAction).toBeInTheDocument()
        fireEvent.click(sendTestAction)

        const toEmailInput = await screen.findByLabelText("To email")
        expect(toEmailInput).toBeInTheDocument()
        expect((toEmailInput as HTMLInputElement).value).toBe("admin@example.com")
    })

    it("sends a test email with touched variable overrides and opt-out override", async () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(await screen.findByRole("button", { name: "Actions for Personal Template" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Send test email" }))

        const toEmailInput = await screen.findByLabelText("To email")
        fireEvent.change(toEmailInput, { target: { value: "qa@example.com" } })
        fireEvent.click(screen.getByRole("checkbox", { name: "Send even if unsubscribed" }))
        fireEvent.click(screen.getByRole("button", { name: "Variables (optional)" }))

        const fullNameInput = await screen.findByLabelText("{{full_name}}")
        expect(fullNameInput).toHaveValue("Jordan Smith")
        fireEvent.change(fullNameInput, { target: { value: "Custom Recipient" } })

        fireEvent.click(screen.getByRole("button", { name: "Send test" }))

        await waitFor(() => {
            expect(mockSendTestEmailTemplate).toHaveBeenCalledWith({
                id: "tpl_personal_1",
                payload: {
                    to_email: "qa@example.com",
                    variables: { full_name: "Custom Recipient" },
                    ignore_opt_out: true,
                },
            })
        })
    })

    it("labels organization template action menus with template context", async () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))

        expect(
            await screen.findByRole("button", { name: "Actions for Org Template" })
        ).toBeInTheDocument()
    })

    it("adds an accessible name to the signature photo upload button", async () => {
        const { container } = render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "My Signature" }))

        expect(
            await screen.findByRole("button", { name: "Upload signature photo" }),
        ).toBeInTheDocument()
        expect(container.querySelector("#signature-photo-upload")).toHaveAttribute(
            "aria-label",
            "Upload signature photo",
        )
    })

    it("preserves an in-progress signature edit when equivalent signature data rerenders", async () => {
        userSignatureData = {
            signature_name: "Saved Name",
            signature_title: null,
            signature_phone: null,
            signature_linkedin: null,
            signature_twitter: null,
            signature_instagram: null,
        }
        const view = render(<EmailTemplatesPage />)
        fireEvent.click(screen.getByRole("tab", { name: "My Signature" }))

        const nameInput = await screen.findByLabelText("Name")
        fireEvent.change(nameInput, { target: { value: "Unsaved Name" } })

        userSignatureData = { ...userSignatureData }
        await React.act(async () => {
            view.rerender(<EmailTemplatesPage />)
            await Promise.resolve()
        })

        expect(screen.getByLabelText("Name")).toHaveValue("Unsaved Name")
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

    it("clears library preview state when the preview dialog closes", async () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Platform Templates" }))
        fireEvent.click(screen.getByRole("button", { name: "Preview" }))

        expect(await screen.findByText("Hi there")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Close" }))

        fireEvent.click(screen.getByRole("tab", { name: "My Email Templates" }))
        fireEvent.click(await screen.findByRole("button", { name: "Actions for Personal Template" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Edit" }))
        fireEvent.click(await screen.findByRole("button", { name: "Preview" }))

        expect(await screen.findByText("Personal Body")).toBeInTheDocument()
        expect(screen.queryByText("Hi there")).not.toBeInTheDocument()
    })

    it("does not show the previous template body while a library preview is loading", async () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(await screen.findByRole("button", { name: "Actions for Personal Template" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Edit" }))
        fireEvent.click(await screen.findByRole("button", { name: "Preview" }))
        expect(await screen.findByText("Personal Body")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Close" }))
        await waitFor(() => {
            expect(screen.queryByRole("heading", { name: "Email Preview" })).not.toBeInTheDocument()
        })
        fireEvent.click(screen.getByRole("button", { name: "Close" }))

        libraryTemplateDetailFixture = null
        fireEvent.click(await screen.findByRole("tab", { name: "Platform Templates" }))
        fireEvent.click(screen.getAllByRole("button", { name: "Preview" })[0]!)

        expect(await screen.findByText("Email Preview")).toBeInTheDocument()
        expect(screen.queryByText("Personal Body")).not.toBeInTheDocument()
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

        fireEvent.click(await screen.findByRole("button", { name: "Actions for Personal Template" }))

        fireEvent.click(await screen.findByRole("menuitem", { name: "Edit" }))
        fireEvent.click(await screen.findByRole("button", { name: "Preview" }))

        expect(await screen.findByText("Email Preview")).toBeInTheDocument()
        expect(screen.getByText("Personal Signature")).toBeInTheDocument()
        expect(screen.queryByText("Org Signature")).not.toBeInTheDocument()
    })

    it("opens complex existing templates in HTML mode with the loaded detail body", async () => {
        TEMPLATE_DETAIL_BY_ID.tpl_personal_1.body =
            "<table><tbody><tr><td>Personal Body</td></tr></tbody></table>"

        render(<EmailTemplatesPage />)

        fireEvent.click(await screen.findByRole("button", { name: "Actions for Personal Template" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Edit" }))

        const htmlTextarea = await screen.findByLabelText("Email Body")
        expect(htmlTextarea).toHaveValue(
            "<table><tbody><tr><td>Personal Body</td></tr></tbody></table>",
        )
        expect(screen.queryByTestId("rich-text-editor")).not.toBeInTheDocument()
    })

    it("creates an organization template with the current editor draft", async () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))
        fireEvent.click(screen.getByRole("button", { name: /Create Org Template/i }))
        fireEvent.change(screen.getByLabelText("Template Name"), {
            target: { value: "New Org Template" },
        })
        fireEvent.change(screen.getByLabelText("Subject Line"), {
            target: { value: "Hello {{full_name}}" },
        })

        fireEvent.click(screen.getByRole("button", { name: "HTML" }))
        fireEvent.change(await screen.findByLabelText("Email Body"), {
            target: { value: "<p>Welcome</p>" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Create Template" }))

        expect(mockCreateEmailTemplate).toHaveBeenCalledWith(
            {
                name: "New Org Template",
                subject: "Hello {{full_name}}",
                body: "<p>Welcome</p>",
                scope: "org",
            },
            expect.any(Object),
        )
    })

    it("updates an existing template and resets stale edit draft on create reopen", async () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(await screen.findByRole("button", { name: "Actions for Personal Template" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Edit" }))
        fireEvent.change(await screen.findByLabelText("Template Name"), {
            target: { value: "Renamed Personal Template" },
        })
        fireEvent.change(screen.getByLabelText("Subject Line"), {
            target: { value: "Updated subject" },
        })
        fireEvent.click(screen.getByRole("button", { name: "HTML" }))
        fireEvent.change(await screen.findByLabelText("Email Body"), {
            target: { value: "<p>Updated Body</p>" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save Changes" }))

        expect(mockUpdateEmailTemplate).toHaveBeenCalledWith(
            {
                id: "tpl_personal_1",
                data: {
                    name: "Renamed Personal Template",
                    subject: "Updated subject",
                    body: "<p>Updated Body</p>",
                },
            },
            expect.any(Object),
        )

        fireEvent.click(screen.getByRole("button", { name: "Close" }))
        fireEvent.click(screen.getByRole("button", { name: /^Create Template$/i }))

        expect(screen.getByRole("heading", { name: "Create Template" })).toBeInTheDocument()
        expect(screen.getByLabelText("Template Name")).toHaveValue("")
        expect(screen.getByLabelText("Subject Line")).toHaveValue("")
        expect(screen.getByText("Personal")).toBeInTheDocument()
    })

    it("uses org signature in preview for organization templates", async () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))

        fireEvent.click(await screen.findByRole("button", { name: "Actions for Org Template" }))

        fireEvent.click(await screen.findByRole("menuitem", { name: "Edit" }))
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

    it.each(["admin", "developer"] as const)(
        "shows send test action for %s on non-owned personal templates",
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

            const triggers = document.querySelectorAll('[data-slot="dropdown-menu-trigger"]')
            expect(triggers.length).toBeGreaterThan(0)
            fireEvent.click(triggers[0] as HTMLElement)

            expect(await screen.findByText("Send test email")).toBeInTheDocument()
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

        const htmlTextarea = (await screen.findByLabelText("Email Body")) as HTMLTextAreaElement
        fireEvent.change(htmlTextarea, { target: { value: "<p>Body</p>" } })

        fireEvent.click(screen.getByRole("button", { name: "Visual" }))
        await waitFor(() => {
            expect(screen.getByTestId("rich-text-editor")).toBeInTheDocument()
        })

        fireEvent.click(screen.getByRole("button", { name: "Insert Variable" }))
        fireEvent.click(await screen.findByText("{{full_name}}"))

        fireEvent.click(screen.getByRole("button", { name: "HTML" }))
        const htmlTextareaAfter = screen.getByLabelText("Email Body") as HTMLTextAreaElement
        expect(htmlTextareaAfter.value).toBe("<p>Body</p>")
    })
})
