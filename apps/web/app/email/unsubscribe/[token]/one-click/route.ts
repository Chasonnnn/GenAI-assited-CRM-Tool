import { postUnsubscribeToApi } from "../unsubscribe-api"

export const dynamic = "force-dynamic"

export async function POST(
    request: Request,
    { params }: { params: Promise<{ token: string }> },
) {
    const { token } = await params
    try {
        await postUnsubscribeToApi(token, request.headers)
        return new Response("OK", {
            status: 200,
            headers: {
                "Cache-Control": "no-store",
                "Content-Type": "text/plain",
            },
        })
    } catch {
        return new Response("Service Unavailable", {
            status: 503,
            headers: {
                "Cache-Control": "no-store",
                "Content-Type": "text/plain",
                "Retry-After": "60",
            },
        })
    }
}
