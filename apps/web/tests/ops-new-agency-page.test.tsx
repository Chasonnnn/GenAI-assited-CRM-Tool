import type { ReactNode } from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import NewAgencyPage from "../app/ops/agencies/new/page.client"
import { ApiError } from "@/lib/api"

const mockCreateOrganization = vi.fn()
const mockPush = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: mockPush }),
}))

vi.mock("@/lib/api/platform", () => ({
    createOrganization: (...args: unknown[]) => mockCreateOrganization(...args),
}))

vi.mock("@/components/app-link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

describe("NewAgencyPage validation", () => {
    beforeEach(() => {
        mockCreateOrganization.mockReset()
        mockPush.mockReset()
    })

    it("uses custom validation only and hides errors until blur or submit", () => {
        const { container } = render(<NewAgencyPage />)

        expect(container.querySelector("form")).toHaveAttribute("novalidate")
        expect(screen.queryByText("Enter an agency name.")).not.toBeInTheDocument()
        expect(screen.getByLabelText("Agency Name")).not.toHaveAttribute("aria-invalid")

        fireEvent.blur(screen.getByLabelText("Agency Name"))
        expect(screen.getByText("Enter an agency name.")).toBeInTheDocument()
        expect(screen.queryByText("Enter the first admin email.")).not.toBeInTheDocument()
    })

    it("marks invalid fields on submit, focuses the first one and clears errors as fields are fixed", async () => {
        render(<NewAgencyPage />)

        fireEvent.click(screen.getByRole("button", { name: "Create Agency" }))

        const name = screen.getByLabelText("Agency Name")
        const email = screen.getByLabelText("First Admin Email")
        expect(name).toHaveAttribute("aria-invalid", "true")
        expect(name.getAttribute("aria-describedby")).toContain("name-error")
        expect(screen.getByText("Enter an agency name.")).toBeInTheDocument()
        expect(screen.getByText("Enter a slug.")).toBeInTheDocument()
        expect(screen.getByText("Enter the first admin email.")).toBeInTheDocument()
        await waitFor(() => expect(name).toHaveFocus())
        expect(mockCreateOrganization).not.toHaveBeenCalled()

        fireEvent.change(name, { target: { value: "QA Ops Agency" } })
        expect(screen.queryByText("Enter an agency name.")).not.toBeInTheDocument()
        expect(screen.queryByText("Enter a slug.")).not.toBeInTheDocument()
        expect(screen.getByLabelText("Slug")).toHaveValue("qa-ops-agency")

        fireEvent.change(email, { target: { value: "not-an-email" } })
        expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument()
        fireEvent.change(email, { target: { value: "admin@example.com" } })
        expect(screen.queryByText("Enter a valid email address.")).not.toBeInTheDocument()
    })

    it("shows a slug format error instead of a required error", () => {
        render(<NewAgencyPage />)

        const slug = screen.getByLabelText("Slug")
        fireEvent.change(slug, { target: { value: "Bad Slug" } })
        fireEvent.blur(slug)

        expect(screen.getByText("Use only lowercase letters, numbers, and hyphens.")).toBeInTheDocument()
        expect(screen.queryByText("Enter a slug.")).not.toBeInTheDocument()
    })

    it("attaches a duplicate slug response to the slug field", async () => {
        mockCreateOrganization.mockRejectedValue(
            new ApiError(400, "Bad Request", "Slug 'qa-ops' is already taken.")
        )
        render(<NewAgencyPage />)

        fireEvent.change(screen.getByLabelText("Agency Name"), { target: { value: "QA Ops" } })
        fireEvent.change(screen.getByLabelText("First Admin Email"), {
            target: { value: "admin@example.com" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Create Agency" }))

        expect(await screen.findByText("Slug 'qa-ops' is already taken.")).toBeInTheDocument()
        expect(screen.getByLabelText("Slug")).toHaveAttribute("aria-invalid", "true")
        expect(mockCreateOrganization).toHaveBeenCalledWith({
            name: "QA Ops",
            slug: "qa-ops",
            timezone: "America/Los_Angeles",
            admin_email: "admin@example.com",
        })
    })
})
