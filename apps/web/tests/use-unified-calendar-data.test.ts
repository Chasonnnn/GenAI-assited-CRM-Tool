import { beforeEach, describe, expect, it, vi } from "vitest"
import { renderHook } from "@testing-library/react"

import { useUnifiedCalendarData } from "@/lib/hooks/use-unified-calendar-data"

const mocks = vi.hoisted(() => ({
    appointments: vi.fn(),
    tasks: vi.fn(),
    refetchAppointments: vi.fn(),
    refetchTasks: vi.fn(),
}))

vi.mock("@/lib/hooks/use-appointments", () => ({
    useAppointments: () => mocks.appointments(),
    useGoogleCalendarEvents: () => ({ data: { events: [], connected: true, error: null } }),
}))
vi.mock("@/lib/hooks/use-tasks", () => ({
    useTasks: () => mocks.tasks(),
}))

const dateRange = { date_start: "2026-09-01", date_end: "2026-09-30" }

function querySuccess(refetch: () => void) {
    return { data: { items: [] }, isLoading: false, isError: false, error: null, refetch, isFetching: false }
}

function queryFailure(refetch: () => void, isFetching = false) {
    return { data: undefined, isLoading: false, isError: true, error: new Error("boom"), refetch, isFetching }
}

describe("useUnifiedCalendarData load errors", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mocks.appointments.mockReturnValue(querySuccess(mocks.refetchAppointments))
        mocks.tasks.mockReturnValue(querySuccess(mocks.refetchTasks))
    })

    it("reports no errors when both sources load", () => {
        const { result } = renderHook(() => useUnifiedCalendarData({ dateRange }))

        expect(result.current.appointmentsError).toBeNull()
        expect(result.current.tasksError).toBeNull()
        expect(result.current.isRetryingFailed).toBe(false)
    })

    it("retries only the failed source", () => {
        mocks.tasks.mockReturnValue(queryFailure(mocks.refetchTasks))
        const { result } = renderHook(() => useUnifiedCalendarData({ dateRange }))

        expect(result.current.tasksError).toBeInstanceOf(Error)
        expect(result.current.appointmentsError).toBeNull()

        result.current.retryFailed()
        expect(mocks.refetchTasks).toHaveBeenCalledTimes(1)
        expect(mocks.refetchAppointments).not.toHaveBeenCalled()
    })

    it("reports retrying only while a failed source refetches", () => {
        mocks.appointments.mockReturnValue({ ...querySuccess(mocks.refetchAppointments), isFetching: true })
        mocks.tasks.mockReturnValue(queryFailure(mocks.refetchTasks))
        const { result, rerender } = renderHook(() => useUnifiedCalendarData({ dateRange }))
        expect(result.current.isRetryingFailed).toBe(false)

        mocks.tasks.mockReturnValue(queryFailure(mocks.refetchTasks, true))
        rerender()
        expect(result.current.isRetryingFailed).toBe(true)
    })

    it("ignores errors from a source the calendar does not include", () => {
        mocks.appointments.mockReturnValue(queryFailure(mocks.refetchAppointments))
        mocks.tasks.mockReturnValue(queryFailure(mocks.refetchTasks))
        const { result } = renderHook(() =>
            useUnifiedCalendarData({ dateRange, includeAppointments: false, includeTasks: false }),
        )

        expect(result.current.appointmentsError).toBeNull()
        expect(result.current.tasksError).toBeNull()
        result.current.retryFailed()
        expect(mocks.refetchAppointments).not.toHaveBeenCalled()
        expect(mocks.refetchTasks).not.toHaveBeenCalled()
    })
})
