import { describe, expect, it } from 'vitest'

import { buildServerApiHeaders } from '../lib/server-api-headers'

describe('buildServerApiHeaders', () => {
    it('copies forwarded headers from the current request', () => {
        const source = new Headers({
            'x-forwarded-for': '203.0.113.10, 34.54.23.120',
            'x-forwarded-host': 'ewi.surrogacyforce.com',
            'x-forwarded-proto': 'https',
        })

        const headers = buildServerApiHeaders(source, {
            'content-type': 'application/json',
        })

        expect(headers.get('content-type')).toBe('application/json')
        expect(headers.get('x-forwarded-for')).toBe('203.0.113.10, 34.54.23.120')
        expect(headers.get('x-forwarded-host')).toBe('ewi.surrogacyforce.com')
        expect(headers.get('x-forwarded-proto')).toBe('https')
    })

    it('omits missing forwarded headers', () => {
        const headers = buildServerApiHeaders(new Headers())

        expect(headers.get('x-forwarded-for')).toBeNull()
        expect(headers.get('x-forwarded-host')).toBeNull()
        expect(headers.get('x-forwarded-proto')).toBeNull()
    })
})
