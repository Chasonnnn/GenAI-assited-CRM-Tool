import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { EmailLayoutCanvas, EmailLayoutSettings } from "@/components/email/design/email-layout-canvas"
import type { EmailLayout, EmailLayoutFrame } from "@/lib/api/email-templates"
import { defaultEmailLayout } from "@/lib/email-design"

const FRAME: EmailLayoutFrame = {
    layout: defaultEmailLayout("org"),
    logo_url: "https://api.example.com/forms/public/org-1/signature-logo?v=abc",
    logo_alt: "Smith & Co",
    accent_color: "#b8335f",
    signature_html: "<p>Smith &amp; Co</p>",
    footer_html: "<p>Unsubscribe</p>",
}

function renderCanvas(layout: EmailLayout, frame: Partial<EmailLayoutFrame> | null = {}) {
    return render(
        <EmailLayoutCanvas
            layout={layout}
            viewport="desktop"
            frame={{ data: frame ? { ...FRAME, layout, ...frame } : undefined, isError: false, onRetry: vi.fn() }}
            header={<p>Header rows</p>}
        >
            <p>Editable body</p>
        </EmailLayoutCanvas>,
    )
}

describe("EmailLayoutCanvas", () => {
    it("draws Card on the page background with the logo above the body", () => {
        const layout = { ...defaultEmailLayout("org"), page_background: "#e0f2fe" }
        const { container } = renderCanvas(layout)

        const card = container.querySelector('[data-email-layout="card"]')
        expect(card).toHaveStyle({ backgroundColor: "#e0f2fe" })
        const logo = screen.getByRole("img", { name: "Smith & Co" })
        expect(logo).toHaveClass("mx-auto")
        expect(logo.compareDocumentPosition(screen.getByText("Editable body"))).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
        expect(screen.getByTitle("Signature and unsubscribe footer")).toBeInTheDocument()
        expect(screen.getByText("Header rows")).toBeInTheDocument()
    })

    it("draws Letterhead with a left logo and the accent rule", () => {
        const layout: EmailLayout = { ...defaultEmailLayout("org"), kind: "letterhead", logo_position: "left" }
        renderCanvas(layout)

        expect(screen.getByRole("img", { name: "Smith & Co" })).not.toHaveClass("mx-auto")
        expect(screen.getByTestId("letterhead-rule")).toHaveStyle({ borderTopColor: "#b8335f" })
    })

    it("draws Plain without a logo or page background", () => {
        const { container } = renderCanvas(defaultEmailLayout("personal"), { logo_url: null })

        expect(container.querySelector('[data-email-layout="plain"]')).toBeInTheDocument()
        expect(screen.queryByRole("img")).not.toBeInTheDocument()
    })

    it("shows loading while the frame loads", () => {
        renderCanvas(defaultEmailLayout("org"), null)

        expect(screen.getByRole("status")).toHaveTextContent("Loading signature")
        expect(screen.getByText("Editable body")).toBeInTheDocument()
    })
})

describe("EmailLayoutSettings", () => {
    it("shows only the settings the chosen layout uses", () => {
        const onChange = vi.fn()
        const { rerender } = render(
            <EmailLayoutSettings value={defaultEmailLayout("personal")} onChange={onChange} defaultAccent="#b8335f" />,
        )
        expect(screen.queryByLabelText("Show logo")).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("radio", { name: /Card/ }))
        expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ kind: "card" }))

        rerender(<EmailLayoutSettings value={defaultEmailLayout("org")} onChange={onChange} defaultAccent="#b8335f" />)
        expect(screen.getByLabelText("Page background")).toHaveValue("#f4f4f5")
        expect(screen.queryByLabelText("Accent color")).not.toBeInTheDocument()

        const letterhead: EmailLayout = { ...defaultEmailLayout("org"), kind: "letterhead" }
        rerender(<EmailLayoutSettings value={letterhead} onChange={onChange} defaultAccent="#b8335f" />)
        expect(screen.getByLabelText("Accent color")).toHaveValue("#b8335f")
        fireEvent.click(screen.getByRole("switch", { name: "Show logo" }))
        expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ show_logo: false }))
    })

    it("locks every choice when the body is a full document", () => {
        render(
            <EmailLayoutSettings value={defaultEmailLayout("org")} onChange={vi.fn()} defaultAccent="#111827" disabled />,
        )

        for (const radio of screen.getAllByRole("radio", { name: /Plain|Card|Letterhead/ })) {
            expect(radio).toHaveAttribute("data-disabled")
        }
    })
})
