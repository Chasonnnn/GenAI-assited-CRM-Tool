import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useQuery } from '@tanstack/react-query'

import { useGoogleCalendarEvents } from '@/lib/hooks/use-appointments'

describe('useGoogleCalendarEvents', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('enables automatic refresh for external Google Calendar changes', () => {
        useGoogleCalendarEvents('2026-02-01', '2026-02-28', 'America/New_York')

        const mockedUseQuery = vi.mocked(useQuery)
        expect(mockedUseQuery).toHaveBeenCalledTimes(1)

        const options = mockedUseQuery.mock.calls[0]?.[0]
        expect(options?.staleTime).toBe(15 * 1000)
        expect(options?.refetchInterval).toBe(30 * 1000)
        expect(options?.refetchIntervalInBackground).toBe(true)
        expect(options?.refetchOnWindowFocus).toBe('always')
    })
})

