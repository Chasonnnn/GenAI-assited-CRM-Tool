import { emailDesignEditorMock } from "./fixtures/email-design-editor-mock"
import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render as renderWithoutQueries, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import OrganizationEmailTemplateStudio from "@/components/email/organization-email-template-studio"
import { ApiError } from "@/lib/api"

// The studio queries the layout frame and checks, so every render gets its own query client.
function render(ui: React.ReactElement) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return renderWithoutQueries(ui, {
        wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
    })
}

const LAYOUT_FRAME = {
    layout: {
        kind: "card",
        show_logo: true,
        logo_position: "center",
        accent_color: null,
        page_background: "#f4f4f5",
    },
    logo_url: "https://api.example.com/forms/public/org-1/signature-logo?v=abc",
    logo_alt: "EWI Family Global",
    accent_color: "#b8335f",
    signature_html: "<p>EWI Family Global</p>",
    footer_html: '<p>If you no longer wish to receive these emails, <a href="#unsubscribe">Unsubscribe</a>.</p>',
}

const mocks = vi.hoisted(() => ({
    push: vi.fn(),
    replace: vi.fn(),
    createDraft: vi.fn(),
    createDraftFromTemplate: vi.fn(),
    updateDraft: vi.fn(),
    discardDraft: vi.fn(),
    publishDraft: vi.fn(),
    restoreDraftVersion: vi.fn(),
    sendTestDraft: vi.fn(),
    preview: vi.fn(),
    layoutFrame: vi.fn(),
    draftListParams: vi.fn(),
    refetchDrafts: vi.fn(),
    refetchPublished: vi.fn(),
    refetchDraft: vi.fn(),
    refetchVersions: vi.fn(),
    state: {
        permissionPolicy: 1,
        permissions: [] as string[],
        publishedTemplate: null as Record<string, unknown> | null,
        draft: null as Record<string, unknown> | null,
        publishedLookupErrorId: null as string | null,
        publishedLookupError: null as Error | null,
        draftsLoading: false,
        draftsError: false,
        draftsErrorValue: null as Error | null,
        versions: [
            {
                id: "version-7",
                version: 7,
                created_by_user_id: "user-1",
                comment: "Updated",
                created_at: "2026-07-23T12:00:00Z",
            },
            {
                id: "version-3",
                version: 3,
                created_by_user_id: "user-1",
                comment: "Created",
                created_at: "2026-07-01T12:00:00Z",
            },
        ],
    },
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => ({ data: {
        policy_version: mocks.state.permissionPolicy, permissions: mocks.state.permissions,
    } }),
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({
        user: {
            email: "owner@example.com",
            org_name: "EWI Family Global",
            org_display_name: "EWI Family Global",
        },
    }),
}))

vi.mock("@/components/email/design/email-design-editor", () => import("./fixtures/email-design-editor-mock"))

vi.mock("@/lib/api/email-templates", async (importOriginal) => ({
    ...(await importOriginal<typeof import("@/lib/api/email-templates")>()),
    previewEmailTemplate: mocks.preview,
    getEmailLayoutFrame: mocks.layoutFrame,
}))

vi.mock("@/lib/hooks/use-email-templates", () => ({
    useEmailTemplate: (id: string | null) => ({
        data: mocks.state.publishedTemplate,
        isLoading: false,
        isError:
            Boolean(id) && id === mocks.state.publishedLookupErrorId,
        error:
            Boolean(id) && id === mocks.state.publishedLookupErrorId
                ? mocks.state.publishedLookupError
                : null,
        isFetching: false,
        refetch: mocks.refetchPublished,
    }),
    useEmailTemplateVariables: () => ({
        data: [
            {
                name: "first_name",
                description: "Recipient first name",
                category: "Recipient",
                required: false,
                value_type: "text",
                html_safe: false,
            },
        ],
        isLoading: false,
    }),
    useEmailTemplateVersions: () => ({
        data: mocks.state.versions,
        isLoading: false,
        isError: false,
        refetch: mocks.refetchVersions,
    }),
}))

vi.mock("@/lib/hooks/use-email-template-drafts", () => ({
    useEmailTemplateDrafts: (params: Record<string, unknown>) => {
        mocks.draftListParams(params)
        return {
            data: mocks.state.draft ? [mocks.state.draft] : [],
            isLoading: mocks.state.draftsLoading,
            isError: mocks.state.draftsError,
            error: mocks.state.draftsErrorValue,
            isFetching: false,
            refetch: mocks.refetchDrafts,
        }
    },
    useEmailTemplateDraft: () => ({
        data: mocks.state.draft,
        isLoading: false,
        isError: false,
        refetch: mocks.refetchDraft,
    }),
    useCreateEmailTemplateDraft: () => ({
        mutateAsync: mocks.createDraft,
        isPending: false,
    }),
    useCreateEmailTemplateDraftFromTemplate: () => ({
        mutateAsync: mocks.createDraftFromTemplate,
        isPending: false,
    }),
    useUpdateEmailTemplateDraft: () => ({
        mutateAsync: mocks.updateDraft,
        isPending: false,
    }),
    useDiscardEmailTemplateDraft: () => ({
        mutateAsync: mocks.discardDraft,
        isPending: false,
    }),
    usePublishEmailTemplateDraft: () => ({
        mutateAsync: mocks.publishDraft,
        isPending: false,
    }),
    useRestoreEmailTemplateDraftVersion: () => ({
        mutateAsync: mocks.restoreDraftVersion,
        isPending: false,
    }),
    useSendTestEmailTemplateDraft: () => ({
        mutateAsync: mocks.sendTestDraft,
        isPending: false,
    }),
}))

const publishedTemplate = {
    id: "template-1",
    organization_id: "org-1",
    created_by_user_id: "user-1",
    name: "Legacy welcome",
    subject: "Original subject",
    from_email: "Surrogacy Force <hello@example.com>",
    body: "<table><tr><td>{{unknown_legacy_token}}</td></tr></table>",
    is_active: true,
    scope: "org",
    owner_user_id: null,
    owner_name: null,
    source_template_id: null,
    is_system_template: false,
    current_version: 7,
    created_at: "2026-07-01T12:00:00Z",
    updated_at: "2026-07-01T12:00:00Z",
}

const draftFromPublished = {
    id: "draft-1",
    organization_id: "org-1",
    template_id: "template-1",
    created_by_user_id: "user-1",
    updated_by_user_id: "user-1",
    scope: "org",
    owner_user_id: null,
    owner_name: null,
    name: publishedTemplate.name,
    subject: publishedTemplate.subject,
    from_email: publishedTemplate.from_email,
    body: publishedTemplate.body,
    is_active: true,
    category: null,
    base_version: 7,
    revision: 1,
    published_version: 7,
    is_stale: false,
    last_tested_revision: null,
    last_tested_at: null,
    created_at: "2026-07-23T12:00:00Z",
    updated_at: "2026-07-23T12:00:00Z",
}

describe("OrganizationEmailTemplateStudio", () => {
    it("requires the send action before opening a v2 draft test", () => {
        mocks.state.permissionPolicy = 2
        mocks.state.permissions = ["manage_email_templates", "manage_org_templates"]
        mocks.state.draft = draftFromPublished
        const view = render(<OrganizationEmailTemplateStudio templateId="template-1" />)
        expect(screen.getByRole("button", { name: "Send test" })).toBeDisabled()
        mocks.state.permissions.push("send_email")
        view.rerender(<OrganizationEmailTemplateStudio templateId="template-1" />)
        expect(screen.getByRole("button", { name: "Send test" })).toBeEnabled()
    })

    beforeEach(() => {
        mocks.state.permissionPolicy = 1
        mocks.state.permissions = ["manage_email_templates"]
        mocks.push.mockReset()
        mocks.replace.mockReset()
        mocks.createDraft.mockReset()
        mocks.createDraftFromTemplate.mockReset()
        mocks.updateDraft.mockReset()
        mocks.discardDraft.mockReset()
        mocks.publishDraft.mockReset()
        mocks.restoreDraftVersion.mockReset()
        mocks.sendTestDraft.mockReset()
        emailDesignEditorMock.reset()
        mocks.preview.mockReset()
        mocks.preview.mockResolvedValue({
            subject: "Original subject",
            html: "<!doctype html><html><body><p>Hi</p><a href=\"#unsubscribe\">Unsubscribe</a></body></html>",
            unresolved_variables: [],
        })
        mocks.layoutFrame.mockReset()
        mocks.layoutFrame.mockImplementation(({ layout }: { layout: Record<string, unknown> }) =>
            Promise.resolve({ ...LAYOUT_FRAME, layout }),
        )
        mocks.draftListParams.mockReset()
        mocks.refetchDrafts.mockReset()
        mocks.refetchPublished.mockReset()
        mocks.refetchDraft.mockReset()
        mocks.refetchVersions.mockReset()
        mocks.state.publishedTemplate = publishedTemplate
        mocks.state.draft = null
        mocks.state.publishedLookupErrorId = null
        mocks.state.draftsLoading = false
        mocks.state.draftsError = false
        mocks.state.draftsErrorValue = null
        mocks.state.publishedLookupError = null

        mocks.createDraftFromTemplate.mockResolvedValue(draftFromPublished)
        mocks.updateDraft.mockResolvedValue({
            ...draftFromPublished,
            subject: "A safer subject",
            revision: 2,
        })
        mocks.restoreDraftVersion.mockResolvedValue({
            ...draftFromPublished,
            name: "Historical welcome",
            subject: "Historical subject",
            body: "<p>Historical body</p>",
            revision: 2,
            last_tested_revision: null,
        })
    })

    it("shows the canonical published version before a draft exists", () => {
        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        expect(screen.getByText("No draft")).toBeInTheDocument()
        expect(screen.getByText("Published version 7")).toBeInTheDocument()
        expect(screen.getByText("Save draft to test")).toBeInTheDocument()
    })

    it("loads personal drafts when the Studio is opened for personal scope", () => {
        render(
            <OrganizationEmailTemplateStudio
                templateId="template-1"
                scope="personal"
            />,
        )

        expect(mocks.draftListParams).toHaveBeenCalledWith({
            scope: "personal",
            showAllPersonal: true,
        })
    })

    it("creates a personal draft in personal scope without publishing it", async () => {
        mocks.state.publishedTemplate = null
        mocks.createDraft.mockResolvedValue({
            ...draftFromPublished,
            id: "draft-personal-created",
            template_id: null,
            scope: "personal",
            owner_user_id: "user-1",
            name: "My follow-up",
            subject: "Hello there",
            from_email: null,
            body: "<p>Welcome</p>",
            published_version: null,
        })

        render(<OrganizationEmailTemplateStudio scope="personal" />)
        fireEvent.change(screen.getByLabelText("Template name"), {
            target: { value: "My follow-up" },
        })
        fireEvent.change(screen.getByLabelText("Subject"), {
            target: { value: "Hello there" },
        })
        fireEvent.change(screen.getByLabelText("Email body"), {
            target: { value: "<p>Welcome</p>" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => {
            expect(mocks.createDraft).toHaveBeenCalledWith({
                name: "My follow-up",
                subject: "Hello there",
                from_email: null,
                body: "<p>Welcome</p>",
                scope: "personal",
            })
        })
        expect(mocks.publishDraft).not.toHaveBeenCalled()
        expect(mocks.push).toHaveBeenCalledWith(
            "/automation/email-templates/personal/draft-personal-created",
        )
    })

    it("saves a subject-only edit without resending unchanged legacy body or sender", async () => {
        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        fireEvent.change(screen.getByLabelText("Subject"), {
            target: { value: "A safer subject" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => {
            expect(mocks.createDraftFromTemplate).toHaveBeenCalledWith({
                templateId: "template-1",
            })
        })
        expect(mocks.updateDraft).toHaveBeenCalledWith({
            id: "draft-1",
            data: {
                expected_revision: 1,
                subject: "A safer subject",
            },
        })
        expect(screen.getByLabelText("Subject")).toHaveValue("A safer subject")
    })

    it("publishes only after explicit confirmation with both version guards", async () => {
        mocks.state.draft = draftFromPublished
        mocks.publishDraft.mockResolvedValue({
            ...publishedTemplate,
            id: "canonical-template-8",
            current_version: 8,
        })

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        fireEvent.click(screen.getByRole("button", { name: "Publish" }))
        expect(mocks.publishDraft).not.toHaveBeenCalled()
        expect(
            screen.getByRole("heading", { name: "Publish this template?" }),
        ).toBeInTheDocument()
        expect(
            screen.getByText(
                "This saved revision has not been test-sent. Testing is recommended, but not required to publish.",
            ),
        ).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Publish now" }))

        await waitFor(() => {
            expect(mocks.publishDraft).toHaveBeenCalledWith({
                id: "draft-1",
                data: {
                    expected_revision: 1,
                    expected_published_version: 7,
                },
            })
        })
        expect(mocks.replace).toHaveBeenCalledWith(
            "/automation/email-templates/org/canonical-template-8",
        )
    })

    it("restores published history into an isolated draft before production changes", async () => {
        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        fireEvent.click(screen.getByRole("button", { name: "View history" }))
        expect(
            await screen.findByRole("heading", { name: "Template history" }),
        ).toBeInTheDocument()
        expect(
            screen.getByText(
                "Review published versions or load one into an isolated draft. Production stays unchanged until you publish.",
            ),
        ).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Restore version 3" }))
        fireEvent.click(screen.getByRole("button", { name: "Restore to draft" }))

        await waitFor(() => {
            expect(mocks.createDraftFromTemplate).toHaveBeenCalledWith({
                templateId: "template-1",
            })
        })
        expect(mocks.restoreDraftVersion).toHaveBeenCalledWith({
            id: "draft-1",
            data: {
                target_version: 3,
                expected_revision: 1,
            },
        })
        expect(screen.getByLabelText("Template name")).toHaveValue(
            "Historical welcome",
        )
        expect(screen.getByLabelText("Subject")).toHaveValue("Historical subject")
        expect(screen.getByText("Published version 7")).toBeInTheDocument()
        expect(mocks.publishDraft).not.toHaveBeenCalled()
    })

    it("retains the saved draft and offers recovery when publish hits a version conflict", async () => {
        mocks.state.draft = draftFromPublished
        mocks.publishDraft.mockRejectedValue(
            new ApiError(409, "Conflict", "Published version mismatch"),
        )

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)
        fireEvent.click(screen.getByRole("button", { name: "Publish" }))
        fireEvent.click(screen.getByRole("button", { name: "Publish now" }))

        expect(
            await screen.findByRole("heading", {
                name: "Draft changed elsewhere",
            }),
        ).toBeInTheDocument()
        expect(screen.getByLabelText("Subject")).toHaveValue("Original subject")
        expect(mocks.replace).not.toHaveBeenCalled()
    })

    it("retains local content when saving hits a stale revision conflict", async () => {
        mocks.state.draft = draftFromPublished
        mocks.updateDraft.mockRejectedValue(
            new ApiError(409, "Conflict", "Draft revision mismatch"),
        )

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        fireEvent.change(screen.getByLabelText("Subject"), {
            target: { value: "Keep this local subject" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        expect(
            await screen.findByRole("heading", { name: "Draft changed elsewhere" }),
        ).toBeInTheDocument()
        expect(screen.getByLabelText("Subject")).toHaveValue(
            "Keep this local subject",
        )
        expect(
            screen.getByRole("button", { name: "Copy local draft" }),
        ).toBeInTheDocument()
        expect(
            screen.getByRole("button", { name: "Reload latest" }),
        ).toBeInTheDocument()
    })

    it("recovers an initially stale draft only after an explicit discard confirmation", async () => {
        mocks.state.draft = {
            ...draftFromPublished,
            is_stale: true,
        }
        mocks.discardDraft.mockResolvedValue(undefined)

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        expect(
            screen.getByRole("heading", { name: "Draft changed elsewhere" }),
        ).toBeInTheDocument()
        expect(screen.getByText("Stale draft")).toBeInTheDocument()
        fireEvent.click(
            screen.getByRole("button", { name: "Discard stale draft" }),
        )
        expect(mocks.discardDraft).not.toHaveBeenCalled()
        expect(
            screen.getByRole("heading", { name: "Discard this stale draft?" }),
        ).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Discard draft" }))

        await waitFor(() => {
            expect(mocks.discardDraft).toHaveBeenCalledWith({
                id: "draft-1",
                expectedRevision: 1,
            })
        })
        expect(mocks.replace).toHaveBeenCalledWith(
            "/automation/email-templates",
        )
        expect(mocks.publishDraft).not.toHaveBeenCalled()
    })

    it("guards back navigation while local edits are unsaved", async () => {
        mocks.state.draft = draftFromPublished

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)
        fireEvent.change(screen.getByLabelText("Subject"), {
            target: { value: "Unsaved subject" },
        })

        const unloadEvent = new Event("beforeunload", { cancelable: true })
        window.dispatchEvent(unloadEvent)
        expect(unloadEvent.defaultPrevented).toBe(true)

        fireEvent.click(
            screen.getByRole("button", { name: "Back to email templates" }),
        )
        expect(mocks.push).not.toHaveBeenCalled()
        expect(
            screen.getByRole("heading", { name: "Leave without saving?" }),
        ).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Discard changes" })).toHaveClass(
            "bg-destructive",
        )

        fireEvent.click(screen.getByRole("button", { name: "Keep editing" }))
        expect(mocks.push).not.toHaveBeenCalled()

        fireEvent.click(
            screen.getByRole("button", { name: "Back to email templates" }),
        )
        fireEvent.click(screen.getByRole("button", { name: "Discard changes" }))

        expect(mocks.push).toHaveBeenCalledWith("/automation/email-templates")
    })

    it("draws the whole email in the Edit tab, with no separate Preview tab", async () => {
        mocks.state.draft = { ...draftFromPublished, body: "<p>Welcome</p>" }

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Edit", "HTML"])
        expect(screen.getByLabelText("From")).toHaveValue(publishedTemplate.from_email)
        expect(screen.getByText("Recipient")).toBeInTheDocument()
        expect(screen.getByLabelText("Subject")).toHaveValue("Original subject")
        // Org templates default to Card: the server frame gives the logo, signature, and footer.
        await waitFor(() => {
            expect(mocks.layoutFrame).toHaveBeenCalledWith({
                scope: "org",
                layout: expect.objectContaining({ kind: "card", show_logo: true }),
            })
        })
        expect(await screen.findByRole("img", { name: "EWI Family Global" })).toBeInTheDocument()
        expect(screen.getByTitle("Signature and unsubscribe footer")).toBeInTheDocument()
        expect(screen.getByRole("radio", { name: /Card/ })).toBeChecked()
        expect(emailDesignEditorMock.render).toHaveBeenLastCalledWith(
            expect.objectContaining({ documentStyles: false }),
        )
    })

    it("defaults personal templates to Plain with the sender's own address", async () => {
        mocks.state.publishedTemplate = { ...publishedTemplate, scope: "personal" }
        mocks.state.draft = { ...draftFromPublished, scope: "personal", body: "<p>Hi</p>" }

        render(<OrganizationEmailTemplateStudio templateId="template-1" scope="personal" />)

        expect(screen.getByText("owner@example.com")).toBeInTheDocument()
        expect(screen.getByRole("radio", { name: /Plain/ })).toBeChecked()
        await waitFor(() => {
            expect(mocks.layoutFrame).toHaveBeenCalledWith({
                scope: "personal",
                layout: expect.objectContaining({ kind: "plain" }),
            })
        })
        expect(emailDesignEditorMock.render).toHaveBeenLastCalledWith(
            expect.objectContaining({ documentStyles: true }),
        )
    })

    it("saves a layout change with the draft", async () => {
        mocks.state.draft = { ...draftFromPublished, body: "<p>Welcome</p>" }
        mocks.updateDraft.mockResolvedValue({ ...draftFromPublished, revision: 2 })

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)
        fireEvent.click(screen.getByRole("radio", { name: /Letterhead/ }))
        fireEvent.click(screen.getByRole("radio", { name: "Left" }))
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => {
            expect(mocks.updateDraft).toHaveBeenCalledWith({
                id: "draft-1",
                data: {
                    expected_revision: 1,
                    layout: {
                        kind: "letterhead",
                        show_logo: true,
                        logo_position: "left",
                        accent_color: null,
                        page_background: "#f4f4f5",
                    },
                },
            })
        })
    })

    it("keeps the body's own logo placement in the canvas", async () => {
        mocks.state.draft = { ...draftFromPublished, body: '<img src="{{org_logo_url}}"><p>Hi</p>' }

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        await waitFor(() => {
            expect(mocks.layoutFrame).toHaveBeenCalledWith({
                scope: "org",
                layout: expect.objectContaining({ kind: "card", show_logo: false }),
            })
        })
    })

    it("offers a retry when the signature frame fails to load", async () => {
        mocks.state.draft = { ...draftFromPublished, body: "<p>Welcome</p>" }
        mocks.layoutFrame.mockRejectedValueOnce(new Error("down"))

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        expect(await screen.findByText("Signature could not load.")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(await screen.findByTitle("Signature and unsubscribe footer")).toBeInTheDocument()
    })

    it("opens a legacy body in the block editor without marking it changed", () => {
        mocks.state.draft = draftFromPublished

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        expect(emailDesignEditorMock.render).toHaveBeenCalledWith(
            expect.objectContaining({
                initialValue: { body: publishedTemplate.body, bodyDesign: null },
            }),
        )
        expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled()
    })

    it("saves the compiled body and its design together", async () => {
        const design = { type: "doc" as const, content: [{ type: "paragraph" }] }
        mocks.state.draft = draftFromPublished
        emailDesignEditorMock.nextDesign = design
        mocks.updateDraft.mockResolvedValue({
            ...draftFromPublished,
            body: "<p>Designed</p>",
            body_design: design,
            revision: 2,
        })

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)
        fireEvent.change(screen.getByLabelText("Email body"), {
            target: { value: "<p>Designed</p>" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => {
            expect(mocks.updateDraft).toHaveBeenCalledWith({
                id: "draft-1",
                data: {
                    expected_revision: 1,
                    body: "<p>Designed</p>",
                    body_design: design,
                },
            })
        })
    })

    it("sends a body edit without a design so the server clears the old design", async () => {
        mocks.state.draft = {
            ...draftFromPublished,
            body: "<p>Designed</p>",
            body_design: { type: "doc", content: [] },
        }
        mocks.updateDraft.mockResolvedValue({ ...draftFromPublished, body: "<p>Raw</p>", revision: 2 })

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)
        fireEvent.change(screen.getByLabelText("Email body"), { target: { value: "<p>Raw</p>" } })
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => {
            expect(mocks.updateDraft).toHaveBeenCalledWith({
                id: "draft-1",
                data: { expected_revision: 1, body: "<p>Raw</p>", body_design: null },
            })
        })
    })

    it.each(["org", "personal"] as const)(
        "checks unsaved %s content through the server composition with variable names",
        async (scope) => {
            mocks.state.publishedTemplate = {
                ...publishedTemplate,
                scope,
                owner_user_id: scope === "personal" ? "user-1" : null,
            }
            mocks.state.draft = {
                ...draftFromPublished,
                scope,
                owner_user_id: scope === "personal" ? "user-1" : null,
                subject: "Hello {{first_name}}",
                body: "<p>Welcome {{mystery}}</p>",
            }
            mocks.preview.mockResolvedValue({
                subject: "Hello {{first_name}}",
                html: "<!doctype html><html><body><p>Welcome {{mystery}}</p></body></html>",
                unresolved_variables: ["mystery"],
            })

            render(<OrganizationEmailTemplateStudio templateId="template-1" scope={scope} />)

            await waitFor(() => {
                expect(mocks.preview).toHaveBeenCalledWith({
                    subject: "Hello {{first_name}}",
                    body: "<p>Welcome {{mystery}}</p>",
                    layout: null,
                    scope,
                    variable_mode: "names",
                })
            })
            expect(await screen.findByText("Unknown: mystery")).toBeInTheDocument()
            expect(screen.getByText("1 KB")).toBeInTheDocument()
        },
    )

    it("shows the stored send HTML", () => {
        mocks.state.draft = draftFromPublished

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)
        fireEvent.click(screen.getByRole("tab", { name: "HTML" }))

        expect(screen.getByRole("heading", { name: "Email HTML" })).toBeInTheDocument()
        expect(screen.getByText(publishedTemplate.body, { selector: "pre" })).toBeInTheDocument()
    })

    it("saves an active template as inactive through the Studio status control", async () => {
        mocks.state.draft = draftFromPublished
        mocks.updateDraft.mockResolvedValue({
            ...draftFromPublished,
            is_active: false,
            revision: 2,
        })

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        const activeSwitch = screen.getByRole("switch", {
            name: "Template is active",
        })
        expect(activeSwitch).toBeChecked()
        fireEvent.click(activeSwitch)
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => {
            expect(mocks.updateDraft).toHaveBeenCalledWith({
                id: "draft-1",
                data: {
                    expected_revision: 1,
                    is_active: false,
                },
            })
        })
    })

    it("inserts a variable into the field being edited", () => {
        mocks.state.draft = {
            ...draftFromPublished,
            body: "<p>Hello</p>",
        }

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        const subject = screen.getByLabelText("Subject")
        fireEvent.focus(subject)
        fireEvent.click(screen.getByRole("button", { name: "Insert {{first_name}}" }))

        expect(subject).toHaveValue("Original subject{{first_name}}")
    })

    it("reuses one test occurrence across retries and reports a queued Resend test truthfully", async () => {
        mocks.state.draft = {
            ...draftFromPublished,
            body: "<p>Hello {{first_name}}</p>",
        }
        mocks.sendTestDraft
            .mockRejectedValueOnce(new Error("Temporary provider failure"))
            .mockResolvedValueOnce({
                success: true,
                queued: true,
                provider_used: "resend",
                submitted_revision: 1,
                tested_revision: null,
            })

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        expect(screen.getByText("Not tested")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Send test" }))
        fireEvent.change(screen.getByLabelText("To email"), {
            target: { value: "qa@example.com" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Variables (optional)" }))
        fireEvent.change(await screen.findByLabelText("First name"), {
            target: { value: "Taylor" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Send test email" }))

        expect(
            await screen.findByText("Test email failed. Your draft was not changed."),
        ).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Send test email" }))

        await waitFor(() => expect(mocks.sendTestDraft).toHaveBeenCalledTimes(2))
        const [firstRequest, secondRequest] = mocks.sendTestDraft.mock.calls
        if (!firstRequest || !secondRequest) throw new Error("Expected both test sends")
        const firstCall = firstRequest[0]
        const secondCall = secondRequest[0]
        expect(firstCall).toEqual({
            id: "draft-1",
            payload: {
                to_email: "qa@example.com",
                variables: { first_name: "Taylor" },
                idempotency_key: expect.any(String),
                ignore_opt_out: false,
                expected_revision: 1,
            },
        })
        expect(secondCall.payload.idempotency_key).toBe(
            firstCall.payload.idempotency_key,
        )
        expect(
            await screen.findByText("Test queued for current draft"),
        ).toBeInTheDocument()
        expect(screen.queryByText("Tested current draft")).not.toBeInTheDocument()
    })

    it.each(["recipient", "variables", "opt-out"])(
        "starts a new test occurrence after changing %s",
        async (field) => {
            mocks.state.draft = { ...draftFromPublished, body: "<p>{{first_name}}</p>" }
            mocks.sendTestDraft.mockRejectedValue(new Error("Temporary failure"))
            render(<OrganizationEmailTemplateStudio templateId="template-1" />)
            fireEvent.click(screen.getByRole("button", { name: "Send test" }))
            fireEvent.change(screen.getByLabelText("To email"), {
                target: { value: "qa@example.com" },
            })
            fireEvent.click(screen.getByRole("button", { name: "Send test email" }))
            await screen.findByRole("alert")

            if (field === "recipient") {
                fireEvent.change(screen.getByLabelText("To email"), {
                    target: { value: "changed@example.com" },
                })
            } else if (field === "variables") {
                fireEvent.click(screen.getByRole("button", { name: "Variables (optional)" }))
                fireEvent.change(await screen.findByLabelText("First name"), {
                    target: { value: "Changed" },
                })
            } else {
                fireEvent.click(screen.getByRole("checkbox", { name: "Send even if unsubscribed" }))
            }
            fireEvent.click(screen.getByRole("button", { name: "Send test email" }))
            await waitFor(() => expect(mocks.sendTestDraft).toHaveBeenCalledTimes(2))
            expect(mocks.sendTestDraft.mock.calls[1]?.[0].payload.idempotency_key).not.toBe(
                mocks.sendTestDraft.mock.calls[0]?.[0].payload.idempotency_key,
            )
        },
    )

    it("shows a recoverable send conflict without treating the draft as stale", async () => {
        mocks.state.draft = draftFromPublished
        mocks.sendTestDraft.mockResolvedValue({
            success: false,
            error_code: "idempotency_conflict",
            error: "Private provider detail",
        })
        render(<OrganizationEmailTemplateStudio templateId="template-1" />)
        fireEvent.click(screen.getByRole("button", { name: "Send test" }))
        fireEvent.change(screen.getByLabelText("To email"), {
            target: { value: "qa@example.com" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Send test email" }))
        expect(await screen.findByRole("alert")).toHaveTextContent(
            "Test email details changed since the previous attempt. Close and reopen this dialog to start a new test.",
        )
        expect(screen.queryByText("Private provider detail")).not.toBeInTheDocument()
        expect(screen.queryByText("Refresh required")).not.toBeInTheDocument()
        expect(screen.getByText("Not tested")).toBeInTheDocument()
    })

    it("keeps the test dialog open when the provider returns a resolved failure", async () => {
        mocks.state.draft = draftFromPublished
        mocks.sendTestDraft.mockResolvedValue({
            success: false,
            queued: false,
            provider_used: "resend",
            submitted_revision: 1,
            tested_revision: null,
            error: "Recipient is suppressed",
        })

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)
        fireEvent.click(screen.getByRole("button", { name: "Send test" }))
        fireEvent.change(screen.getByLabelText("To email"), {
            target: { value: "qa@example.com" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Send test email" }))

        expect(
            await screen.findByText(
                "Test email was not queued. Check the recipient and email integration, then try again.",
            ),
        ).toBeInTheDocument()
        expect(screen.queryByText("Recipient is suppressed")).not.toBeInTheDocument()
        expect(screen.getByLabelText("To email")).toHaveValue(
            "qa@example.com",
        )
        expect(screen.getByRole("button", { name: "Send test email" })).toBeEnabled()
        expect(screen.getByText("Not tested")).toBeInTheDocument()
    })

    it("uses the server-confirmed tested revision instead of assuming the current draft", async () => {
        mocks.state.draft = draftFromPublished
        mocks.sendTestDraft.mockResolvedValue({
            success: true,
            queued: false,
            provider_used: "gmail",
            submitted_revision: 1,
            tested_revision: 2,
        })

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)
        fireEvent.click(screen.getByRole("button", { name: "Send test" }))
        fireEvent.change(screen.getByLabelText("To email"), {
            target: { value: "qa@example.com" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Send test email" }))

        await waitFor(() => expect(mocks.sendTestDraft).toHaveBeenCalledOnce())
        expect(screen.getByText("Not tested")).toBeInTheDocument()
    })

    it("opens a draft-only route without looking it up as a canonical template", () => {
        mocks.state.publishedTemplate = null
        mocks.state.publishedLookupErrorId = "draft-new"
        mocks.state.draft = {
            ...draftFromPublished,
            id: "draft-new",
            template_id: null,
            published_version: null,
        }

        render(<OrganizationEmailTemplateStudio templateId="draft-new" />)

        expect(
            screen.getByRole("heading", { level: 1, name: "Legacy welcome" }),
        ).toBeInTheDocument()
        expect(
            screen.queryByRole("heading", { name: "New email template" }),
        ).not.toBeInTheDocument()
        expect(
            screen.queryByRole("heading", {
                name: "Couldn't load template studio",
            }),
        ).not.toBeInTheDocument()
    })

    it("titles a published template with its saved name, not the name being typed", () => {
        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        expect(
            screen.getByRole("heading", { level: 1, name: "Legacy welcome" }),
        ).toBeInTheDocument()
        fireEvent.change(screen.getByLabelText("Template name"), {
            target: { value: "Renamed" },
        })
        expect(
            screen.getByRole("heading", { level: 1, name: "Legacy welcome" }),
        ).toBeInTheDocument()
    })

    it("shows a denied state with a way back when organization drafts return 403", () => {
        mocks.state.publishedTemplate = null
        mocks.state.draftsError = true
        mocks.state.draftsErrorValue = new ApiError(403, "Forbidden", "Missing permission")

        render(<OrganizationEmailTemplateStudio />)

        expect(
            screen.getByRole("heading", {
                level: 2,
                name: "Organization templates require template management access",
            }),
        ).toBeInTheDocument()
        expect(screen.queryByText("Missing permission")).not.toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to Email Templates" })).toHaveAttribute(
            "href",
            "/automation/email-templates",
        )
    })

    it("shows a not-found state for a missing template id instead of loading", () => {
        mocks.state.publishedTemplate = null
        mocks.state.publishedLookupErrorId = "missing-template"
        mocks.state.publishedLookupError = new ApiError(404, "Not Found", "Template not found")

        render(<OrganizationEmailTemplateStudio templateId="missing-template" />)

        expect(
            screen.getByRole("heading", { level: 2, name: "Template not found" }),
        ).toBeInTheDocument()
        expect(screen.getByRole("link", { name: /Back to Email Templates/ })).toHaveAttribute(
            "href",
            "/automation/email-templates",
        )
        expect(screen.queryByText("Loading template studio…")).not.toBeInTheDocument()
    })

    it("shows a not-found state when an id resolves to no draft or template", () => {
        mocks.state.publishedTemplate = null

        render(<OrganizationEmailTemplateStudio templateId="missing-template" />)

        expect(
            screen.getByRole("heading", { level: 2, name: "Template not found" }),
        ).toBeInTheDocument()
    })

    it("applies only explicit local edits when the created draft baseline has diverged", async () => {
        mocks.createDraftFromTemplate.mockResolvedValue({
            ...draftFromPublished,
            body: "<p>Newer canonical body</p>",
            from_email: "New Sender <new@example.com>",
            base_version: 8,
        })

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)
        fireEvent.change(screen.getByLabelText("Subject"), {
            target: { value: "Only this changed locally" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => expect(mocks.updateDraft).toHaveBeenCalledOnce())
        expect(mocks.updateDraft).toHaveBeenCalledWith({
            id: "draft-1",
            data: {
                expected_revision: 1,
                subject: "Only this changed locally",
            },
        })
    })

    it("does not overwrite a newer value when a locally edited field diverged during first save", async () => {
        mocks.createDraftFromTemplate.mockResolvedValue({
            ...draftFromPublished,
            subject: "A newer server subject",
            base_version: 8,
        })

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)
        fireEvent.change(screen.getByLabelText("Subject"), {
            target: { value: "My local subject" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        expect(
            await screen.findByRole("heading", {
                name: "Draft changed elsewhere",
            }),
        ).toBeInTheDocument()
        expect(screen.getByLabelText("Subject")).toHaveValue("My local subject")
        expect(mocks.updateDraft).not.toHaveBeenCalled()
    })

    it("creates a new organization draft without publishing it", async () => {
        mocks.state.publishedTemplate = null
        const newDraft = {
            ...draftFromPublished,
            id: "draft-created",
            template_id: null,
            name: "New outreach",
            subject: "Hello there",
            from_email: null,
            body: "<p>Welcome</p>",
            published_version: null,
        }
        mocks.createDraft.mockResolvedValue(newDraft)

        render(<OrganizationEmailTemplateStudio />)
        fireEvent.change(screen.getByLabelText("Template name"), {
            target: { value: "New outreach" },
        })
        fireEvent.change(screen.getByLabelText("Subject"), {
            target: { value: "Hello there" },
        })
        fireEvent.change(screen.getByLabelText("Email body"), {
            target: { value: "<p>Welcome</p>" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => {
            expect(mocks.createDraft).toHaveBeenCalledWith({
                name: "New outreach",
                subject: "Hello there",
                from_email: null,
                body: "<p>Welcome</p>",
                scope: "org",
            })
        })
        expect(mocks.publishDraft).not.toHaveBeenCalled()
        expect(mocks.push).toHaveBeenCalledWith(
            "/automation/email-templates/org/draft-created",
        )
    })

    it("validates required fields before creating a draft", async () => {
        mocks.state.publishedTemplate = null

        render(<OrganizationEmailTemplateStudio />)
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        expect(await screen.findByText("Enter a template name.")).toBeInTheDocument()
        expect(screen.getByText("Enter a subject.")).toBeInTheDocument()
        expect(screen.getByText("Enter the email body.")).toBeInTheDocument()
        expect(screen.getByLabelText("Template name")).toHaveAttribute("aria-invalid", "true")
        expect(screen.getByLabelText("Subject")).toHaveAttribute("aria-invalid", "true")
        expect(mocks.createDraft).not.toHaveBeenCalled()

        fireEvent.change(screen.getByLabelText("Template name"), {
            target: { value: "New outreach" },
        })
        fireEvent.change(screen.getByLabelText("Subject"), {
            target: { value: "Hello there" },
        })
        fireEvent.change(screen.getByLabelText("Email body"), {
            target: { value: "<p>Welcome</p>" },
        })

        expect(screen.queryByText("Enter a template name.")).not.toBeInTheDocument()
        expect(screen.queryByText("Enter a subject.")).not.toBeInTheDocument()
        expect(screen.queryByText("Enter the email body.")).not.toBeInTheDocument()
        expect(screen.getByLabelText("Template name")).not.toHaveAttribute("aria-invalid")
    })

    it("offers a retryable terminal state when draft loading fails", async () => {
        mocks.state.publishedTemplate = null
        mocks.state.draftsError = true
        mocks.refetchDrafts.mockResolvedValue(undefined)

        render(<OrganizationEmailTemplateStudio />)

        expect(
            screen.getByRole("heading", {
                name: "Couldn't load template studio",
            }),
        ).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        await waitFor(() => expect(mocks.refetchDrafts).toHaveBeenCalledOnce())
    })
    it.each(["personal", "org"] as const)("denies direct %s studio creation without authoring permission", (scope) => {
        mocks.state.permissionPolicy = 2
        mocks.state.permissions = ["view_email_templates"]
        render(<OrganizationEmailTemplateStudio scope={scope} />)
        expect(screen.getByRole("heading", { level: 1, name: scope === "org" ? "Organization template" : "Personal template" })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to Email Templates" })).toHaveAttribute("href", "/automation/email-templates")
        expect(mocks.draftListParams).not.toHaveBeenCalled()
        expect(mocks.createDraft).not.toHaveBeenCalled()
    })

    it("requires organization management in the organization studio", () => {
        mocks.state.permissionPolicy = 2
        mocks.state.permissions = ["manage_email_templates"]
        render(<OrganizationEmailTemplateStudio scope="org" />)
        expect(screen.getByRole("heading", { level: 2, name: "Organization templates require template management access" })).toBeInTheDocument()
        expect(mocks.draftListParams).not.toHaveBeenCalled()
    })

    it("checks v1 organization template access before requesting drafts", () => {
        mocks.state.permissionPolicy = 1
        mocks.state.permissions = ["view_email_templates"]
        render(<OrganizationEmailTemplateStudio scope="org" />)
        expect(screen.getByRole("heading", { level: 1, name: "Organization template" })).toBeInTheDocument()
        expect(screen.getByRole("heading", { level: 2, name: "Organization templates require template management access" })).toBeInTheDocument()
        expect(mocks.draftListParams).not.toHaveBeenCalled()
    })

    it("opens the v1 personal studio without organization template access", () => {
        mocks.state.permissionPolicy = 1
        mocks.state.permissions = ["view_email_templates"]
        render(<OrganizationEmailTemplateStudio scope="personal" />)
        expect(mocks.draftListParams).toHaveBeenCalled()
    })

})
