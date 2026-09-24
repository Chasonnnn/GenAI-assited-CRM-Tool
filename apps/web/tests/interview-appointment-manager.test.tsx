import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { InterviewAppointmentManager, localDateTimeToIso } from "@/components/surrogates/InterviewAppointmentManager"
import { formatSchedulingDate, formatSchedulingTime, schedulingTimezoneLabel } from "@/lib/scheduling-time"
import type { InterviewAppointmentState } from "@/lib/api/interview-appointment"

const mutateAsync = vi.fn()
const retryGoogleSync = vi.fn()
const refetch = vi.fn()
const useInterviewAppointment = vi.fn()
const slotStart = "2026-09-21T14:30:00.000Z"
const slotEnd = "2026-09-21T15:00:00.000Z"
const refetchSlots = vi.fn()

vi.mock("@/lib/hooks/use-interview-appointment", () => ({
    useInterviewAppointment: (...args: unknown[]) => useInterviewAppointment(...args),
    useInterviewSlots: () => ({ data: { slots: [{ start: slotStart, end: slotEnd }] }, isLoading: false, isFetching: false, isError: false, refetch: refetchSlots }),
    useManageInterviewAppointment: () => ({ mutateAsync, isPending: false }),
    useRetryInterviewAppointmentGoogleSync: () => ({ mutateAsync: retryGoogleSync, isPending: false }),
}))

vi.mock("@/lib/hooks/use-appointments", () => ({
    useRetryAppointmentGoogleSync: () => ({ mutate: vi.fn(), isPending: false }),
    useResolveAppointmentGoogleConflict: () => ({ mutate: vi.fn(), isPending: false }),
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
        external_sync_status: null,
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
        retryGoogleSync.mockReset().mockResolvedValue({})
        refetch.mockReset()
        useInterviewAppointment.mockReset()
        refetchSlots.mockReset()
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
        fireEvent.click(screen.getByRole("button", { name: "Cancel appointment" }))

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
        fireEvent.click(screen.getByRole("button", { name: "Cancel appointment" }))

        await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({
            action: "cancel",
            move_stage: false,
        })))
    })

    it("previews and books from Reschedule Needed while requesting the stage move", async () => {
        renderManager(activeState({ appointment: null }), rescheduleStage.id)
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))
        fireEvent.click(await screen.findByRole("button", { name: "Schedule appointment" }))
        expect(screen.getByRole("dialog")).toHaveClass("sm:max-w-2xl")

        fireEvent.click(screen.getByRole("button", { name: /2:30 PM|10:30 AM|7:30 AM|14:30/ }))
        fireEvent.click(screen.getByRole("button", { name: "Schedule & update stage" }))

        await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({
            action: "schedule",
            scheduled_start: slotStart,
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
        expect(screen.getByRole("alert")).toHaveTextContent("Choose a valid date and time.")
        expect(mutateAsync).not.toHaveBeenCalled()

        fireEvent.click(screen.getByRole("button", { name: "Choose a time outside availability" }))
        fireEvent.change(screen.getByLabelText(/Date and time/), { target: { value: "2026-09-18T08:00" } })
        fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "Staff override" } })
        fireEvent.click(screen.getByRole("button", { name: "Reschedule" }))
        expect(screen.getByRole("alert")).toHaveTextContent("Choose a future date and time.")
        expect(mutateAsync).not.toHaveBeenCalled()
    })

    it("returns to Interview Scheduled when rescheduling an existing appointment from Reschedule Needed", async () => {
        renderManager(activeState(), rescheduleStage.id)
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))
        fireEvent.click(await screen.findByRole("button", { name: "Reschedule" }))
        fireEvent.click(screen.getByRole("button", { name: "Choose a time outside availability" }))
        fireEvent.change(screen.getByLabelText(/Date and time/), { target: { value: "2026-09-22T10:15" } })
        fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "Staff override" } })
        fireEvent.click(screen.getByRole("button", { name: "Reschedule & update stage" }))
        await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({
            action: "reschedule", move_stage: true, expected_appointment_id: appointment.id,
        })))
    })

    it("uses the viewer timezone for both the summary and editor, not the client timezone", async () => {
        renderManager(activeState())
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
        const expected = `${formatSchedulingDate(appointment.scheduled_start, timezone)} · ${formatSchedulingTime(appointment.scheduled_start, timezone)} ${schedulingTimezoneLabel(timezone)}`
        expect(screen.getByText(expected)).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))
        fireEvent.click(await screen.findByRole("button", { name: "Reschedule" }))
        expect(screen.getByText(timezone.replaceAll("_", " "))).toBeInTheDocument()
        const local = new Date(appointment.scheduled_start)
        const pad = (value: number) => String(value).padStart(2, "0")
        expect(screen.queryByLabelText("Interview date and time")).not.toBeInTheDocument()
        expect(localDateTimeToIso(`2026-09-20T${pad(local.getHours())}:${pad(local.getMinutes())}`)).not.toBeNull()
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
        fireEvent.click(screen.getByRole("button", { name: "Cancel appointment" }))

        expect(await screen.findByRole("alert")).toHaveTextContent("Appointment was changed by another user.")
        expect(screen.getByRole("dialog")).toBeInTheDocument()
    })

    it("keeps the cancellation result visible when Google delivery fails and retries without a stage action", async () => {
        retryGoogleSync.mockResolvedValueOnce(activeState({
            appointment: { ...appointment, status: "cancelled" },
            external_sync_status: "pending",
        }))
        const rendered = renderManager(activeState({
            appointment: { ...appointment, status: "cancelled" },
            external_sync_status: "failed",
        }))
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))

        expect(await screen.findByText("Interview saved, but Google Calendar could not be updated. Retry the update.")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Retry Google update" })).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry Google update" }))

        await waitFor(() => expect(retryGoogleSync).toHaveBeenCalledWith(appointment.id))
        expect(mutateAsync).not.toHaveBeenCalled()
        useInterviewAppointment.mockReturnValue({
            data: activeState({ appointment: { ...appointment, status: "cancelled" }, external_sync_status: "pending" }),
            isLoading: false,
            isError: false,
            refetch,
        })
        rendered.rerender(<InterviewAppointmentManager surrogateId="surrogate-1" stageId={scheduledStage.id} />)
        expect(screen.getByText("Interview saved. Updating Google Calendar…")).toBeInTheDocument()
    })

    it("keeps the dialog open while pending delivery becomes completed", async () => {
        const rendered = renderManager(activeState({ external_sync_status: "pending" }))
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))
        expect(await screen.findByText("Interview saved. Updating Google Calendar…")).toBeInTheDocument()
        useInterviewAppointment.mockReturnValue({
            data: activeState({ external_sync_status: "completed" }),
            isLoading: false,
            isError: false,
            refetch,
        })
        rendered.rerender(<InterviewAppointmentManager surrogateId="surrogate-1" stageId={scheduledStage.id} />)
        expect(screen.getByRole("dialog")).toBeInTheDocument()
        expect(screen.getByText("Google Calendar is up to date.")).toBeInTheDocument()
    })

    it("keeps a Google conflict read-only", async () => {
        renderManager(activeState({ external_sync_status: "conflict" }))
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))
        expect(await screen.findByText("Google Calendar changed. This appointment needs manual review before further CRM changes.")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Reschedule" })).toBeDisabled()
        expect(screen.getByRole("button", { name: "Cancel appointment" })).toBeDisabled()
        expect(screen.queryByRole("button", { name: "Retry Google update" })).not.toBeInTheDocument()
        expect(mutateAsync).not.toHaveBeenCalled()
    })

    it("blocks new scheduling until a pending Google update resolves", async () => {
        renderManager(activeState({
            appointment: { ...appointment, status: "cancelled" },
            external_sync_status: "pending",
        }), rescheduleStage.id)
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))

        expect(await screen.findByText("Interview saved. Updating Google Calendar…")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Schedule appointment" })).toBeDisabled()
    })

    it("allows a new appointment after a cancelled V2 appointment finishes Google delivery", async () => {
        renderManager(activeState({
            appointment: {
                ...appointment,
                status: "cancelled",
                scheduling: {
                    revision: 4,
                    capabilities: { can_reschedule: false, can_cancel: false, can_retry_google_sync: false, can_resolve_google_conflict: false },
                    google_sync: { state: "completed", linked: true, error_code: null, conflict: null },
                },
            },
            external_sync_status: "completed",
        }), rescheduleStage.id)
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))

        expect(await screen.findByText("Google Calendar synced")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Schedule appointment" })).toBeEnabled()
    })

    it("blocks lifecycle actions while delivery failed but keeps the failed-only retry enabled", async () => {
        renderManager(activeState({ external_sync_status: "failed" }))
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))

        expect(await screen.findByRole("alert")).toHaveTextContent("Interview saved, but Google Calendar could not be updated.")
        expect(screen.getByRole("button", { name: "Reschedule" })).toBeDisabled()
        expect(screen.getByRole("button", { name: "Cancel appointment" })).toBeDisabled()
        expect(screen.getByRole("button", { name: "Retry Google update" })).toBeEnabled()
    })

    it("uses V2 cancellation capability during pending Google delivery", async () => {
        renderManager(activeState({
            appointment: {
                ...appointment,
                scheduling: {
                    revision: 3,
                    capabilities: { can_reschedule: false, can_cancel: true, can_retry_google_sync: false, can_resolve_google_conflict: false },
                    google_sync: { state: "pending", linked: true, error_code: null, conflict: null },
                },
            },
            external_sync_status: "pending",
        }))
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))
        expect(await screen.findByRole("button", { name: "Cancel appointment" })).toBeEnabled()
        fireEvent.click(screen.getByRole("button", { name: "Cancel appointment" }))
        expect(screen.getAllByRole("button", { name: "Cancel appointment" }).at(-1)).toBeEnabled()
    })

    it("keeps V2 cancellation disabled when the server denies it", async () => {
        renderManager(activeState({
            appointment: {
                ...appointment,
                scheduling: {
                    revision: 3,
                    capabilities: { can_reschedule: false, can_cancel: false, can_retry_google_sync: false, can_resolve_google_conflict: false },
                    google_sync: { state: "pending", linked: true, error_code: null, conflict: null },
                },
            },
            external_sync_status: "pending",
        }))
        fireEvent.click(screen.getByRole("button", { name: "Manage" }))
        expect(await screen.findByRole("button", { name: "Cancel appointment" })).toBeDisabled()
    })
})
