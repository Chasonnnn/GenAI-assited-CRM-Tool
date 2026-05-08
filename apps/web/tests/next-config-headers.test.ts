import { createRequire } from 'node:module'

import { describe, expect, it } from 'vitest'

const require = createRequire(import.meta.url)
const nextConfig = require('../next.config.js')

describe('next.config headers', () => {
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
