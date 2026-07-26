export type ResendReadinessFreshness = "fresh" | "stale" | "never_checked"
export type ResendReadinessProbeStatus = "succeeded" | "limited" | "failed"
export type ResendReadinessCapabilityStatus =
    | "ready"
    | "needs_attention"
    | "limited"
    | "unknown"
    | "not_configured"
export type ResendReadinessCheckStatus = "idle" | "queued" | "running"
export type ResendReadinessIssueCode =
    | "admission_unavailable"
    | "credential_rejected"
    | "credential_unavailable"
    | "delivery_events_missing"
    | "domain_not_verified"
    | "engagement_events_missing"
    | "invalid_provider_response"
    | "limited_visibility"
    | "provider_unavailable"
    | "sending_disabled"
    | "snapshot_stale"
    | "timeout"
    | "webhook_disabled"
    | "webhook_missing"

export interface ResendReadinessSnapshot {
    freshness: ResendReadinessFreshness
    probe_status: ResendReadinessProbeStatus | null
    overall_status: ResendReadinessCapabilityStatus
    domain_status: ResendReadinessCapabilityStatus
    webhook_status: ResendReadinessCapabilityStatus
    sending_status: ResendReadinessCapabilityStatus
    delivery_tracking_status: ResendReadinessCapabilityStatus
    engagement_tracking_status: ResendReadinessCapabilityStatus
    verified_domain_count: number
    enabled_webhook_count: number
    issue_codes: ResendReadinessIssueCode[]
    checked_at: string | null
    last_success_at: string | null
}

export interface ResendReadinessEnvelope {
    check_status: ResendReadinessCheckStatus
    last_snapshot: ResendReadinessSnapshot
}
