import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'

vi.unmock('@tanstack/react-query')

import { ApiError } from '@/lib/api'
import { useCancelAppointment, useRescheduleAppointment } from '@/lib/hooks/use-appointments'

const rescheduleAppointmentMock = vi.fn()
const cancelAppointmentMock = vi.fn()
const toastErrorMock = vi.fn()

vi.mock('@/lib/api/appointments', () => ({
    cancelAppointment: (appointmentId: string) => cancelAppointmentMock(appointmentId),
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

describe('useCancelAppointment', () => {
    it('shows the rejection reason when cancellation fails and allows retry', async () => {
        vi.clearAllMocks()
        const backendError = new ApiError(400, 'Bad Request', 'Google appointment link requires review')
        cancelAppointmentMock.mockRejectedValueOnce(backendError)
        const { result } = renderHook(() => useCancelAppointment())
        await act(async () => {
            await expect(result.current.mutateAsync({ appointmentId: 'appt-123' })).rejects.toBe(backendError)
        })
        expect(toastErrorMock).toHaveBeenCalledWith('Google appointment link requires review')
        expect(result.current.isPending).toBe(false)
        cancelAppointmentMock.mockResolvedValueOnce({ id: 'appt-123', status: 'cancelled' })
        await act(async () => {
            await result.current.mutateAsync({ appointmentId: 'appt-123' })
        })
        expect(result.current.data?.status).toBe('cancelled')
        expect(toastErrorMock).toHaveBeenCalledTimes(1)
    })
})
