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
    const submissionId = form.get("submission_id")
    const redirect = new URL(`/public/messaging-consent/${encodeURIComponent(token)}`, request.url)
    if (
        (action !== "opt_in" && action !== "opt_out")
        || (purpose !== "operational" && purpose !== "promotional")
        || typeof submissionId !== "string"
        || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(submissionId)
    ) {
        redirect.searchParams.set("error", "invalid")
        return NextResponse.redirect(redirect, 303)
    }
    try {
        await updateMessagingPreference(token, request.headers, {
            action,
            purposes: [purpose],
            submission_id: submissionId,
        })
        redirect.searchParams.set("status", "updated")
    } catch {
        redirect.searchParams.set("error", "update")
    }
    return NextResponse.redirect(redirect, 303)
}
