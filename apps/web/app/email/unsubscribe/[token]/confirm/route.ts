import { NextResponse } from "next/server"

import { postUnsubscribeToApi } from "../unsubscribe-api"

export const dynamic = "force-dynamic"

export async function POST(
    request: Request,
    { params }: { params: Promise<{ token: string }> },
) {
    const { token } = await params
    await postUnsubscribeToApi(token, request.headers)

    const redirectUrl = new URL(`/email/unsubscribe/${encodeURIComponent(token)}`, request.url)
    redirectUrl.searchParams.set("status", "unsubscribed")
    return NextResponse.redirect(redirectUrl, 303)
}
