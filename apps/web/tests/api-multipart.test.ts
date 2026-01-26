import { describe, it, expect, vi, afterEach } from 'vitest'

import { previewImport, executeImport } from '@/lib/api/import'

function makeResponse(body: unknown) {
    return {
        status: 200,
        statusText: 'OK',
        ok: true,
        headers: {
            get: () => null,
        },
        json: async () => body,
    }
}

function getContentType(headers: RequestInit['headers'] | undefined): string | undefined {
    if (!headers) return undefined
    if (headers instanceof Headers) {
        return headers.get('Content-Type') ?? headers.get('content-type') ?? undefined
    }
    if (Array.isArray(headers)) {
        const found = headers.find(([key]) => key.toLowerCase() === 'content-type')
        return found?.[1]
    }
    return (headers as Record<string, string>)['Content-Type']
        ?? (headers as Record<string, string>)['content-type']
        ?? undefined
}

describe('multipart requests', () => {
    const originalFetch = global.fetch

    afterEach(() => {
        global.fetch = originalFetch
    })

    it('previewImport does not set multipart Content-Type header', async () => {
        const fetchMock = vi.fn().mockResolvedValue(
            makeResponse({
                total_rows: 0,
                sample_rows: [],
                detected_columns: [],
                unmapped_columns: [],
                duplicate_emails_db: 0,
                duplicate_emails_csv: 0,
                validation_errors: 0,
            })
        )
        global.fetch = fetchMock as unknown as typeof fetch

        const file = new File(['test'], 'test.csv', { type: 'text/csv' })
        await previewImport(file)

        const requestInit = fetchMock.mock.calls[0]?.[1] as RequestInit
        expect(getContentType(requestInit?.headers)).toBeUndefined()
    })

    it('executeImport does not set multipart Content-Type header', async () => {
        const fetchMock = vi.fn().mockResolvedValue(
            makeResponse({
                import_id: '00000000-0000-0000-0000-000000000000',
                message: 'queued',
            })
        )
        global.fetch = fetchMock as unknown as typeof fetch

        const file = new File(['test'], 'test.csv', { type: 'text/csv' })
        await executeImport(file)

        const requestInit = fetchMock.mock.calls[0]?.[1] as RequestInit
        expect(getContentType(requestInit?.headers)).toBeUndefined()
    })
})
