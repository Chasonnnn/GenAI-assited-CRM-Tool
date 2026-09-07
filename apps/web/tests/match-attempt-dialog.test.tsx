import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MatchAttemptDialog } from "@/components/matches/MatchAttemptDialog"
import { CompleteMatchDialog } from "@/components/matches/CompleteMatchDialog"

const save = vi.fn()
vi.mock("@/lib/hooks/use-matches", () => ({ useSaveMatchAttempt: () => ({ mutateAsync: save, isPending: false }) }))

describe("match attempt lifecycle controls", () => {
    beforeEach(() => { save.mockReset(); save.mockResolvedValue({ id: "attempt1" }) })
    it("renders enum labels and creates an attempt in the explicit match", async () => {
        const onClose = vi.fn()
        render(<MatchAttemptDialog matchId="match1" kind="surrogate" onClose={onClose} />)
        expect(screen.getByRole("combobox", { name: "Type" })).toHaveTextContent("Embryo Transfer")
        expect(screen.getByRole("combobox", { name: "Status" })).toHaveTextContent("Planned")
        fireEvent.click(screen.getByRole("button", { name: "Save Attempt" }))
        await waitFor(() => expect(save).toHaveBeenCalledWith({ data: { attempt_type: "embryo_transfer", status: "planned", started_at: null, ended_at: null, outcome: null } }))
        expect(onClose).toHaveBeenCalledOnce()
    })
    it("preserves the attempt identity when updating dates and outcome", async () => {
        render(<MatchAttemptDialog matchId="match1" kind="donor" attempt={{ id: "attempt2", match_id: "match1", sequence: 2, attempt_type: "collection", status: "in_progress", started_at: "2026-09-05", ended_at: null, outcome: null }} onClose={vi.fn()} />)
        fireEvent.change(screen.getByLabelText("Outcome"), { target: { value: "Collection complete" } })
        fireEvent.click(screen.getByRole("button", { name: "Save Attempt" }))
        await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({ attemptId: "attempt2", data: expect.objectContaining({ attempt_type: "collection", outcome: "Collection complete" }) })))
    })
    it("rejects invalid date ordering without submitting", () => {
        render(<MatchAttemptDialog matchId="match1" kind="donor" onClose={vi.fn()} />)
        fireEvent.change(screen.getByLabelText("Start Date"), { target: { value: "2026-09-06" } })
        fireEvent.change(screen.getByLabelText("End Date"), { target: { value: "2026-09-05" } })
        fireEvent.click(screen.getByRole("button", { name: "Save Attempt" }))
        expect(screen.getByRole("alert")).toHaveTextContent("End date must be on or after start date")
        expect(save).not.toHaveBeenCalled()
    })
    it("keeps completion dialog open when an active attempt prevents closure", async () => {
        const close = vi.fn()
        const complete = vi.fn().mockRejectedValue(new Error("Finish active attempts before completing the match"))
        render(<CompleteMatchDialog onClose={close} onComplete={complete} isPending={false} />)
        fireEvent.change(screen.getByLabelText("Outcome"), { target: { value: "Finished" } })
        fireEvent.click(screen.getByRole("button", { name: "Complete Match" }))
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Finish active attempts"))
        expect(close).not.toHaveBeenCalled()
    })
})
