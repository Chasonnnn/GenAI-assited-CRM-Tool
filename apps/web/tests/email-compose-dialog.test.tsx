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
        selectedLabel: string
        setSelectedLabel: (label: string) => void
    }>({
        value: "",
        onValueChange: () => undefined,
        selectedLabel: "",
        setSelectedLabel: () => undefined,
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
        const [selectedLabel, setSelectedLabel] = ReactModule.useState("")
        return (
            <SelectContext.Provider value={{ value, onValueChange, selectedLabel, setSelectedLabel }}>
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
        children?: React.ReactNode
    }) {
        const { value, selectedLabel } = ReactModule.useContext(SelectContext)
        const fallback = selectedLabel || value || placeholder
        return <span>{children ?? fallback}</span>
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
        const { onValueChange, value: selectedValue, setSelectedLabel } = ReactModule.useContext(SelectContext)
        const label = extractNodeText(children)

        ReactModule.useEffect(() => {
            if (selectedValue === value && label) {
                setSelectedLabel(label)
            }
        }, [label, selectedValue, setSelectedLabel, value])

        return (
            <button
                type="button"
                onClick={() => {
                    setSelectedLabel(label)
                    onValueChange(value)
                }}
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

    it("renders html preview with variable interpolation and signature block", async () => {
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
        fireEvent.click(await screen.findByRole("button", { name: "Preview" }))

        await waitFor(() => {
            expect(screen.getByText("Hello Ashley Nicole Harden")).toBeInTheDocument()
            const proseBody = document.querySelector(".prose")
            expect(proseBody).toBeTruthy()
            expect(proseBody).toHaveTextContent("Hi Ashley Nicole Harden, thank you for applying.")
            expect(screen.getByText("Org Signature Block")).toBeInTheDocument()
            expect(screen.queryByText("<p>Hi <strong>{{full_name}}</strong>, thank you for applying.</p>")).not.toBeInTheDocument()
        })
    })
})
