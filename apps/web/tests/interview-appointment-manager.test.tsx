import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { InterviewAppointmentManager, localDateTimeToIso } from "@/components/surrogates/InterviewAppointmentManager"
import type { InterviewAppointmentState } from "@/lib/api/interview-appointment"

const mutateAsync = vi.fn()
const refetch = vi.fn()
const useInterviewAppointment = vi.fn()

vi.mock("@/lib/hooks/use-interview-appointment", () => ({
    useInterviewAppointment: (...args: unknown[]) => useInterviewAppointment(...args),
    useManageInterviewAppointment: () => ({ mutateAsync, isPending: false }),
}))

const scheduledStage = { id: "interview-scheduled", label: "Interview Scheduled", color: "#0f766e" }
const rescheduleStage = { id: "reschedule-needed", label: "Reschedule Needed", color: "#fde68a" }
const appointment = {
    id: "appointment-1",
    scheduled_start: "2026-09-20T15:00:00.000Z",
    scheduled_end: "2026-09-20T16:00:00.000Z",
    client_timezone: "Pacific/Honolulu",
    status: "confirmed",
    meeting_started_at: null,
    meeting_ended_at: null,
}

function renderManager(state: InterviewAppointmentState, stageId = scheduledStage.id) {
    useInterviewAppointment.mockReturnValue({ data: state, isLoading: false, isError: false, refetch })
    return render(<InterviewAppointmentManager surrogateId="surrogate-1" stageId={stageId} />)
}

function activeState(overrides: Partial<InterviewAppointmentState> = {}): InterviewAppointmentState {
    return {
        appointment,
        can_manage: true,
        scheduled_stage: scheduledStage,
        reschedule_stage: rescheduleStage,
        ...overrides,
    }
}

async function openCancel() {
    fireEvent.click(screen.getByRole("button", { name: "Manage" }))
    fireEvent.click(await screen.findByRole("button", { name: "Cancel appointment" }))
}

describe("InterviewAppointmentManager", () => {
    beforeEach(() => {
        vi.useFakeTimers({ shouldAdvanceTime: true })
        vi.setSystemTime(new Date("2026-09-19T09:00:00.000Z"))
        mutateAsync.mockReset().mockResolvedValue({})
        refetch.mockReset()
        useInterviewAppointment.mockReset()
    })

    it("groups Reschedule, Cancel appointment, and Done in the same action row", async () => {
        renderManager(activeState())
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))
        const dialog = await screen.findByRole("dialog", { name: "Manage appointment" })
        const footer = dialog.querySelector('[data-slot="dialog-footer"]')
        expect(footer).not.toBeNull()
        expect(within(footer as HTMLElement).getAllByRole("button").map((button) => button.textContent)).toEqual([
            "Reschedule", "Cancel appointment", "Done",
        ])
        fireEvent.click(within(footer as HTMLElement).getByRole("button", { name: "Done" }))
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    })

    it("cancels with an explicit move to Reschedule Needed choice", async () => {
        renderManager(activeState())
        await openCancel()

        expect(screen.getByRole("radio", { name: /move to reschedule needed/i })).toBeChecked()
        expect(screen.getByText("Stage will change to Reschedule Needed when you confirm.")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Confirm cancellation" }))

        await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({
            action: "cancel",
            move_stage: true,
            expected_stage_id: scheduledStage.id,
            expected_appointment_id: appointment.id,
            expected_scheduled_start: appointment.scheduled_start,
        }))
    })

    it("cancels while explicitly keeping the current stage", async () => {
        renderManager(activeState())
        await openCancel()

        fireEvent.click(screen.getByRole("radio", { name: "Keep current stage" }))
        expect(screen.getByText("Stage will stay unchanged.")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Confirm cancellation" }))

        await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({
            action: "cancel",
            move_stage: false,
        })))
    })

    it("previews and books from Reschedule Needed while requesting the stage move", async () => {
        renderManager(activeState({ appointment: null }), rescheduleStage.id)
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))
        fireEvent.click(await screen.findByRole("button", { name: "Schedule appointment" }))

        expect(screen.getByText("Reschedule Needed")).toBeInTheDocument()
        expect(screen.getByText("Interview Scheduled")).toBeInTheDocument()
        expect(screen.getByText("Stage will change to Interview Scheduled when you confirm.")).toBeInTheDocument()
        const input = screen.getByLabelText("Interview date and time")
        fireEvent.change(input, { target: { value: "2026-09-21T14:30" } })
        fireEvent.click(screen.getByRole("button", { name: "Schedule & update stage" }))

        await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({
            action: "schedule",
            scheduled_start: localDateTimeToIso("2026-09-21T14:30"),
            move_stage: true,
            expected_stage_id: rescheduleStage.id,
            expected_appointment_id: null,
            expected_scheduled_start: null,
        }))
    })

    it("rejects an unchanged reschedule and a past date without submitting", async () => {
        renderManager(activeState())
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))
        fireEvent.click(await screen.findByRole("button", { name: "Reschedule" }))

        fireEvent.click(screen.getByRole("button", { name: "Reschedule" }))
        expect(screen.getByRole("alert")).toHaveTextContent("Choose a different appointment time.")
        expect(mutateAsync).not.toHaveBeenCalled()

        fireEvent.change(screen.getByLabelText("Interview date and time"), { target: { value: "2026-09-18T08:00" } })
        fireEvent.click(screen.getByRole("button", { name: "Reschedule" }))
        expect(screen.getByRole("alert")).toHaveTextContent("Choose a future date and time.")
        expect(mutateAsync).not.toHaveBeenCalled()
    })

    it("returns to Interview Scheduled when rescheduling an existing appointment from Reschedule Needed", async () => {
        renderManager(activeState(), rescheduleStage.id)
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))
        fireEvent.click(await screen.findByRole("button", { name: "Reschedule" }))
        expect(screen.getByText("Interview Scheduled")).toHaveStyle({ backgroundColor: scheduledStage.color })
        fireEvent.change(screen.getByLabelText("Interview date and time"), { target: { value: "2026-09-22T10:15" } })
        fireEvent.click(screen.getByRole("button", { name: "Reschedule & update stage" }))
        await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({
            action: "reschedule", move_stage: true, expected_appointment_id: appointment.id,
        })))
    })

    it("uses the viewer timezone for both the summary and editor, not the client timezone", async () => {
        renderManager(activeState())
        const expected = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(appointment.scheduled_start))
        expect(screen.getByText(expected)).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))
        fireEvent.click(await screen.findByRole("button", { name: "Reschedule" }))
        expect(screen.getByText(`Your timezone: ${Intl.DateTimeFormat().resolvedOptions().timeZone}`)).toBeInTheDocument()
        const local = new Date(appointment.scheduled_start)
        const pad = (value: number) => String(value).padStart(2, "0")
        expect(screen.getByLabelText("Interview date and time")).toHaveValue(`2026-09-20T${pad(local.getHours())}:${pad(local.getMinutes())}`)
        expect(screen.getByText("Stage will stay unchanged.")).toBeInTheDocument()
    })

    it("disables management for read-only users", () => {
        renderManager(activeState({ can_manage: false }))
        expect(screen.getByRole("button", { name: "Manage" })).toBeDisabled()
    })

    it("keeps the inline trigger disabled while appointment data loads", () => {
        useInterviewAppointment.mockReturnValue({ data: undefined, isLoading: true, isError: false, refetch })
        render(<InterviewAppointmentManager surrogateId="surrogate-1" stageId={scheduledStage.id} triggerOnly />)

        expect(screen.getByRole("button", { name: "Loading interview appointment" })).toBeDisabled()
        expect(screen.queryByText("Loading appointment")).not.toBeInTheDocument()
    })

    it("offers a compact retry action when the inline appointment query fails", () => {
        useInterviewAppointment.mockReturnValue({ data: undefined, isLoading: false, isError: true, refetch })
        render(<InterviewAppointmentManager surrogateId="surrogate-1" stageId={scheduledStage.id} triggerOnly />)

        fireEvent.click(screen.getByRole("button", { name: "Retry appointment" }))
        expect(refetch).toHaveBeenCalledOnce()
        expect(screen.queryByText("Appointment unavailable")).not.toBeInTheDocument()
    })

    it("preserves read-only access in the inline trigger", () => {
        useInterviewAppointment.mockReturnValue({ data: activeState({ can_manage: false }), isLoading: false, isError: false, refetch })
        render(<InterviewAppointmentManager surrogateId="surrogate-1" stageId={scheduledStage.id} triggerOnly />)

        expect(screen.getByRole("button", { name: "Manage" })).toBeDisabled()
        expect(screen.queryByText("Interview appointment")).not.toBeInTheDocument()
    })

    it("offers retry when loading the appointment fails", () => {
        useInterviewAppointment.mockReturnValue({ data: undefined, isLoading: false, isError: true, refetch })
        render(<InterviewAppointmentManager surrogateId="surrogate-1" stageId={scheduledStage.id} />)

        expect(screen.getByText("Appointment unavailable")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(refetch).toHaveBeenCalledOnce()
    })

    it("keeps the dialog open and presents mutation errors", async () => {
        mutateAsync.mockRejectedValueOnce(new Error("Appointment was changed by another user."))
        renderManager(activeState())
        await openCancel()
        fireEvent.click(screen.getByRole("button", { name: "Confirm cancellation" }))

        expect(await screen.findByRole("alert")).toHaveTextContent("Appointment was changed by another user.")
        expect(screen.getByRole("dialog")).toBeInTheDocument()
    })
})
