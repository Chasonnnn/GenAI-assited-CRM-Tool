import * as React from "react"
import { describe, expect, it, beforeEach, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { EmailComposeDialog } from "@/components/email/EmailComposeDialog"

const mockUseEmailTemplates = vi.fn()
const mockUseEmailTemplate = vi.fn()
const mockUseSendSurrogateEmail = vi.fn()
const mockUseSignaturePreview = vi.fn()
const mockUseOrgSignaturePreview = vi.fn()

vi.mock("@/components/ui/dialog", () => ({
    Dialog: ({ open, children }: { open: boolean; children: React.ReactNode }) =>
        open ? <div>{children}</div> : null,
    DialogContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
    DialogDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
    DialogFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/components/ui/select", async () => {
    const ReactModule = await import("react")

    const extractNodeText = (node: React.ReactNode): string => {
        if (typeof node === "string" || typeof node === "number") return String(node)
        if (Array.isArray(node)) return node.map((item) => extractNodeText(item)).join("")
        if (ReactModule.isValidElement(node)) {
            return extractNodeText(
                (node.props as { children?: React.ReactNode } | null | undefined)?.children ?? ""
            )
        }
        return ""
    }

    const SelectContext = ReactModule.createContext<{
        value: string
        onValueChange: (value: string) => void
    }>({
        value: "",
        onValueChange: () => undefined,
    })

    function Select({
        value,
        onValueChange,
        children,
    }: {
        value: string
        onValueChange: (value: string) => void
        children: React.ReactNode
    }) {
        return (
            <SelectContext.Provider value={{ value, onValueChange }}>
                <div>{children}</div>
            </SelectContext.Provider>
        )
    }

    function SelectTrigger({
        id,
        children,
    }: {
        id?: string
        children: React.ReactNode
    }) {
        return (
            <div id={id} data-testid="email-template-trigger">
                {children}
            </div>
        )
    }

    function SelectValue({
        placeholder,
        children,
    }: {
        placeholder?: string
        children?: ((value: string | null) => React.ReactNode) | React.ReactNode
    }) {
        const { value } = ReactModule.useContext(SelectContext)
        if (!value) return <span>{placeholder}</span>
        if (typeof children === "function") {
            return <span>{children(value)}</span>
        }
        return <span>{value}</span>
    }

    function SelectContent({ children }: { children: React.ReactNode }) {
        return <div>{children}</div>
    }

    function SelectItem({
        value,
        children,
    }: {
        value: string
        children: React.ReactNode
    }) {
        const { onValueChange } = ReactModule.useContext(SelectContext)
        const label = extractNodeText(children)

        return (
            <button
                type="button"
                onClick={() => {
                    onValueChange(value)
                }}
                aria-label={label}
            >
                {children}
            </button>
        )
    }

    return {
        Select,
        SelectTrigger,
        SelectValue,
        SelectContent,
        SelectItem,
    }
})

vi.mock("@/lib/hooks/use-email-templates", () => ({
    useEmailTemplates: (params?: unknown) => mockUseEmailTemplates(params),
    useEmailTemplate: (id: string | null) => mockUseEmailTemplate(id),
}))

vi.mock("@/lib/hooks/use-surrogates", () => ({
    useSendSurrogateEmail: () => mockUseSendSurrogateEmail(),
}))

vi.mock("@/lib/hooks/use-signature", () => ({
    useSignaturePreview: () => mockUseSignaturePreview(),
    useOrgSignaturePreview: (options?: unknown) => mockUseOrgSignaturePreview(options),
}))

const baseSurrogateData = {
    id: "sur-1",
    email: "ashley@example.com",
    full_name: "Ashley Nicole Harden",
    surrogate_number: "S10001",
    status: "New Unread",
    state: "CA",
    phone: "(555) 111-2222",
}

describe("EmailComposeDialog", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUseSendSurrogateEmail.mockReturnValue({
            mutateAsync: vi.fn().mockResolvedValue({ success: true }),
            isPending: false,
            isError: false,
            isSuccess: false,
            error: null,
        })
        mockUseSignaturePreview.mockReturnValue({
            data: { html: "<div>Personal Signature Block</div>" },
            isLoading: false,
        })
        mockUseOrgSignaturePreview.mockReturnValue({
            data: { html: "<div>Org Signature Block</div>" },
            isLoading: false,
        })
    })

    it("shows resolved template name instead of raw uuid in the selected value", async () => {
        const templateId = "129ba716-7291-457c-baec-545951262c1a"

        mockUseEmailTemplates.mockReturnValue({
            data: [
                {
                    id: templateId,
                    name: "",
                    subject: "",
                    from_email: null,
                    is_active: true,
                    scope: "org",
                    owner_user_id: null,
                    owner_name: null,
                    is_system_template: false,
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                },
            ],
            isLoading: false,
        })

        mockUseEmailTemplate.mockImplementation((id: string | null) => {
            if (id !== templateId) return { data: null, isLoading: false }
            return {
                data: {
                    id: templateId,
                    organization_id: "org-1",
                    created_by_user_id: null,
                    name: "Follow-up on Application",
                    subject: "Hello {{full_name}}",
                    from_email: null,
                    body: "<p>Thanks for applying.</p>",
                    is_active: true,
                    scope: "org",
                    owner_user_id: null,
                    owner_name: null,
                    source_template_id: null,
                    is_system_template: false,
                    current_version: 1,
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                },
                isLoading: false,
            }
        })

        render(
            <EmailComposeDialog
                open
                onOpenChange={vi.fn()}
                surrogateData={baseSurrogateData}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: templateId }))

        await waitFor(() => {
            const trigger = screen.getByTestId("email-template-trigger")
            expect(trigger).toHaveTextContent("Follow-up on Application")
            expect(trigger).not.toHaveTextContent(templateId)
        })
    })

    it("renders html preview by default with variable interpolation and signature block", async () => {
        const templateId = "tpl-1"

        mockUseEmailTemplates.mockReturnValue({
            data: [
                {
                    id: templateId,
                    name: "Initial Outreach",
                    subject: "Hello {{full_name}}",
                    from_email: null,
                    is_active: true,
                    scope: "org",
                    owner_user_id: null,
                    owner_name: null,
                    is_system_template: false,
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                },
            ],
            isLoading: false,
        })

        mockUseEmailTemplate.mockImplementation((id: string | null) => {
            if (id !== templateId) return { data: null, isLoading: false }
            return {
                data: {
                    id: templateId,
                    organization_id: "org-1",
                    created_by_user_id: null,
                    name: "Initial Outreach",
                    subject: "Hello {{full_name}}",
                    from_email: null,
                    body: "<p>Hi <strong>{{full_name}}</strong>, thank you for applying.</p>",
                    is_active: true,
                    scope: "org",
                    owner_user_id: null,
                    owner_name: null,
                    source_template_id: null,
                    is_system_template: false,
                    current_version: 1,
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                },
                isLoading: false,
            }
        })

        render(
            <EmailComposeDialog
                open
                onOpenChange={vi.fn()}
                surrogateData={baseSurrogateData}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: "Initial Outreach" }))

        await waitFor(() => {
            expect(screen.getByText("Hello Ashley Nicole Harden")).toBeInTheDocument()
            const proseBody = document.querySelector(".prose")
            expect(proseBody).toBeTruthy()
            expect(proseBody).toHaveTextContent("Hi Ashley Nicole Harden, thank you for applying.")
            expect(proseBody).not.toHaveTextContent("{{full_name}}")
            expect(screen.getByText("Org Signature Block")).toBeInTheDocument()
        })
    })

    it("shows html editor when toggled and applies edits when returning to preview", async () => {
        const templateId = "tpl-live-edit"

        mockUseEmailTemplates.mockReturnValue({
            data: [
                {
                    id: templateId,
                    name: "Welcome Email",
                    subject: "Welcome {{full_name}}",
                    from_email: null,
                    is_active: true,
                    scope: "org",
                    owner_user_id: null,
                    owner_name: null,
                    is_system_template: false,
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                },
            ],
            isLoading: false,
        })

        mockUseEmailTemplate.mockImplementation((id: string | null) => {
            if (id !== templateId) return { data: null, isLoading: false }
            return {
                data: {
                    id: templateId,
                    organization_id: "org-1",
                    created_by_user_id: null,
                    name: "Welcome Email",
                    subject: "Welcome {{full_name}}",
                    from_email: null,
                    body: "<p>Initial content.</p>",
                    is_active: true,
                    scope: "org",
                    owner_user_id: null,
                    owner_name: null,
                    source_template_id: null,
                    is_system_template: false,
                    current_version: 1,
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                },
                isLoading: false,
            }
        })

        render(
            <EmailComposeDialog
                open
                onOpenChange={vi.fn()}
                surrogateData={baseSurrogateData}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: "Welcome Email" }))

        await waitFor(() => {
            const proseBody = document.querySelector(".prose")
            expect(proseBody).toBeTruthy()
            expect(proseBody).toHaveTextContent("Initial content.")
        })

        fireEvent.click(await screen.findByRole("button", { name: /edit html/i }))

        const bodyTextarea = screen.getByPlaceholderText("Enter email message...")
        fireEvent.change(bodyTextarea, {
            target: { value: "<p>Custom hello {{full_name}}.</p>" },
        })

        fireEvent.click(screen.getByRole("button", { name: /show preview/i }))

        await waitFor(() => {
            const proseBody = document.querySelector(".prose")
            expect(proseBody).toBeTruthy()
            expect(proseBody).toHaveTextContent("Custom hello Ashley Nicole Harden.")
        })
    })

    it("allows customizing message directly in preview mode without toggling to html editor", async () => {
        const templateId = "tpl-preview-edit"
        const mutateAsync = vi.fn().mockResolvedValue({ success: true })

        mockUseSendSurrogateEmail.mockReturnValue({
            mutateAsync,
            isPending: false,
            isError: false,
            isSuccess: false,
            error: null,
        })

        mockUseEmailTemplates.mockReturnValue({
            data: [
                {
                    id: templateId,
                    name: "Preview Editable Template",
                    subject: "Welcome {{full_name}}",
                    from_email: null,
                    is_active: true,
                    scope: "org",
                    owner_user_id: null,
                    owner_name: null,
                    is_system_template: false,
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                },
            ],
            isLoading: false,
        })

        mockUseEmailTemplate.mockImplementation((id: string | null) => {
            if (id !== templateId) return { data: null, isLoading: false }
            return {
                data: {
                    id: templateId,
                    organization_id: "org-1",
                    created_by_user_id: null,
                    name: "Preview Editable Template",
                    subject: "Welcome {{full_name}}",
                    from_email: null,
                    body: "<p>Initial draft for {{full_name}}.</p>",
                    is_active: true,
                    scope: "org",
                    owner_user_id: null,
                    owner_name: null,
                    source_template_id: null,
                    is_system_template: false,
                    current_version: 1,
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                },
                isLoading: false,
            }
        })

        render(
            <EmailComposeDialog
                open
                onOpenChange={vi.fn()}
                surrogateData={baseSurrogateData}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: "Preview Editable Template" }))

        const previewEditor = await screen.findByLabelText("Message preview editor")
        expect(previewEditor).toHaveTextContent("Initial draft for Ashley Nicole Harden.")

        previewEditor.innerHTML = "<p>Final custom note for Ashley before send.</p>"
        fireEvent.input(previewEditor)

        await waitFor(() => {
            expect(previewEditor).toHaveTextContent("Final custom note for Ashley before send.")
        })

        fireEvent.click(screen.getByRole("button", { name: /send email/i }))

        await waitFor(() => {
            expect(mutateAsync).toHaveBeenCalledWith(
                expect.objectContaining({
                    surrogateId: "sur-1",
                    data: expect.objectContaining({
                        subject: "Welcome {{full_name}}",
                        body: expect.stringContaining("Final custom note for Ashley before send."),
                    }),
                })
            )
        })
    })
})
