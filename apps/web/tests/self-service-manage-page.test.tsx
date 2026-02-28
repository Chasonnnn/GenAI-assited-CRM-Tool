import { beforeEach, describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import * as React from "react"

import ManageAppointmentPage from "../app/book/self-service/[orgId]/manage/[token]/page"

const getAppointmentForManageMock = vi.fn()
const getRescheduleSlotsByTokenMock = vi.fn()
const rescheduleByManageTokenMock = vi.fn()
const cancelByManageTokenMock = vi.fn()

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
    scheduled_start: "2026-03-03T16:00:00.000Z",
    scheduled_end: "2026-03-03T16:30:00.000Z",
    duration_minutes: 30,
    meeting_mode: "zoom",
    meeting_location: "Zoom",
    dial_in_number: null,
    status: "confirmed",
    client_timezone: "America/New_York",
    zoom_join_url: null,
    google_meet_url: null,
}

async function renderManagePage(searchParams: Record<string, string> = {}) {
    await act(async () => {
        render(
            <React.Suspense fallback={<div>Loading...</div>}>
                <ManageAppointmentPage
                    params={Promise.resolve({ orgId: "org-1", token: "token-1" })}
                    searchParams={Promise.resolve(searchParams)}
                />
            </React.Suspense>
        )
        await Promise.resolve()
    })
}

describe("Self-service manage appointment page", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        vi.useFakeTimers({ toFake: ["Date"] })
        vi.setSystemTime(new Date("2026-03-01T00:00:00.000Z"))

        getAppointmentForManageMock.mockResolvedValue(APPOINTMENT)
        getRescheduleSlotsByTokenMock.mockResolvedValue({
            slots: [
                {
                    start: "2026-03-04T16:00:00.000Z",
                    end: "2026-03-04T16:30:00.000Z",
                },
            ],
            appointment_type: null,
        })
        rescheduleByManageTokenMock.mockResolvedValue(APPOINTMENT)
        cancelByManageTokenMock.mockResolvedValue({ ...APPOINTMENT, status: "cancelled" })
    })

    it("renders invalid/expired token error state", async () => {
        getAppointmentForManageMock.mockRejectedValueOnce(new Error("Appointment not found"))

        await renderManagePage()

        expect(await screen.findByText("Unable to Manage Appointment")).toBeInTheDocument()
        expect(screen.getByText("Appointment not found")).toBeInTheDocument()
    })

    it("completes cancel flow", async () => {
        await renderManagePage({ action: "cancel" })

        expect(await screen.findByText("Manage Appointment")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Cancel Appointment" }))

        await waitFor(() => {
            expect(cancelByManageTokenMock).toHaveBeenCalledWith("org-1", "token-1", undefined)
        })

        expect(await screen.findByText("Appointment Cancelled")).toBeInTheDocument()
    })

    it("completes reschedule flow", async () => {
        await renderManagePage()

        expect(await screen.findByText("Manage Appointment")).toBeInTheDocument()

        const dateButton = screen
            .getAllByRole("button")
            .find((button) => /^\d+$/.test((button.textContent || "").trim()) && !button.hasAttribute("disabled"))

        expect(dateButton).toBeDefined()
        fireEvent.click(dateButton as HTMLElement)

        await waitFor(() => {
            expect(getRescheduleSlotsByTokenMock).toHaveBeenCalled()
        })

        const slotButton = await screen.findByRole("button", { name: /\d{1,2}:\d{2}/ })
        fireEvent.click(slotButton)

        fireEvent.click(screen.getByRole("button", { name: "Confirm Reschedule" }))

        await waitFor(() => {
            expect(rescheduleByManageTokenMock).toHaveBeenCalledWith(
                "org-1",
                "token-1",
                "2026-03-04T16:00:00.000Z"
            )
        })

        expect(await screen.findByText("Appointment Rescheduled")).toBeInTheDocument()
    })

    afterEach(() => {
        vi.useRealTimers()
    })
})
