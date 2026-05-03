import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { addDays, format } from "date-fns"
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
        id: "stage_interview_scheduled",
        stage_key: "interview_scheduled",
        slug: "interview_scheduled",
        label: "Interview Scheduled",
        color: "#0f766e",
        order: 4,
        stage_type: "intake" as const,
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

    it("uses placeholder hints for interview time without defaulting the value", async () => {
        const onSubmit = vi.fn().mockResolvedValue({ status: "applied" })

        render(
            <ChangeStageModal
                open
                onOpenChange={vi.fn()}
                stages={stages}
                currentStageId="stage_new_unread"
                currentStageLabel="New Unread"
                onSubmit={onSubmit}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: /interview scheduled/i }))

        expect(screen.getByText("Interview appointment")).toBeInTheDocument()
        expect(screen.getByRole("region", { name: /interview appointment/i })).not.toHaveClass("p-3")
        expect(screen.queryByText("Hour")).not.toBeInTheDocument()
        expect(screen.queryByText("Minute")).not.toBeInTheDocument()
        expect(screen.queryByText("AM/PM")).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: /switch interview time to am/i })).toHaveTextContent("PM")
        expect(screen.getByLabelText(/interview hour/i)).toHaveValue("")
        expect(screen.getByLabelText(/interview minute/i)).toHaveValue("")
        expect(screen.getByRole("button", { name: "Save Change" })).toBeDisabled()

        const interviewDate = addDays(new Date(), 7)
        fireEvent.click(screen.getByRole("button", { name: /select date/i }))
        const dayButton = screen
            .getAllByText(format(interviewDate, "d"))
            .map((element) => element.closest("button"))
            .find((button): button is HTMLButtonElement => Boolean(button) && !button.disabled)
        expect(dayButton).toBeDefined()
        fireEvent.click(dayButton!)

        expect(screen.getByRole("button", { name: "Save Change" })).toBeDisabled()

        fireEvent.change(screen.getByLabelText(/interview hour/i), {
            target: { value: "1" },
        })
        const minuteInput = screen.getByLabelText(/interview minute/i)
        fireEvent.change(minuteInput, { target: { value: "1" } })
        expect(minuteInput).toHaveValue("1")
        fireEvent.change(minuteInput, { target: { value: "15" } })
        expect(minuteInput).toHaveValue("15")
        fireEvent.click(screen.getByRole("button", { name: "Save Change" }))

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith({
                stage_id: "stage_interview_scheduled",
                interview_scheduled_at: `${format(interviewDate, "yyyy-MM-dd")}T13:15:00`,
            })
        })
    })

    it("toggles interview meridiem with one compact control", async () => {
        const onSubmit = vi.fn().mockResolvedValue({ status: "applied" })

        render(
            <ChangeStageModal
                open
                onOpenChange={vi.fn()}
                stages={stages}
                currentStageId="stage_new_unread"
                currentStageLabel="New Unread"
                onSubmit={onSubmit}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: /interview scheduled/i }))

        const meridiemToggle = screen.getByRole("button", { name: /switch interview time to am/i })
        fireEvent.click(meridiemToggle)
        expect(screen.getByRole("button", { name: /switch interview time to pm/i })).toHaveTextContent("AM")
        expect(screen.queryByRole("button", { name: "PM" })).not.toBeInTheDocument()

        const interviewDate = addDays(new Date(), 7)
        fireEvent.click(screen.getByRole("button", { name: /select date/i }))
        const dayButton = screen
            .getAllByText(format(interviewDate, "d"))
            .map((element) => element.closest("button"))
            .find((button): button is HTMLButtonElement => Boolean(button) && !button.disabled)
        expect(dayButton).toBeDefined()
        fireEvent.click(dayButton!)

        fireEvent.change(screen.getByLabelText(/interview hour/i), {
            target: { value: "1" },
        })
        fireEvent.change(screen.getByLabelText(/interview minute/i), {
            target: { value: "15" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save Change" }))

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith({
                stage_id: "stage_interview_scheduled",
                interview_scheduled_at: `${format(interviewDate, "yyyy-MM-dd")}T01:15:00`,
            })
        })
    })

    it("keeps interview time entry constrained to hour and minute fields", () => {
        render(
            <ChangeStageModal
                open
                onOpenChange={vi.fn()}
                stages={stages}
                currentStageId="stage_new_unread"
                currentStageLabel="New Unread"
                onSubmit={vi.fn().mockResolvedValue({ status: "applied" })}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: /interview scheduled/i }))

        const hourInput = screen.getByLabelText(/interview hour/i)
        const minuteInput = screen.getByLabelText(/interview minute/i)

        fireEvent.change(hourInput, { target: { value: "1-45" } })
        expect(hourInput).toHaveValue("1")
        expect(minuteInput).toHaveValue("45")

        fireEvent.change(minuteInput, { target: { value: "75" } })
        expect(screen.getByText(/enter an hour from 1-12 and minutes from 00-59/i)).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Save Change" })).toBeDisabled()
    })
})
