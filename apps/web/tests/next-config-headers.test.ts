import { createRequire } from 'node:module'

import { afterEach, describe, expect, it, vi } from 'vitest'

const require = createRequire(import.meta.url)
const nextConfig = require('../next.config.js')

describe('next.config headers', () => {
    afterEach(() => vi.unstubAllEnvs())

    it('allows only the local website to frame the donor prototype in development', async () => {
        vi.stubEnv('NODE_ENV', 'development')
        const headers = await nextConfig.headers()
        expect(headers.find((item: { source: string }) => item.source === '/prototype/donor-intake/:slug')?.headers)
            .toContainEqual({ key: 'Content-Security-Policy', value: 'frame-ancestors http://127.0.0.1:3027' })
    })

    it('keeps production frame protection for prototype paths', async () => {
        vi.stubEnv('NODE_ENV', 'production')
        const headers = await nextConfig.headers()
        expect(headers.some((item: { source: string }) => item.source.includes('prototype'))).toBe(false)
        expect(headers.find((item: { source: string }) => item.source === '/((?!embed/forms).*)')?.headers)
            .toContainEqual({ key: 'X-Frame-Options', value: 'SAMEORIGIN' })
    })

    it('marks embed form iframe documents as no-store', async () => {
        const headers = await nextConfig.headers()

        expect(headers).toEqual(
            expect.arrayContaining([
                expect.objectContaining({
                    source: '/embed/forms/:slug',
                    headers: expect.arrayContaining([
                        { key: 'Cache-Control', value: 'no-store' },
                    ]),
                }),
            ]),
        )
    })
})
