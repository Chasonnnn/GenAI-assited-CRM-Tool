import { getApiBase } from "@/lib/api-base"

const ERROR_KINDS = new Set([
    "window_error",
    "unhandled_rejection",
    "react_error_boundary",
])
const ERROR_CLASSES = new Set([
    "Error",
    "TypeError",
    "ReferenceError",
    "RangeError",
    "SyntaxError",
    "URIError",
    "EvalError",
    "AggregateError",
    "DOMException",
    "NonError",
])
const SESSION_COOKIE_NAME = "crm_session"
const CSRF_COOKIE_NAME = "crm_csrf"
const CSRF_HEADER_NAME = "x-csrf-token"

function getCookieValue(cookieHeader: string, name: string): string | null {
    const prefix = `${name}=`
    for (const part of cookieHeader.split(";")) {
        const cookie = part.trim()
        if (cookie.startsWith(prefix)) {
            return cookie.slice(prefix.length) || null
        }
    }
    return null
}

function getPublicOrigin(request: Request): string | null {
    const requestUrl = new URL(request.url)
    const forwardedHost = request.headers.get("x-forwarded-host")?.split(",", 1)[0]?.trim()
    const host = forwardedHost || request.headers.get("host") || requestUrl.host
    const forwardedProto = request.headers.get("x-forwarded-proto")?.split(",", 1)[0]?.trim()
    const protocol = forwardedProto === "http" || forwardedProto === "https"
        ? `${forwardedProto}:`
        : requestUrl.protocol

    try {
        const origin = new URL(`${protocol}//${host}`)
        if (process.env.NODE_ENV === "production") {
            const platformDomain = process.env.PLATFORM_BASE_DOMAIN?.toLowerCase()
            const hostname = origin.hostname.toLowerCase()
            if (
                protocol !== "https:"
                || !platformDomain
                || (hostname !== platformDomain && !hostname.endsWith(`.${platformDomain}`))
            ) {
                return null
            }
        }
        return origin.origin
    } catch {
        return null
    }
}

async function hasAuthenticatedSession(request: Request, cookie: string): Promise<boolean> {
    const origin = getPublicOrigin(request)
    if (!origin) {
        return false
    }

    try {
        const response = await fetch(`${getApiBase()}/auth/me`, {
            cache: "no-store",
            headers: {
                cookie,
                origin,
            },
        })
        return response.ok
    } catch {
        return false
    }
}

export async function POST(request: Request) {
    const fetchSite = request.headers.get("sec-fetch-site")
    if (fetchSite && fetchSite !== "same-origin") {
        return new Response(null, { status: 403 })
    }
    if (request.headers.get("content-type")?.split(";", 1)[0] !== "application/json") {
        return new Response(null, { status: 415 })
    }
    const cookie = request.headers.get("cookie")
    if (!cookie || !getCookieValue(cookie, SESSION_COOKIE_NAME)) {
        return new Response(null, { status: 401 })
    }
    const csrfCookie = getCookieValue(cookie, CSRF_COOKIE_NAME)
    const csrfHeader = request.headers.get(CSRF_HEADER_NAME)
    if (!csrfCookie || !csrfHeader || csrfCookie !== csrfHeader) {
        return new Response(null, { status: 403 })
    }
    if (!(await hasAuthenticatedSession(request, cookie))) {
        return new Response(null, { status: 401 })
    }

    let payload: unknown
    try {
        payload = await request.json()
    } catch {
        return new Response(null, { status: 400 })
    }

    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        return new Response(null, { status: 400 })
    }

    const fields = payload as Record<string, unknown>
    const keys = Object.keys(fields)
    if (
        keys.length !== 2
        || !keys.includes("kind")
        || !keys.includes("errorClass")
        || typeof fields.kind !== "string"
        || !ERROR_KINDS.has(fields.kind)
        || typeof fields.errorClass !== "string"
        || !ERROR_CLASSES.has(fields.errorClass)
    ) {
        return new Response(null, { status: 400 })
    }

    console.error(JSON.stringify({
        severity: "ERROR",
        event: "frontend_client_error",
        service: "crm-web",
        revision: process.env.K_REVISION ?? "unknown",
        kind: fields.kind,
        error_class: fields.errorClass,
    }))

    return new Response(null, { status: 204 })
}
