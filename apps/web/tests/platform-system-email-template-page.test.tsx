import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import * as React from "react"
import PlatformSystemEmailTemplatePage from "../app/ops/templates/system/[systemKey]/page.client"

const mocks = vi.hoisted(() => ({
    push: vi.fn(),
    update: vi.fn(),
    updateBranding: vi.fn(),
    uploadLogo: vi.fn(),
    deleteTemplate: vi.fn(),
    sendTest: vi.fn(),
    sendCampaign: vi.fn(),
    toastSuccess: vi.fn(),
    toastError: vi.fn(),
    listOrganizations: vi.fn(),
    listMembers: vi.fn(),
    refetchTemplate: vi.fn(),
    richTextEditor: vi.fn(),
    state: {
        templateBody: "<table><tbody><tr><td>Hello {{org_name}}</td></tr></tbody></table>",
        templateQueryError: false,
        isBuiltin: true,
    },
}))

vi.mock("next/image", () => ({
    default: function MockImage({ alt, src }: { alt: string; src: string }) {
        return <div role="img" aria-label={alt} data-src={src} />
    },
}))

vi.mock("next/navigation", () => ({
    useParams: () => ({ systemKey: "org_invite" }),
    useRouter: () => ({
        push: mocks.push,
        replace: vi.fn(),
    }),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: {
        success: mocks.toastSuccess,
        error: mocks.toastError,
    },
}))

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: function MockRichTextEditor(props: unknown) {
        const { ref } = props as { ref?: React.Ref<{ insertText: () => void; insertHtml: () => void }> }
        mocks.richTextEditor(props)
        React.useImperativeHandle(ref, () => ({
            insertText: vi.fn(),
            insertHtml: vi.fn(),
        }))
        return <div data-testid="rich-text-editor" />
    },
}))

vi.mock("@/lib/api/platform", () => ({
    listOrganizations: mocks.listOrganizations,
    listMembers: mocks.listMembers,
}))

vi.mock("@/lib/hooks/use-platform-templates", () => ({
    usePlatformSystemEmailTemplate: () =>
        mocks.state.templateQueryError
            ? {
                  data: undefined,
                  error: new Error("sensitive backend failure detail"),
                  isError: true,
                  isFetching: false,
                  isLoading: false,
                  refetch: mocks.refetchTemplate,
              }
            : {
                  data: {
                      system_key: "org_invite",
                      name: "Organization Invite",
                      subject: "Invite {{org_name}}",
                      from_email: "Invites <welcome@surrogacyforce.com>",
                      body: mocks.state.templateBody,
                      is_active: true,
                      current_version: 7,
                      updated_at: new Date().toISOString(),
                      is_builtin: mocks.state.isBuiltin,
                  },
                  error: null,
                  isError: false,
                  isFetching: false,
                  isLoading: false,
                  refetch: mocks.refetchTemplate,
              },
    usePlatformSystemEmailTemplateVariables: () => ({
        data: [
            {
                name: "org_name",
                description: "Organization name",
                category: "Organization",
                required: true,
                value_type: "text",
                html_safe: false,
            },
        ],
        isLoading: false,
    }),
    usePlatformEmailBranding: () => ({
        data: { logo_url: "/platform/email/branding/logo/local/platform.png" },
    }),
    useUpdatePlatformSystemEmailTemplate: () => ({ mutateAsync: mocks.update }),
    useUpdatePlatformEmailBranding: () => ({ mutateAsync: mocks.updateBranding }),
    useUploadPlatformEmailBrandingLogo: () => ({
        mutateAsync: mocks.uploadLogo,
        isPending: false,
    }),
    useDeletePlatformSystemEmailTemplate: () => ({
        mutateAsync: mocks.deleteTemplate,
        isPending: false,
    }),
    useSendTestPlatformSystemEmailTemplate: () => ({ mutateAsync: mocks.sendTest }),
    useSendPlatformSystemEmailCampaign: () => ({ mutateAsync: mocks.sendCampaign }),
}))

async function openCampaignDialog() {
    fireEvent.click(screen.getByRole("button", { name: "More actions" }))
    fireEvent.click(await screen.findByRole("menuitem", { name: "Send campaign" }))
    return screen.findByRole("dialog")
}

async function confirmCampaignSend(dialog: HTMLElement) {
    fireEvent.click(within(dialog).getByRole("button", { name: "Send campaign" }))
    const confirm = await screen.findByRole("alertdialog")
    fireEvent.click(within(confirm).getByRole("button", { name: "Send campaign" }))
    return confirm
}

describe("PlatformSystemEmailTemplatePage", () => {
    beforeEach(() => {
        mocks.state.templateBody = "<table><tbody><tr><td>Hello {{org_name}}</td></tr></tbody></table>"
        mocks.state.templateQueryError = false
        mocks.state.isBuiltin = true
        mocks.push.mockReset()
        mocks.update.mockReset()
        mocks.updateBranding.mockReset()
        mocks.uploadLogo.mockReset()
        mocks.deleteTemplate.mockReset()
        mocks.sendTest.mockReset()
        mocks.sendCampaign.mockReset()
        mocks.toastSuccess.mockReset()
        mocks.toastError.mockReset()
        mocks.listOrganizations.mockReset()
        mocks.listMembers.mockReset()
        mocks.refetchTemplate.mockReset()
        mocks.richTextEditor.mockClear()
        mocks.refetchTemplate.mockResolvedValue(undefined)
        mocks.listOrganizations.mockResolvedValue({
            items: [
                {
                    id: "org-1",
                    name: "Acme Surrogacy",
                    slug: "acme",
                    subscription_plan: "professional",
                },
            ],
        })
    })

    it("renders loaded template and branding data without waiting for synchronization effects", async () => {
        render(<PlatformSystemEmailTemplatePage />)

        expect(screen.getByLabelText("From (required for Resend)")).toHaveValue(
            "Invites <welcome@surrogacyforce.com>"
        )
        expect(screen.getByLabelText("Subject")).toHaveValue("Invite {{org_name}}")
        expect(screen.getByRole("img", { name: "Platform logo" })).toHaveAttribute(
            "data-src",
            "/platform/email/branding/logo/local/platform.png"
        )
        expect(await screen.findByPlaceholderText("Paste or edit the HTML for this template...")).toHaveValue(
            mocks.state.templateBody
        )
    })

    it("shows a retryable terminal state when system template loading fails", () => {
        mocks.state.templateQueryError = true

        render(<PlatformSystemEmailTemplatePage />)

        expect(screen.getByText("Unable to load system template")).toBeInTheDocument()
        expect(screen.queryByText("sensitive backend failure detail")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(mocks.refetchTemplate).toHaveBeenCalledOnce()
    })

    it("reenables save after an update failure and sends the latest draft with version guard", async () => {
        mocks.update.mockRejectedValueOnce(new Error("Version conflict"))

        render(<PlatformSystemEmailTemplatePage />)

        fireEvent.change(screen.getByLabelText("Subject"), {
            target: { value: "Updated invite {{org_name}}" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save" }))

        await waitFor(() =>
            expect(mocks.update).toHaveBeenCalledWith({
                systemKey: "org_invite",
                payload: expect.objectContaining({
                    subject: "Updated invite {{org_name}}",
                    expected_version: 7,
                }),
            })
        )
        await waitFor(() => expect(screen.getByRole("button", { name: "Save" })).toBeEnabled())
        expect(screen.getByText("Not saved")).toBeInTheDocument()
        expect(mocks.toastError).toHaveBeenCalledWith("Couldn't save template.")
        expect(mocks.toastError).not.toHaveBeenCalledWith("Version conflict")
    })

    it("lists organizations with plan labels in the campaign dialog", async () => {
        render(<PlatformSystemEmailTemplatePage />)

        await waitFor(() => expect(mocks.listOrganizations).toHaveBeenCalledWith({ limit: 200 }))
        const dialog = await openCampaignDialog()
        expect(await within(dialog).findByText("Acme Surrogacy")).toBeInTheDocument()
        expect(within(dialog).getByText("Professional")).toBeInTheDocument()
        expect(within(dialog).queryByText("professional")).not.toBeInTheDocument()
    })

    it("keeps Send campaign disabled until a recipient is selected", async () => {
        mocks.listMembers.mockResolvedValue([
            {
                id: "member-1",
                user_id: "user-active",
                email: "active@example.com",
                display_name: "Active Member",
                role: "admin",
                is_active: true,
                created_at: "2026-01-01T00:00:00Z",
            },
        ])
        render(<PlatformSystemEmailTemplatePage />)

        const dialog = await openCampaignDialog()
        await within(dialog).findByText("Acme Surrogacy")
        const send = within(dialog).getByRole("button", { name: "Send campaign" })
        expect(send).toBeDisabled()
        expect(within(dialog).getByText("0 recipients selected")).toBeInTheDocument()

        fireEvent.click(within(dialog).getByText("Acme Surrogacy"))
        await within(dialog).findByText("Active Member")
        await waitFor(() => expect(send).toBeEnabled())

        fireEvent.click(send)
        const confirm = await screen.findByRole("alertdialog")
        expect(within(confirm).getByText("Send to 1 organization?")).toBeInTheDocument()
        expect(within(confirm).getByText("Organization Invite is sent to 1 recipient.")).toBeInTheDocument()
        expect(mocks.sendCampaign).not.toHaveBeenCalled()
    })

    it("offers Reset to default instead of Delete for a built-in template", async () => {
        mocks.deleteTemplate.mockResolvedValue(undefined)
        render(<PlatformSystemEmailTemplatePage />)

        fireEvent.click(screen.getByRole("button", { name: "More actions" }))
        expect(await screen.findByRole("menuitem", { name: "Reset to default" })).toBeInTheDocument()
        expect(screen.queryByRole("menuitem", { name: "Delete" })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("menuitem", { name: "Reset to default" }))
        const confirm = await screen.findByRole("alertdialog")
        expect(within(confirm).getByText("Reset Organization Invite to default?")).toBeInTheDocument()
        const resetButton = within(confirm).getByRole("button", { name: "Reset to default" })
        expect(resetButton).not.toHaveClass("bg-destructive")

        fireEvent.click(resetButton)
        await waitFor(() => expect(mocks.deleteTemplate).toHaveBeenCalledWith({ systemKey: "org_invite" }))
        expect(mocks.toastSuccess).toHaveBeenCalledWith("System template reset to default")
        expect(mocks.push).not.toHaveBeenCalled()
        expect(mocks.refetchTemplate).toHaveBeenCalled()
    })

    it("shows Delete with a destructive confirm for a custom template", async () => {
        mocks.state.isBuiltin = false
        mocks.deleteTemplate.mockResolvedValue(undefined)
        render(<PlatformSystemEmailTemplatePage />)

        fireEvent.click(screen.getByRole("button", { name: "More actions" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Delete" }))
        const confirm = await screen.findByRole("alertdialog")
        const deleteButton = within(confirm).getByRole("button", { name: "Delete" })
        expect(deleteButton).toHaveClass("bg-destructive")

        fireEvent.click(deleteButton)
        await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/ops/templates?tab=system"))
    })

    it("shows a preview placeholder when the body is empty", () => {
        mocks.state.templateBody = ""
        render(<PlatformSystemEmailTemplatePage />)

        expect(screen.getByRole("heading", { name: "No content yet" })).toBeInTheDocument()
    })

    it("sends campaign to selected active organization members", async () => {
        mocks.listMembers.mockResolvedValue([
            {
                id: "member-1",
                user_id: "user-active",
                email: "active@example.com",
                display_name: "Active Member",
                role: "admin",
                is_active: true,
                created_at: "2026-01-01T00:00:00Z",
            },
            {
                id: "member-2",
                user_id: "user-inactive",
                email: "inactive@example.com",
                display_name: "Inactive Member",
                role: "viewer",
                is_active: false,
                created_at: "2026-01-01T00:00:00Z",
            },
        ])
        mocks.sendCampaign.mockResolvedValue({ queued: 1, suppressed: 0, failed: 0 })

        render(<PlatformSystemEmailTemplatePage />)

        const dialog = await openCampaignDialog()
        await within(dialog).findByText("Acme Surrogacy")
        fireEvent.click(within(dialog).getByText("Acme Surrogacy"))

        await waitFor(() => expect(mocks.listMembers).toHaveBeenCalledWith("org-1"))
        expect(await screen.findByText("Active Member")).toBeInTheDocument()
        expect(screen.getByText("Inactive Member")).toBeInTheDocument()

        await confirmCampaignSend(dialog)

        await waitFor(() =>
            expect(mocks.sendCampaign).toHaveBeenCalledWith({
                systemKey: "org_invite",
                payload: {
                    campaign_occurrence_id: expect.stringMatching(
                        /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
                    ),
                    targets: [{ org_id: "org-1", user_ids: ["user-active"] }],
                },
            })
        )
        expect(mocks.toastSuccess).toHaveBeenCalledWith(
            "Campaign queued: 1 queued, 0 suppressed, 0 failed"
        )
    })

    it("keeps a partially queued campaign open with a safe retry summary", async () => {
        mocks.listMembers.mockResolvedValue([
            {
                id: "member-1",
                user_id: "user-active",
                email: "active@example.com",
                display_name: "Active Member",
                role: "admin",
                is_active: true,
                created_at: "2026-01-01T00:00:00Z",
            },
        ])
        mocks.sendCampaign
            .mockResolvedValueOnce({
                queued: 0,
                suppressed: 0,
                failed: 1,
                recipients: 1,
                failures: [
                    {
                        org_id: "org-1",
                        user_id: "user-active",
                        error: "raw provider failure detail",
                    },
                ],
            })
            .mockResolvedValueOnce({
                queued: 1,
                suppressed: 0,
                failed: 0,
                recipients: 1,
                failures: [],
            })

        render(<PlatformSystemEmailTemplatePage />)

        const dialog = await openCampaignDialog()
        await within(dialog).findByText("Acme Surrogacy")
        fireEvent.click(within(dialog).getByText("Acme Surrogacy"))
        await screen.findByText("Active Member")

        await confirmCampaignSend(dialog)

        await waitFor(() => expect(mocks.sendCampaign).toHaveBeenCalledTimes(1))
        await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument())
        expect(screen.getByRole("dialog")).toBeInTheDocument()
        expect(within(dialog).getByRole("alert")).toHaveAttribute("data-slot", "alert")
        expect(within(dialog).getByText("Campaign needs attention")).toBeInTheDocument()
        expect(
            within(dialog).getByText(
                "1 recipient could not be queued. Review the selected recipients, then retry this campaign."
            )
        ).toBeInTheDocument()
        expect(within(dialog).queryByText("raw provider failure detail")).not.toBeInTheDocument()
        expect(mocks.toastError).toHaveBeenCalledWith(
            "Campaign partially queued. Review the selected recipients and retry."
        )
        expect(mocks.toastSuccess).not.toHaveBeenCalled()

        await confirmCampaignSend(dialog)
        await waitFor(() => expect(mocks.sendCampaign).toHaveBeenCalledTimes(2))

        const firstOccurrenceId =
            mocks.sendCampaign.mock.calls[0][0].payload.campaign_occurrence_id
        const retriedOccurrenceId =
            mocks.sendCampaign.mock.calls[1][0].payload.campaign_occurrence_id
        expect(retriedOccurrenceId).toBe(firstOccurrenceId)
    })

    it("reuses one campaign occurrence after an error and creates a new one after reopening", async () => {
        mocks.listMembers.mockResolvedValue([
            {
                id: "member-1",
                user_id: "user-active",
                email: "active@example.com",
                display_name: "Active Member",
                role: "admin",
                is_active: true,
                created_at: "2026-01-01T00:00:00Z",
            },
        ])
        mocks.sendCampaign
            .mockRejectedValueOnce(new Error("Temporary failure"))
            .mockResolvedValue({ queued: 1, suppressed: 0, failed: 0 })

        render(<PlatformSystemEmailTemplatePage />)

        let dialog = await openCampaignDialog()
        await within(dialog).findByText("Acme Surrogacy")
        fireEvent.click(within(dialog).getByText("Acme Surrogacy"))
        await screen.findByText("Active Member")

        await confirmCampaignSend(dialog)
        await waitFor(() => expect(mocks.sendCampaign).toHaveBeenCalledTimes(1))
        await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument())
        expect(mocks.toastError).toHaveBeenCalledWith("Couldn't send campaign.")

        await confirmCampaignSend(dialog)
        await waitFor(() => expect(mocks.sendCampaign).toHaveBeenCalledTimes(2))
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())

        const firstOccurrenceId =
            mocks.sendCampaign.mock.calls[0][0].payload.campaign_occurrence_id
        const retriedOccurrenceId =
            mocks.sendCampaign.mock.calls[1][0].payload.campaign_occurrence_id
        expect(retriedOccurrenceId).toBe(firstOccurrenceId)

        dialog = await openCampaignDialog()
        await within(dialog).findAllByText("Acme Surrogacy")
        await confirmCampaignSend(dialog)
        await waitFor(() => expect(mocks.sendCampaign).toHaveBeenCalledTimes(3))

        const nextOccurrenceId =
            mocks.sendCampaign.mock.calls[2][0].payload.campaign_occurrence_id
        expect(nextOccurrenceId).not.toBe(firstOccurrenceId)
    })

    it("reuses a test-send occurrence after failure and reports durable queue acceptance", async () => {
        mocks.sendTest
            .mockRejectedValueOnce(new Error("Send failed"))
            .mockResolvedValueOnce({
                queued: true,
                message_id: null,
                email_log_id: "log-1",
            })

        render(<PlatformSystemEmailTemplatePage />)

        // The only agency is selected by default, so no raw organization id is typed.
        expect(screen.queryByLabelText("Organization ID")).not.toBeInTheDocument()
        await waitFor(() => expect(screen.getByLabelText("Agency")).toHaveTextContent("Acme Surrogacy"))
        fireEvent.change(screen.getByLabelText("Test email"), {
            target: { value: "qa@example.com" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Send test" }))

        await waitFor(() =>
            expect(mocks.sendTest).toHaveBeenCalledWith({
                systemKey: "org_invite",
                payload: {
                    to_email: "qa@example.com",
                    org_id: "org-1",
                    idempotency_key: expect.any(String),
                },
            })
        )
        expect(screen.getByRole("button", { name: "Send test" })).toBeEnabled()

        fireEvent.click(screen.getByRole("button", { name: "Send test" }))
        await waitFor(() => expect(mocks.sendTest).toHaveBeenCalledTimes(2))

        const firstOccurrenceId =
            mocks.sendTest.mock.calls[0][0].payload.idempotency_key
        const retriedOccurrenceId =
            mocks.sendTest.mock.calls[1][0].payload.idempotency_key
        expect(retriedOccurrenceId).toBe(firstOccurrenceId)
        expect(mocks.toastSuccess).toHaveBeenCalledWith("Test email queued")
    })

    it("requires an agency pick when several agencies exist", async () => {
        mocks.listOrganizations.mockResolvedValue({
            items: [
                { id: "org-1", name: "Acme Surrogacy", slug: "acme", subscription_plan: "starter" },
                { id: "org-2", name: "Beta Family", slug: "beta", subscription_plan: "starter" },
            ],
        })
        mocks.sendTest.mockResolvedValue({ queued: true, message_id: null, email_log_id: "log-1" })

        render(<PlatformSystemEmailTemplatePage />)

        const agency = screen.getByLabelText("Agency")
        await waitFor(() => expect(agency).toBeEnabled())
        expect(agency).toHaveTextContent("Select agency")

        fireEvent.click(screen.getByRole("button", { name: "Send test" }))
        expect(await screen.findByText("Select an agency.")).toBeInTheDocument()
        expect(screen.getByText("Enter a test email.")).toBeInTheDocument()
        expect(agency).toHaveAttribute("aria-invalid", "true")
        expect(mocks.sendTest).not.toHaveBeenCalled()

        fireEvent.click(agency)
        const beta = await screen.findByRole("option", { name: /Beta Family/ })
        fireEvent.mouseMove(beta)
        fireEvent.click(beta)
        await waitFor(() => expect(agency).toHaveTextContent("Beta Family"))
        expect(agency).not.toHaveTextContent("org-2")

        fireEvent.change(screen.getByLabelText("Test email"), { target: { value: "qa@example.com" } })
        fireEvent.click(screen.getByRole("button", { name: "Send test" }))
        await waitFor(() =>
            expect(mocks.sendTest).toHaveBeenCalledWith({
                systemKey: "org_invite",
                payload: expect.objectContaining({ org_id: "org-2", to_email: "qa@example.com" }),
            })
        )
    })

    it("labels the platform branding logo upload control", () => {
        render(<PlatformSystemEmailTemplatePage />)

        expect(screen.getByLabelText("Platform branding logo upload")).toHaveAttribute(
            "accept",
            "image/png,image/jpeg"
        )
    })
})
