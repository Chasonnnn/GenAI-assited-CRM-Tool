import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const PUBLIC_PATH_PREFIXES = ['/login', '/invite', '/apply', '/book']

function isPublicPath(pathname: string): boolean {
    if (pathname.startsWith('/_next') || pathname.startsWith('/api')) return true
    if (pathname === '/favicon.ico' || pathname === '/robots.txt' || pathname === '/sitemap.xml') {
        return true
    }
    return PUBLIC_PATH_PREFIXES.some(
        (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
    )
}

export function proxy(request: NextRequest) {
    const { pathname } = request.nextUrl
    if (isPublicPath(pathname)) {
        return NextResponse.next()
    }

    const session = request.cookies.get('crm_session')
    if (!session) {
        const loginUrl = request.nextUrl.clone()
        loginUrl.pathname = '/login'
        return NextResponse.redirect(loginUrl)
    }

    return NextResponse.next()
}

export const config = {
    matcher: ['/((?!_next|api|favicon.ico).*)'],
}
