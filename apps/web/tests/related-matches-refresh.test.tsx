import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, expect, it, vi } from "vitest"

import { RelatedMatchesCard } from "@/components/matches/RelatedMatchesCard"
import { useCreateMatch } from "@/lib/hooks/use-matches"

const listMatches = vi.fn()
const createMatch = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}))

vi.mock("@/lib/api/matches", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/matches")>("@/lib/api/matches")
    return {
        ...actual,
        listMatches: (...args: unknown[]) => listMatches(...args),
        createMatch: (...args: unknown[]) => createMatch(...args),
    }
})

const proposedMatch = {
    id: "match1",
    match_number: "M10042",
    match_kind: "surrogate",
    status: "under_review",
    surrogate_name: "Jane Doe",
    ip_name: "John Smith",
    proposed_at: "2026-09-26T12:00:00Z",
}

function CreateMatchProbe() {
    const createMatchMutation = useCreateMatch()
    return (
        <button
            type="button"
            onClick={() => { void createMatchMutation.mutateAsync({ surrogate_id: "surrogate1", intended_parent_id: "ip1" }) }}
        >
            Propose
        </button>
    )
}

describe("Related Matches after a proposal", () => {
    it("refetches the intended parent's related matches when a match is created", async () => {
        listMatches.mockResolvedValueOnce({ items: [], total: 0, page: 1, per_page: 5, pages: 0 })
        listMatches.mockResolvedValueOnce({ items: [proposedMatch], total: 1, page: 1, per_page: 5, pages: 1 })
        createMatch.mockResolvedValue(proposedMatch)
        const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 60_000 } } })

        render(
            <QueryClientProvider client={client}>
                <RelatedMatchesCard kind="intended_parent" recordId="ip1" name="John Smith" canView canPropose />
                <CreateMatchProbe />
            </QueryClientProvider>,
        )
        expect(await screen.findByText("No matches yet.")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Propose" }))

        await waitFor(() => expect(screen.getByText(/M10042/)).toBeInTheDocument())
        expect(createMatch).toHaveBeenCalledOnce()
        expect(listMatches).toHaveBeenLastCalledWith({ intended_parent_id: "ip1", page: 1, per_page: 5 })
    })
})
