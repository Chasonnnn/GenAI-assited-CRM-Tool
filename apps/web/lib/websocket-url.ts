import { resolveApiBase } from "@/lib/api-base"

type LocationLike = {
    protocol: string
    hostname: string
    host?: string
}

function resolveWebSocketBase(apiBase: string, location?: LocationLike): string {
    if (apiBase.startsWith("/")) {
        if (!location) {
            return apiBase
        }

        const protocol = location.protocol === "https:" ? "wss:" : "ws:"
        const host = location.host ?? location.hostname
        return `${protocol}//${host}${apiBase}`
    }

    return resolveApiBase(apiBase, location).replace(/^http/, "ws")
}

export function resolveWebSocketUrl(
    apiBase: string,
    path: string,
    location?: LocationLike
): string {
    const base = resolveWebSocketBase(apiBase, location).replace(/\/$/, "")
    return `${base}${path}`
}

export function getWebSocketUrl(path: string, location?: LocationLike): string {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
    const resolvedLocation =
        location ?? (typeof window !== "undefined" ? window.location : undefined)
    return resolveWebSocketUrl(apiBase, path, resolvedLocation)
}
