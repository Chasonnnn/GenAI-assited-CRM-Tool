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
        vi.useFakeTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
        global.fetch = originalFetch
    })

    it('retries GET requests when Retry-After is provided', async () => {
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(makeResponse(429, { detail: 'rate limit' }, { 'Retry-After': '1' }))
            .mockResolvedValueOnce(makeResponse(200, { ok: true }))

        global.fetch = fetchMock as unknown as typeof fetch

        const promise = api.get('/surrogates')
        await vi.runAllTimersAsync()
        const result = await promise

        expect(fetchMock).toHaveBeenCalledTimes(2)
        expect(result).toEqual({ ok: true })
    })

    it('does not auto-retry expensive endpoints', async () => {
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(makeResponse(429, { detail: 'rate limit' }, { 'Retry-After': '1' }))

        global.fetch = fetchMock as unknown as typeof fetch

        await expect(api.get('/analytics/summary')).rejects.toBeInstanceOf(RateLimitError)
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
