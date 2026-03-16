import { describe, expect, it, vi, afterEach } from 'vitest'

import { isPlatformRootHost, proxy } from '../proxy'

function createRequest(url: string, headersInit?: HeadersInit) {
    const nextUrl = new URL(url) as URL & { clone: () => URL }
    nextUrl.clone = () => new URL(nextUrl.toString())

    return {
        headers: new Headers(headersInit),
        nextUrl,
        cookies: {
            get: () => undefined,
        },
    }
}

describe('isPlatformRootHost', () => {
    it('treats the bare platform domain as a root host', () => {
        expect(isPlatformRootHost('surrogacyforce.com', 'surrogacyforce.com')).toBe(true)
    })

    it('treats the www platform domain as a root host', () => {
        expect(isPlatformRootHost('www.surrogacyforce.com', 'surrogacyforce.com')).toBe(true)
    })

    it('does not treat org or ops subdomains as root hosts', () => {
        expect(isPlatformRootHost('ewi.surrogacyforce.com', 'surrogacyforce.com')).toBe(false)
        expect(isPlatformRootHost('ops.surrogacyforce.com', 'surrogacyforce.com')).toBe(false)
    })
})

describe('proxy hard-fail behavior', () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    it('returns 404 for unknown non-platform hosts', async () => {
        const response = await proxy(
            createRequest('https://unknown.example.com/dashboard', {
                host: 'unknown.example.com',
            }) as never,
        )

        expect(response.status).toBe(404)
    })

    it('lets the health route bypass host hard-fail checks', async () => {
        const response = await proxy(
            createRequest('https://crm-web-00145-jj5-uc.a.run.app/health', {
                host: 'crm-web-00145-jj5-uc.a.run.app',
            }) as never,
        )

        expect(response.status).toBe(200)
        expect(response.headers.get('x-middleware-rewrite')).toBeNull()
    })

    it('returns 500 when tenant lookup fails for a platform subdomain', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(
            new Response('upstream failure', { status: 500 }),
        )

        const response = await proxy(
            createRequest('https://ewi.surrogacyforce.com/dashboard', {
                host: 'ewi.surrogacyforce.com',
            }) as never,
        )

        expect(response.status).toBe(500)
    })

    it('rewrites missing route resources to /_not-found with a real 404', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(
            new Response(null, { status: 404 }),
        )

        const response = await proxy(
            createRequest('http://localhost:3000/automation/campaigns/00000000-0000-0000-0000-000000000000', {
                host: 'localhost:3000',
                cookie: 'crm_session=test-token',
            }) as never,
        )

        expect(response.status).toBe(404)
        expect(response.headers.get('x-middleware-rewrite')).toContain('/_not-found')
    })

    it('treats invalid UUID route params as a hard 404 without hitting the API', async () => {
        const fetchSpy = vi.spyOn(globalThis, 'fetch')

        const response = await proxy(
            createRequest('http://localhost:3000/automation/campaigns/not-a-uuid', {
                host: 'localhost:3000',
            }) as never,
        )

        expect(response.status).toBe(404)
        expect(response.headers.get('x-middleware-rewrite')).toContain('/_not-found')
        expect(fetchSpy).not.toHaveBeenCalled()
    })

    it('passes through route-resource permission responses', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(
            new Response(null, { status: 403 }),
        )

        const response = await proxy(
            createRequest('http://localhost:3000/automation/campaigns/00000000-0000-0000-0000-000000000000', {
                host: 'localhost:3000',
                cookie: 'crm_session=test-token',
            }) as never,
        )

        expect(response.status).toBe(200)
        expect(response.headers.get('x-middleware-rewrite')).toBeNull()
    })
})
