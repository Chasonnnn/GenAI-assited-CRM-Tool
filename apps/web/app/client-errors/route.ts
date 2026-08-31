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

export async function POST(request: Request) {
    const fetchSite = request.headers.get("sec-fetch-site")
    if (fetchSite && fetchSite !== "same-origin") {
        return new Response(null, { status: 403 })
    }
    if (request.headers.get("content-type")?.split(";", 1)[0] !== "application/json") {
        return new Response(null, { status: 415 })
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
