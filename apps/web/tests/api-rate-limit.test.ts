import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('sonner', () => ({
    toast: {
        error: vi.fn(),
    },
}))

import { api, RateLimitError } from '../lib/api'

type MockResponse = {
    status: number
    statusText: string
    ok: boolean
    headers: { get: (key: string) => string | null }
    json: () => Promise<unknown>
}

function makeResponse(
    status: number,
    body: unknown = {},
    headers: Record<string, string> = {},
): MockResponse {
    return {
        status,
        statusText: status === 429 ? 'Too Many Requests' : 'OK',
        ok: status >= 200 && status < 300,
        headers: {
            get: (key: string) => headers[key] ?? headers[key.toLowerCase()] ?? null,
        },
        json: async () => body,
    }
}

describe('api rate limit handling', () => {
    const originalFetch = global.fetch

    beforeEach(() => {
        vi.clearAllMocks()
    })

    afterEach(() => {
        global.fetch = originalFetch
    })

    it('does not auto-retry GET requests when Retry-After is provided', async () => {
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(makeResponse(429, { detail: 'rate limit' }, { 'Retry-After': '1' }))

        global.fetch = fetchMock as unknown as typeof fetch

        await expect(api.get('/surrogates')).rejects.toMatchObject({ retryAfter: 1 })
        expect(fetchMock).toHaveBeenCalledTimes(1)
    })

    it('does not auto-retry non-GET requests', async () => {
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(makeResponse(429, { detail: 'rate limit' }, { 'Retry-After': '1' }))

        global.fetch = fetchMock as unknown as typeof fetch

        await expect(api.post('/surrogates', { name: 'Test' })).rejects.toBeInstanceOf(RateLimitError)
        expect(fetchMock).toHaveBeenCalledTimes(1)
    })
})
