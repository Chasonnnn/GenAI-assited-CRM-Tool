# Resend integration audit and implementation handoff

Date: 2026-07-23
Scope: SurrogacyForce-native Resend, organization-owned Resend, user-owned Gmail,
templates, delivery durability, webhooks, engagement visibility, and deliverability
operations.

## Executive outcome

The repository now has one durable Resend delivery boundary for native platform
mail and organization-owned Resend mail. The implementation replaces direct,
best-effort provider calls with an immutable message snapshot, a leased
transactional outbox, credential-scoped request admission, exact-request
idempotency, fenced result projection, and a verified webhook inbox.

The highest-risk defects found in the audit are addressed:

- Resend `409` responses are classified by error type. An
  `invalid_idempotent_request` is terminal; only
  `concurrent_idempotent_requests` is retryable.
- Every provider request is made by the durable dispatcher. Platform, campaign,
  organization workflow, organization template test-send, and invite producers
  queue work instead of calling Resend directly.
- Resend's 24-hour idempotency window is represented locally. Unknown network
  outcomes retry only with the exact same key while that window is safe; an
  exhausted or expired unknown outcome moves to `reconciliation_required`.
  A successful HTTP response without a provider message ID is reconciled
  immediately.
- Webhook signatures are checked against the unmodified request body, accepted
  events are deduplicated by `svix-id`, and lifecycle projection is safe for
  at-least-once, unordered delivery. A fast webhook cannot be overwritten by a
  later send response or retryable transport failure. A final expired lease is
  reconciled instead of falsely failed, and signed evidence can resolve it
  whether the webhook arrives before or after expiry.
- Organization onboarding accepts permission-limited Sending access keys,
  requires an explicit domain and sender, and no longer silently selects the
  first domain returned by Resend. Changing a stored sender identity now
  requires same-request credential revalidation in both the API and UI.
- A sanitized, organization-scoped Email Operations surface exposes readiness,
  24-hour metrics, messages, attempts, and provider events. Opens are labeled
  as estimates, and pre-send states never claim that a message was sent.
- Organization template history and append-only rollback are available in the
  existing editor. Test sends and platform campaigns keep one client-held
  occurrence key across retries, and partial campaign failures remain visible.
- RFC 8058 one-click unsubscribe POSTs are executable and covered by route
  tests. The endpoint acknowledges only a durable suppression response and
  returns a retryable `503` when the local API is unavailable.

This is a material reliability upgrade, but it is not the end state. The most
important remaining gaps are long-lived orphan-event operations, remote
domain/webhook verification, cross-organization Resend-team rate identity,
append-only suppression evidence, and a full draft/publish template studio.

## Non-negotiable channel boundaries

These channels have different identity, credential, and user-expectation
contracts and must remain explicit:

| Channel | Sender identity | Credential owner | Current delivery path | Intended use |
| --- | --- | --- | --- | --- |
| SurrogacyForce native | SurrogacyForce domain | Platform | Platform Resend transactional outbox | Invitations and native system mail |
| Organization Resend | Organization verified domain | Organization | Organization Resend transactional outbox | Campaigns, organization workflows, and organization test sends |
| User Gmail | Signed-in user's work Gmail | User | Gmail API | Human-authored one-to-one case mail and personal-scope workflow mail |

Manual case email remains Gmail-only. It does not fall back to platform or
organization Resend when Gmail is disconnected. That preserves the visible
human sender, the user's mailbox history, and the product distinction between
human correspondence and system automation.

## What is implemented

### 1. One immutable, transactional Resend outbox

Evidence:

- `apps/api/app/services/email_delivery_service.py`
- `apps/api/app/services/email_delivery_dispatch.py`
- `apps/api/app/services/resend_transport.py`
- `apps/api/app/jobs/handlers/email.py`
- `apps/api/app/worker.py`
- `apps/api/app/db/models/email.py`

The queue transaction stores:

- normalized recipient and sender identity;
- subject, HTML, generated plaintext, reply-to, headers, and safe tags;
- source, purpose, template, case, actor, and job correlation;
- provider scope and logical provider account;
- a stable idempotency key and immutable request fingerprint;
- an ordered attachment manifest containing filename, type, byte count, and
  SHA-256, without storing attachment bytes in the outbox row.

The same transaction creates the `EmailLog`, attachment links, and
`EmailDelivery`. Suppressed messages are recorded as skipped without creating
send work. Before provider I/O, the dispatcher rechecks suppression, campaign
eligibility, stored request integrity, attachment metadata and bytes, lease
ownership, credential identity, and idempotency expiry.

Producer cutovers include:

- platform mail and invitations;
- repeatable platform system campaigns with a client-held occurrence UUID;
- organization campaign recipients and retries;
- organization workflow email;
- organization email/template test sends;
- appointment notifications whose audit state changes only with the linked
  provider outcome; every confirmation, reminder, reschedule, and cancellation
  occurrence is revalidated immediately before provider I/O, while
  rescheduling/cancellation atomically fence stale queued occurrences;
- the legacy `SEND_EMAIL` job, which is migrated into the outbox rather than
  making a provider call.

The source-boundary test permits `resend_transport.send_email` only in
`email_delivery_dispatch.py`.

### 2. Leases, retries, and ambiguous outcomes

Delivery rows use fencing tokens, attempt records, `FOR UPDATE SKIP LOCKED`
claims on PostgreSQL, stale-lease reclamation, and a terminal attempt budget.
Current operational defaults are:

- batch size: 10;
- maximum batches drained per worker tick: 10;
- delivery lease: 120 seconds;
- maximum attempts per message: 5;
- Resend admission: 10 requests/second per exact credential fingerprint;
- Resend idempotency window: 24 hours from the first claim.

The transport performs exactly one HTTP request per admission slot. The durable
scheduler—not the HTTP helper—owns retry timing. It honors `Retry-After` before
`ratelimit-reset`, applies bounded exponential delay otherwise, and only marks
documented transient outcomes as retryable.

Claims prefer transactional messages over campaign/marketing work. A full
delivery batch is drained immediately, up to the per-tick bound, before the
worker enters its normal job-poll sleep.

Important failure semantics:

- invalid credentials, sender/domain errors, invalid payloads, and
  `invalid_idempotent_request` are terminal;
- rate-limit `429`, transient `5xx`, network failures, timeouts, and
  `concurrent_idempotent_requests` may be retried with the exact idempotency
  key;
- daily or monthly quota exhaustion requires account action and is not retried;
- a `2xx` without a provider message ID is ambiguous and requires
  reconciliation;
- a read/write/network failure whose provider outcome may be unknown retries
  safely within the attempt and idempotency bounds, then requires
  reconciliation instead of being mislabeled as a confirmed failure;
- a retry that would cross the 24-hour provider idempotency window requires
  reconciliation and is never sent automatically; its attempt is recorded as
  terminal rather than falsely advertising a scheduled retry;
- a changed provider credential after an attempt has begun requires
  reconciliation and is never used for the retry.

Terminal failure and `reconciliation_required` are visible in the message
operations data, but there is not yet an operator retry/reconcile action.

### 3. Provider-account and credential binding

Every durable delivery records a logical provider account:

- `platform:default` for native platform mail;
- `organization:{organization_id}` for organization BYOK mail.

The first attempted request stores a SHA-256 credential fingerprint. Subsequent
attempts must resolve the same credential fingerprint before provider I/O. This
prevents an unresolved request from being retried through a newly configured
API key, potentially in a different Resend team namespace.

Provider message identity has a partial uniqueness constraint on:

```text
(provider, provider_account_id, provider_message_id)
```

The credential fingerprint is both a retry safety fence and the request-
admission key. Two organizations using the exact same API key share one
application-side lane. It is not Resend team discovery: Resend does not expose a
team identifier through the send path used here. If two organizations configure
different API keys belonging to the same Resend team, the application cannot
coordinate their shared official 10 requests/second team pool. This limitation
must remain in production documentation until a stable remote account/team
identity is available.

### 4. Credential-scoped no-burst request admission

`email_provider_admission_service.py` serializes request reservations with a
database row lock and PostgreSQL `clock_timestamp()`. At the default 10
requests/second setting, each exact credential fingerprint receives one slot
every 100 ms with no application-side burst.

This prevents independent workers from each assuming they own the full
allowance and eliminates inline transport retries that would bypass admission.
Traffic using an identical key converges on one lane; traffic using distinct
keys remains isolated even when those keys belong to one remote team.

The remaining cross-organization same-team limitation is described above.
Also, each send currently constructs its own async HTTP client; shared
connection pooling is a performance follow-up, not a correctness blocker.

### 5. Verified webhook inbox and monotonic projection

Evidence:

- `apps/api/app/routers/webhooks.py`
- `apps/api/app/services/webhooks/resend.py`
- `apps/api/app/jobs/handlers/resend.py`
- `apps/api/app/db/models/email.py`

Platform and organization webhooks:

1. read the raw request body once;
2. enforce a payload-size bound;
3. require configured signing secrets;
4. validate Svix headers, signature, and timestamp before parsing JSON;
5. persist a tenant-scoped event with a unique provider event ID;
6. return `200` after durable acceptance;
7. project immediately when the email is known, or enqueue correlation when it
   is not.

The inbox stores provider event time, received time, processed time, type, and
raw JSON payload. Duplicate `svix-id` deliveries do not increment engagement or
campaign aggregates twice.

Projection covers:

- scheduled, sent, delayed, delivered, failed, and suppressed;
- bounced and complained;
- opened and clicked.

Lifecycle state is rank-monotonic and uses provider event timestamps. Higher
milestones can advance state even when delivered out of order, while an older
equal-rank event cannot regress the projection. Provider event and email rows
are locked during processing. Campaign run, campaign, recipient, and delivery
updates use a consistent lock order and recompute totals from recipient state,
so concurrent outbox and webhook projections do not publish stale totals.

Signed non-PII `organization_id` and `email_log_id` tags are resolved before
legacy provider-message lookup. This closes the race where a webhook arrives
before the provider response is committed locally. The webhook locks the
linked outbox row, validates provider-message identity, resolves
`reconciliation_required` when signed evidence proves acceptance, and
preserves the original ambiguous attempt as audit evidence. The later provider
response merges acceptance monotonically and cannot regress delivered,
bounced, failed, suppressed, or complained state. If that response is instead a
retryable failure—or the worker disappears until its final lease expires—the
verified provider identity still resolves the outbox as accepted and prevents a
duplicate retry while preserving the webhook's canonical message state. Without
that evidence, the expired final lease becomes `reconciliation_required`
instead of a false dead-letter; a later signed webhook can still resolve it.

An unmatched event with a known organization is retained and receives a
bounded reconciliation job. The current job has eight attempts with
exponential delay, survives the 120-second send lease, and a duplicate signed
event revives a previously failed reconciliation job. There is no durable
sweeper, alert, operator queue, or long-retention dead-letter workflow after
those attempts. Legacy platform events without the required non-PII
correlation tags are acknowledged as unsupported and are not recoverable
locally.

### 6. Suppression and campaign safety

Queueing checks suppressions before an outbox row is created, and dispatch
checks again after the admission wait and immediately before provider I/O.
Campaign delivery also rechecks that the campaign, run, and recipient remain
eligible. Cancelling a campaign prevents pending or retry-scheduled rows from
being sent. Full-send and retry execution acquire the canonical run-to-campaign
locks and cannot overwrite a concurrent cancelled state.

Suppression reasons have serial precedence:

```text
archived < opt_out < bounced < complaint
```

Permanent/hard bounce values suppress; non-permanent values are preserved as
evidence without automatic permanent suppression. Complaints receive the
highest suppression precedence.

`add_to_suppression` uses one PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`
statement with precedence encoded in SQL. Concurrent first events converge on
one tenant-scoped row, and a weaker event cannot overwrite stronger evidence.
The remaining limitation is historical: evidence is represented by one mutable
row rather than an append-only suppression-event history.

### 7. Least-privilege organization onboarding

Organization setup now requires the administrator to supply both the verified
domain and sender when saving a new API key. Full-access keys use `GET /domains`
as evidence that the supplied domain is verified. Resend's named error
contract is enforced: HTTP `401` with `restricted_api_key` is accepted as
permission-limited Sending access, while HTTP `403` with `invalid_api_key` and
unknown authentication errors fail closed.

This does not prove that a permission-limited key can send from the asserted
domain. The UI clearly warns about that limitation, and the first queued test
send plus resulting provider evidence remains the operational proof. If a
stored verified domain or From address changes, Save is disabled until the
administrator re-enters and tests the credential again; the API independently
rejects a bypass attempt that omits same-request credential validation.

The API key and webhook secret remain encrypted at rest and write-only through
the API. The product intentionally uses BYOK with guided manual webhook setup.
Resend OAuth, PKCE, refresh-token rotation, revocation, and automatic remote
webhook provisioning are not planned. Read-only readiness checks may compare
the remote configuration with the expected local endpoint and event set, but
they must never create, modify, or delete provider resources.

### 8. Email Operations and case visibility

The organization-scoped read API provides:

- send and tracking capability separately;
- stored configuration checks and observed webhook evidence;
- a last-24-hours summary of messages, attempts, webhook events, delivery
  outcomes, estimated opens, and clicks;
- stable cursor pagination for messages;
- sanitized per-message attempts and provider event milestones.

The shadcn-based UI is available at:

```text
/settings/integrations/email
```

It deliberately excludes message bodies, raw provider payloads, raw click URLs,
recipient IP addresses, user agents, lease tokens, raw keys, and raw error
messages. Case activity also exposes delivery and engagement summaries. Opens
are labeled **estimated opens**, not proof that a human read a message. The
detail view uses neutral recipient language for pending, suppressed, cancelled,
and reconciliation states; `reconciliation_required` is visibly action-needed.

Current readiness is persisted-evidence readiness, not a live Resend
deliverability audit. It does not remotely recheck the current key, SPF, DKIM,
DMARC, webhook subscriptions, tracking subdomain, quotas, or reputation. The
read endpoints currently require an authenticated organization session but not
a narrower operations permission; consider restricting recipient/subject and
provider diagnostics to an explicit email-operations role.

### 9. Template history and rollback

The existing organization template editor now has a shadcn Sheet for version
history and an explicit rollback confirmation. A rollback creates a new
version; it never overwrites the audit trail. Test sends are queued through the
durable organization Resend path, and the UI truthfully reports “queued” rather
than claiming immediate provider acceptance. Organization and platform
test-send retries reuse the same payload-bound occurrence key. Platform
campaign partial failures keep the selection dialog open with a sanitized
shadcn error state so successful recipients can deduplicate while failed
recipients are retried.

This is not yet a complete Template Studio. Remaining work:

- explicit draft, published, and archived states;
- immutable published-version pinning for scheduled sends;
- optimistic editor conflict handling and unsaved-change protection;
- first-class preheader, plaintext, mobile preview, and content/link lint;
- typed variables with required and fallback values;
- purpose-aware tracking and unsubscribe checks;
- convergence of platform-hosted and organization-hosted template contracts.

Resend hosted Templates provide draft/publish, version history, rollback, and
collaborative authoring. The embedded `@react-email/editor` is also a viable
future organization editor. Either choice should publish into the same
provider-neutral immutable `RenderedEmail` contract already used by the
outbox.

## Quantified operational benefit

| Improvement | Current effect |
| --- | --- |
| Transactional queueing | Business change and email intent can commit together; a process exit before provider I/O does not lose the send intent |
| Fenced leases | At most one current lease token can project an attempt; expired workers cannot overwrite a newer attempt |
| Provider admission | One slot every 100 ms at the default 10 requests/second per exact credential, with no local burst |
| Idempotency | Automated producers reuse one payload-bound key; automatic sends stop at Resend's 24-hour safety boundary |
| Attempt budget | Default maximum of 5 provider attempts, with sanitized per-attempt evidence |
| Unknown provider outcomes | Safe retries reuse the original idempotency key; exhaustion becomes operator reconciliation rather than a false confirmed failure |
| Webhook deduplication | One provider event ID can affect engagement and campaign totals once per organization |
| Orphan acceptance | Signed unknown-message events are retained before `200` instead of being discarded during a send/commit race |
| Queue priority | Transactional work is claimed before campaign/marketing work, with up to 10 full batches drained per worker tick |
| Campaign consistency | Recipient state is the aggregate source of truth; concurrent delivery/webhook writers are serialized by a stable lock order |
| Attachment integrity | Filename, MIME type, byte length, and SHA-256 must still match the queued manifest before every send |
| Operations visibility | A 24-hour organization summary plus message, attempt, and event timeline is available without exposing bodies or raw tracking metadata |

## Remaining work, in priority order

### P0 before broad production volume

1. Add a long-lived orphan-event sweeper, alerting, and an operator
   dead-letter/replay workflow. Eight bounded reconciliation attempts are not
   enough for delayed local recovery, and Resend's manual replay capability
   should have a local operational counterpart.
2. Add an operator action for `reconciliation_required` that first queries or
   confirms provider state; never “retry” it by silently generating a new
   idempotency key.
3. Add live readiness checks for credential, domain, and webhook state. A
   historical successful domain-list request is insufficient for ongoing
   readiness.
4. Decide how shared Resend-team identity will be configured or discovered so
   different organization keys in one team share one 10 requests/second
   admission pool.

### P1 product and operations

1. Add domain-level SPF, DKIM, DMARC, custom tracking-subdomain, quota, recent
   complaint/bounce, and last-test-send evidence.
2. Add purpose-specific sending subdomains. Resend tracking configuration is
   domain-level, so authentication/sensitive transactional links should not
   share a tracked domain with marketing mail.
3. Restrict Email Operations diagnostics to a dedicated permission and define
   retention/export/deletion policy for stored email bodies and raw webhook
   payloads.
4. Reuse a pooled HTTP client or supported SDK transport after preserving the
   current single-request/admission contract.
5. Add bounded refresh for active campaign screens so the UI converges while
   outbox and webhook work is in flight.
6. Split provider-result persistence from optional campaign/activity
   projections so an auxiliary projection fault cannot roll back a provider
   acceptance record.

### P2 authoring and deliverability

1. Complete one `EmailTemplateStudio` with draft/publish/version pinning,
   plaintext, preheader, mobile preview, typed variables, lint, and approvals.
2. Add suppression management and append-only evidence UI.
3. Add deliverability trends by provider account and sending domain.
4. Add purpose-aware tracking controls and clear click/open retention policy.

## Deliverability and privacy policy

For high-volume Gmail delivery, keep these operational gates:

1. SPF and DKIM are valid for the sending subdomain.
2. DMARC is monitored, then moved toward enforcement after all legitimate
   senders are aligned.
3. Complaint/spam rate remains below Resend's documented 0.08% threshold.
4. Marketing mail has RFC 8058 one-click unsubscribe and suppression is applied
   promptly. Both GET and POST unsubscribe paths are covered; the POST path is
   the one Gmail and other mailbox subscription controls invoke. Backend
   failure returns a retryable non-success status instead of falsely
   acknowledging the opt-out.
5. TLS mode is chosen deliberately for the stream.

The linked Resend Gmail guidance specifically calls out tightening requirements
for senders above 5,000 messages/day and Gmail's subscription-management
surface. That makes a working one-click POST path an operational requirement,
not merely footer UX.

Open tracking is approximate because image blocking, proxying, and privacy
features alter the signal. Clicks are stronger engagement evidence but can also
be generated by security scanners. Disable open/click tracking for
authentication and sensitive transactional links, and use a custom tracking
subdomain where tracking is appropriate.

Email bodies are intentionally retained locally as immutable delivery
snapshots, and verified webhook JSON is retained for deduplication and audit.
Those stores require explicit role access and retention policy. Separately,
Resend documents an option for qualifying Pro/Scale accounts to disable
provider-side message-content storage through a paid add-on. That is an
account/vendor configuration decision and is not enabled by this repository.

Do not put medical, legal, recipient, or other sensitive values in subjects or
Resend tags. The current correlation tags are non-PII identifiers. Vendor
security marketing alone is not evidence of a HIPAA BAA; obtain written
vendor/legal approval before allowing PHI through Resend.

## Verification map

The implementation is covered by focused tests for:

- transport error classification, retry headers, single-attempt behavior, and
  ambiguous responses;
- outbox idempotency, immutable fingerprints, attachment manifests, leases,
  stale reclaim, idempotency expiry, credential changes, and admission;
- platform, invite, campaign, workflow, and test-send producer cutovers;
- webhook signature rejection, `svix-id` deduplication, orphan acceptance,
  unordered lifecycle events, concurrent engagement events, provider-ID
  conflicts, fast-webhook/send-response races, reconciliation resolution,
  retryable-failure and final-lease races both before and after verified
  acceptance, suppressions, and campaign aggregates;
- organization scoping and sanitization of Email Operations APIs;
- Email Operations, case engagement, restricted-key onboarding, and template
  history/rollback UI behavior;
- retry-stable test/campaign/shared-intake occurrences, partial campaign
  feedback, API-enforced sender-identity revalidation, campaign cancellation
  races, stale appointment occurrences, terminal template-load states, and
  one-click unsubscribe success/failure handling.

## Local verification

The final repository state passed:

- backend: `1984 passed` with the full pytest suite and `ruff check .`;
- frontend: `221` test files and `1402` tests passed, plus ESLint and
  `tsc --noEmit`;
- database: Alembic current/head both resolve to `20260723_0210`, and
  `alembic check` reports no pending schema operations.

Rendered browser QA used an isolated local API/web pair on ports `8002/3002`
with a seeded developer session and no external email send. The following
surfaces rendered successfully using the production component paths:

- Integrations and the shadcn Email Configuration dialog, including
  least-privilege key guidance, explicit domain/sender inputs, webhook URL and
  signing-secret setup;
- Email Operations readiness, 24-hour metrics, the open-tracking caveat,
  sanitized message table, and message-detail sheet with neutral `Recipient:`
  copy and a bounced status;
- organization/platform template tabs and the visual/HTML template editor;
- surrogate case history with Resend bounce/provider evidence.

The final browser console contained no warnings or errors. The local QA session
cookies were removed afterward, the isolated services were stopped, and the
pre-existing port-3000 development server was restored. A live Resend
credential/domain/webhook test was intentionally not performed because no
production credential or real-send authorization was in scope.

Schema revisions added by this batch run from
`20260723_0048_add_resend_webhook_events` through
`20260723_0210_link_appointment_email_delivery`.

## Official references

- [Resend docs for agents](https://resend.com/docs/ai-onboarding)
- [Send email API](https://resend.com/docs/api-reference/emails/send-email)
- [API errors](https://resend.com/docs/api-reference/errors)
- [Idempotency keys: 24-hour retention](https://resend.com/docs/dashboard/emails/idempotency-keys)
- [Rate limit: 10 requests/second per team](https://resend.com/docs/api-reference/rate-limit)
- [Webhook introduction: at-least-once and unordered](https://resend.com/docs/webhooks/introduction)
- [Webhook retries and manual replays](https://resend.com/docs/webhooks/retries-and-replays)
- [Verify webhooks using the raw body](https://resend.com/docs/webhooks/verify-webhooks-requests)
- [Webhook event catalog](https://resend.com/docs/webhooks/event-types)
- [Domain-level tracking](https://resend.com/docs/dashboard/domains/tracking)
- [Why open rates are approximate](https://resend.com/docs/knowledge-base/why-are-my-open-rates-not-accurate)
- [Resend Templates](https://resend.com/docs/dashboard/templates/introduction)
- [Template version history](https://resend.com/docs/dashboard/templates/version-history)
- [Embed the React Email editor](https://resend.com/docs/knowledge-base/embed-react-email-editor)
- [Resend tags](https://resend.com/docs/dashboard/emails/tags)
- [Account quotas and limits](https://resend.com/docs/knowledge-base/account-quotas-and-limits)
- [Disable provider-side message-content storage](https://resend.com/docs/knowledge-base/how-do-i-ensure-sensitive-data-isnt-stored-on-resend)
- [API-key permissions](https://resend.com/docs/api-reference/api-keys/create-api-key)
- [Build a Resend OAuth client](https://resend.com/docs/guides/building-a-resend-oauth-client)
- [Multi-tenant Resend options](https://resend.com/docs/knowledge-base/setting-up-resend-for-multi-tenants)
- [DMARC](https://resend.com/docs/dashboard/domains/dmarc)
- [One-click unsubscribe](https://resend.com/docs/dashboard/emails/add-unsubscribe-to-transactional-emails)
- [TLS modes](https://resend.com/docs/knowledge-base/whats-the-difference-between-opportunistic-tls-vs-enforced-tls)
- [Linked Resend Gmail guidance thread](https://x.com/resend/status/2079567941406949554)
