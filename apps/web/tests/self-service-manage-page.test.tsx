import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import ManageAppointmentPage from "../app/book/self-service/[orgId]/manage/[token]/page"

const getAppointmentForManageMock = vi.fn()
const getRescheduleSlotsByTokenMock = vi.fn()
const rescheduleByManageTokenMock = vi.fn()
const cancelByManageTokenMock = vi.fn()
const ORG_ID = "11111111-1111-4111-8111-111111111111"
const TOKEN = "token-1"

vi.unmock("@tanstack/react-query")

vi.mock("@/lib/api/appointments", () => ({
    getAppointmentForManage: (orgId: string, token: string) =>
        getAppointmentForManageMock(orgId, token),
    getRescheduleSlotsByToken: (
        orgId: string,
        token: string,
        dateStart: string,
        dateEnd?: string,
        clientTimezone?: string
    ) => getRescheduleSlotsByTokenMock(orgId, token, dateStart, dateEnd, clientTimezone),
    rescheduleByManageToken: (orgId: string, token: string, scheduledStart: string) =>
        rescheduleByManageTokenMock(orgId, token, scheduledStart),
    cancelByManageToken: (orgId: string, token: string, reason?: string) =>
        cancelByManageTokenMock(orgId, token, reason),
}))

const APPOINTMENT = {
    id: "appt-1",
    appointment_type_name: "Initial Consultation",
    staff_name: "Dr. Smith",
    client_name: "Jordan Client",
    client_email: "jordan@example.com",
    scheduled_start: "2026-06-03T16:00:00.000Z",
    scheduled_end: "2026-06-03T16:30:00.000Z",
    duration_minutes: 30,
    meeting_mode: "zoom",
    meeting_location: "Zoom",
    dial_in_number: null,
    status: "confirmed",
    client_timezone: "America/New_York",
    zoom_join_url: null,
    google_meet_url: null,
}

async function renderManagePage(
    searchParams: Record<string, string> = {},
    routeParams: { orgId: string; token: string } = { orgId: ORG_ID, token: TOKEN }
) {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    })
    let view!: ReturnType<typeof render>
    await act(async () => {
        view = render(
            <QueryClientProvider client={queryClient}>
                <React.Suspense fallback={<div>Loading</div>}>
                    <ManageAppointmentPage
                        params={Promise.resolve(routeParams)}
                        searchParams={Promise.resolve(searchParams)}
                    />
                </React.Suspense>
            </QueryClientProvider>
        )
        await Promise.resolve()
    })
    return { view, queryClient }
}

describe("Self-service manage appointment page", () => {
    beforeEach(() => {
        vi.useFakeTimers({ shouldAdvanceTime: true })
        vi.setSystemTime(new Date("2026-06-01T12:00:00.000Z"))
        vi.clearAllMocks()
        getAppointmentForManageMock.mockResolvedValue(APPOINTMENT)
        getRescheduleSlotsByTokenMock.mockResolvedValue({
            slots: [
                {
                    start: "2026-06-04T16:00:00.000Z",
                    end: "2026-06-04T16:30:00.000Z",
                },
            ],
            appointment_type: null,
        })
        rescheduleByManageTokenMock.mockResolvedValue(APPOINTMENT)
        cancelByManageTokenMock.mockResolvedValue({ ...APPOINTMENT, status: "cancelled" })
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("renders invalid/expired token error state", async () => {
        getAppointmentForManageMock.mockRejectedValueOnce(new Error("Appointment not found"))

        await renderManagePage()

        expect(await screen.findByText("Unable to Manage Appointment")).toBeInTheDocument()
        expect(screen.getByText("Appointment not found")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument()
    })

    it("rejects a malformed management link before requesting appointment data", async () => {
        await renderManagePage({}, { orgId: "not-a-valid-org", token: "not-a-valid-token" })

        expect(await screen.findByText("Unable to Manage Appointment")).toBeInTheDocument()
        expect(screen.getByText("Invalid appointment management link")).toBeInTheDocument()
        expect(getAppointmentForManageMock).not.toHaveBeenCalled()
        expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument()
    })

    it("retries a failed initial appointment load", async () => {
        getAppointmentForManageMock
            .mockRejectedValueOnce(new TypeError("Failed to fetch"))
            .mockResolvedValueOnce(APPOINTMENT)

        await renderManagePage()
        expect(await screen.findByText("Unable to load this appointment. Please try again.")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))

        expect(await screen.findByText("Manage Appointment")).toBeInTheDocument()
        expect(getAppointmentForManageMock).toHaveBeenCalledTimes(2)
    })

    it("completes cancel flow", async () => {
        await renderManagePage({ action: "cancel" })

        expect(await screen.findByText("Manage Appointment")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Cancel Appointment" }))

        await waitFor(() => {
            expect(cancelByManageTokenMock).toHaveBeenCalledWith(ORG_ID, TOKEN, undefined)
        })

        expect(await screen.findByText("Appointment Cancelled")).toBeInTheDocument()
    })

    it("shows only actions allowed by the manage token and no internal sync controls", async () => {
        getAppointmentForManageMock.mockResolvedValue({
            ...APPOINTMENT,
            manage_actions: { can_reschedule: true, can_cancel: false },
            scheduling: {
                revision: 1,
                capabilities: { can_reschedule: true, can_cancel: true, can_retry_google_sync: true, can_resolve_google_conflict: true },
                google_sync: { state: "failed", linked: true, error_code: "test", conflict: null },
            },
        })
        await renderManagePage({ action: "cancel" })

        expect(await screen.findByRole("button", { name: "Reschedule" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Cancel Appointment" })).not.toBeInTheDocument()
        expect(screen.queryByText(/Google sync/i)).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /retry sync|resolve conflict/i })).not.toBeInTheDocument()
    })

    it("shows cancellation without rescheduling for a cancellation-only token", async () => {
        getAppointmentForManageMock.mockResolvedValue({
            ...APPOINTMENT,
            manage_actions: { can_reschedule: false, can_cancel: true },
        })
        await renderManagePage({ action: "reschedule" })

        expect(await screen.findByRole("button", { name: "Cancel Appointment" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Reschedule" })).not.toBeInTheDocument()
        expect(getRescheduleSlotsByTokenMock).not.toHaveBeenCalled()
    })

    it("completes reschedule flow", async () => {
        await renderManagePage()

        expect(await screen.findByText("Manage Appointment")).toBeInTheDocument()
        expect(await screen.findByText("June 2026")).toBeInTheDocument()
        expect(screen.getByText("Eastern Time (US)")).toBeInTheDocument()
        expect(screen.getByText("Choose a date.")).toBeInTheDocument()
        expect(screen.queryByText("No available times on this date.")).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Previous month" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Next month" })).toBeInTheDocument()

        const dateButton = screen
            .getAllByRole("button")
            .find((button) => button.textContent?.trim() === "4" && !button.hasAttribute("disabled"))

        expect(dateButton).toBeDefined()
        fireEvent.click(dateButton as HTMLElement)

        await waitFor(() => {
            expect(getRescheduleSlotsByTokenMock).toHaveBeenCalledWith(
                ORG_ID,
                TOKEN,
                expect.any(String),
                expect.any(String),
                "America/New_York"
            )
        })

        const slotButton = await screen.findByRole("button", { name: /12:00 PM/ })
        fireEvent.click(slotButton)

        fireEvent.click(screen.getByRole("button", { name: "Confirm Reschedule" }))

        await waitFor(() => {
            expect(rescheduleByManageTokenMock).toHaveBeenCalledWith(
                ORG_ID,
                TOKEN,
                "2026-06-04T16:00:00.000Z"
            )
        })

        expect(await screen.findByText("Appointment Rescheduled")).toBeInTheDocument()
    })

    it("shows the appointment and available slots in the selected Pacific timezone across a date boundary", async () => {
        getAppointmentForManageMock.mockResolvedValue({
            ...APPOINTMENT,
            client_timezone: "America/Los_Angeles",
            scheduled_start: "2026-06-04T01:00:00.000Z",
        })
        getRescheduleSlotsByTokenMock.mockResolvedValue({
            slots: [{ start: "2026-06-05T01:00:00.000Z", end: "2026-06-05T01:30:00.000Z" }],
            appointment_type: null,
        })
        rescheduleByManageTokenMock.mockResolvedValue({ ...APPOINTMENT, scheduled_start: "2026-06-05T01:00:00.000Z" })

        await renderManagePage()
        expect(await screen.findByText("Wednesday, June 3, 2026")).toBeInTheDocument()
        expect(screen.getByText(/6:00 PM/)).toBeInTheDocument()

        const dateButton = screen.getAllByRole("button").find(
            (button) => button.textContent?.trim() === "4" && !button.hasAttribute("disabled"),
        )
        fireEvent.click(dateButton as HTMLElement)
        fireEvent.click(await screen.findByRole("button", { name: /6:00 PM/ }))
        fireEvent.click(screen.getByRole("button", { name: "Confirm Reschedule" }))
        expect(await screen.findByText("Appointment Rescheduled")).toBeInTheDocument()
        expect(screen.getByText(/Thursday, June 4, 2026 · 6:00 PM · Pacific Time/)).toBeInTheDocument()
    })

    it("retries availability for the selected date after a load error", async () => {
        getRescheduleSlotsByTokenMock
            .mockRejectedValueOnce(new Error("Availability unavailable"))
            .mockResolvedValueOnce({ slots: [], appointment_type: null })
        await renderManagePage()
        await screen.findByText("Manage Appointment")

        const dateButton = screen
            .getAllByRole("button")
            .find((button) => /^\d+$/.test((button.textContent || "").trim()) && !button.hasAttribute("disabled"))
        fireEvent.click(dateButton as HTMLElement)

        expect(await screen.findByRole("alert")).toHaveTextContent("Calendar availability is unavailable.")
        fireEvent.click(screen.getByRole("button", { name: "Retry availability" }))

        await waitFor(() => expect(getRescheduleSlotsByTokenMock).toHaveBeenCalledTimes(2))
    })

    it("allows weekend dates and ignores a late response for a different date", async () => {
        let resolveThursday: (value: unknown) => void = () => undefined
        getRescheduleSlotsByTokenMock.mockImplementation((_orgId, _token, dateStart: string) =>
            dateStart === "2026-06-04"
                ? new Promise((resolve) => { resolveThursday = resolve })
                : Promise.resolve({ slots: [{ start: "2026-06-06T16:00:00.000Z", end: "2026-06-06T16:30:00.000Z" }], appointment_type: null }),
        )
        await renderManagePage()
        await screen.findByText("Manage Appointment")
        fireEvent.click(screen.getByRole("button", { name: "4" }))
        fireEvent.click(screen.getByRole("button", { name: "6" }))

        expect(await screen.findByRole("button", { name: /12:00 PM/ })).toBeInTheDocument()
        await act(async () => {
            resolveThursday({ slots: [{ start: "2026-06-04T16:00:00.000Z", end: "2026-06-04T16:30:00.000Z" }], appointment_type: null })
        })
        expect(screen.getByRole("button", { name: /12:00 PM/ })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Confirm Reschedule" })).toBeDisabled()
    })

    it("keeps the newest token appointment when the older request finishes last", async () => {
        let resolveFirst: (value: unknown) => void = () => undefined
        let resolveSecond: (value: unknown) => void = () => undefined
        const firstRequest = new Promise((resolve) => {
            resolveFirst = resolve
        })
        const secondRequest = new Promise((resolve) => {
            resolveSecond = resolve
        })
        getAppointmentForManageMock.mockImplementation((_orgId: string, token: string) =>
            token === TOKEN ? firstRequest : secondRequest
        )
        const { view, queryClient } = await renderManagePage()
        await waitFor(() => expect(getAppointmentForManageMock).toHaveBeenCalledTimes(1))

        await act(async () => {
            view.rerender(
                <QueryClientProvider client={queryClient}>
                    <React.Suspense fallback={<div>Loading</div>}>
                        <ManageAppointmentPage
                            params={Promise.resolve({
                                orgId: "22222222-2222-4222-8222-222222222222",
                                token: "token-2",
                            })}
                            searchParams={Promise.resolve({})}
                        />
                    </React.Suspense>
                </QueryClientProvider>
            )
            await Promise.resolve()
        })
        await waitFor(() => expect(getAppointmentForManageMock).toHaveBeenCalledTimes(2))

        await act(async () => {
            resolveSecond({
                ...APPOINTMENT,
                id: "appt-2",
                appointment_type_name: "Second Consultation",
                client_name: "Second Client",
            })
        })
        expect(await screen.findByText("Second Consultation")).toBeInTheDocument()

        await act(async () => {
            resolveFirst({
                ...APPOINTMENT,
                appointment_type_name: "Older Consultation",
                client_name: "Older Client",
            })
            await Promise.resolve()
        })

        expect(screen.getByText("Second Consultation")).toBeInTheDocument()
        expect(screen.queryByText("Older Consultation")).not.toBeInTheDocument()
    })
})
