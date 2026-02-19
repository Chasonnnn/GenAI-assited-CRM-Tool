import { beforeEach, describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import * as React from "react"
import PlatformEmailTemplatePage from "../app/ops/templates/email/[id]/page"

const richTextEditorSpy = vi.fn()

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: React.forwardRef((props: { content?: string }, _ref) => {
        richTextEditorSpy(props)
        return <div data-testid="rich-text-editor" />
    }),
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
    usePlatformEmailTemplate: () => ({ data: mockTemplateData, isLoading: false }),
    usePlatformEmailTemplateVariables: () => ({ data: [], isLoading: false }),
    useCreatePlatformEmailTemplate: () => ({ mutateAsync: vi.fn() }),
    useUpdatePlatformEmailTemplate: () => ({ mutateAsync: vi.fn() }),
    usePublishPlatformEmailTemplate: () => ({ mutateAsync: vi.fn() }),
    useDeletePlatformEmailTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSendTestPlatformEmailTemplate: () => ({ mutateAsync: vi.fn() }),
}))

describe("PlatformEmailTemplatePage", () => {
    beforeEach(() => {
        richTextEditorSpy.mockClear()
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

    it("disables send test on new templates", () => {
        mockParamsId = "new"
        render(<PlatformEmailTemplatePage />)
        expect(screen.getByRole("button", { name: "Send test" })).toBeDisabled()
        expect(screen.getByText("Save template first.")).toBeInTheDocument()
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
