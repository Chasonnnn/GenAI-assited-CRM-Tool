import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom"

import { NewMatchDialog } from "@/components/matches/NewMatchDialog"
import { ApiError } from "@/lib/api"

const mockPush = vi.fn()
const mockMutateAsync = vi.fn()
const mockToastSuccess = vi.fn()
const mockUseSurrogates = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: mockPush, replace: vi.fn() }),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: { success: (...args: unknown[]) => mockToastSuccess(...args), error: vi.fn() },
}))

vi.mock("@/lib/hooks/use-matches", () => ({
    useCreateMatch: () => ({ mutateAsync: mockMutateAsync, isPending: false }),
}))

vi.mock("@/lib/hooks/use-surrogates", () => ({
    useSurrogates: (...args: unknown[]) => mockUseSurrogates(...args),
}))

vi.mock("@/lib/hooks/use-intended-parents", () => ({
    useIntendedParents: () => ({
        data: { items: [{ id: "ip_1", full_name: "Pat Parent", email: null, intended_parent_number: "I10001" }] },
        isLoading: false,
    }),
}))

const eligibleStage = {
    id: "stage-ready",
    stage_key: "ready_to_match",
    slug: "matching_queue",
    label: "Matching Queue",
    color: "#0ea5e9",
    order: 1,
    stage_type: "post_approval",
    is_active: true,
    system_role: "handoff",
    semantics: { capabilities: { eligible_for_matching: true } },
}

const matchedStage = {
    id: "stage-matched",
    stage_key: "matched",
    slug: "match_confirmed",
    label: "Matched",
    color: "#10b981",
    order: 2,
    stage_type: "post_approval",
    is_active: true,
    system_role: "matched",
    semantics: { capabilities: { eligible_for_matching: false } },
}

vi.mock("@/lib/hooks/use-pipelines", () => ({
    useDefaultPipeline: () => ({ data: { id: "pipeline-1", stages: [eligibleStage, matchedStage] }, isLoading: false }),
}))

async function chooseOption(comboboxName: RegExp, optionName: RegExp) {
    fireEvent.mouseDown(screen.getByRole("combobox", { name: comboboxName }))
    const option = await screen.findByRole("option", { name: optionName })
    fireEvent.mouseMove(option)
    fireEvent.click(option)
    await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument())
}

describe("NewMatchDialog", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUseSurrogates.mockReturnValue({
            data: {
                items: [
                    { id: "sur_1", surrogate_number: "S10001", full_name: "Eligible Surrogate", stage_key: null, stage_slug: "matching_queue", state: "TX" },
                    { id: "sur_2", surrogate_number: "S10002", full_name: "Ineligible Surrogate", stage_key: null, stage_slug: "match_confirmed", state: "CA" },
                ],
            },
            isLoading: false,
        })
    })

    it("lists only surrogates in a stage that is eligible for matching", async () => {
        render(<NewMatchDialog open onOpenChange={vi.fn()} />)

        expect(screen.getByRole("dialog", { name: "New Match" })).toBeInTheDocument()
        fireEvent.mouseDown(screen.getByRole("combobox", { name: /surrogate \(matching queue only\)/i }))
        expect(await screen.findByRole("option", { name: /eligible surrogate/i })).toBeInTheDocument()
        expect(screen.queryByRole("option", { name: /ineligible surrogate/i })).not.toBeInTheDocument()
    })

    it("asks the API for surrogates in the eligible stage instead of filtering the first page", () => {
        render(<NewMatchDialog open onOpenChange={vi.fn()} />)

        expect(mockUseSurrogates).toHaveBeenCalledWith(
            { per_page: 100, stage_id: "stage-ready" },
            { enabled: true },
        )
    })

    it("focuses the surrogate picker on open, not Notes", async () => {
        render(<NewMatchDialog open onOpenChange={vi.fn()} />)

        const picker = screen.getByRole("combobox", { name: /surrogate \(matching queue only\)/i })
        await waitFor(() => expect(picker).toHaveFocus())
        expect(screen.getByRole("textbox", { name: /notes/i })).not.toHaveFocus()
    })

    it("focuses the dialog while surrogates load, not Notes", async () => {
        mockUseSurrogates.mockReturnValue({ data: undefined, isLoading: true })
        render(<NewMatchDialog open onOpenChange={vi.fn()} />)

        const dialog = screen.getByRole("dialog", { name: "New Match" })
        await waitFor(() => expect(dialog).toHaveFocus())
        expect(screen.getByRole("textbox", { name: /notes/i })).not.toHaveFocus()
    })

    it("creates the match, closes, and shows a toast with a View action", async () => {
        const onOpenChange = vi.fn()
        mockMutateAsync.mockResolvedValue({ id: "match-42", match_number: "M10042" })
        render(<NewMatchDialog open onOpenChange={onOpenChange} />)

        await chooseOption(/surrogate \(matching queue only\)/i, /eligible surrogate/i)
        await chooseOption(/intended parents/i, /pat parent/i)
        fireEvent.click(screen.getByRole("button", { name: "Create Match" }))

        await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
        expect(mockMutateAsync).toHaveBeenCalledWith({ surrogate_id: "sur_1", intended_parent_id: "ip_1" })
        expect(mockToastSuccess).toHaveBeenCalledWith(
            "Match M10042 proposed",
            expect.objectContaining({ action: expect.objectContaining({ label: "View" }) }),
        )
        const options = mockToastSuccess.mock.calls[0]?.[1] as { action: { onClick: () => void } }
        options.action.onClick()
        expect(mockPush).toHaveBeenCalledWith("/intended-parents/matches/match-42")
    })

    it("shows a sanitized error when the API fails", async () => {
        const onOpenChange = vi.fn()
        mockMutateAsync.mockRejectedValue(new ApiError(500, "Internal Server Error", "psycopg.errors.UniqueViolation"))
        render(<NewMatchDialog open onOpenChange={onOpenChange} />)

        await chooseOption(/surrogate \(matching queue only\)/i, /eligible surrogate/i)
        await chooseOption(/intended parents/i, /pat parent/i)
        fireEvent.click(screen.getByRole("button", { name: "Create Match" }))

        expect(await screen.findByText("Couldn't create match. Try again.")).toBeInTheDocument()
        expect(screen.queryByText(/UniqueViolation/)).not.toBeInTheDocument()
        expect(onOpenChange).not.toHaveBeenCalled()
    })
})
