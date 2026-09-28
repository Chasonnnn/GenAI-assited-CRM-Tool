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
        vi.useRealTimers()
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

    it('returns a retryable service-unavailable response when tenant lookup fails', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(
            new Response('upstream failure', { status: 500 }),
        )
        const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)

        const response = await proxy(
            createRequest('https://ewi.surrogacyforce.com/dashboard', {
                host: 'ewi.surrogacyforce.com',
            }) as never,
        )

        expect(response.status).toBe(503)
        expect(await response.text()).toBe('Tenant service temporarily unavailable')
        expect(response.headers.get('Retry-After')).toBe('5')
        expect(consoleErrorSpy).toHaveBeenCalledWith(
            '[middleware] API error resolving org for ewi.surrogacyforce.com: 500'
        )
    })

    it('allows five seconds for a tenant lookup before returning service unavailable', async () => {
        vi.useFakeTimers()
        vi.spyOn(console, 'error').mockImplementation(() => undefined)
        vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) => {
            return new Promise((_resolve, reject) => {
                init?.signal?.addEventListener('abort', () => {
                    reject(new DOMException('aborted', 'AbortError'))
                })
            })
        })

        let settled = false
        const responsePromise = proxy(
            createRequest('https://timeout-tenant.surrogacyforce.com/dashboard', {
                host: 'timeout-tenant.surrogacyforce.com',
            }) as never,
        ).then((response) => {
            settled = true
            return response
        })

        await vi.advanceTimersByTimeAsync(4_999)
        expect(settled).toBe(false)

        await vi.advanceTimersByTimeAsync(1)
        const response = await responsePromise

        expect(response.status).toBe(503)
        expect(response.headers.get('Retry-After')).toBe('5')
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

const MISSING_UUID = '00000000-0000-4000-8000-000000000000'

function rewritePath(response: Response): string | null {
    const rewrite = response.headers.get('x-middleware-rewrite')
    return rewrite ? new URL(rewrite).pathname : null
}

function requestedApiUrl(fetchSpy: { mock: { calls: unknown[][] } }): string {
    return String(fetchSpy.mock.calls[0]?.[0])
}

function appRequest(path: string) {
    return createRequest(`http://localhost:3000${path}`, {
        host: 'localhost:3000',
        cookie: 'crm_session=test-token',
    }) as never
}

describe('proxy record not-found rewrites', () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    const appShellMatchers = [
        {
            kind: 'campaign',
            routePath: `/automation/campaigns/${MISSING_UUID}`,
            apiPath: `/campaigns/${MISSING_UUID}`,
            invalidPath: '/automation/campaigns/not-a-uuid',
        },
        {
            kind: 'form',
            routePath: `/automation/forms/${MISSING_UUID}`,
            apiPath: `/forms/${MISSING_UUID}`,
            invalidPath: '/automation/forms/not-a-uuid',
        },
        {
            kind: 'match',
            routePath: `/intended-parents/matches/${MISSING_UUID}`,
            apiPath: `/matches/${MISSING_UUID}`,
            invalidPath: '/intended-parents/matches/not-a-uuid',
        },
        {
            kind: 'member',
            routePath: `/settings/team/members/${MISSING_UUID}`,
            apiPath: `/settings/permissions/members/${MISSING_UUID}`,
            invalidPath: '/settings/team/members/not-a-uuid',
        },
        {
            kind: 'role',
            routePath: '/settings/team/roles/bogus_role',
            apiPath: '/settings/permissions/roles/bogus_role',
            invalidPath: null,
        },
    ] as const

    describe.each(appShellMatchers)('$kind route', ({ kind, routePath, apiPath, invalidPath }) => {
        it.each([404, 422])('rewrites an API %i to the in-shell not-found route', async (status) => {
            const fetchSpy = vi
                .spyOn(globalThis, 'fetch')
                .mockResolvedValue(new Response(null, { status }))

            const response = await proxy(appRequest(routePath))

            expect(requestedApiUrl(fetchSpy)).toMatch(new RegExp(`${apiPath}$`))
            expect(response.status).toBe(404)
            expect(response.headers.get('Cache-Control')).toBe('no-store')
            expect(rewritePath(response)).toBe(`/record-not-found/${kind}`)
        })

        it('passes through a record the API returns', async () => {
            vi.spyOn(globalThis, 'fetch').mockResolvedValue(Response.json({ id: 'record' }))

            const response = await proxy(appRequest(routePath))

            expect(response.status).toBe(200)
            expect(rewritePath(response)).toBeNull()
        })

        if (invalidPath) {
            it('rewrites a non-UUID id without calling the API', async () => {
                const fetchSpy = vi.spyOn(globalThis, 'fetch')

                const response = await proxy(appRequest(invalidPath))

                expect(fetchSpy).not.toHaveBeenCalled()
                expect(response.status).toBe(404)
                expect(rewritePath(response)).toBe(`/record-not-found/${kind}`)
            })
        }
    })

    it('does not check the new-form route', async () => {
        const fetchSpy = vi.spyOn(globalThis, 'fetch')

        const response = await proxy(appRequest('/automation/forms/new'))

        expect(fetchSpy).not.toHaveBeenCalled()
        expect(response.status).toBe(200)
        expect(rewritePath(response)).toBeNull()
    })

    it('keeps the 404 status when the proxy runs for the rewrite target', async () => {
        const fetchSpy = vi.spyOn(globalThis, 'fetch')

        const response = await proxy(appRequest('/record-not-found/campaign'))

        expect(fetchSpy).not.toHaveBeenCalled()
        expect(response.status).toBe(404)
        expect(response.headers.get('Cache-Control')).toBe('no-store')
        expect(rewritePath(response)).toBeNull()
    })

    it.each([
        '/ops/templates/email/not-a-uuid',
        '/ops/templates/forms/not-a-uuid',
        '/ops/templates/workflows/not-a-uuid',
    ])('keeps %s on the root not-found page', async (path) => {
        const response = await proxy(appRequest(path))

        expect(response.status).toBe(404)
        expect(rewritePath(response)).toBe('/_not-found')
    })

    it('keeps an API 404 for an ops template on the root not-found page', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 404 }))

        const response = await proxy(appRequest(`/ops/templates/email/${MISSING_UUID}`))

        expect(response.status).toBe(404)
        expect(rewritePath(response)).toBe('/_not-found')
    })

    it('keeps a missing embed form on the root not-found page', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 404 }))

        const response = await proxy(appRequest('/embed/forms/missing-form'))

        expect(response.status).toBe(404)
        expect(rewritePath(response)).toBe('/_not-found')
    })
})
