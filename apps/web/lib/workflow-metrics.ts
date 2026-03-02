import { recordWorkflowMetricEvent, type WorkflowMetricEventPayload } from "@/lib/api/workflow-metrics"
import { ApiError } from "@/lib/api"

const DASHBOARD_VIEWED_AT_KEY = "workflow_metrics_dashboard_viewed_at_ms"
const UNASSIGNED_VIEWED_AT_KEY = "workflow_metrics_unassigned_viewed_at_ms"
const SURROGATE_VIEWED_AT_KEY = "workflow_metrics_surrogate_viewed_at_ms"
const SURROGATE_VIEWED_ID_KEY = "workflow_metrics_surrogate_viewed_id"
const METRICS_DISABLED_UNTIL_KEY = "workflow_metrics_disabled_until_ms"
const METRICS_DISABLE_WINDOW_MS = 60 * 60 * 1000

function isBrowserRuntime(): boolean {
    return typeof window !== "undefined" && typeof window.sessionStorage !== "undefined"
}

function isMetricsTemporarilyDisabled(): boolean {
    if (!isBrowserRuntime()) return false
    const raw = window.sessionStorage.getItem(METRICS_DISABLED_UNTIL_KEY)
    if (!raw) return false

    const disabledUntil = Number(raw)
    if (!Number.isFinite(disabledUntil)) {
        window.sessionStorage.removeItem(METRICS_DISABLED_UNTIL_KEY)
        return false
    }
    if (Date.now() >= disabledUntil) {
        window.sessionStorage.removeItem(METRICS_DISABLED_UNTIL_KEY)
        return false
    }
    return true
}

function disableMetricsTemporarily(): void {
    if (!isBrowserRuntime()) return
    window.sessionStorage.setItem(
        METRICS_DISABLED_UNTIL_KEY,
        String(Date.now() + METRICS_DISABLE_WINDOW_MS),
    )
}

function sendMetricEvent(payload: WorkflowMetricEventPayload): void {
    if (process.env.NODE_ENV === "test") return
    if (isMetricsTemporarilyDisabled()) return

    void recordWorkflowMetricEvent(payload).catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 404) {
            // Endpoint unavailable on this deployment revision: stop retrying in this tab.
            disableMetricsTemporarily()
        }
        // Best effort only - never block user flows on telemetry.
    })
}

function getStoredNumber(key: string): number | null {
    if (!isBrowserRuntime()) return null
    const raw = window.sessionStorage.getItem(key)
    if (!raw) return null
    const parsed = Number(raw)
    return Number.isFinite(parsed) ? parsed : null
}

function setStoredNumber(key: string, value: number): void {
    if (!isBrowserRuntime()) return
    window.sessionStorage.setItem(key, String(value))
}

function clearPathSession(): void {
    if (!isBrowserRuntime()) return
    window.sessionStorage.removeItem(DASHBOARD_VIEWED_AT_KEY)
    window.sessionStorage.removeItem(UNASSIGNED_VIEWED_AT_KEY)
    window.sessionStorage.removeItem(SURROGATE_VIEWED_AT_KEY)
    window.sessionStorage.removeItem(SURROGATE_VIEWED_ID_KEY)
}

function createSessionId(): string {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return crypto.randomUUID()
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function trackDashboardViewed(): void {
    const now = Date.now()
    setStoredNumber(DASHBOARD_VIEWED_AT_KEY, now)
    sendMetricEvent({ event_type: "workflow_path_dashboard_viewed" })
}

export function trackUnassignedQueueViewed(): void {
    const now = Date.now()
    setStoredNumber(UNASSIGNED_VIEWED_AT_KEY, now)
    sendMetricEvent({ event_type: "workflow_path_unassigned_queue_viewed" })
}

export function trackSurrogateViewed(surrogateId: string): void {
    const now = Date.now()
    setStoredNumber(SURROGATE_VIEWED_AT_KEY, now)
    if (isBrowserRuntime()) {
        window.sessionStorage.setItem(SURROGATE_VIEWED_ID_KEY, surrogateId)
    }
    sendMetricEvent({
        event_type: "workflow_path_surrogate_viewed",
        target_type: "surrogate",
        target_id: surrogateId,
    })
}

export function trackFirstContactLogged(
    surrogateId: string,
    details: Record<string, unknown> = {}
): void {
    const now = Date.now()
    const dashboardViewedAt = getStoredNumber(DASHBOARD_VIEWED_AT_KEY)
    const unassignedViewedAt = getStoredNumber(UNASSIGNED_VIEWED_AT_KEY)
    const surrogateViewedAt = getStoredNumber(SURROGATE_VIEWED_AT_KEY)
    const viewedSurrogateId = isBrowserRuntime()
        ? window.sessionStorage.getItem(SURROGATE_VIEWED_ID_KEY)
        : null

    const enriched: Record<string, unknown> = {
        ...details,
        path_started_from_dashboard: dashboardViewedAt !== null,
        path_started_from_unassigned_queue: unassignedViewedAt !== null,
    }
    if (dashboardViewedAt !== null) {
        enriched.dashboard_to_first_contact_ms = Math.max(0, now - dashboardViewedAt)
    }
    if (unassignedViewedAt !== null) {
        enriched.unassigned_to_first_contact_ms = Math.max(0, now - unassignedViewedAt)
    }
    if (surrogateViewedAt !== null) {
        enriched.surrogate_view_to_first_contact_ms = Math.max(0, now - surrogateViewedAt)
    }
    if (viewedSurrogateId) {
        enriched.last_viewed_surrogate_id = viewedSurrogateId
        enriched.same_surrogate_path = viewedSurrogateId === surrogateId
    }

    sendMetricEvent({
        event_type: "workflow_path_first_contact_logged",
        target_type: "surrogate",
        target_id: surrogateId,
        details: enriched,
    })
    clearPathSession()
}

export function startWorkflowSetup(scope: "org" | "personal"): string {
    const sessionId = createSessionId()
    if (isBrowserRuntime()) {
        window.sessionStorage.setItem(`workflow_metrics_setup_started_at_${sessionId}`, String(Date.now()))
    }
    sendMetricEvent({
        event_type: "workflow_setup_started",
        details: {
            setup_session_id: sessionId,
            scope,
        },
    })
    return sessionId
}

export function completeWorkflowSetup(
    setupSessionId: string | null,
    scope: "org" | "personal"
): void {
    if (!setupSessionId) return
    const key = `workflow_metrics_setup_started_at_${setupSessionId}`
    const startedAt = getStoredNumber(key)
    if (isBrowserRuntime()) {
        window.sessionStorage.removeItem(key)
    }
    const details: Record<string, unknown> = {
        setup_session_id: setupSessionId,
        scope,
    }
    if (startedAt !== null) {
        details.setup_duration_ms = Math.max(0, Date.now() - startedAt)
    }
    sendMetricEvent({
        event_type: "workflow_setup_completed",
        details,
    })
}
