import { beforeEach, describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import PlatformEmailTemplatePage from "../app/ops/templates/email/[id]/page.client"
import { emailDesignEditorMock } from "./fixtures/email-design-editor-mock"

const mocks = vi.hoisted(() => ({
    preview: vi.fn(),
    updateTemplate: vi.fn(),
    publishTemplate: vi.fn(),
    deleteTemplate: vi.fn(),
    sendTest: vi.fn(),
    refetchTemplate: vi.fn(),
    listOrganizations: vi.fn(),
    push: vi.fn(),
    toastSuccess: vi.fn(),
    toastError: vi.fn(),
    state: {
        templateQueryError: false,
    },
}))

vi.mock("@/components/app-link", () => ({
    default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: {
        success: mocks.toastSuccess,
        error: mocks.toastError,
        info: vi.fn(),
    },
}))

vi.mock("@/lib/api/platform", () => ({
    listOrganizations: mocks.listOrganizations,
    previewPlatformEmailTemplate: mocks.preview,
}))

vi.mock("@/components/email/design/email-design-editor", () => import("./fixtures/email-design-editor-mock"))

vi.mock("@/components/ops/templates/PublishDialog", () => ({
    PublishDialog: ({ onPublish }: { onPublish: (publishAll: boolean, orgIds: string[]) => void }) => (
        <button onClick={() => onPublish(true, [])}>Confirm email publish</button>
    ),
}))

const templateBodyWithTable =
    "<table><tr><td>Hi</td></tr></table><p>Extra</p>"

const mockTemplateData = {
    id: "tpl_1",
    status: "draft",
    current_version: 2,
    published_version: 0,
    is_published_globally: true,
    draft: {
        name: "Missed Appointment",
        subject: "We missed you",
        body: templateBodyWithTable,
        from_email: null,
        category: null,
    },
    updated_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
}

let mockParamsId = "tpl_1"

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: mockParamsId }),
    useRouter: () => ({
        push: mocks.push,
        replace: vi.fn(),
    }),
}))

vi.mock("@/lib/hooks/use-platform-templates", () => ({
    usePlatformEmailTemplate: () =>
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
                  data: mockTemplateData,
                  error: null,
                  isError: false,
                  isFetching: false,
                  isLoading: false,
                  refetch: mocks.refetchTemplate,
              },
    usePlatformEmailTemplateVariables: () => ({ data: [], isLoading: false }),
    useCreatePlatformEmailTemplate: () => ({ mutateAsync: vi.fn() }),
    useUpdatePlatformEmailTemplate: () => ({ mutateAsync: mocks.updateTemplate }),
    usePublishPlatformEmailTemplate: () => ({ mutateAsync: mocks.publishTemplate }),
    useDeletePlatformEmailTemplate: () => ({ mutateAsync: mocks.deleteTemplate, isPending: false }),
    useSendTestPlatformEmailTemplate: () => ({ mutateAsync: mocks.sendTest }),
}))

function requiredAt<T>(items: readonly T[], index: number): T {
    const item = items[index]
    if (item === undefined) throw new Error(`Expected item at index ${index}`)
    return item
}

describe("PlatformEmailTemplatePage", () => {
    beforeEach(() => {
        mockParamsId = "tpl_1"
        emailDesignEditorMock.reset()
        mocks.preview.mockReset()
        mocks.updateTemplate.mockReset()
        mocks.publishTemplate.mockReset()
        mocks.deleteTemplate.mockReset()
        mocks.sendTest.mockReset()
        mocks.refetchTemplate.mockReset()
        mocks.listOrganizations.mockReset()
        mocks.push.mockReset()
        mocks.toastSuccess.mockReset()
        mocks.toastError.mockReset()
        mocks.state.templateQueryError = false
        mocks.updateTemplate.mockResolvedValue(mockTemplateData)
        mocks.publishTemplate.mockResolvedValue(mockTemplateData)
        mocks.deleteTemplate.mockResolvedValue(undefined)
        mocks.sendTest.mockResolvedValue({ queued: true, provider_used: "resend" })
        mocks.refetchTemplate.mockResolvedValue(undefined)
        mocks.listOrganizations.mockResolvedValue({
            items: [{ id: "org-1", name: "Acme Surrogacy", slug: "acme", deleted_at: null }],
        })
    })

    it("opens a legacy HTML body as is and saves it without a design", async () => {
        render(<PlatformEmailTemplatePage />)

        expect(emailDesignEditorMock.render).toHaveBeenCalledWith(
            expect.objectContaining({
                initialValue: { body: templateBodyWithTable, bodyDesign: null },
            }),
        )
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() =>
            expect(mocks.updateTemplate).toHaveBeenCalledWith({
                id: "tpl_1",
                payload: expect.objectContaining({ body: templateBodyWithTable, body_design: null }),
            }),
        )
    })

    it("saves the compiled body and its design together", async () => {
        const design = { type: "doc" as const, content: [{ type: "paragraph" }] }
        emailDesignEditorMock.nextDesign = design
        render(<PlatformEmailTemplatePage />)

        fireEvent.change(screen.getByLabelText("Email body"), { target: { value: "<p>Designed</p>" } })
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() =>
            expect(mocks.updateTemplate).toHaveBeenCalledWith({
                id: "tpl_1",
                payload: expect.objectContaining({ body: "<p>Designed</p>", body_design: design }),
            }),
        )
    })

    it("inserts the organization logo as an image block", () => {
        render(<PlatformEmailTemplatePage />)

        fireEvent.click(screen.getByRole("button", { name: "Insert logo" }))

        expect(emailDesignEditorMock.insertImage).toHaveBeenCalledWith(
            "{{org_logo_url}}",
            "{{org_name}} logo",
        )
    })

    it("previews through the platform endpoint for the test agency", async () => {
        mocks.preview.mockResolvedValue({
            subject: "Welcome",
            html: "<!doctype html><html><body><p>Hi</p></body></html>",
            unresolved_variables: [],
        })
        render(
            <QueryClientProvider client={new QueryClient()}>
                <PlatformEmailTemplatePage />
            </QueryClientProvider>,
        )

        fireEvent.click(screen.getByRole("tab", { name: "Preview" }))

        await waitFor(() =>
            expect(mocks.preview).toHaveBeenCalledWith({
                subject: mockTemplateData.draft.subject,
                body: templateBodyWithTable,
                variable_mode: "sample",
                org_id: "org-1",
            }),
        )
        expect(screen.queryByRole("button", { name: "Record" })).not.toBeInTheDocument()
        expect(await screen.findByTitle("Desktop email preview")).toBeInTheDocument()
    })

    it("renders send test email card", () => {
        mockParamsId = "tpl_1"
        render(<PlatformEmailTemplatePage />)
        expect(screen.getByText("Send test email")).toBeInTheDocument()
    })

    it("shows a retryable terminal state when template loading fails", () => {
        mocks.state.templateQueryError = true
        mockParamsId = "tpl_1"

        render(<PlatformEmailTemplatePage />)

        expect(screen.getByText("Unable to load email template")).toBeInTheDocument()
        expect(screen.queryByText("sensitive backend failure detail")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(mocks.refetchTemplate).toHaveBeenCalledOnce()
    })

    it("disables send test on new templates", () => {
        mockParamsId = "new"
        render(<PlatformEmailTemplatePage />)
        expect(screen.getByRole("button", { name: "Send test" })).toBeDisabled()
        expect(screen.getByText("Save template first.")).toBeInTheDocument()
    })

    it("uses a retry-stable occurrence for test sends", async () => {
        mocks.sendTest
            .mockRejectedValueOnce(new Error("Temporary failure"))
            .mockResolvedValueOnce({ queued: true, provider_used: "resend" })

        mockParamsId = "tpl_1"
        render(<PlatformEmailTemplatePage />)

        // The only agency is selected by default.
        await waitFor(() => expect(screen.getByLabelText("Agency")).toHaveTextContent("Acme Surrogacy"))
        fireEvent.change(screen.getByLabelText("Test email"), {
            target: { value: "qa@example.com" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Send test" }))

        await waitFor(() => expect(mocks.sendTest).toHaveBeenCalledTimes(1))
        expect(requiredAt(mocks.sendTest.mock.calls, 0)[0].payload).toMatchObject({
            org_id: "org-1",
            to_email: "qa@example.com",
        })
        expect(mocks.toastError).toHaveBeenCalledWith("Couldn't send test email.")
        expect(mocks.toastError).not.toHaveBeenCalledWith("Temporary failure")
        expect(screen.getByRole("button", { name: "Send test" })).toBeEnabled()

        fireEvent.click(screen.getByRole("button", { name: "Send test" }))
        await waitFor(() => expect(mocks.sendTest).toHaveBeenCalledTimes(2))

        const firstKey = requiredAt(mocks.sendTest.mock.calls, 0)[0].payload.idempotency_key
        const retriedKey = requiredAt(mocks.sendTest.mock.calls, 1)[0].payload.idempotency_key
        expect(firstKey).toMatch(
            /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
        )
        expect(retriedKey).toBe(firstKey)
    })

    it("publishes the revision returned by the preceding save", async () => {
        mocks.updateTemplate.mockResolvedValue({ ...mockTemplateData, current_version: 3 })
        mocks.publishTemplate.mockResolvedValue({ ...mockTemplateData, current_version: 4 })
        render(<PlatformEmailTemplatePage />)

        fireEvent.click(screen.getByRole("button", { name: "Publish" }))
        fireEvent.click(screen.getByRole("button", { name: "Confirm email publish" }))

        await waitFor(() => expect(mocks.publishTemplate).toHaveBeenCalledWith({
            id: "tpl_1",
            payload: { publish_all: true, org_ids: null, expected_version: 3 },
        }))
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))
        await waitFor(() => expect(mocks.updateTemplate).toHaveBeenLastCalledWith({
            id: "tpl_1", payload: expect.objectContaining({ expected_version: 4 }),
        }))
    })

    it("shows the save state next to the status badge", async () => {
        mocks.updateTemplate.mockRejectedValueOnce(new Error("Version conflict on row 42"))
        render(<PlatformEmailTemplatePage />)

        expect(screen.getByText("Draft")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))
        expect(await screen.findByText("Not saved")).toBeInTheDocument()
        expect(mocks.toastError).toHaveBeenCalledWith("Couldn't save template.")
        expect(mocks.toastError).not.toHaveBeenCalledWith("Version conflict on row 42")

        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))
        expect(await screen.findByText("Saved")).toBeInTheDocument()

        fireEvent.change(screen.getByLabelText("Template name"), { target: { value: "Missed visit" } })
        expect(screen.queryByText("Saved")).not.toBeInTheDocument()
    })

    it("deletes from the overflow menu with a destructive confirm", async () => {
        render(<PlatformEmailTemplatePage />)

        expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "More actions" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Delete" }))

        const confirm = await screen.findByRole("alertdialog")
        expect(within(confirm).getByText("Delete Missed Appointment?")).toBeInTheDocument()
        const deleteButton = within(confirm).getByRole("button", { name: "Delete" })
        expect(deleteButton).toHaveClass("bg-destructive")
        expect(deleteButton.className).not.toMatch(/linear-gradient/)

        fireEvent.click(deleteButton)
        await waitFor(() => expect(mocks.deleteTemplate).toHaveBeenCalledWith({ id: "tpl_1" }))
        expect(mocks.push).toHaveBeenCalledWith("/ops/templates?tab=email")
    })

    it("keeps the delete dialog open with a safe message when delete fails", async () => {
        mocks.deleteTemplate.mockRejectedValue(new Error("FK constraint templates_org_fk"))
        render(<PlatformEmailTemplatePage />)

        fireEvent.click(screen.getByRole("button", { name: "More actions" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Delete" }))
        const confirm = await screen.findByRole("alertdialog")
        fireEvent.click(within(confirm).getByRole("button", { name: "Delete" }))

        expect(await within(confirm).findByText("Couldn't delete template.")).toBeInTheDocument()
        expect(screen.queryByText(/FK constraint/)).not.toBeInTheDocument()
        expect(mocks.push).not.toHaveBeenCalled()
    })

    it("requires an agency pick when several agencies exist", async () => {
        mocks.listOrganizations.mockResolvedValue({
            items: [
                { id: "org-1", name: "Acme Surrogacy", slug: "acme", deleted_at: null },
                { id: "org-2", name: "Beta Family", slug: "beta", deleted_at: null },
            ],
        })
        render(<PlatformEmailTemplatePage />)

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
        await waitFor(() => expect(mocks.sendTest).toHaveBeenCalledTimes(1))
        expect(requiredAt(mocks.sendTest.mock.calls, 0)[0].payload).toMatchObject({ org_id: "org-2" })
    })

    it("shows no overflow menu for a new template", () => {
        mockParamsId = "new"
        render(<PlatformEmailTemplatePage />)

        expect(screen.queryByRole("button", { name: "More actions" })).not.toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to email templates" })).toHaveAttribute(
            "href",
            "/ops/templates?tab=email",
        )
    })
})
