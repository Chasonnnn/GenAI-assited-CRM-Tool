import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import ManageAppointmentPage from "../app/book/self-service/[orgId]/manage/[token]/page"

const getAppointmentForManageMock = vi.fn()
const getRescheduleSlotsByTokenMock = vi.fn()
const rescheduleByManageTokenMock = vi.fn()
const cancelByManageTokenMock = vi.fn()

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
    routeParams: { orgId: string; token: string } = { orgId: "org-1", token: "token-1" }
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
        expect(await screen.findByText("June 2026")).toBeInTheDocument()
        expect(screen.getByText("Eastern Time (US)")).toBeInTheDocument()

        const dateButton = screen
            .getAllByRole("button")
            .find((button) => /^\d+$/.test((button.textContent || "").trim()) && !button.hasAttribute("disabled"))

        expect(dateButton).toBeDefined()
        fireEvent.click(dateButton as HTMLElement)

        await waitFor(() => {
            expect(getRescheduleSlotsByTokenMock).toHaveBeenCalledWith(
                "org-1",
                "token-1",
                expect.any(String),
                expect.any(String),
                "America/New_York"
            )
        })

        const slotButton = await screen.findByRole("button", { name: /\d{1,2}:\d{2}/ })
        fireEvent.click(slotButton)

        fireEvent.click(screen.getByRole("button", { name: "Confirm Reschedule" }))

        await waitFor(() => {
            expect(rescheduleByManageTokenMock).toHaveBeenCalledWith(
                "org-1",
                "token-1",
                "2026-06-04T16:00:00.000Z"
            )
        })

        expect(await screen.findByText("Appointment Rescheduled")).toBeInTheDocument()
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
            token === "token-1" ? firstRequest : secondRequest
        )
        const { view, queryClient } = await renderManagePage()
        await waitFor(() => expect(getAppointmentForManageMock).toHaveBeenCalledTimes(1))

        await act(async () => {
            view.rerender(
                <QueryClientProvider client={queryClient}>
                    <React.Suspense fallback={<div>Loading</div>}>
                        <ManageAppointmentPage
                            params={Promise.resolve({ orgId: "org-2", token: "token-2" })}
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
