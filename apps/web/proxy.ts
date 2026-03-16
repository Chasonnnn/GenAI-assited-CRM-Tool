import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

import { buildServerApiHeaders } from './lib/server-api-headers';

const PLATFORM_BASE_DOMAIN =
    process.env.PLATFORM_BASE_DOMAIN || 'surrogacyforce.com';
const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const ORG_CACHE_TTL_MS = 60_000;
const ORG_LOOKUP_TIMEOUT_MS = 2000;
const ROUTE_LOOKUP_TIMEOUT_MS = 2000;
const ORG_COOKIE_ID = 'sf_org_id';
const ORG_COOKIE_SLUG = 'sf_org_slug';
const ORG_COOKIE_NAME = 'sf_org_name';
const UUID_PARAM_RE =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type OrgRecord = {
    id: string;
    slug: string;
    name: string;
};

type OrgCacheEntry = {
    value: OrgRecord | null;
    expiresAt: number;
};

const orgCache = new Map<string, OrgCacheEntry>();

export function isPlatformRootHost(hostname: string, platformBaseDomain: string): boolean {
    return hostname === platformBaseDomain || hostname === `www.${platformBaseDomain}`;
}

function getHostname(request: NextRequest) {
    const forwardedHost = request.headers
        .get('x-forwarded-host')
        ?.split(',')[0]
        ?.trim();
    const rawHost =
        forwardedHost || request.headers.get('host') || request.nextUrl.host;

    if (rawHost) {
        try {
            return new URL(`http://${rawHost}`).hostname;
        } catch {
            // fall through to nextUrl
        }
    }
    return request.nextUrl.hostname || '';
}

function getCachedEntry(hostname: string, now: number) {
    const cached = orgCache.get(hostname);
    if (!cached) return null;
    if (cached.expiresAt >= now) return cached;
    return null;
}

function setCachedOrg(hostname: string, value: OrgRecord | null, now: number, ttlMs: number) {
    orgCache.set(hostname, {
        value,
        expiresAt: now + ttlMs,
    });
}

function getCookieOrg(request: NextRequest): OrgRecord | null {
    const id = request.cookies.get(ORG_COOKIE_ID)?.value;
    const slug = request.cookies.get(ORG_COOKIE_SLUG)?.value;
    const name = request.cookies.get(ORG_COOKIE_NAME)?.value;
    if (!id || !slug || !name) return null;
    return { id, slug, name };
}

function attachOrgHeaders(
    request: NextRequest,
    org: OrgRecord
): { response: NextResponse; headers: Headers } {
    const requestHeaders = new Headers(request.headers);
    requestHeaders.set('x-org-id', org.id);
    requestHeaders.set('x-org-slug', org.slug);
    requestHeaders.set('x-org-name', org.name);
    const response = NextResponse.next({ request: { headers: requestHeaders } });
    return { response, headers: requestHeaders };
}

function setOrgCookies(
    response: NextResponse,
    org: OrgRecord,
    secure: boolean
) {
    const baseOptions = {
        httpOnly: true,
        sameSite: 'lax' as const,
        secure,
        path: '/',
    };
    response.cookies.set(ORG_COOKIE_ID, org.id, baseOptions);
    response.cookies.set(ORG_COOKIE_SLUG, org.slug, baseOptions);
    response.cookies.set(ORG_COOKIE_NAME, org.name, baseOptions);
}

function clearOrgCookies(response: NextResponse, secure: boolean) {
    const baseOptions = {
        httpOnly: true,
        sameSite: 'lax' as const,
        secure,
        path: '/',
        maxAge: 0,
    };
    response.cookies.set(ORG_COOKIE_ID, '', baseOptions);
    response.cookies.set(ORG_COOKIE_SLUG, '', baseOptions);
    response.cookies.set(ORG_COOKIE_NAME, '', baseOptions);
}

function createHardFailureResponse(status: number, message: string): NextResponse {
    return new NextResponse(message, {
        status,
        headers: {
            'Cache-Control': 'no-store',
            'Content-Type': 'text/plain; charset=utf-8',
        },
    });
}

function createNotFoundRewrite(request: NextRequest): NextResponse {
    return NextResponse.rewrite(new URL('/_not-found', request.nextUrl), {
        status: 404,
        headers: {
            'Cache-Control': 'no-store',
        },
    });
}

function getRouteResourceApiPath(pathname: string): string | null | 'not_found' {
    const routeMatchers: Array<{
        pattern: RegExp;
        resolveApiPath: (segment: string) => string | null | 'not_found';
    }> = [
        {
            pattern: /^\/automation\/campaigns\/([^/]+)$/,
            resolveApiPath: (id) => (UUID_PARAM_RE.test(id) ? `/campaigns/${id}` : 'not_found'),
        },
        {
            pattern: /^\/automation\/forms\/([^/]+)$/,
            resolveApiPath: (id) => {
                if (id === 'new') return null;
                return UUID_PARAM_RE.test(id) ? `/forms/${id}` : 'not_found';
            },
        },
        {
            pattern: /^\/intended-parents\/matches\/([^/]+)$/,
            resolveApiPath: (id) => (UUID_PARAM_RE.test(id) ? `/matches/${id}` : 'not_found'),
        },
        {
            pattern: /^\/settings\/team\/members\/([^/]+)$/,
            resolveApiPath: (id) =>
                UUID_PARAM_RE.test(id) ? `/settings/permissions/members/${id}` : 'not_found',
        },
        {
            pattern: /^\/settings\/team\/roles\/([^/]+)$/,
            resolveApiPath: (role) => `/settings/permissions/roles/${encodeURIComponent(role)}`,
        },
        {
            pattern: /^\/ops\/templates\/email\/([^/]+)$/,
            resolveApiPath: (id) => {
                if (id === 'new') return null;
                return UUID_PARAM_RE.test(id)
                    ? `/platform/templates/email/${id}`
                    : 'not_found';
            },
        },
        {
            pattern: /^\/ops\/templates\/forms\/([^/]+)$/,
            resolveApiPath: (id) => {
                if (id === 'new') return null;
                return UUID_PARAM_RE.test(id)
                    ? `/platform/templates/forms/${id}`
                    : 'not_found';
            },
        },
        {
            pattern: /^\/ops\/templates\/workflows\/([^/]+)$/,
            resolveApiPath: (id) => {
                if (id === 'new') return null;
                return UUID_PARAM_RE.test(id)
                    ? `/platform/templates/workflows/${id}`
                    : 'not_found';
            },
        },
    ];

    for (const { pattern, resolveApiPath } of routeMatchers) {
        const match = pathname.match(pattern);
        if (!match) continue;
        return resolveApiPath(match[1] ?? '');
    }

    return null;
}

async function enforceRouteResourceHardFail(
    request: NextRequest
): Promise<NextResponse | null> {
    const apiPath = getRouteResourceApiPath(request.nextUrl.pathname);
    if (!apiPath) {
        return null;
    }

    if (apiPath === 'not_found') {
        return createNotFoundRewrite(request);
    }

    const headers = buildServerApiHeaders(request.headers, {
        'Content-Type': 'application/json',
    });
    const cookie = request.headers.get('cookie');
    if (cookie) {
        headers.set('cookie', cookie);
    }

    for (const headerName of ['x-org-id', 'x-org-slug', 'x-org-name']) {
        const value = request.headers.get(headerName);
        if (value) {
            headers.set(headerName, value);
        }
    }

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(
            () => controller.abort(),
            ROUTE_LOOKUP_TIMEOUT_MS
        );
        const res = await fetch(`${API_BASE_URL}${apiPath}`, {
            headers,
            cache: 'no-store',
            signal: controller.signal,
        }).finally(() => clearTimeout(timeoutId));

        if (res.status === 404 || res.status === 422) {
            return createNotFoundRewrite(request);
        }

        if (res.status === 401 || res.status === 403) {
            return null;
        }

        if (!res.ok) {
            console.error(
                `[middleware] API error resolving route resource ${apiPath}: ${res.status}`
            );
            return createHardFailureResponse(500, 'Route resolution failed');
        }
    } catch (error) {
        console.error(
            `[middleware] Network error resolving route resource ${apiPath}:`,
            error
        );
        return createHardFailureResponse(500, 'Route resolution failed');
    }

    return null;
}

export async function proxy(request: NextRequest) {
    const hostname = getHostname(request);
    const pathname = request.nextUrl.pathname;
    // Skip static assets, API routes, and Next.js internals
    if (
        pathname === '/health' ||
        pathname === '/_not-found' ||
        pathname.startsWith('/_next') ||
        pathname.startsWith('/api') ||
        pathname.startsWith('/static') ||
        pathname.includes('.') // Static files with extensions
    ) {
        return NextResponse.next();
    }

    const routeResourceResponse = await enforceRouteResourceHardFail(request);
    if (routeResourceResponse) {
        return routeResourceResponse;
    }

    const isDev = process.env.NODE_ENV !== 'production';
    // Local development bypass (dev only)
    if (
        isDev &&
        (hostname === 'localhost' ||
            hostname === '127.0.0.1' ||
            hostname === '::1' ||
            hostname.endsWith('.localhost') ||
            hostname.endsWith('.test'))
    ) {
        return NextResponse.next();
    }

    const opsHost = `ops.${PLATFORM_BASE_DOMAIN}`;
    if (hostname === opsHost) {
        return NextResponse.next();
    }

    // Validate hostname format: {slug}.surrogacyforce.com
    if (!hostname.endsWith(`.${PLATFORM_BASE_DOMAIN}`)) {
        if (isPlatformRootHost(hostname, PLATFORM_BASE_DOMAIN)) {
            return NextResponse.next();
        }
        return createHardFailureResponse(404, 'Organization not found');
    }

    if (isPlatformRootHost(hostname, PLATFORM_BASE_DOMAIN)) {
        return NextResponse.next();
    }

    const now = Date.now();
    const secureCookies = request.nextUrl.protocol === 'https:';
    const cookieOrg = getCookieOrg(request);
    if (cookieOrg) {
        const { response } = attachOrgHeaders(request, cookieOrg);
        return response;
    }

    const cachedEntry = getCachedEntry(hostname, now);
    if (cachedEntry) {
        if (!cachedEntry.value) {
            const response = createHardFailureResponse(404, 'Organization not found');
            clearOrgCookies(response, secureCookies);
            return response;
        }

        const { response } = attachOrgHeaders(request, cachedEntry.value);
        return response;
    }

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(
            () => controller.abort(),
            ORG_LOOKUP_TIMEOUT_MS
        );
        const res = await fetch(
            `${API_BASE_URL}/public/org-by-domain?domain=${encodeURIComponent(hostname)}`,
            {
                headers: buildServerApiHeaders(request.headers, {
                    'Content-Type': 'application/json',
                }),
                // Edge runtime doesn't support revalidate in fetch options
                cache: 'no-store',
                signal: controller.signal,
            }
        ).finally(() => clearTimeout(timeoutId));

        if (res.status === 404) {
            setCachedOrg(hostname, null, now, ORG_CACHE_TTL_MS);
            const response = createHardFailureResponse(404, 'Organization not found');
            clearOrgCookies(response, secureCookies);
            return response;
        }

        if (!res.ok) {
            console.error(
                `[middleware] API error resolving org for ${hostname}: ${res.status}`
            );
            return createHardFailureResponse(500, 'Tenant resolution failed');
        }

        const org = (await res.json()) as OrgRecord;
        setCachedOrg(hostname, org, now, ORG_CACHE_TTL_MS);

        // Pass org context via request headers for server components
        const { response } = attachOrgHeaders(request, org);
        setOrgCookies(response, org, secureCookies);
        return response;
    } catch (error) {
        console.error(
            `[middleware] Network error resolving org for ${hostname}:`,
            error
        );
        return createHardFailureResponse(500, 'Tenant resolution failed');
    }
}

export const config = {
    matcher: [
        /*
         * Match all request paths except for:
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico (favicon file)
         */
        '/((?!_next/static|_next/image|favicon.ico).*)',
    ],
};
