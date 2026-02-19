import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import * as React from "react"
import PlatformSystemEmailTemplateNewPage from "../app/ops/templates/system/new/page"

const mockPush = vi.fn()
const richTextEditorSpy = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: mockPush,
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
    RichTextEditor: React.forwardRef((props: unknown, _ref) => {
        richTextEditorSpy(props)
        return <div data-testid="rich-text-editor" />
    }),
}))

const mockCreate = vi.fn()

vi.mock("@/lib/hooks/use-platform-templates", () => ({
    useCreatePlatformSystemEmailTemplate: () => ({ mutateAsync: mockCreate }),
    usePlatformSystemEmailTemplateVariables: () => ({
        data: [
            {
                name: "org_name",
                description: "Organization name",
                category: "Organization",
                required: false,
                value_type: "text",
                html_safe: false,
            },
        ],
        isLoading: false,
    }),
}))

describe("PlatformSystemEmailTemplateNewPage", () => {
    beforeEach(() => {
        mockPush.mockReset()
        mockCreate.mockReset()
        richTextEditorSpy.mockClear()
    })

    it("creates a system email template and navigates to the detail page", async () => {
        mockCreate.mockResolvedValueOnce({
            system_key: "custom_announcement",
            name: "Custom Announcement",
            subject: "Announcement for {{org_name}}",
            from_email: "Ops <ops@surrogacyforce.com>",
            body: "<p>Hello</p>",
            is_active: true,
            current_version: 1,
            updated_at: new Date().toISOString(),
        })

        render(<PlatformSystemEmailTemplateNewPage />)

        fireEvent.change(screen.getByLabelText("System key"), {
            target: { value: "custom_announcement" },
        })
        fireEvent.change(screen.getByLabelText("Name"), {
            target: { value: "Custom Announcement" },
        })
        fireEvent.change(screen.getByLabelText("Subject"), {
            target: { value: "Announcement for {{org_name}}" },
        })

        fireEvent.click(screen.getByRole("button", { name: "HTML" }))
        fireEvent.change(screen.getByPlaceholderText("Paste or edit the HTML for this template..."), {
            target: { value: "<p>Hello</p>" },
        })

        fireEvent.click(screen.getByRole("button", { name: "Create" }))

        await waitFor(() =>
            expect(mockCreate).toHaveBeenCalledWith(
                expect.objectContaining({
                    system_key: "custom_announcement",
                    name: "Custom Announcement",
                    subject: "Announcement for {{org_name}}",
                })
            )
        )
        expect(mockPush).toHaveBeenCalledWith("/ops/templates/system/custom_announcement")
    })

    it("enables emoji picker in visual editor mode", () => {
        render(<PlatformSystemEmailTemplateNewPage />)
        expect(screen.getByTestId("rich-text-editor")).toBeInTheDocument()

        const hasEmojiEnabled = richTextEditorSpy.mock.calls.some(
            ([props]) => Boolean((props as { enableEmojiPicker?: boolean }).enableEmojiPicker)
        )
        expect(hasEmojiEnabled).toBe(true)
    })
})
