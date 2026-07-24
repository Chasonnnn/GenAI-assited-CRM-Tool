import * as React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import OrganizationEmailTemplateStudio from "@/components/email/organization-email-template-studio"
import { ApiError } from "@/lib/api"

const mocks = vi.hoisted(() => ({
    push: vi.fn(),
    replace: vi.fn(),
    createDraft: vi.fn(),
    createDraftFromTemplate: vi.fn(),
    updateDraft: vi.fn(),
    discardDraft: vi.fn(),
    publishDraft: vi.fn(),
    sendTestDraft: vi.fn(),
    richTextEditor: vi.fn(),
    refetchDrafts: vi.fn(),
    refetchPublished: vi.fn(),
    refetchDraft: vi.fn(),
    state: {
        publishedTemplate: null as Record<string, unknown> | null,
        draft: null as Record<string, unknown> | null,
        publishedLookupErrorId: null as string | null,
        draftsLoading: false,
        draftsError: false,
    },
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
}))

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: ({
        content,
        onChange,
        ariaLabel,
    }: {
        content?: string
        onChange?: (value: string) => void
        ariaLabel?: string
    }) => (
        <>
            {mocks.richTextEditor({ content, onChange, ariaLabel })}
            <textarea
                aria-label={ariaLabel ?? "Email body"}
                value={content ?? ""}
                onChange={(event) => onChange?.(event.target.value)}
            />
        </>
    ),
}))

vi.mock("@/components/email/TemplateVariablePicker", () => ({
    TemplateVariablePicker: ({
        onSelect,
    }: {
        onSelect: (variable: {
            name: string
            description: string
            category: string
            required: boolean
            value_type: "text"
            html_safe: boolean
        }) => void
    }) => (
        <button
            type="button"
            onClick={() =>
                onSelect({
                    name: "first_name",
                    description: "Recipient first name",
                    category: "Recipient",
                    required: false,
                    value_type: "text",
                    html_safe: false,
                })
            }
        >
            Insert variable
        </button>
    ),
}))

vi.mock("@/lib/hooks/use-email-templates", () => ({
    useEmailTemplate: (id: string | null) => ({
        data: mocks.state.publishedTemplate,
        isLoading: false,
        isError:
            Boolean(id) && id === mocks.state.publishedLookupErrorId,
        refetch: mocks.refetchPublished,
    }),
    useEmailTemplateVariables: () => ({ data: [], isLoading: false }),
}))

vi.mock("@/lib/hooks/use-signature", () => ({
    useOrgSignaturePreview: () => ({
        data: { html: "<div><strong>Agency signature</strong></div>" },
        isLoading: false,
    }),
}))

vi.mock("@/lib/hooks/use-email-template-drafts", () => ({
    useEmailTemplateDrafts: () => ({
        data: mocks.state.draft ? [mocks.state.draft] : [],
        isLoading: mocks.state.draftsLoading,
        isError: mocks.state.draftsError,
        refetch: mocks.refetchDrafts,
    }),
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
    beforeEach(() => {
        mocks.push.mockReset()
        mocks.replace.mockReset()
        mocks.createDraft.mockReset()
        mocks.createDraftFromTemplate.mockReset()
        mocks.updateDraft.mockReset()
        mocks.discardDraft.mockReset()
        mocks.publishDraft.mockReset()
        mocks.sendTestDraft.mockReset()
        mocks.richTextEditor.mockReset()
        mocks.refetchDrafts.mockReset()
        mocks.refetchPublished.mockReset()
        mocks.refetchDraft.mockReset()
        mocks.state.publishedTemplate = publishedTemplate
        mocks.state.draft = null
        mocks.state.publishedLookupErrorId = null
        mocks.state.draftsLoading = false
        mocks.state.draftsError = false

        mocks.createDraftFromTemplate.mockResolvedValue(draftFromPublished)
        mocks.updateDraft.mockResolvedValue({
            ...draftFromPublished,
            subject: "A safer subject",
            revision: 2,
        })
    })

    it("shows the canonical published version before a draft exists", () => {
        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        expect(screen.getByText("No draft")).toBeInTheDocument()
        expect(screen.getByText("Published version 7")).toBeInTheDocument()
        expect(screen.getByText("Save draft to test")).toBeInTheDocument()
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

        fireEvent.click(screen.getByRole("button", { name: "Keep editing" }))
        expect(mocks.push).not.toHaveBeenCalled()

        fireEvent.click(
            screen.getByRole("button", { name: "Back to email templates" }),
        )
        fireEvent.click(screen.getByRole("button", { name: "Leave without saving" }))

        expect(mocks.push).toHaveBeenCalledWith("/automation/email-templates")
    })

    it("shows a sanitized live preview with the organization signature and managed footer", () => {
        mocks.state.draft = {
            ...draftFromPublished,
            subject: "Hello {{first_name}}",
            body: "<p>Welcome {{first_name}}</p><script>window.bad = true</script>",
        }

        const { container } = render(
            <OrganizationEmailTemplateStudio templateId="template-1" />,
        )

        expect(
            screen.getByRole("heading", { name: "Live preview" }),
        ).toBeInTheDocument()
        expect(screen.getByText("Hello John")).toBeInTheDocument()
        expect(screen.getByText("Welcome John")).toBeInTheDocument()
        expect(screen.getByText("Agency signature")).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Unsubscribe" })).toBeInTheDocument()
        expect(container.querySelector("script")).toBeNull()
    })

    it("keeps advanced legacy HTML in source mode without mounting it in the rich editor", () => {
        mocks.state.draft = draftFromPublished

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        expect(screen.getByLabelText("Email HTML")).toHaveValue(
            publishedTemplate.body,
        )
        expect(mocks.richTextEditor).not.toHaveBeenCalled()
        expect(
            screen.getByText(
                "Source mode protects tables, images, and email-client layout.",
            ),
        ).toBeInTheDocument()
    })

    it("opens simple stored HTML in the visual editor without marking it changed", () => {
        mocks.state.draft = {
            ...draftFromPublished,
            body: "<p style=\"margin:0\">Simple legacy HTML</p>",
        }

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        expect(screen.getByLabelText("Email body")).toHaveValue(
            "<p style=\"margin:0\">Simple legacy HTML</p>",
        )
        expect(mocks.richTextEditor).toHaveBeenCalledWith(
            expect.objectContaining({
                content: "<p style=\"margin:0\">Simple legacy HTML</p>",
            }),
        )
        expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled()
    })

    it("inserts a variable into the field being edited", () => {
        mocks.state.draft = {
            ...draftFromPublished,
            body: "<p>Hello</p>",
        }

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        const subject = screen.getByLabelText("Subject")
        fireEvent.focus(subject)
        fireEvent.click(screen.getByRole("button", { name: "Insert variable" }))

        expect(subject).toHaveValue("Original subject{{first_name}}")
    })

    it("reuses one test occurrence across retries and marks the current revision tested", async () => {
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
                tested_revision: 1,
            })

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)

        expect(screen.getByText("Test required")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Send test" }))
        fireEvent.change(screen.getByLabelText("Test recipient"), {
            target: { value: "qa@example.com" },
        })
        fireEvent.change(screen.getByLabelText("Test value for first_name"), {
            target: { value: "Taylor" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Send test email" }))

        expect(
            await screen.findByText("Test email failed. Your draft was not changed."),
        ).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Send test email" }))

        await waitFor(() => expect(mocks.sendTestDraft).toHaveBeenCalledTimes(2))
        const firstCall = mocks.sendTestDraft.mock.calls[0][0]
        const secondCall = mocks.sendTestDraft.mock.calls[1][0]
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
        expect(await screen.findByText("Tested current draft")).toBeInTheDocument()
    })

    it("uses the server-confirmed tested revision instead of assuming the current draft", async () => {
        mocks.state.draft = draftFromPublished
        mocks.sendTestDraft.mockResolvedValue({
            success: true,
            queued: true,
            provider_used: "resend",
            tested_revision: 0,
        })

        render(<OrganizationEmailTemplateStudio templateId="template-1" />)
        fireEvent.click(screen.getByRole("button", { name: "Send test" }))
        fireEvent.change(screen.getByLabelText("Test recipient"), {
            target: { value: "qa@example.com" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Send test email" }))

        await waitFor(() => expect(mocks.sendTestDraft).toHaveBeenCalledOnce())
        expect(screen.getByText("Test required")).toBeInTheDocument()
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
            screen.getByRole("heading", { name: "New email template" }),
        ).toBeInTheDocument()
        expect(
            screen.queryByRole("heading", {
                name: "Unable to load template studio",
            }),
        ).not.toBeInTheDocument()
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

        expect(
            await screen.findByText("Name, subject, and email body are required."),
        ).toBeInTheDocument()
        expect(mocks.createDraft).not.toHaveBeenCalled()
    })

    it("offers a retryable terminal state when draft loading fails", async () => {
        mocks.state.publishedTemplate = null
        mocks.state.draftsError = true
        mocks.refetchDrafts.mockResolvedValue(undefined)

        render(<OrganizationEmailTemplateStudio />)

        expect(
            screen.getByRole("heading", {
                name: "Unable to load template studio",
            }),
        ).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        await waitFor(() => expect(mocks.refetchDrafts).toHaveBeenCalledOnce())
    })
})
