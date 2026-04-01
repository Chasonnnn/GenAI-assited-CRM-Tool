type LocationLike = {
    protocol: string
    hostname: string
}

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1"])

function formatUrl(url: URL): string {
    const path = url.pathname === "/" ? "" : url.pathname
    return `${url.protocol}//${url.host}${path}${url.search}${url.hash}`
}

export function resolveApiBase(base: string, location?: LocationLike): string {
    if (!location || base.startsWith("/")) {
        return base
    }

    const resolved = new URL(base)

    if (location.protocol === "https:" && resolved.protocol === "http:") {
        resolved.protocol = "https:"
    }

    if (LOOPBACK_HOSTS.has(location.hostname) && LOOPBACK_HOSTS.has(resolved.hostname)) {
        resolved.hostname = location.hostname
    }

    return formatUrl(resolved)
}

export function getApiBase(): string {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

    if (typeof window !== "undefined") {
        return resolveApiBase(base, window.location)
    }

    return base
}
