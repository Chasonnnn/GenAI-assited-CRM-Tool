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
import type { EmailTemplateVersion } from "@/lib/api/email-template-history"
import type { EmailTemplateDraft } from "@/lib/api/email-template-drafts"

const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()
const mockRichTextEditorProps = vi.fn()
const mockUseEmailTemplates = vi.fn()
const mockCreateEmailTemplate = vi.fn()
const mockUpdateEmailTemplate = vi.fn()
const mockSendTestEmailTemplate = vi.fn()
const mockRollbackEmailTemplate = vi.fn()
const mockDiscardEmailTemplateDraft = vi.fn()
const mockRouterPush = vi.fn()
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

const TEMPLATE_VERSIONS: EmailTemplateVersion[] = [
    {
        id: "version-2",
        version: 2,
        created_by_user_id: "user_1",
        comment: "Updated",
        created_at: "2026-01-02T00:00:00.000Z",
    },
    {
        id: "version-1",
        version: 1,
        created_by_user_id: "user_1",
        comment: "Created",
        created_at: FIXED_TIMESTAMP,
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

const NEW_ORG_DRAFT: EmailTemplateDraft = {
    id: "draft_new_1",
    organization_id: "org_1",
    template_id: null,
    created_by_user_id: "user_1",
    updated_by_user_id: "user_1",
    scope: "org",
    owner_user_id: null,
    owner_name: null,
    name: "New Journey Draft",
    subject: "Hello {{full_name}}",
    from_email: null,
    body: "<p>Hello</p>",
    is_active: true,
    category: null,
    base_version: 0,
    revision: 3,
    published_version: null,
    is_stale: false,
    last_tested_revision: null,
    last_tested_at: null,
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
        current_version: 2,
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
let orgDraftsFixture: EmailTemplateDraft[] = []

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
    useEmailTemplateVersions: (id: string | null, enabled = true) => ({
        data: id === "tpl_org_1" && enabled ? TEMPLATE_VERSIONS : [],
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
    }),
    useCreateEmailTemplate: () => ({ mutate: mockCreateEmailTemplate, isPending: false }),
    useUpdateEmailTemplate: () => ({ mutate: mockUpdateEmailTemplate, isPending: false }),
    useRollbackEmailTemplate: () => ({
        mutateAsync: mockRollbackEmailTemplate,
        isPending: false,
    }),
    useDeleteEmailTemplate: () => ({ mutate: vi.fn(), isPending: false }),
    useCopyTemplateToPersonal: () => ({ mutate: vi.fn(), isPending: false }),
    useShareTemplateWithOrg: () => ({ mutate: vi.fn(), isPending: false }),
    useCopyTemplateFromLibrary: () => ({ mutate: vi.fn(), isPending: false }),
    useSendTestEmailTemplate: () => ({ mutateAsync: mockSendTestEmailTemplate, isPending: false }),
}))

vi.mock("@/lib/hooks/use-email-template-drafts", () => ({
    useEmailTemplateDrafts: () => ({
        data: orgDraftsFixture,
        isLoading: false,
    }),
    useDiscardEmailTemplateDraft: () => ({
        mutate: mockDiscardEmailTemplateDraft,
        isPending: false,
    }),
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
        mockRollbackEmailTemplate.mockReset()
        mockDiscardEmailTemplateDraft.mockReset()
        mockRouterPush.mockReset()
        mockSendTestEmailTemplate.mockResolvedValue({ provider_used: "resend" })
        mockRollbackEmailTemplate.mockResolvedValue({
            ...TEMPLATE_DETAIL_BY_ID.tpl_org_1,
            name: "Restored Org Template",
            subject: "Restored subject",
            body: "<p>Restored body</p>",
            current_version: 3,
        })
        userSignatureData = null
        personalTemplatesFixture = [PERSONAL_TEMPLATE]
        orgTemplatesFixture = [ORG_TEMPLATE]
        orgDraftsFixture = []
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
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["manage_email_templates"] },
        })
    })

    it("renders updated tabs", () => {
        render(<EmailTemplatesPage />)
        expect(screen.getByRole("tab", { name: "My Email Templates" })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: "Organization Templates" })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: "Platform Templates" })).toBeInTheDocument()
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
                    idempotency_key: expect.stringMatching(
                        /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
                    ),
                    ignore_opt_out: true,
                },
            })
        })
    })

    it("reuses one test-send occurrence after a request failure", async () => {
        mockSendTestEmailTemplate
            .mockRejectedValueOnce(new Error("Temporary failure"))
            .mockResolvedValueOnce({ queued: true, provider_used: "resend" })

        render(<EmailTemplatesPage />)

        fireEvent.click(await screen.findByRole("button", { name: "Actions for Personal Template" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Send test email" }))
        fireEvent.click(screen.getByRole("button", { name: "Send test" }))

        await waitFor(() => expect(mockSendTestEmailTemplate).toHaveBeenCalledTimes(1))
        expect(await screen.findByRole("dialog")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Send test" }))
        await waitFor(() => expect(mockSendTestEmailTemplate).toHaveBeenCalledTimes(2))

        const firstKey = mockSendTestEmailTemplate.mock.calls[0][0].payload.idempotency_key
        const retriedKey = mockSendTestEmailTemplate.mock.calls[1][0].payload.idempotency_key
        expect(firstKey).toEqual(expect.any(String))
        expect(retriedKey).toBe(firstKey)
    })

    it("updates untouched email variable samples when the test recipient changes", async () => {
        TEMPLATE_DETAIL_BY_ID.tpl_personal_1.body = "<p>{{email}}</p>"
        render(<EmailTemplatesPage />)

        fireEvent.click(await screen.findByRole("button", { name: "Actions for Personal Template" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Send test email" }))
        fireEvent.click(screen.getByRole("button", { name: "Variables (optional)" }))

        expect(await screen.findByLabelText("{{email}}")).toHaveValue("admin@example.com")
        fireEvent.change(screen.getByLabelText("To email"), {
            target: { value: "qa@example.com" },
        })

        expect(screen.getByLabelText("{{email}}")).toHaveValue("qa@example.com")
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

    it("routes organization template creation to the Studio", () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))
        fireEvent.click(screen.getByRole("button", { name: /Create Org Template/i }))

        expect(mockRouterPush).toHaveBeenCalledWith("/automation/email-templates/org/new")
        expect(screen.queryByRole("heading", { name: "Create Template" })).not.toBeInTheDocument()
    })

    it("routes empty-state organization template creation to the Studio", () => {
        orgTemplatesFixture = []
        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))
        const createButtons = screen.getAllByRole("button", { name: "Create Org Template" })
        fireEvent.click(createButtons[1]!)

        expect(mockRouterPush).toHaveBeenCalledWith("/automation/email-templates/org/new")
        expect(screen.queryByRole("heading", { name: "Create Template" })).not.toBeInTheDocument()
    })

    it("routes organization template editing to the Studio", async () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))
        fireEvent.click(await screen.findByRole("button", { name: "Actions for Org Template" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Edit" }))

        expect(mockRouterPush).toHaveBeenCalledWith(
            "/automation/email-templates/org/tpl_org_1",
        )
        expect(screen.queryByRole("heading", { name: "Edit Template" })).not.toBeInTheDocument()
    })

    it("shows and resumes an unpublished organization draft", () => {
        orgDraftsFixture = [NEW_ORG_DRAFT]

        render(<EmailTemplatesPage />)
        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))

        expect(screen.getByText("New Journey Draft")).toBeInTheDocument()
        expect(screen.getByText("Unpublished draft")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Resume New Journey Draft" }))

        expect(mockRouterPush).toHaveBeenCalledWith(
            "/automation/email-templates/org/draft_new_1",
        )
    })

    it("resumes published-template drafts through their canonical template route", () => {
        orgDraftsFixture = [{
            ...NEW_ORG_DRAFT,
            id: "draft_existing_1",
            template_id: "tpl_org_1",
            name: "Org Template updates",
            base_version: 2,
            published_version: 2,
        }]

        render(<EmailTemplatesPage />)
        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))
        fireEvent.click(screen.getByRole("button", { name: "Resume Org Template updates" }))

        expect(mockRouterPush).toHaveBeenCalledWith(
            "/automation/email-templates/org/tpl_org_1",
        )
    })

    it("requires confirmation before discarding the exact draft revision", async () => {
        orgDraftsFixture = [NEW_ORG_DRAFT]

        render(<EmailTemplatesPage />)
        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))
        fireEvent.click(screen.getByRole("button", { name: "Discard New Journey Draft" }))

        expect(mockDiscardEmailTemplateDraft).not.toHaveBeenCalled()
        expect(await screen.findByRole("heading", { name: "Discard draft?" })).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Discard draft" }))

        expect(mockDiscardEmailTemplateDraft).toHaveBeenCalledWith(
            {
                id: "draft_new_1",
                expectedRevision: 3,
            },
            expect.any(Object),
        )
    })

    it("does not expose organization drafts without template-management permission", () => {
        orgDraftsFixture = [NEW_ORG_DRAFT]
        mockUseAuth.mockReturnValue({
            user: {
                user_id: "user_1",
                role: "case_manager",
                email: "case-manager@example.com",
                display_name: "Case Manager",
                org_name: "Test Org",
                ai_enabled: false,
            },
        })
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: [] },
        })

        render(<EmailTemplatesPage />)
        fireEvent.click(screen.getByRole("tab", { name: "Organization Templates" }))

        expect(screen.queryByText("New Journey Draft")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Resume New Journey Draft" })).not.toBeInTheDocument()
    })

    it("keeps personal template editing in the existing modal", async () => {
        render(<EmailTemplatesPage />)

        fireEvent.click(await screen.findByRole("button", { name: "Actions for Personal Template" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Edit" }))

        expect(mockRouterPush).not.toHaveBeenCalled()
        expect(await screen.findByRole("heading", { name: "Edit Template" })).toBeInTheDocument()
        expect(screen.getByLabelText("Template Name")).toHaveValue("Personal Template")
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
