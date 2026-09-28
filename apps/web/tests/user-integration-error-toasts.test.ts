import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '@/lib/api'
import {
    useConnectGcp,
    useConnectGmail,
    useConnectGoogleCalendar,
    useConnectZoom,
    useSyncGoogleCalendarNow,
} from '@/lib/hooks/use-user-integrations'

const toastMocks = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn(), info: vi.fn(), warning: vi.fn() }))

vi.mock('@tanstack/react-query', async (importOriginal) => {
    const actual = await importOriginal<typeof import('@tanstack/react-query')>()
    return { ...actual, useMutation: vi.fn(), useQueryClient: vi.fn() }
})
vi.mock('@/components/ui/toast', () => ({ toast: toastMocks }))

type CapturedOptions = { onError?: (error: unknown) => void }
let capturedOptions: CapturedOptions | null = null

const cases = [
    { name: 'Zoom connect', hook: useConnectZoom, fallback: "Couldn't start the Zoom connection. Try again." },
    { name: 'Gmail connect', hook: useConnectGmail, fallback: "Couldn't start the Gmail connection. Try again." },
    {
        name: 'Google Calendar connect',
        hook: useConnectGoogleCalendar,
        fallback: "Couldn't start the Google Calendar connection. Try again.",
    },
    { name: 'Google Cloud connect', hook: useConnectGcp, fallback: "Couldn't start the Google Cloud connection. Try again." },
    { name: 'Google Calendar sync', hook: useSyncGoogleCalendarNow, fallback: "Couldn't sync Google Calendar. Try again." },
]

describe('user integration error toasts', () => {
    beforeEach(() => {
        capturedOptions = null
        Object.values(toastMocks).forEach((mock) => mock.mockReset())
        vi.mocked(useQueryClient).mockReturnValue({ invalidateQueries: vi.fn() } as never)
        vi.mocked(useMutation).mockImplementation((options: unknown) => {
            capturedOptions = options as CapturedOptions
            return {} as never
        })
    })

    it.each(cases)('keeps server configuration text out of the $name failure toast', ({ hook, fallback }) => {
        hook()
        capturedOptions?.onError?.(
            new ApiError(503, 'Service Unavailable', 'Zoom integration not configured. Set ZOOM_CLIENT_ID.'),
        )
        expect(toastMocks.error).toHaveBeenCalledWith(fallback)

        toastMocks.error.mockReset()
        capturedOptions?.onError?.(new Error('Zoom authorization URL is missing.'))
        expect(toastMocks.error).toHaveBeenCalledWith(fallback)
    })

    it('keeps the product message of a client error', () => {
        useConnectZoom()
        capturedOptions?.onError?.(new ApiError(409, 'Conflict', 'Zoom is already connected.'))
        expect(toastMocks.error).toHaveBeenCalledWith('Zoom is already connected.')
    })
})
