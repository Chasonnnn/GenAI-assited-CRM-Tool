import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { ChangeStageModal } from "@/components/surrogates/ChangeStageModal"

const stages = [
    {
        id: "stage_new_unread",
        stage_key: "new_unread",
        slug: "new_unread",
        label: "New Unread",
        color: "#3b82f6",
        order: 1,
        stage_type: "intake" as const,
        is_active: true,
    },
    {
        id: "stage_on_hold",
        stage_key: "on_hold",
        slug: "on_hold",
        label: "On-Hold",
        color: "#b4536a",
        order: 18,
        stage_type: "paused" as const,
        is_active: true,
    },
]

describe("ChangeStageModal", () => {
    it("requires a reason and submits follow-up months when moving to On-Hold", async () => {
        const onSubmit = vi.fn().mockResolvedValue({ status: "applied" })

        render(
            <ChangeStageModal
                open
                onOpenChange={vi.fn()}
                stages={stages}
                currentStageId="stage_new_unread"
                currentStageLabel="New Unread"
                onSubmit={onSubmit}
                onHoldFollowUpAssigneeLabel="Jane Owner"
            />
        )

        fireEvent.click(screen.getByRole("button", { name: /on-hold/i }))

        expect(screen.getByText("Follow-up reminder")).toBeInTheDocument()
        expect(screen.getByText(/assigned to jane owner/i)).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Save Change" })).toBeDisabled()

        fireEvent.click(screen.getByRole("button", { name: /3 months/i }))
        fireEvent.change(screen.getByLabelText(/reason/i), {
            target: { value: "Waiting for their next availability window." },
        })

        fireEvent.click(screen.getByRole("button", { name: "Save Change" }))

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith({
                stage_id: "stage_on_hold",
                reason: "Waiting for their next availability window.",
                on_hold_follow_up_months: 3,
            })
        })
    })

    it("treats the paused-from stage as a resume instead of a regression", () => {
        render(
            <ChangeStageModal
                open
                onOpenChange={vi.fn()}
                stages={stages}
                currentStageId="stage_on_hold"
                comparisonStageId="stage_new_unread"
                currentStageLabel="On-Hold"
                onSubmit={vi.fn().mockResolvedValue({ status: "applied" })}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: /new unread/i }))

        expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument()
        expect(screen.queryByText(/admin approval required/i)).not.toBeInTheDocument()
    })
})
