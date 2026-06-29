import { describe, it, expect, vi, afterEach } from 'vitest'

import { previewImport } from '@/lib/api/import'
import { submitSharedPublicForm } from '@/lib/api/forms'

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
                import_id: '00000000-0000-0000-0000-000000000000',
                total_rows: 0,
                sample_rows: [],
                detected_encoding: 'utf-8',
                detected_delimiter: ',',
                has_header: true,
                column_suggestions: [],
                matched_count: 0,
                unmatched_count: 0,
                matching_templates: [],
                available_fields: [],
                duplicate_emails_db: 0,
                duplicate_emails_csv: 0,
                validation_errors: 0,
                date_ambiguity_warnings: [],
                ai_available: false,
            })
        )
        global.fetch = fetchMock as unknown as typeof fetch

        const file = new File(['test'], 'test.csv', { type: 'text/csv' })
        await previewImport(file)

        const requestInit = fetchMock.mock.calls[0]?.[1] as RequestInit
        expect(getContentType(requestInit?.headers)).toBeUndefined()
    })

    it('submitSharedPublicForm aligns files with file_field_keys in FormData', async () => {
        const fetchMock = vi.fn().mockResolvedValue(
            makeResponse({
                id: 'submission-1',
                status: 'pending_review',
                outcome: 'workflow_pending',
                surrogate_id: null,
                intake_lead_id: null,
            })
        )
        global.fetch = fetchMock as unknown as typeof fetch

        const identityFile = new File(['identity'], 'identity.txt', { type: 'text/plain' })
        const insuranceFile = new File(['insurance'], 'insurance.txt', { type: 'text/plain' })

        await submitSharedPublicForm(
            'shared-slug',
            { full_name: 'Hosted Applicant' },
            [identityFile, insuranceFile],
            ['identity_upload', 'insurance_upload'],
        )

        const requestInit = fetchMock.mock.calls[0]?.[1] as RequestInit
        expect(getContentType(requestInit?.headers)).toBeUndefined()
        expect(requestInit.body).toBeInstanceOf(FormData)

        const formData = requestInit.body as FormData
        expect(formData.get('answers')).toBe(JSON.stringify({ full_name: 'Hosted Applicant' }))
        expect(formData.getAll('files')).toEqual([identityFile, insuranceFile])
        expect(formData.get('file_field_keys')).toBe(
            JSON.stringify(['identity_upload', 'insurance_upload']),
        )
    })
})
