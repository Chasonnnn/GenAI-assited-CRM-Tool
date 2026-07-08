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
    listOrganizations: vi.fn(),
    listMembers: vi.fn(),
    richTextEditor: vi.fn(),
    state: {
        templateBody: "<table><tbody><tr><td>Hello {{org_name}}</td></tr></tbody></table>",
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

vi.mock("sonner", () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
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
    usePlatformSystemEmailTemplate: () => ({
        data: {
            system_key: "org_invite",
            name: "Organization Invite",
            subject: "Invite {{org_name}}",
            from_email: "Invites <welcome@surrogacyforce.com>",
            body: mocks.state.templateBody,
            is_active: true,
            current_version: 7,
            updated_at: new Date().toISOString(),
        },
        isLoading: false,
    }),
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

describe("PlatformSystemEmailTemplatePage", () => {
    beforeEach(() => {
        mocks.state.templateBody = "<table><tbody><tr><td>Hello {{org_name}}</td></tr></tbody></table>"
        mocks.push.mockReset()
        mocks.update.mockReset()
        mocks.updateBranding.mockReset()
        mocks.uploadLogo.mockReset()
        mocks.deleteTemplate.mockReset()
        mocks.sendTest.mockReset()
        mocks.sendCampaign.mockReset()
        mocks.listOrganizations.mockReset()
        mocks.listMembers.mockReset()
        mocks.richTextEditor.mockClear()
        mocks.listOrganizations.mockResolvedValue({
            items: [
                {
                    id: "org-1",
                    name: "Acme Surrogacy",
                    slug: "acme",
                    subscription_plan: "Pro",
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

    it("reenables save after an update failure and sends the latest draft with version guard", async () => {
        mocks.update.mockRejectedValueOnce(new Error("Version conflict"))

        render(<PlatformSystemEmailTemplatePage />)

        fireEvent.change(screen.getByLabelText("Subject"), {
            target: { value: "Updated invite {{org_name}}" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save changes" }))

        await waitFor(() =>
            expect(mocks.update).toHaveBeenCalledWith({
                systemKey: "org_invite",
                payload: expect.objectContaining({
                    subject: "Updated invite {{org_name}}",
                    expected_version: 7,
                }),
            })
        )
        expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled()
    })

    it("loads organizations when the campaign dialog opens", async () => {
        render(<PlatformSystemEmailTemplatePage />)

        fireEvent.click(screen.getByRole("button", { name: "Send campaign" }))

        await waitFor(() => expect(mocks.listOrganizations).toHaveBeenCalledWith({ limit: 200 }))
        expect(await screen.findByText("Acme Surrogacy")).toBeInTheDocument()
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
        mocks.sendCampaign.mockResolvedValue({ sent: 1, suppressed: 0, failed: 0 })

        render(<PlatformSystemEmailTemplatePage />)

        fireEvent.click(screen.getByRole("button", { name: "Send campaign" }))
        await screen.findByText("Acme Surrogacy")
        fireEvent.click(screen.getByText("Acme Surrogacy"))

        await waitFor(() => expect(mocks.listMembers).toHaveBeenCalledWith("org-1"))
        expect(await screen.findByText("Active Member")).toBeInTheDocument()
        expect(screen.getByText("Inactive Member")).toBeInTheDocument()

        const dialog = screen.getByRole("dialog")
        fireEvent.click(within(dialog).getByRole("button", { name: "Send campaign" }))

        await waitFor(() =>
            expect(mocks.sendCampaign).toHaveBeenCalledWith({
                systemKey: "org_invite",
                payload: {
                    targets: [{ org_id: "org-1", user_ids: ["user-active"] }],
                },
            })
        )
    })

    it("reenables test send after a failure", async () => {
        mocks.sendTest.mockRejectedValueOnce(new Error("Send failed"))

        render(<PlatformSystemEmailTemplatePage />)

        fireEvent.change(screen.getByLabelText("Organization ID"), {
            target: { value: "org-1" },
        })
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
                },
            })
        )
        expect(screen.getByRole("button", { name: "Send test" })).toBeEnabled()
    })

    it("labels the platform branding logo upload control", () => {
        render(<PlatformSystemEmailTemplatePage />)

        expect(screen.getByLabelText("Platform branding logo upload")).toHaveAttribute(
            "accept",
            "image/png,image/jpeg"
        )
    })
})
