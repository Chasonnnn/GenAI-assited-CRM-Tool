# GCP Monitoring Runbook

This runbook documents GCP Monitoring setup and alert routing verification for non-dev environments.

## Prerequisites
- Runtime service account has:
  - `roles/logging.logWriter`
  - `roles/monitoring.metricWriter`
- API service has one of the following env vars set:
  - `GCP_PROJECT_ID` or `GOOGLE_CLOUD_PROJECT`
 - Monitoring notification channel exists (Slack/email), created out-of-band.

## Setup Checklist
0. If using Terraform, set `alert_notification_channel_ids` to your Monitoring channel ID.
1. Confirm env vars on the API service:
   - `GCP_PROJECT_ID` or `GOOGLE_CLOUD_PROJECT`
2. Confirm logs are flowing to Cloud Logging.
3. Create Monitoring dashboards (optional but recommended):
   - Request rate, error rate, latency, DB connections.
4. Configure log-based metrics for app alerts:
   - Metric: `ws_send_failed_count`
     - Filter: `jsonPayload.event="ws_send_failed"`
     - Label extractors:
       - `org_id`: `EXTRACT(jsonPayload.org_id)`
       - `user_id`: `EXTRACT(jsonPayload.user_id)`
       - `message_type`: `EXTRACT(jsonPayload.message_type)`
   - Metric: `gcp_alert_ingested_count`
     - Filter: `jsonPayload.event="gcp_alert_ingested"`
     - Label extractors:
       - `org_id`: `EXTRACT(jsonPayload.org_id)`
   - Note: use log-based metrics only; no app-side counters needed.
5. Create alert policies from log-based metrics:
   - `ws_send_failed_count` > 0 for 5m (per org).
   - Optional: `gcp_alert_ingested_count` for webhook health verification.
6. Ticketing/email ingestion operational metrics (Terraform-managed):
   - `ticketing_outbound_failures` (worker outbound send failures)
   - `mailbox_ingestion_failures` (mailbox backfill/history/parse/stitch/link failures)
   - Alert policies fire when either metric is > 0 for 5 minutes.
7. For API SLI checks, use `/ops/sli` and review the `ticketing_email` workflow group.
8. For dead-letter remediation, use one of:
   - API: `GET /jobs/dlq`, `POST /jobs/{job_id}/replay`, `POST /jobs/dlq/replay`
   - CLI: `python -m app.cli replay-failed-jobs --org-id <uuid> --job-type ticket_outbound_send`
9. Wire Monitoring webhook notifications to the app:
   - Webhook URL: `https://<api-base>/internal/alerts/gcp`
   - Header: `X-Internal-Secret: <INTERNAL_SECRET>`

## Alert Routing Verification (Required)
1. Create a temporary alert policy with a low threshold (example: 5xx > 1 in 5 minutes).
2. Trigger the alert using a controlled failure (staging only).
3. Confirm the notification arrives in the configured channel (email/Slack/PagerDuty).
4. Disable or remove the temporary alert policy.

## Alert Test Log
| Date (UTC) | Environment | Policy | Channel | Result | Verified By | Notes |
|---|---|---|---|---|---|---|
| | | | | | | |
