import { beforeEach, describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import * as React from "react"
import PlatformEmailTemplatePage from "../app/ops/templates/email/[id]/page.client"

const richTextEditorSpy = vi.fn()
const mocks = vi.hoisted(() => ({
    updateTemplate: vi.fn(),
    sendTest: vi.fn(),
    refetchTemplate: vi.fn(),
    state: {
        templateQueryError: false,
    },
}))

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: function MockRichTextEditor(props: { content?: string }) {
        richTextEditorSpy(props)
        return <div data-testid="rich-text-editor" />
    },
}))

vi.mock("@/components/ops/templates/PublishDialog", () => ({
    PublishDialog: () => <div data-testid="publish-dialog" />,
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
        push: vi.fn(),
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
    usePublishPlatformEmailTemplate: () => ({ mutateAsync: vi.fn() }),
    useDeletePlatformEmailTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSendTestPlatformEmailTemplate: () => ({ mutateAsync: mocks.sendTest }),
}))

describe("PlatformEmailTemplatePage", () => {
    beforeEach(() => {
        richTextEditorSpy.mockClear()
        mocks.updateTemplate.mockReset()
        mocks.sendTest.mockReset()
        mocks.refetchTemplate.mockReset()
        mocks.state.templateQueryError = false
        mocks.updateTemplate.mockResolvedValue(mockTemplateData)
        mocks.sendTest.mockResolvedValue({ queued: true, provider_used: "resend" })
        mocks.refetchTemplate.mockResolvedValue(undefined)
    })

    it("avoids rendering the rich editor with complex HTML", async () => {
        mockParamsId = "tpl_1"
        render(<PlatformEmailTemplatePage />)

        await screen.findByPlaceholderText("Paste or edit the HTML for this template...")

        const richEditorCallsWithTable = richTextEditorSpy.mock.calls.filter(
            ([props]) => (props?.content || "").includes("<table")
        )

        expect(richEditorCallsWithTable.length).toBe(0)
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

        fireEvent.change(screen.getByLabelText("Organization ID"), {
            target: { value: "org-1" },
        })
        fireEvent.change(screen.getByLabelText("Test email"), {
            target: { value: "qa@example.com" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Send test" }))

        await waitFor(() => expect(mocks.sendTest).toHaveBeenCalledTimes(1))
        expect(screen.getByRole("button", { name: "Send test" })).toBeEnabled()

        fireEvent.click(screen.getByRole("button", { name: "Send test" }))
        await waitFor(() => expect(mocks.sendTest).toHaveBeenCalledTimes(2))

        const firstKey = mocks.sendTest.mock.calls[0][0].payload.idempotency_key
        const retriedKey = mocks.sendTest.mock.calls[1][0].payload.idempotency_key
        expect(firstKey).toMatch(
            /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
        )
        expect(retriedKey).toBe(firstKey)
    })

    it("enables emoji picker in visual editor mode", async () => {
        mockParamsId = "tpl_1"
        const previousBody = mockTemplateData.draft.body
        mockTemplateData.draft.body = "<p>Hello there</p>"

        try {
            render(<PlatformEmailTemplatePage />)
            await screen.findByTestId("rich-text-editor")

            const hasEmojiEnabled = richTextEditorSpy.mock.calls.some(
                ([props]) => Boolean((props as { enableEmojiPicker?: boolean }).enableEmojiPicker)
            )
            expect(hasEmojiEnabled).toBe(true)
        } finally {
            mockTemplateData.draft.body = previousBody
        }
    })
})
