import { reportClientError } from "@/lib/client-error-telemetry"

try {
    window.addEventListener("error", (event) => {
        reportClientError("window_error", event.error)
    })
    window.addEventListener("unhandledrejection", (event) => {
        reportClientError("unhandled_rejection", event.reason)
    })
} catch {
    // Instrumentation must not block hydration.
}
