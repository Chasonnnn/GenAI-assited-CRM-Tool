import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"

import AgenciesPage from "../app/ops/agencies/page"

const mockListOrganizations = vi.fn()
const mockPush = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: mockPush }),
}))

vi.mock("@/lib/api/platform", () => ({
    listOrganizations: (...args: unknown[]) => mockListOrganizations(...args),
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
    beforeEach(() => {
        mockListOrganizations.mockReset()
        mockPush.mockReset()
    })

    it("ignores stale list responses and keeps latest search results", async () => {
        const requests: Array<Deferred<{ items: OrganizationSummary[]; total: number }>> = []
        mockListOrganizations.mockImplementation(() => {
            const next = deferred<{ items: OrganizationSummary[]; total: number }>()
            requests.push(next)
            return next.promise
        })

        render(<AgenciesPage />)

        await waitFor(() => expect(requests.length).toBe(1))
        requests[0]?.resolve({ items: [org("init", "Initial Agency")], total: 1 })
        await screen.findByText("Initial Agency")

        const searchInput = screen.getByPlaceholderText("Search by name or slug...")
        fireEvent.change(searchInput, { target: { value: "a" } })

        // Wait for debounce
        await new Promise((resolve) => setTimeout(resolve, 600))

        await waitFor(() => expect(requests.length).toBe(2))

        fireEvent.change(searchInput, { target: { value: "ab" } })

        // Wait for debounce
        await new Promise((resolve) => setTimeout(resolve, 600))

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
})
