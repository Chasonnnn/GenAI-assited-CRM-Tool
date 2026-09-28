import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import AgenciesPage from "../app/ops/agencies/page.client"

const mockListOrganizations = vi.fn()
const mockGetPlatformStats = vi.fn()
const mockPush = vi.fn()

vi.unmock("@tanstack/react-query")

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: mockPush }),
}))

vi.mock("@/lib/api/platform", () => ({
    listOrganizations: (...args: unknown[]) => mockListOrganizations(...args),
    getPlatformStats: (...args: unknown[]) => mockGetPlatformStats(...args),
}))

type Deferred<T> = {
    promise: Promise<T>
    resolve: (value: T) => void
}

function deferred<T>(): Deferred<T> {
    let resolve!: (value: T) => void
    const promise = new Promise<T>((res) => {
        resolve = res
    })
    return { promise, resolve }
}

type OrganizationSummary = {
    id: string
    name: string
    slug: string
    member_count: number
    surrogate_count: number
    subscription_plan: "starter" | "professional" | "enterprise"
    subscription_status: "active" | "trial" | "past_due" | "canceled"
    created_at: string
    deleted_at: string | null
}

function org(id: string, name: string): OrganizationSummary {
    return {
        id,
        name,
        slug: `${id}-slug`,
        member_count: 1,
        surrogate_count: 1,
        subscription_plan: "starter",
        subscription_status: "active",
        created_at: "2026-01-01T00:00:00Z",
        deleted_at: null,
    }
}

describe("Ops agencies data loading", () => {
    const renderAgenciesPage = (queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    })) => ({
        queryClient,
        ...render(
            <QueryClientProvider client={queryClient}>
                <AgenciesPage />
            </QueryClientProvider>
        ),
    })

    beforeEach(() => {
        mockListOrganizations.mockReset()
        mockGetPlatformStats.mockReset()
        mockGetPlatformStats.mockResolvedValue({ agency_count: 3, active_user_count: 5, open_alerts: 0 })
        mockPush.mockReset()
    })

    it("labels plan and status without a header count", async () => {
        mockListOrganizations.mockResolvedValue({
            items: [{ ...org("one", "Agency One"), subscription_status: "past_due", subscription_plan: "professional" }],
            total: 1,
        })

        renderAgenciesPage()

        expect(await screen.findByText("Agency One")).toBeInTheDocument()
        expect(document.querySelector('[data-slot="page-header-count"]')).toBeNull()
        expect(mockGetPlatformStats).not.toHaveBeenCalled()
        expect(screen.getByRole("heading", { level: 1, name: "Agencies" })).toBeInTheDocument()
        expect(screen.getByText("Past due")).toBeInTheDocument()
        expect(screen.getByText("Professional")).toBeInTheDocument()
        expect(screen.queryByText("past_due")).not.toBeInTheDocument()
    })

    it("shows a first-run empty state with a create action when no agencies exist", async () => {
        mockListOrganizations.mockResolvedValue({ items: [], total: 0 })

        renderAgenciesPage()

        expect(await screen.findByRole("heading", { name: "No agencies yet" })).toBeInTheDocument()
        expect(screen.getAllByRole("link", { name: /Create Agency/ })).toHaveLength(2)
        expect(screen.queryByRole("button", { name: "Clear filters" })).not.toBeInTheDocument()
    })

    it("shows a filtered empty state that clears the search", async () => {
        mockListOrganizations.mockImplementation(async (params?: { search?: string }) =>
            params?.search
                ? { items: [], total: 0 }
                : { items: [org("one", "Agency One")], total: 1 }
        )

        renderAgenciesPage()
        await screen.findByText("Agency One")

        const searchInput = screen.getByRole("textbox", { name: "Search agencies" })
        fireEvent.change(searchInput, { target: { value: "zzz" } })

        expect(await screen.findByRole("heading", { name: "No matching agencies" })).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Clear filters" }))

        expect(await screen.findByText("Agency One")).toBeInTheDocument()
        expect(searchInput).toHaveValue("")
    })

    it("shows a retryable error state instead of an empty list when loading fails", async () => {
        mockListOrganizations.mockRejectedValueOnce(new Error("boom"))
        mockListOrganizations.mockResolvedValueOnce({ items: [org("one", "Agency One")], total: 1 })

        renderAgenciesPage()

        expect(await screen.findByRole("heading", { name: "Couldn't load agencies" })).toBeInTheDocument()
        expect(screen.queryByText("No agencies yet")).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /Try again|Retry/ }))
        expect(await screen.findByText("Agency One")).toBeInTheDocument()
    })

    it("ignores stale list responses and keeps latest search results", async () => {
        const requests: Array<Deferred<{ items: OrganizationSummary[]; total: number }>> = []
        mockListOrganizations.mockImplementation(() => {
            const next = deferred<{ items: OrganizationSummary[]; total: number }>()
            requests.push(next)
            return next.promise
        })

        renderAgenciesPage()

        await waitFor(() => expect(requests.length).toBe(1))
        requests[0]?.resolve({ items: [org("init", "Initial Agency")], total: 1 })
        await screen.findByText("Initial Agency")

        const searchInput = screen.getByPlaceholderText("Search by name or slug...")
        fireEvent.change(searchInput, { target: { value: "a" } })
        fireEvent.change(searchInput, { target: { value: "ab" } })

        await waitFor(() => expect(requests.length).toBe(3))

        // Latest query resolves first.
        requests[2]?.resolve({ items: [org("latest", "Latest Agency")], total: 1 })
        await screen.findByText("Latest Agency")

        // Stale in-flight response arrives late and must be ignored.
        requests[1]?.resolve({ items: [org("stale", "Stale Agency")], total: 1 })

        await waitFor(() => {
            expect(screen.getByText("Latest Agency")).toBeInTheDocument()
            expect(screen.queryByText("Stale Agency")).not.toBeInTheDocument()
        })
    })

    it("reuses fresh agency results when the page remounts", async () => {
        mockListOrganizations.mockResolvedValue({
            items: [org("cached", "Cached Agency")],
            total: 1,
        })
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false } },
        })

        const firstView = renderAgenciesPage(queryClient)
        expect(await screen.findByText("Cached Agency")).toBeInTheDocument()
        expect(mockListOrganizations).toHaveBeenCalledTimes(1)

        firstView.unmount()
        renderAgenciesPage(queryClient)

        expect(screen.getByText("Cached Agency")).toBeInTheDocument()
        expect(mockListOrganizations).toHaveBeenCalledTimes(1)
    })
})
