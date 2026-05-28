import { describe, expect, it, vi, afterEach } from 'vitest'

import { getServerApiBaseUrl, isPlatformRootHost, proxy } from '../proxy'

function createRequest(
    url: string,
    headersInit?: HeadersInit,
    cookieValues: Record<string, string> = {},
) {
    const nextUrl = new URL(url) as URL & { clone: () => URL }
    nextUrl.clone = () => new URL(nextUrl.toString())

    return {
        headers: new Headers(headersInit),
        nextUrl,
        cookies: {
            get: (name: string) => {
                const value = cookieValues[name]
                return value ? { name, value } : undefined
            },
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

    it('treats the app platform domain as a root host', () => {
        expect(isPlatformRootHost('app.surrogacyforce.com', 'surrogacyforce.com')).toBe(true)
    })

    it('does not treat org or ops subdomains as root hosts', () => {
        expect(isPlatformRootHost('ewi.surrogacyforce.com', 'surrogacyforce.com')).toBe(false)
        expect(isPlatformRootHost('ops.surrogacyforce.com', 'surrogacyforce.com')).toBe(false)
    })
})

describe('getServerApiBaseUrl', () => {
    afterEach(() => {
        delete process.env.API_BASE_URL
    })

    it('prefers the private API base URL for server-side proxy lookups', () => {
        process.env.API_BASE_URL = 'http://127.0.0.1:8001'

        expect(getServerApiBaseUrl()).toBe('http://127.0.0.1:8001')
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

    it('does not resolve app platform host as an organization subdomain', async () => {
        const fetchSpy = vi.spyOn(globalThis, 'fetch')

        const response = await proxy(
            createRequest('https://app.surrogacyforce.com/dashboard', {
                host: 'app.surrogacyforce.com',
            }) as never,
        )

        expect(response.status).toBe(200)
        expect(fetchSpy).not.toHaveBeenCalled()
    })

    it('keeps the public homepage on the www platform host', async () => {
        const fetchSpy = vi.spyOn(globalThis, 'fetch')

        const response = await proxy(
            createRequest('https://www.surrogacyforce.com/', {
                host: 'www.surrogacyforce.com',
            }) as never,
        )

        expect(response.status).toBe(200)
        expect(response.headers.get('location')).toBeNull()
        expect(fetchSpy).not.toHaveBeenCalled()
    })

    it('redirects a resolved tenant root domain to login instead of the public homepage', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(
            Response.json({
                id: 'org-tenant-root',
                slug: 'tenant-root',
                name: 'Tenant Root',
            }),
        )

        const response = await proxy(
            createRequest('https://tenant-root.surrogacyforce.com/', {
                host: 'tenant-root.surrogacyforce.com',
            }) as never,
        )

        expect(response.status).toBe(307)
        expect(response.headers.get('location')).toBe(
            'https://tenant-root.surrogacyforce.com/login',
        )
    })

    it('redirects a tenant root domain with org cookies to login without resolving again', async () => {
        const fetchSpy = vi.spyOn(globalThis, 'fetch')

        const response = await proxy(
            createRequest(
                'https://ewi.surrogacyforce.com/',
                {
                    host: 'ewi.surrogacyforce.com',
                },
                {
                    sf_org_id: 'org-ewi',
                    sf_org_slug: 'ewi',
                    sf_org_name: 'EWI Family Global',
                },
            ) as never,
        )

        expect(response.status).toBe(307)
        expect(response.headers.get('location')).toBe(
            'https://ewi.surrogacyforce.com/login',
        )
        expect(fetchSpy).not.toHaveBeenCalled()
    })

    it('returns 500 when tenant lookup fails for a platform subdomain', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(
            new Response('upstream failure', { status: 500 }),
        )
        const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)

        const response = await proxy(
            createRequest('https://ewi.surrogacyforce.com/dashboard', {
                host: 'ewi.surrogacyforce.com',
            }) as never,
        )

        expect(response.status).toBe(500)
        expect(consoleErrorSpy).toHaveBeenCalledWith(
            '[middleware] API error resolving org for ewi.surrogacyforce.com: 500'
        )
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

    it('sets dynamic no-store frame policy headers for embed form documents', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(
            Response.json({
                frame_ancestors: ["'self'", 'https://www.ewisurrogacy.com'],
                content_security_policy: "frame-ancestors 'self' https://www.ewisurrogacy.com",
            }),
        )

        const response = await proxy(
            createRequest('http://localhost:3000/embed/forms/lead-form', {
                host: 'localhost:3000',
            }) as never,
        )

        expect(response.status).toBe(200)
        expect(response.headers.get('Content-Security-Policy')).toBe(
            "frame-ancestors 'self' https://www.ewisurrogacy.com",
        )
        expect(response.headers.get('Cache-Control')).toBe('no-store')
    })
})
