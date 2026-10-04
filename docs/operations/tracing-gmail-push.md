# Cloud Trace and Gmail push

## Runtime settings

The deployment's ignored `infra/terraform/terraform.tfvars` owns activation:

```hcl
private_tracing_enabled     = true
private_tracing_sample_rate = 0.1
gmail_push_enabled          = true
```

Cloud Trace receives sanitized API spans through a loopback OTLP/HTTP receiver.
The Google collector uses the API service account; no static cloud keys are used.
The collector adds one CPU and 256 MiB per API instance. Tracing switches the API
service to instance-based CPU allocation so batches drain after requests finish.
Existing minimum and maximum instance limits remain in effect. Sampling limits
trace ingestion, not collector compute cost. Worker tracing is outside this rollout.

The collector accepts traces only. The application removes raw URLs, query strings,
headers, SQL, exception details, and unapproved attributes before export. The
collector adds only the deployment project ID. Existing logs and metrics retain
their separate controls. Google-built collector 0.160.0 is pinned and its configuration
is validated with that image before deployment.

Gmail Pub/Sub uses a dedicated service account, verified Google signatures, exact
audience and subscription matching, and verified sender email. The former optional
query-token authentication is removed. Missing authentication configuration returns
503; invalid credentials never enqueue work. Key-fetch failures return a sanitized
503 so Pub/Sub can retry. Public webhook organization scope comes from the matched
mailbox, never a supplied organization ID.

## Activation order

1. Verify the Google OAuth client belongs to the Terraform project. Gmail requires
   the watch topic to belong to the project executing the watch request.
2. Verify enabled Gmail mailboxes have read-capable credentials. Reconnect only
   connections missing the required permission; do not create or enable mailboxes
   as a side effect of this rollout.
3. Deploy the API authentication changes and the sidecar-aware Cloud Build release
   command before enabling either Terraform flag. The release script selects the
   application container and preserves the collector and runtime environment.
4. Review a saved Terraform plan with the deployment variable file. Apply only
   reviewed task-owned changes; preserve existing service images and runtime flags.
5. Terraform provisions Gmail's publisher grant, subscription, push identity and
   token-signing grant before enabling worker watches. The API then receives the
   exact subscription identity. Transient delivery failures retry with bounded
   backoff; Pub/Sub retains unacknowledged messages for seven days.
6. Confirm enabled mailbox watches renew successfully and show a future expiration.
   The existing one-minute worker scheduler renews watches within 24 hours of expiry.
   Watch refresh does not advance the ingestion history cursor. Polling stays enabled.
7. Confirm a Google-generated watch notification is acknowledged and its mailbox
   history job completes. Confirm an actual incoming mailbox change reaches the
   existing ingestion pipeline without duplicate work; do not send external mail
   merely to test the feature without authorization.
8. Verify sampled non-health requests appear in Cloud Trace, with route templates
   and timing but no raw request or provider data. Check API/collector errors and
   Pub/Sub delivery backlog. The existing alert channels receive a backlog alert
   when notification age remains above five minutes for five minutes.

## Rollback

Disable `private_tracing_enabled` in the deployment variable file and apply the
reviewed API plan to remove the collector and restore normal CPU allocation.

Disable `gmail_push_enabled` and apply the reviewed plan to stop watch refresh,
remove the push subscription, and remove its publisher/identity grants. Existing
Gmail watches expire naturally. Polling continues to recover mailbox changes.
Removing the subscription discards queued push notifications; those notifications
are history hints, not email content. The persisted mailbox history cursor remains
the source for polling recovery.

## References

- [Google collector on Cloud Run](https://docs.cloud.google.com/stackdriver/docs/instrumentation/opentelemetry-collector-cloud-run)
- [Authenticated Pub/Sub delivery](https://docs.cloud.google.com/pubsub/docs/authenticate-push-subscriptions)
- [Gmail push and watch renewal](https://developers.google.com/workspace/gmail/api/guides/push)
- [Private tracing contract](../adr/0007-private-lifespan-owned-tracing.md)
