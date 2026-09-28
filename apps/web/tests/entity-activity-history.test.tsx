import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { EntityActivityHistory } from "@/components/activity/EntityActivityHistory"
import { ApiError } from "@/lib/api"

const mockUseInfiniteEntityActivity = vi.fn()

vi.mock("@/lib/hooks/use-entity-activity", () => ({
    useInfiniteEntityActivity: (...args: unknown[]) => mockUseInfiniteEntityActivity(...args),
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}))

const activity = {
    id: "activity-1",
    activity_type: "note_added",
    actor_user_id: "user-1",
    actor_name: "Morgan Lee",
    details: { preview: "Screening complete" },
    created_at: "2026-08-30T12:00:00Z",
}

describe("EntityActivityHistory", () => {
    beforeEach(() => {
        mockUseInfiniteEntityActivity.mockReset()
    })

    it("keeps loaded entries visible when fetching the next page fails", () => {
        const fetchNextPage = vi.fn()
        mockUseInfiniteEntityActivity.mockReturnValue({
            data: { pages: [{ items: [activity], page: 1, pages: 2, total: 2 }] },
            isLoading: false,
            isError: true,
            isFetchNextPageError: true,
            isFetchingNextPage: false,
            hasNextPage: true,
            fetchNextPage,
            refetch: vi.fn(),
        })

        render(
            <EntityActivityHistory
                entityType="donor"
                entityId="donor-1"
                backHref="/donors/donor-1"
            />,
        )

        expect(screen.getByText("Screening complete")).toBeInTheDocument()
        expect(screen.getByRole("alert")).toHaveTextContent("Failed to load more activity.")
        fireEvent.click(screen.getByRole("button", { name: "Retry load more" }))
        expect(fetchNextPage).toHaveBeenCalledOnce()
    })

    it("uses list semantics and an exact machine-readable timestamp", () => {
        mockUseInfiniteEntityActivity.mockReturnValue({
            data: { pages: [{ items: [activity], page: 1, pages: 1, total: 1 }] },
            isLoading: false,
            isError: false,
            isFetchNextPageError: false,
            isFetchingNextPage: false,
            hasNextPage: false,
            fetchNextPage: vi.fn(),
            refetch: vi.fn(),
        })

        const { container } = render(
            <EntityActivityHistory
                entityType="intended_parent"
                entityId="ip-1"
                backHref="/intended-parents/ip-1"
            />,
        )

        expect(screen.getByRole("list", { name: "Activity history entries" })).toBeInTheDocument()
        expect(screen.getAllByRole("listitem")).toHaveLength(1)
        expect(container.querySelector("time")).toHaveAttribute("datetime", activity.created_at)
    })

    function mockInitialLoadError(error: unknown, refetch = vi.fn()) {
        mockUseInfiniteEntityActivity.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error,
            isFetching: false,
            isFetchNextPageError: false,
            isFetchingNextPage: false,
            hasNextPage: false,
            fetchNextPage: vi.fn(),
            refetch,
        })
    }

    it("shows a permission state when activity is forbidden", () => {
        mockInitialLoadError(new ApiError(403, "Forbidden", "Forbidden"))

        render(<EntityActivityHistory entityType="intended_parent" entityId="ip-1" backHref="/intended-parents/ip-1" />)

        expect(screen.getByRole("heading", { name: "Permission required" })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Go to Dashboard" })).toHaveAttribute("href", "/dashboard")
        expect(screen.queryByText("Failed to load activity.")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument()
    })

    it("shows the not-found state when the record is missing", () => {
        mockInitialLoadError(new ApiError(404, "Not Found", "Intended parent not found"))

        render(<EntityActivityHistory entityType="intended_parent" entityId="ip-1" backHref="/intended-parents/ip-1" />)

        expect(screen.getByRole("heading", { name: "Intended parent not found" })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to Intended Parents" })).toHaveAttribute("href", "/intended-parents")
    })

    it("offers a retry for other activity load failures", () => {
        const refetch = vi.fn()
        mockInitialLoadError(new ApiError(500, "Server Error", "boom"), refetch)

        render(<EntityActivityHistory entityType="donor" entityId="donor-1" backHref="/donors/donor-1" />)

        expect(screen.getByRole("heading", { level: 3, name: "Couldn't load activity" })).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(refetch).toHaveBeenCalledOnce()
    })
})
