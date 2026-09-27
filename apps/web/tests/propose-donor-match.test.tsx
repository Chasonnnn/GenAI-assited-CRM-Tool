import { render, screen, waitFor, fireEvent } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ProposeMatchFromIPDialog } from "@/components/matches/ProposeMatchFromIPDialog"
import { ApiError } from "@/lib/api"

const create = vi.fn()
const donors = vi.fn()
const push = vi.fn()
const toastSuccess = vi.fn()
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }))
vi.mock("@/components/ui/toast", () => ({ toast: { success: (...args: unknown[]) => toastSuccess(...args), error: vi.fn() } }))
vi.mock("@/lib/hooks/use-matches", () => ({ useCreateMatch: () => ({ mutateAsync: create, isPending: false }) }))
vi.mock("@/lib/hooks/use-surrogates", () => ({ useSurrogates: () => ({ data: { items: [] }, isLoading: false }) }))
vi.mock("@/lib/hooks/use-pipelines", () => ({ useDefaultPipeline: () => ({ data: { stages: [] } }) }))
vi.mock("@/lib/api/donors", () => ({ listDonors: (...args: unknown[]) => donors(...args) }))

describe("donor proposal from an IP", () => {
    beforeEach(() => {
        create.mockReset(); create.mockResolvedValue({ id: "match1", match_number: "M10042" })
        donors.mockReset(); donors.mockResolvedValue({ items: [{ id: "donor1", donor_number: "D10001", full_name: "Taylor Donor" }] })
        push.mockReset(); toastSuccess.mockReset()
    })

    async function proposeDonorMatch() {
        const onOpenChange = vi.fn()
        render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ProposeMatchFromIPDialog open onOpenChange={onOpenChange} intendedParentId="ip1" /></QueryClientProvider>)
        fireEvent.click(screen.getByRole("combobox", { name: "Match Kind" }))
        fireEvent.mouseMove(screen.getByRole("option", { name: "Donor" }))
        fireEvent.click(screen.getByRole("option", { name: "Donor" }))
        fireEvent.click(await screen.findByRole("combobox", { name: "Donor" }))
        fireEvent.mouseMove(await screen.findByRole("option", { name: "Taylor Donor #D10001" }))
        fireEvent.click(screen.getByRole("option", { name: "Taylor Donor #D10001" }))
        fireEvent.click(screen.getByRole("button", { name: "Propose Match" }))
        return { onOpenChange }
    }

    it("names the new match in the success toast with a View action", async () => {
        const { onOpenChange } = await proposeDonorMatch()

        await waitFor(() => expect(toastSuccess).toHaveBeenCalledOnce())
        const [title, options] = toastSuccess.mock.calls[0] as [string, { action: { label: string; onClick: () => void } }]
        expect(title).toBe("Match M10042 proposed")
        expect(options.action.label).toBe("View")
        options.action.onClick()
        expect(push).toHaveBeenCalledWith("/intended-parents/matches/match1")
        expect(onOpenChange).toHaveBeenCalledWith(false)
    })

    it("shows the API conflict message and hides server error details", async () => {
        create.mockRejectedValueOnce(new ApiError(409, "Conflict", "Intended parent already has an active match"))
        await proposeDonorMatch()
        expect(await screen.findByText("Intended parent already has an active match")).toBeInTheDocument()

        create.mockRejectedValueOnce(new ApiError(500, "Server Error", "Traceback: KeyError"))
        fireEvent.click(screen.getByRole("button", { name: "Propose Match" }))
        expect(await screen.findByText("Couldn't propose match. Try again.")).toBeInTheDocument()
        expect(screen.queryByText(/Traceback/)).not.toBeInTheDocument()
        expect(toastSuccess).not.toHaveBeenCalled()
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
