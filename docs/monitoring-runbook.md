# GCP Monitoring Runbook

This runbook documents GCP Monitoring setup and alert routing verification for non-dev environments.

## Prerequisites
- Runtime service account has:
  - `roles/logging.logWriter`
  - `roles/monitoring.metricWriter`
- API service has one of the following env vars set:
  - `GCP_PROJECT_ID` or `GOOGLE_CLOUD_PROJECT`

## Setup Checklist
1. Confirm env vars on the API service:
   - `GCP_PROJECT_ID` or `GOOGLE_CLOUD_PROJECT`
2. Confirm logs are flowing to Cloud Logging.
3. Create Monitoring dashboards (optional but recommended):
   - Request rate, error rate, latency, DB connections.

## Alert Routing Verification (Required)
1. Create a temporary alert policy with a low threshold (example: 5xx > 1 in 5 minutes).
2. Trigger the alert using a controlled failure (staging only).
3. Confirm the notification arrives in the configured channel (email/Slack/PagerDuty).
4. Disable or remove the temporary alert policy.

## Alert Test Log
| Date (UTC) | Environment | Policy | Channel | Result | Verified By | Notes |
|---|---|---|---|---|---|---|
| | | | | | | |
