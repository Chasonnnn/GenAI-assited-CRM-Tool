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
    {
        id: "stage_delivered",
        stage_key: "delivered",
        slug: "delivered",
        label: "Delivered",
        color: "#16a34a",
        order: 20,
        stage_type: "post_approval" as const,
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

    it("uses stage_key semantics when the On-Hold slug is renamed", async () => {
        const onSubmit = vi.fn().mockResolvedValue({ status: "applied" })

        render(
            <ChangeStageModal
                open
                onOpenChange={vi.fn()}
                stages={stages.map((stage) =>
                    stage.id === "stage_on_hold" ? { ...stage, slug: "paused_review" } : stage
                )}
                currentStageId="stage_new_unread"
                currentStageLabel="New Unread"
                onSubmit={onSubmit}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: /on-hold/i }))

        expect(screen.getByRole("button", { name: "Save Change" })).toBeDisabled()

        fireEvent.change(screen.getByLabelText(/reason/i), {
            target: { value: "Waiting for updated availability." },
        })

        fireEvent.click(screen.getByRole("button", { name: "Save Change" }))

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith({
                stage_id: "stage_on_hold",
                reason: "Waiting for updated availability.",
            })
        })
    })

    it("shows delivery fields when the delivered slug is renamed", () => {
        render(
            <ChangeStageModal
                open
                onOpenChange={vi.fn()}
                stages={stages.map((stage) =>
                    stage.id === "stage_delivered" ? { ...stage, slug: "birth_complete" } : stage
                )}
                currentStageId="stage_new_unread"
                currentStageLabel="New Unread"
                onSubmit={vi.fn().mockResolvedValue({ status: "applied" })}
                deliveryFieldsEnabled
            />
        )

        fireEvent.click(screen.getByRole("button", { name: /delivered/i }))

        expect(screen.getByLabelText(/baby gender/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/baby weight/i)).toBeInTheDocument()
    })

    it("shows approval copy for regressions without self-approval capability", () => {
        render(
            <ChangeStageModal
                open
                onOpenChange={vi.fn()}
                stages={stages}
                currentStageId="stage_delivered"
                currentStageLabel="Delivered"
                onSubmit={vi.fn().mockResolvedValue({ status: "pending_approval" })}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: /new unread/i }))

        expect(screen.getByText("Admin Approval Required")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Request Approval" })).toBeInTheDocument()
    })

    it("shows immediate-apply copy for regressions with self-approval capability", () => {
        render(
            <ChangeStageModal
                open
                onOpenChange={vi.fn()}
                stages={stages}
                currentStageId="stage_delivered"
                currentStageLabel="Delivered"
                canSelfApproveRegression
                onSubmit={vi.fn().mockResolvedValue({ status: "applied" })}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: /new unread/i }))

        expect(screen.getByText("Earlier Stage Change")).toBeInTheDocument()
        expect(
            screen.getByText(/you can apply this earlier stage change immediately/i)
        ).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Save Change" })).toBeInTheDocument()
        expect(screen.queryByText("Admin Approval Required")).not.toBeInTheDocument()
    })
})
