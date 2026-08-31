import { getCsrfHeaders } from "@/lib/csrf"

export type ClientErrorKind =
    | "window_error"
    | "unhandled_rejection"
    | "react_error_boundary"

const ERROR_CLASSES = new Set([
    "Error",
    "TypeError",
    "ReferenceError",
    "RangeError",
    "SyntaxError",
    "URIError",
    "EvalError",
    "AggregateError",
])
const reported = new Set<string>()

function normalizeErrorClass(value: unknown): string {
    if (typeof DOMException !== "undefined" && value instanceof DOMException) {
        return "DOMException"
    }
    if (!(value instanceof Error)) {
        return "NonError"
    }
    return ERROR_CLASSES.has(value.name) ? value.name : "Error"
}

export function reportClientError(kind: ClientErrorKind, error: unknown): void {
    const errorClass = normalizeErrorClass(error)
    const fingerprint = `${kind}:${errorClass}`
    if (reported.has(fingerprint)) {
        return
    }
    reported.add(fingerprint)

    try {
        void fetch("/client-errors", {
            method: "POST",
            credentials: "include",
            keepalive: true,
            cache: "no-store",
            headers: {
                "content-type": "application/json",
                ...getCsrfHeaders(),
            },
            body: JSON.stringify({ kind, errorClass }),
        }).catch(() => undefined)
    } catch {
        // Telemetry must never interfere with the user-facing error path.
    }
}
