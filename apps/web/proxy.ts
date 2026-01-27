import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PLATFORM_BASE_DOMAIN =
    process.env.PLATFORM_BASE_DOMAIN || 'surrogacyforce.com';
const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const ORG_CACHE_TTL_MS = 60_000;
const ORG_CACHE_STALE_MS = 5 * 60_000;
const ORG_LOOKUP_TIMEOUT_MS = 2000;

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

    // Local development bypass
    if (
        hostname === 'localhost' ||
        hostname === '127.0.0.1' ||
        hostname === '::1' ||
        hostname.endsWith('.localhost') ||
        hostname.endsWith('.test')
    ) {
        return NextResponse.next();
    }

    const opsHost = `ops.${PLATFORM_BASE_DOMAIN}`;

    if (hostname === opsHost) {
        const url = request.nextUrl.clone();
        if (pathname === '/') {
            url.pathname = '/ops';
            return NextResponse.rewrite(url);
        }
        if (pathname === '/login') {
            url.pathname = '/ops/login';
            return NextResponse.rewrite(url);
        }
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
    const cachedEntry = getCachedEntry(hostname, now);
    if (cachedEntry) {
        if (!cachedEntry.value) {
            const url = request.nextUrl.clone();
            url.pathname = '/org-not-found';
            return NextResponse.rewrite(url);
        }

        const requestHeaders = new Headers(request.headers);
        requestHeaders.set('x-org-id', cachedEntry.value.id);
        requestHeaders.set('x-org-slug', cachedEntry.value.slug);
        requestHeaders.set('x-org-name', cachedEntry.value.name);
        return NextResponse.next({ request: { headers: requestHeaders } });
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
            return NextResponse.rewrite(url);
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
                    return NextResponse.rewrite(url);
                }
                const requestHeaders = new Headers(request.headers);
                requestHeaders.set('x-org-id', staleEntry.value.id);
                requestHeaders.set('x-org-slug', staleEntry.value.slug);
                requestHeaders.set('x-org-name', staleEntry.value.name);
                return NextResponse.next({ request: { headers: requestHeaders } });
            }
            return NextResponse.next();
        }

        const org = (await res.json()) as OrgRecord;
        setCachedOrg(hostname, org, now, ORG_CACHE_TTL_MS);

        // Pass org context via request headers for server components
        const requestHeaders = new Headers(request.headers);
        requestHeaders.set('x-org-id', org.id);
        requestHeaders.set('x-org-slug', org.slug);
        requestHeaders.set('x-org-name', org.name);

        return NextResponse.next({ request: { headers: requestHeaders } });
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
                return NextResponse.rewrite(url);
            }
            const requestHeaders = new Headers(request.headers);
            requestHeaders.set('x-org-id', staleEntry.value.id);
            requestHeaders.set('x-org-slug', staleEntry.value.slug);
            requestHeaders.set('x-org-name', staleEntry.value.name);
            return NextResponse.next({ request: { headers: requestHeaders } });
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
