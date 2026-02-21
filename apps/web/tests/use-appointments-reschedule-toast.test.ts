import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '@/lib/api'
import { useRescheduleAppointment } from '@/lib/hooks/use-appointments'

const rescheduleAppointmentMock = vi.fn()
const toastErrorMock = vi.fn()
const queryClientMock = {
    setQueryData: vi.fn(),
    invalidateQueries: vi.fn(),
}

vi.mock('@/lib/api/appointments', () => ({
    rescheduleAppointment: (appointmentId: string, scheduledStart: string) =>
        rescheduleAppointmentMock(appointmentId, scheduledStart),
}))

vi.mock('sonner', () => ({
    toast: {
        error: (...args: unknown[]) => toastErrorMock(...args),
    },
}))

describe('useRescheduleAppointment', () => {
    beforeEach(() => {
        vi.clearAllMocks()

        vi.mocked(useQueryClient).mockReturnValue(queryClientMock as never)
        vi.mocked(useMutation).mockImplementation((options: {
            mutationFn: (variables: unknown) => Promise<unknown>
            onSuccess?: (data: unknown, variables: unknown) => void
            onError?: (error: unknown, variables: unknown) => void
        }) => ({
            mutateAsync: async (variables: unknown) => {
                try {
                    const data = await options.mutationFn(variables)
                    options.onSuccess?.(data, variables)
                    return data
                } catch (error) {
                    options.onError?.(error, variables)
                    throw error
                }
            },
            isPending: false,
            error: null,
        }) as never)
    })

    it('shows backend detail toast when reschedule fails with 400', async () => {
        const backendError = new ApiError(
            400,
            'Bad Request',
            'Selected time is no longer available.'
        )
        rescheduleAppointmentMock.mockRejectedValueOnce(backendError)

        const mutation = useRescheduleAppointment()
        await expect(
            mutation.mutateAsync({
                appointmentId: 'appt-123',
                scheduledStart: '2026-02-21T17:00:00.000Z',
            })
        ).rejects.toBe(backendError)

        expect(toastErrorMock).toHaveBeenCalledWith(
            'Selected time is no longer available.'
        )
    })
})
