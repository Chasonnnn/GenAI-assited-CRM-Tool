import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

import {
    getRecordNotFoundPath,
    RECORD_NOT_FOUND_PATH,
    type RecordNotFoundKind,
} from './lib/record-not-found';
import { buildServerApiHeaders } from './lib/server-api-headers';

const PLATFORM_BASE_DOMAIN =
    process.env.PLATFORM_BASE_DOMAIN || 'surrogacyforce.com';
const ORG_CACHE_TTL_MS = 60_000;
const ORG_LOOKUP_TIMEOUT_MS = 5000;
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
    return (
        hostname === platformBaseDomain ||
        hostname === `www.${platformBaseDomain}` ||
        hostname === `app.${platformBaseDomain}`
    );
}

export function getServerApiBaseUrl(): string {
    return process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
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

function createTenantRootRedirect(
    request: NextRequest,
    org: OrgRecord,
    secure: boolean
): NextResponse | null {
    if (request.nextUrl.pathname !== '/') {
        return null;
    }

    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = '/login';
    loginUrl.search = '';
    loginUrl.hash = '';

    const response = NextResponse.redirect(loginUrl);
    setOrgCookies(response, org, secure);
    return response;
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

function createTenantUnavailableResponse(): NextResponse {
    const response = createHardFailureResponse(
        503,
        'Tenant service temporarily unavailable'
    );
    response.headers.set('Retry-After', '5');
    return response;
}

/**
 * Rewrites to a not-found page with a 404 status. App-shell records pass their kind so
 * the state renders inside app/(app)/layout; other routes use the root not-found page.
 */
function createNotFoundRewrite(
    request: NextRequest,
    recordKind?: RecordNotFoundKind
): NextResponse {
    const target = recordKind ? getRecordNotFoundPath(recordKind) : '/_not-found';
    return NextResponse.rewrite(new URL(target, request.nextUrl), {
        status: 404,
        headers: {
            'Cache-Control': 'no-store',
        },
    });
}

function isRecordNotFoundPath(pathname: string): boolean {
    return (
        pathname === RECORD_NOT_FOUND_PATH ||
        pathname.startsWith(`${RECORD_NOT_FOUND_PATH}/`)
    );
}

type RouteResource = {
    apiPath: string | null | 'not_found';
    recordKind: RecordNotFoundKind | undefined;
};

function getRouteResource(pathname: string): RouteResource | null {
    const routeMatchers: Array<{
        pattern: RegExp;
        recordKind?: RecordNotFoundKind;
        resolveApiPath: (segment: string) => string | null | 'not_found';
    }> = [
        {
            pattern: /^\/automation\/campaigns\/([^/]+)$/,
            recordKind: 'campaign',
            resolveApiPath: (id) => (UUID_PARAM_RE.test(id) ? `/campaigns/${id}` : 'not_found'),
        },
        {
            pattern: /^\/automation\/forms\/([^/]+)$/,
            recordKind: 'form',
            resolveApiPath: (id) => {
                if (id === 'new') return null;
                return UUID_PARAM_RE.test(id) ? `/forms/${id}` : 'not_found';
            },
        },
        {
            pattern: /^\/intended-parents\/matches\/([^/]+)$/,
            recordKind: 'match',
            resolveApiPath: (id) => (UUID_PARAM_RE.test(id) ? `/matches/${id}` : 'not_found'),
        },
        {
            pattern: /^\/settings\/team\/members\/([^/]+)$/,
            recordKind: 'member',
            resolveApiPath: (id) =>
                UUID_PARAM_RE.test(id) ? `/settings/permissions/members/${id}` : 'not_found',
        },
        {
            pattern: /^\/settings\/team\/roles\/([^/]+)$/,
            recordKind: 'role',
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

    for (const { pattern, recordKind, resolveApiPath } of routeMatchers) {
        const match = pathname.match(pattern);
        if (!match) continue;
        return { apiPath: resolveApiPath(match[1] ?? ''), recordKind };
    }

    return null;
}

async function enforceRouteResourceHardFail(
    request: NextRequest
): Promise<NextResponse | null> {
    const resource = getRouteResource(request.nextUrl.pathname);
    if (!resource?.apiPath) {
        return null;
    }

    const { apiPath, recordKind } = resource;
    if (apiPath === 'not_found') {
        return createNotFoundRewrite(request, recordKind);
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
        const res = await fetch(`${getServerApiBaseUrl()}${apiPath}`, {
            headers,
            cache: 'no-store',
            signal: controller.signal,
        }).finally(() => clearTimeout(timeoutId));

        if (res.status === 404 || res.status === 422) {
            return createNotFoundRewrite(request, recordKind);
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

async function applyEmbedFramePolicy(request: NextRequest): Promise<NextResponse | null> {
    const match = request.nextUrl.pathname.match(/^\/embed\/forms\/([^/]+)$/);
    if (!match) {
        return null;
    }
    const slug = match[1] ?? '';
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(
            () => controller.abort(),
            ROUTE_LOOKUP_TIMEOUT_MS
        );
        const res = await fetch(
            `${getServerApiBaseUrl()}/forms/public/embed/${encodeURIComponent(slug)}/frame-policy`,
            {
                headers: buildServerApiHeaders(request.headers, {
                    'Content-Type': 'application/json',
                }),
                cache: 'no-store',
                signal: controller.signal,
            }
        ).finally(() => clearTimeout(timeoutId));

        if (res.status === 404 || res.status === 403) {
            return createNotFoundRewrite(request);
        }
        if (!res.ok) {
            console.error(`[middleware] API error resolving embed frame policy ${slug}: ${res.status}`);
            return createHardFailureResponse(500, 'Embed policy resolution failed');
        }

        const payload = (await res.json()) as { content_security_policy?: string };
        const response = NextResponse.next();
        if (payload.content_security_policy) {
            response.headers.set('Content-Security-Policy', payload.content_security_policy);
        }
        response.headers.set('Cache-Control', 'no-store');
        return response;
    } catch (error) {
        console.error(`[middleware] Network error resolving embed frame policy ${slug}:`, error);
        return createHardFailureResponse(500, 'Embed policy resolution failed');
    }
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

    // `next dev` runs the proxy again for the rewritten path and takes the status from that
    // pass. The app shell renders pages only on the client, so a page notFound() cannot
    // set the status either. Keep the 404 here for that pass and for direct requests.
    if (isRecordNotFoundPath(pathname)) {
        return NextResponse.next({
            status: 404,
            headers: {
                'Cache-Control': 'no-store',
            },
        });
    }

    const embedFramePolicyResponse = await applyEmbedFramePolicy(request);
    if (embedFramePolicyResponse) {
        return embedFramePolicyResponse;
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
        const redirect = createTenantRootRedirect(request, cookieOrg, secureCookies);
        if (redirect) {
            return redirect;
        }

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

        const redirect = createTenantRootRedirect(request, cachedEntry.value, secureCookies);
        if (redirect) {
            return redirect;
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
            `${getServerApiBaseUrl()}/public/org-by-domain?domain=${encodeURIComponent(hostname)}`,
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
            return createTenantUnavailableResponse();
        }

        const org = (await res.json()) as OrgRecord;
        setCachedOrg(hostname, org, now, ORG_CACHE_TTL_MS);

        const redirect = createTenantRootRedirect(request, org, secureCookies);
        if (redirect) {
            return redirect;
        }

        // Pass org context via request headers for server components
        const { response } = attachOrgHeaders(request, org);
        setOrgCookies(response, org, secureCookies);
        return response;
    } catch (error) {
        console.error(
            `[middleware] Network error resolving org for ${hostname}:`,
            error
        );
        return createTenantUnavailableResponse();
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
