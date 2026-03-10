import { NextResponse } from "next/server"

import { buildServerApiHeaders } from "@/lib/server-api-headers"

export const dynamic = "force-dynamic"

async function _postToApi(token: string, requestHeaders: Headers) {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
    const safeToken = encodeURIComponent(token || "")
    if (!safeToken) return

    // Best-effort: API endpoint is responsible for recording suppressions.
    try {
        await fetch(`${apiBase}/email/unsubscribe/${safeToken}`, {
            method: "POST",
            cache: "no-store",
            headers: buildServerApiHeaders(requestHeaders),
        })
    } catch {
        // Ignore failures to avoid leaking availability details.
    }
}

export async function POST(
    request: Request,
    { params }: { params: Promise<{ token: string }> }
) {
    const { token } = await params
    await _postToApi(token, request.headers)
    return new Response("OK", { status: 200, headers: { "Content-Type": "text/plain" } })
}

export async function GET(
    _request: Request,
    { params }: { params: Promise<{ token: string }> }
) {
    const { token } = await params
    // Some clients may call the List-Unsubscribe URL directly via GET.
    // Redirect to the user-facing page (which also performs the unsubscribe).
    return NextResponse.redirect(new URL(`/email/unsubscribe/${encodeURIComponent(token)}`, _request.url))
}
