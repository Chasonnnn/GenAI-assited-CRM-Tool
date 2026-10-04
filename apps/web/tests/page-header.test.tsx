import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import { PageHeader } from "@/components/page-header"

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}))

describe("PageHeader", () => {
    it("renders a 64px band with a 24px h1 and right-aligned actions that can wrap", () => {
        const { container } = render(
            <PageHeader title="Team" actions={<button type="button">Invite Member</button>} />
        )

        const heading = screen.getByRole("heading", { level: 1, name: "Team" })
        expect(heading).toHaveClass("text-2xl", "font-semibold", "truncate")

        const band = container.querySelector('[data-slot="page-header"]')
        expect(band).toHaveClass("border-b")
        const row = band?.firstElementChild
        expect(row).toHaveClass("min-h-16", "px-6", "flex-wrap")

        const actions = container.querySelector('[data-slot="page-header-actions"]')
        // grow + justify-end: right-aligned beside the title, full row once wrapped, so
        // `flex-1 sm:flex-none` buttons can share the wrapped row at 390px.
        expect(actions).toHaveClass("ml-auto", "grow", "justify-end", "flex-wrap")
        expect(actions).toContainElement(screen.getByRole("button", { name: "Invite Member" }))
    })

    it("renders a labelled back link and inline meta for detail pages", () => {
        render(
            <PageHeader
                title="Welcome email"
                back={{ href: "/ops/templates", label: "Back to templates" }}
                meta={<span>Draft</span>}
            />
        )

        const back = screen.getByRole("link", { name: "Back to templates" })
        expect(back).toHaveAttribute("href", "/ops/templates")
        expect(screen.getByText("Draft")).toBeInTheDocument()
    })

    it("has no back link or actions on a plain top-level page", () => {
        const { container } = render(<PageHeader title="Dashboard" />)

        expect(screen.queryByRole("link")).not.toBeInTheDocument()
        expect(container.querySelector('[data-slot="page-header-actions"]')).toBeNull()
        expect(container.querySelector('[data-slot="page-header-eyebrow"]')).toBeNull()
    })

    it("renders an optional eyebrow line above the title", () => {
        const { container } = render(<PageHeader title="Dashboard" eyebrow="Good morning, Test" />)

        const eyebrow = container.querySelector('[data-slot="page-header-eyebrow"]')
        expect(eyebrow).toHaveTextContent("Good morning, Test")
        expect(eyebrow).toHaveClass("text-sm", "text-muted-foreground", "truncate")
        expect(screen.getByRole("heading", { level: 1, name: "Dashboard" })).toBeInTheDocument()
    })
})
