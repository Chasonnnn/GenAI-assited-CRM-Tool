import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'

vi.unmock('@tanstack/react-query')

import { ApiError } from '@/lib/api'
import { useRescheduleAppointment } from '@/lib/hooks/use-appointments'

const rescheduleAppointmentMock = vi.fn()
const toastErrorMock = vi.fn()

vi.mock('@/lib/api/appointments', () => ({
    rescheduleAppointment: (appointmentId: string, scheduledStart: string) =>
        rescheduleAppointmentMock(appointmentId, scheduledStart),
}))

vi.mock('@/components/ui/toast', () => ({
    toast: {
        error: (...args: unknown[]) => toastErrorMock(...args),
    },
}))

describe('useRescheduleAppointment', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('shows backend detail toast when reschedule fails with 400', async () => {
        const backendError = new ApiError(
            400,
            'Bad Request',
            'Selected time is no longer available.'
        )
        rescheduleAppointmentMock.mockRejectedValueOnce(backendError)

        const { result } = renderHook(() => useRescheduleAppointment())
        await act(async () => {
            await expect(
                result.current.mutateAsync({
                    appointmentId: 'appt-123',
                    scheduledStart: '2026-02-21T17:00:00.000Z',
                })
            ).rejects.toBe(backendError)
        })

        expect(toastErrorMock).toHaveBeenCalledWith(
            'Selected time is no longer available.'
        )
    })
})
