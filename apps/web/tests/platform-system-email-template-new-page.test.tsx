import { describe, it, expect, vi, beforeEach } from "vitest"
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react"
import * as React from "react"
import PlatformSystemEmailTemplateNewPage from "../app/ops/templates/system/new/page"
import { toast } from "@/components/ui/toast"
import { ApiError } from "@/lib/api"

const mockPush = vi.fn()
const richTextEditorSpy = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: mockPush,
        replace: vi.fn(),
    }),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
    },
}))

vi.mock("@/components/app-link", () => ({
    default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: function MockRichTextEditor(props: unknown) {
        richTextEditorSpy(props)
        return <div data-testid="rich-text-editor" />
    },
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

    it("derives the system key from the name until the key is edited manually", async () => {
        render(<PlatformSystemEmailTemplateNewPage />)

        const nameInput = screen.getByLabelText("Name")
        const systemKeyInput = screen.getByLabelText("System key")

        fireEvent.change(nameInput, { target: { value: "Password Reset Notice" } })
        await waitFor(() => expect(systemKeyInput).toHaveValue("password_reset_notice"))

        fireEvent.change(systemKeyInput, { target: { value: "manual_key" } })
        fireEvent.change(nameInput, { target: { value: "Changed Name" } })

        expect(systemKeyInput).toHaveValue("manual_key")
    })

    it("switches to HTML editing when visual content contains complex HTML", async () => {
        render(<PlatformSystemEmailTemplateNewPage />)

        const latestEditorProps = richTextEditorSpy.mock.calls.at(-1)?.[0] as {
            onChange?: (html: string) => void
        }
        act(() => {
            latestEditorProps.onChange?.("<table><tbody><tr><td>Hello</td></tr></tbody></table>")
        })

        expect(await screen.findByPlaceholderText("Paste or edit the HTML for this template...")).toBeInTheDocument()
    })

    it("reenables creation after a create failure", async () => {
        mockCreate.mockRejectedValueOnce(new Error("System key already exists"))

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

        await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1))
        await waitFor(() => expect(screen.getByRole("button", { name: "Create" })).toBeEnabled())
        expect(toast.error).toHaveBeenCalledWith("Couldn't create system email.")
    })

    it("shows a preview placeholder until the body has content", async () => {
        render(<PlatformSystemEmailTemplateNewPage />)

        expect(screen.getByRole("heading", { name: "No content yet" })).toBeInTheDocument()

        const latestEditorProps = richTextEditorSpy.mock.calls.at(-1)?.[0] as {
            onChange?: (html: string) => void
        }
        act(() => {
            latestEditorProps.onChange?.("<p>Hello preview</p>")
        })

        await waitFor(() =>
            expect(screen.queryByRole("heading", { name: "No content yet" })).not.toBeInTheDocument(),
        )
        expect(screen.getByText("Hello preview")).toBeInTheDocument()
    })

    it("hides required errors on an untouched form and keeps Create enabled", () => {
        render(<PlatformSystemEmailTemplateNewPage />)

        expect(screen.getByRole("button", { name: "Create" })).toBeEnabled()
        expect(screen.queryByText("System key is required.")).not.toBeInTheDocument()
        expect(screen.queryByText("Name is required.")).not.toBeInTheDocument()
        expect(screen.queryByText("Subject is required.")).not.toBeInTheDocument()
        expect(screen.queryByText("Body is required.")).not.toBeInTheDocument()
        expect(screen.getByLabelText("Subject")).not.toHaveAttribute("aria-invalid")
    })

    it("shows a field error after blur and all errors after a blocked create", async () => {
        render(<PlatformSystemEmailTemplateNewPage />)

        // Leaving an unedited field shows nothing; leaving it after an edit shows its error.
        const name = screen.getByLabelText("Name")
        fireEvent.blur(name)
        expect(screen.queryByText("Name is required.")).not.toBeInTheDocument()
        fireEvent.change(name, { target: { value: "W" } })
        fireEvent.change(name, { target: { value: "" } })
        fireEvent.blur(name)
        expect(screen.getByText("Name is required.")).toBeInTheDocument()
        expect(screen.queryByText("Subject is required.")).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Create" }))

        const subject = screen.getByLabelText("Subject")
        expect(screen.getByText("System key is required.")).toBeInTheDocument()
        expect(screen.getByText("Subject is required.")).toBeInTheDocument()
        expect(screen.getByText("Body is required.")).toBeInTheDocument()
        expect(subject).toHaveAttribute("aria-invalid", "true")
        expect(subject).toHaveAttribute("aria-describedby", "subject-error")
        // The subject error sits directly under its input, not under Insert Variable.
        expect(subject.nextElementSibling).toHaveTextContent("Subject is required.")
        await waitFor(() => expect(screen.getByLabelText("System key")).toHaveFocus())
        expect(mockCreate).not.toHaveBeenCalled()

        fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Welcome" } })
        expect(screen.queryByText("Name is required.")).not.toBeInTheDocument()
        expect(screen.queryByText("System key is required.")).not.toBeInTheDocument()
    })

    it("attaches a duplicate system key to the system key field", async () => {
        mockCreate.mockRejectedValueOnce(new ApiError(409, "Conflict", "System template already exists"))

        render(<PlatformSystemEmailTemplateNewPage />)

        fireEvent.change(screen.getByLabelText("System key"), { target: { value: "org_invite" } })
        fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Invite" } })
        fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Hi" } })
        fireEvent.click(screen.getByRole("button", { name: "HTML" }))
        fireEvent.change(screen.getByPlaceholderText("Paste or edit the HTML for this template..."), {
            target: { value: "<p>Hello</p>" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Create" }))

        expect(await screen.findByText("A template with this system key already exists.")).toBeInTheDocument()
        expect(screen.getByLabelText("System key")).toHaveAttribute("aria-invalid", "true")
    })
})
