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

    it("shows the count badge with a screen-reader noun", () => {
        render(<PageHeader title="Surrogates" count={1510} countLabel="surrogates" />)

        const badge = document.querySelector('[data-slot="page-header-count"]')
        expect(badge).toHaveTextContent("1,510 surrogates")
        expect(badge?.textContent?.startsWith("1,510")).toBe(true)
        expect(screen.getByText("surrogates")).toHaveClass("sr-only")
    })

    it("reads 'n of total' while a filter narrows the list", () => {
        render(<PageHeader title="Matches" count={3} countTotal={42} />)

        expect(document.querySelector('[data-slot="page-header-count"]')).toHaveTextContent("3 of 42")
    })

    it("hides the badge while the count is unknown", () => {
        render(<PageHeader title="Matches" count={null} countTotal={42} />)

        expect(document.querySelector('[data-slot="page-header-count"]')).toBeNull()
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
    })
})
