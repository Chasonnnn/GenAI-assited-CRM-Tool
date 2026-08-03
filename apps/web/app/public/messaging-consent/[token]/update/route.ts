import { NextResponse } from "next/server"

import { updateMessagingPreference } from "../preference-api"

export const dynamic = "force-dynamic"

export async function POST(
    request: Request,
    { params }: { params: Promise<{ token: string }> },
) {
    const { token } = await params
    const form = await request.formData()
    const action = form.get("action")
    const purpose = form.get("purpose")
    const redirect = new URL(`/public/messaging-consent/${encodeURIComponent(token)}`, request.url)
    if (
        (action !== "opt_in" && action !== "opt_out")
        || (purpose !== "operational" && purpose !== "promotional")
    ) {
        redirect.searchParams.set("error", "invalid")
        return NextResponse.redirect(redirect, 303)
    }
    try {
        await updateMessagingPreference(token, request.headers, {
            action,
            purposes: [purpose],
        })
        redirect.searchParams.set("status", "updated")
    } catch {
        redirect.searchParams.set("error", "update")
    }
    return NextResponse.redirect(redirect, 303)
}
