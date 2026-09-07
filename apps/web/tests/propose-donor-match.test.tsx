import { render, screen, waitFor, fireEvent } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ProposeMatchFromIPDialog } from "@/components/matches/ProposeMatchFromIPDialog"

const create = vi.fn()
const donors = vi.fn()
vi.mock("@/lib/hooks/use-matches", () => ({ useCreateMatch: () => ({ mutateAsync: create, isPending: false }) }))
vi.mock("@/lib/hooks/use-surrogates", () => ({ useSurrogates: () => ({ data: { items: [] }, isLoading: false }) }))
vi.mock("@/lib/hooks/use-pipelines", () => ({ useDefaultPipeline: () => ({ data: { stages: [] } }) }))
vi.mock("@/lib/api/donors", () => ({ listDonors: (...args: unknown[]) => donors(...args) }))

describe("donor proposal from an IP", () => {
    beforeEach(() => {
        create.mockReset(); create.mockResolvedValue({ id: "match1" })
        donors.mockReset(); donors.mockResolvedValue({ items: [{ id: "donor1", donor_number: "D10001", full_name: "Taylor Donor" }] })
    })
    it("loads donors only after selecting donor kind and sends the donor identity", async () => {
        render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ProposeMatchFromIPDialog open onOpenChange={vi.fn()} intendedParentId="ip1" /></QueryClientProvider>)
        expect(donors).not.toHaveBeenCalled()
        fireEvent.click(screen.getByRole("combobox", { name: "Match Kind" }))
        fireEvent.mouseMove(screen.getByRole("option", { name: "Donor" }))
        fireEvent.click(screen.getByRole("option", { name: "Donor" }))
        await waitFor(() => expect(donors).toHaveBeenCalledWith({ donor_type: "egg", per_page: 100 }))
        fireEvent.click(await screen.findByRole("combobox", { name: "Donor" }))
        fireEvent.mouseMove(screen.getByRole("option", { name: "Taylor Donor #D10001" }))
        fireEvent.click(screen.getByRole("option", { name: "Taylor Donor #D10001" }))
        expect(screen.getByRole("combobox", { name: "Donor" })).toHaveTextContent("Taylor Donor")
        fireEvent.click(screen.getByRole("button", { name: "Propose Match" }))
        await waitFor(() => expect(create).toHaveBeenCalledWith({ match_kind: "donor", donor_id: "donor1", intended_parent_id: "ip1" }))
    })
})
