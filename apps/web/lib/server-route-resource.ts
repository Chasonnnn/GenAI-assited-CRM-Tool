import { headers } from "next/headers"

import { buildServerApiHeaders } from "@/lib/server-api-headers"

export type ServerRouteResourceStatus = "ok" | "not_found" | "pass_through"

type ServerRouteResourceOptions = {
    passThroughStatuses?: number[]
}

const DEFAULT_PASS_THROUGH_STATUSES = [401, 403]

export class ServerRouteResourceError extends Error {
    constructor(
        public readonly status: number,
        path: string,
    ) {
        super(`Failed route resource request for ${path}: ${status}`)
        this.name = "ServerRouteResourceError"
    }
}

async function requestServerRouteResource(path: string) {
    const requestHeaders = await headers()
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
    const upstreamHeaders = buildServerApiHeaders(requestHeaders)
    const forwardedHeaders = ["cookie", "x-org-id", "x-org-slug", "x-org-name"]

    for (const headerName of forwardedHeaders) {
        const value = requestHeaders.get(headerName)
        if (value) {
            upstreamHeaders.set(headerName, value)
        }
    }

    return fetch(`${apiBase}${path}`, {
        cache: "no-store",
        headers: upstreamHeaders,
    })
}

export async function fetchServerRouteResource<T>(path: string): Promise<T> {
    const response = await requestServerRouteResource(path)

    if (!response.ok) {
        throw new ServerRouteResourceError(response.status, path)
    }

    return response.json() as Promise<T>
}

export async function getServerRouteResourceStatus(
    path: string,
    options: ServerRouteResourceOptions = {},
): Promise<ServerRouteResourceStatus> {
    const passThroughStatuses =
        options.passThroughStatuses ?? DEFAULT_PASS_THROUGH_STATUSES
    const response = await requestServerRouteResource(path)

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
