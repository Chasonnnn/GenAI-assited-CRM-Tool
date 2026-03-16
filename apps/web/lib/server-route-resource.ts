import { headers } from "next/headers"

import { buildServerApiHeaders } from "@/lib/server-api-headers"

export type ServerRouteResourceStatus = "ok" | "not_found" | "pass_through"

type ServerRouteResourceOptions = {
    passThroughStatuses?: number[]
}

const DEFAULT_PASS_THROUGH_STATUSES = [401, 403]

export async function getServerRouteResourceStatus(
    path: string,
    options: ServerRouteResourceOptions = {},
): Promise<ServerRouteResourceStatus> {
    const requestHeaders = await headers()
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
    const upstreamHeaders = buildServerApiHeaders(requestHeaders)
    const cookieHeader = requestHeaders.get("cookie")
    const orgId = requestHeaders.get("x-org-id")
    const orgSlug = requestHeaders.get("x-org-slug")
    const orgName = requestHeaders.get("x-org-name")
    const passThroughStatuses =
        options.passThroughStatuses ?? DEFAULT_PASS_THROUGH_STATUSES

    if (cookieHeader) {
        upstreamHeaders.set("cookie", cookieHeader)
    }
    if (orgId) {
        upstreamHeaders.set("x-org-id", orgId)
    }
    if (orgSlug) {
        upstreamHeaders.set("x-org-slug", orgSlug)
    }
    if (orgName) {
        upstreamHeaders.set("x-org-name", orgName)
    }

    const response = await fetch(`${apiBase}${path}`, {
        cache: "no-store",
        headers: upstreamHeaders,
    })

    if (response.status === 404) {
        return "not_found"
    }

    if (passThroughStatuses.includes(response.status)) {
        return "pass_through"
    }

    if (!response.ok) {
        throw new Error(`Failed route resource check for ${path}: ${response.status}`)
    }

    return "ok"
}
