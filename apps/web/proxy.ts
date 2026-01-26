import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PLATFORM_BASE_DOMAIN =
    process.env.PLATFORM_BASE_DOMAIN || 'surrogacyforce.com';
const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export async function proxy(request: NextRequest) {
    const hostname = request.headers.get('host')?.split(':')[0] || '';
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
        hostname.endsWith('.localhost') ||
        hostname.endsWith('.test')
    ) {
        return NextResponse.next();
    }

    const opsHost = `ops.${PLATFORM_BASE_DOMAIN}`;

    if (hostname === opsHost) {
        if (pathname === '/' || pathname === '/dashboard') {
            return NextResponse.redirect(new URL('/ops', request.url));
        }
        return NextResponse.next();
    }

    // Validate hostname format: {slug}.surrogacyforce.com
    if (!hostname.endsWith(`.${PLATFORM_BASE_DOMAIN}`)) {
        if (hostname === PLATFORM_BASE_DOMAIN) {
            return NextResponse.next();
        }
        // Unknown domain - show org not found
        return NextResponse.rewrite(new URL('/org-not-found', request.url));
    }

    try {
        const res = await fetch(
            `${API_BASE_URL}/public/org-by-domain?domain=${encodeURIComponent(hostname)}`,
            {
                headers: { 'Content-Type': 'application/json' },
                // Edge runtime doesn't support revalidate in fetch options
                cache: 'no-store',
            }
        );

        if (res.status === 404) {
            return NextResponse.rewrite(new URL('/org-not-found', request.url));
        }

        if (!res.ok) {
            // API error (not 404) - let the request through to show a proper error page
            console.error(
                `[middleware] API error resolving org for ${hostname}: ${res.status}`
            );
            return NextResponse.next();
        }

        const org = await res.json();

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
