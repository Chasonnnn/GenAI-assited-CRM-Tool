import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PLATFORM_BASE_DOMAIN =
    process.env.PLATFORM_BASE_DOMAIN || 'surrogacyforce.com';
const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const ORG_CACHE_TTL_MS = 60_000;
const ORG_CACHE_STALE_MS = 5 * 60_000;
const ORG_LOOKUP_TIMEOUT_MS = 2000;
const ORG_COOKIE_ID = 'sf_org_id';
const ORG_COOKIE_SLUG = 'sf_org_slug';
const ORG_COOKIE_NAME = 'sf_org_name';

type OrgRecord = {
    id: string;
    slug: string;
    name: string;
};

type OrgCacheEntry = {
    value: OrgRecord | null;
    expiresAt: number;
    staleUntil: number;
};

const orgCache = new Map<string, OrgCacheEntry>();

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

function getStaleEntry(hostname: string, now: number) {
    const cached = orgCache.get(hostname);
    if (!cached) return null;
    if (cached.staleUntil >= now) return cached;
    return null;
}

function setCachedOrg(hostname: string, value: OrgRecord | null, now: number, ttlMs: number) {
    orgCache.set(hostname, {
        value,
        expiresAt: now + ttlMs,
        staleUntil: now + ORG_CACHE_STALE_MS,
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

export async function proxy(request: NextRequest) {
    const hostname = getHostname(request);
    const pathname = request.nextUrl.pathname;
    // Skip static assets, API routes, and Next.js internals
    if (
        pathname.startsWith('/_next') ||
        pathname.startsWith('/api') ||
        pathname.startsWith('/static') ||
        pathname.includes('.') // Static files with extensions
    ) {
        return NextResponse.next();
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
        if (hostname === PLATFORM_BASE_DOMAIN) {
            return NextResponse.next();
        }
        // Unknown domain - show org not found
        const url = request.nextUrl.clone();
        url.pathname = '/org-not-found';
        return NextResponse.rewrite(url);
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
            const url = request.nextUrl.clone();
            url.pathname = '/org-not-found';
            const response = NextResponse.rewrite(url);
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
                headers: { 'Content-Type': 'application/json' },
                // Edge runtime doesn't support revalidate in fetch options
                cache: 'no-store',
                signal: controller.signal,
            }
        ).finally(() => clearTimeout(timeoutId));

        if (res.status === 404) {
            setCachedOrg(hostname, null, now, ORG_CACHE_TTL_MS);
            const url = request.nextUrl.clone();
            url.pathname = '/org-not-found';
            const response = NextResponse.rewrite(url);
            clearOrgCookies(response, secureCookies);
            return response;
        }

        if (!res.ok) {
            // API error (not 404) - let the request through to show a proper error page
            console.error(
                `[middleware] API error resolving org for ${hostname}: ${res.status}`
            );
            const staleEntry = getStaleEntry(hostname, now);
            if (staleEntry) {
                if (!staleEntry.value) {
                    const url = request.nextUrl.clone();
                    url.pathname = '/org-not-found';
                    const response = NextResponse.rewrite(url);
                    clearOrgCookies(response, secureCookies);
                    return response;
                }
                const { response } = attachOrgHeaders(request, staleEntry.value);
                return response;
            }
            return NextResponse.next();
        }

        const org = (await res.json()) as OrgRecord;
        setCachedOrg(hostname, org, now, ORG_CACHE_TTL_MS);

        // Pass org context via request headers for server components
        const { response } = attachOrgHeaders(request, org);
        setOrgCookies(response, org, secureCookies);
        return response;
    } catch (error) {
        // Network error - let the request through to avoid blocking users
        console.error(
            `[middleware] Network error resolving org for ${hostname}:`,
            error
        );
        const staleEntry = getStaleEntry(hostname, Date.now());
        if (staleEntry) {
            if (!staleEntry.value) {
                const url = request.nextUrl.clone();
                url.pathname = '/org-not-found';
                const response = NextResponse.rewrite(url);
                clearOrgCookies(response, secureCookies);
                return response;
            }
            const { response } = attachOrgHeaders(request, staleEntry.value);
            return response;
        }
        return NextResponse.next();
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
