import { describe, expect, it, vi, beforeEach } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { useQuery } from "@tanstack/react-query"
import { PublishDialog } from "@/components/ops/templates/PublishDialog"

const organizations = [
    {
        id: "org-a",
        name: "Acme Surrogacy",
        slug: "acme",
        portal_base_url: "https://acme.test",
        timezone: "America/Los_Angeles",
        member_count: 3,
        surrogate_count: 12,
        subscription_plan: "professional",
        subscription_status: "active",
        created_at: "2026-01-01T00:00:00.000Z",
        deleted_at: null,
    },
    {
        id: "org-b",
        name: "Beta Family",
        slug: "beta",
        portal_base_url: "https://beta.test",
        timezone: "America/New_York",
        member_count: 2,
        surrogate_count: 8,
        subscription_plan: "starter",
        subscription_status: "active",
        created_at: "2026-01-02T00:00:00.000Z",
        deleted_at: null,
    },
]

describe("PublishDialog", () => {
    beforeEach(() => {
        vi.mocked(useQuery).mockReturnValue({
            data: { items: organizations, total: organizations.length },
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        } as never)
    })

    it("resets publish mode, search, and selected orgs each time it opens", () => {
        const onOpenChange = vi.fn()
        const onPublish = vi.fn()
        const { rerender } = render(
            <PublishDialog
                open
                onOpenChange={onOpenChange}
                onPublish={onPublish}
                defaultPublishAll={false}
                initialOrgIds={["org-a"]}
            />
        )

        expect(screen.getByRole("radio", { name: /selected organizations/i })).toBeChecked()
        expect(screen.getByRole("checkbox", { name: /Acme Surrogacy/i })).toBeChecked()

        fireEvent.change(screen.getByPlaceholderText("Search organizations…"), {
            target: { value: "beta" },
        })
        expect(screen.queryByText("Acme Surrogacy")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("checkbox", { name: /Beta Family/i }))

        rerender(
            <PublishDialog
                open={false}
                onOpenChange={onOpenChange}
                onPublish={onPublish}
                defaultPublishAll={false}
                initialOrgIds={["org-a"]}
            />
        )
        rerender(
            <PublishDialog
                open
                onOpenChange={onOpenChange}
                onPublish={onPublish}
                defaultPublishAll
                initialOrgIds={[]}
            />
        )

        expect(screen.getByRole("radio", { name: /all organizations/i })).toBeChecked()
        expect(screen.queryByPlaceholderText("Search organizations…")).not.toBeInTheDocument()

        rerender(
            <PublishDialog
                open={false}
                onOpenChange={onOpenChange}
                onPublish={onPublish}
                defaultPublishAll
                initialOrgIds={[]}
            />
        )
        rerender(
            <PublishDialog
                open
                onOpenChange={onOpenChange}
                onPublish={onPublish}
                defaultPublishAll={false}
                initialOrgIds={["org-b"]}
            />
        )

        expect(screen.getByRole("radio", { name: /selected organizations/i })).toBeChecked()
        expect(screen.getByPlaceholderText("Search organizations…")).toHaveValue("")
        expect(screen.getByRole("checkbox", { name: /Beta Family/i })).toBeChecked()
        expect(screen.getByRole("checkbox", { name: /Acme Surrogacy/i })).not.toBeChecked()
        expect(screen.getByText("1 selected")).toBeInTheDocument()
    })
})
