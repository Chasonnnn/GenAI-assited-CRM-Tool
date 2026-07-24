# Resend integration audit and implementation handoff

Date: 2026-07-23
Scope: SurrogacyForce-native Resend, organization-owned Resend, user-owned Gmail,
templates, delivery durability, webhooks, engagement visibility, and deliverability
operations.

## Executive outcome

The repository now has one durable Resend delivery boundary for native platform
mail and organization-owned Resend mail. The implementation replaces direct,
best-effort provider calls with an immutable message snapshot, a leased
transactional outbox, resolved credential-or-team request admission,
exact-request idempotency, fenced result projection, and a verified webhook
inbox.

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
- Orphan webhook events and unknown delivery outcomes now produce sanitized,
  organization-scoped reconciliation cases. Operations users can retry local
  correlation, link signed events, dismiss controlled non-actionable events,
  or confirm an unknown delivery outcome without sending another email.
- Organization and platform operators can request a coalesced, durable,
  read-only Resend readiness check. Cached results separate domain, sending,
  webhook, delivery-event, and open/click-event readiness and retain explicit
  fresh, stale, and never-checked states.
- A write-only rate-limit group token can bind different Resend API keys from
  the same remote team to one local admission lane. Only a domain-separated
  SHA-256 fingerprint is persisted. Unconfigured routes retain exact-credential
  isolation, and Resend `429` responses advance a bounded cooldown shared by
  sibling send and control-plane requests on the resolved lane.
- RFC 8058 one-click unsubscribe POSTs are executable and covered by route
  tests. The endpoint acknowledges only a durable suppression response and
  returns a retryable `503` when the local API is unavailable.

The reconciliation workflow, live read-only readiness, and shared-team
admission slices are implemented. The highest-value remaining product
investment is a production-safe draft/publish Template Studio. Broader
deliverability signals, append-only suppression evidence, narrower diagnostics
permissions and retention policy, and connection pooling remain follow-ups.
Resend OAuth and automatic webhook provisioning are intentionally not planned.

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
- Resend admission: 5 requests/second per resolved credential-or-team
  admission identity;
- Resend idempotency window: 24 hours from the first claim.

The transport performs exactly one HTTP request per admission slot. The durable
scheduler—not the HTTP helper—owns retry timing. It honors `Retry-After` before
`ratelimit-reset`, applies bounded exponential delay otherwise, and only marks
documented transient outcomes as retryable. A `429` also advances the shared
admission lane, bounded to one hour, so sibling send and read-only control-plane
requests do not immediately repeat the same rate-limit failure.

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
operations data. Unknown outcomes now create version-fenced operator cases;
resolution actions update local evidence and never invoke provider transport.

### 3. Logical provider routes, credential fences, and shared admission identity

Every durable delivery records a logical provider account:

- `platform:default` for native platform mail;
- `organization:{organization_id}` for organization BYOK mail.

The first attempted request stores a SHA-256 credential fingerprint. Subsequent
attempts must resolve the same credential fingerprint before provider I/O. This
prevents an unresolved request from being retried through a newly configured
API key, potentially in a different Resend team namespace.

Logical provider accounts remain separate from request-admission identities.
This preserves webhook correlation, snapshot scoping, and provider-message
uniqueness while allowing one Resend team to coordinate requests across
multiple local routes.

Provider message identity has a partial uniqueness constraint on:

```text
(provider, provider_account_id, provider_message_id)
```

Admission identity resolves as follows:

- when no rate-limit group is configured, `credential:{sha256(api_key)}` keeps
  exact credentials isolated;
- when administrators assign the same write-only group token to keys from one
  Resend team, `team:{domain_separated_sha256(group_token)}` gives those keys
  one shared lane;
- platform-native Resend can use the equivalent secret environment setting;
- sending, API-key validation, and live readiness use the same resolver.

The group token is trimmed, length-bounded, case-sensitive, write-only, and
never persisted or returned. Organization settings expose only whether a group
is configured; the database stores only its lowercase fingerprint. Existing
rows remain ungrouped without a data backfill, preserving their prior
exact-credential behavior.

This is explicit local configuration, not remote team discovery. Resend does
not expose the required team identifier through these request paths. Keys from
the same remote team share a lane only when administrators configure the same
group token, so rollout and rotation must be coordinated operationally.

### 4. Resolved-identity no-burst request admission

`email_provider_admission_service.py` serializes request reservations with a
database row lock and PostgreSQL `clock_timestamp()`. At the default 5
requests/second setting, each resolved admission identity receives one slot
every 200 ms with no application-side burst. This matches Resend's current
official default of 5 requests/second per team.

This prevents independent workers from each assuming they own the full
allowance and eliminates inline transport retries that would bypass admission.
Traffic using an identical key converges automatically. Distinct keys remain
isolated unless their administrators explicitly assign the same team group.
On a `429`, the row-locked deferral moves the resolved lane forward
monotonically; a shorter concurrent deferral cannot move it backward.

Each provider call still constructs its own async HTTP client. Shared connection
pooling is a performance follow-up, not a correctness blocker.

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
event revives a previously failed reconciliation job. Stale reconciliation
claims are swept and recovered with fencing; exhausted correlation moves to an
`action_required` case instead of disappearing.

The shadcn Email Operations workspace exposes a sanitized reconciliation queue
for two case types:

- `orphan_webhook` for a signed event that cannot yet be linked to a local
  message;
- `unknown_delivery` for a delivery whose provider acceptance is uncertain.

Operations users with `OPS_MANAGE` can retry local correlation, link an orphan
to an organization-scoped message, dismiss only controlled unsupported/test/
non-actionable events, or confirm that an unknown delivery was or was not sent.
Every mutation is organization-scoped, CSRF-protected, optimistic-version
fenced, and audited. None of these actions sends email. Later verified provider
evidence remains authoritative and can supersede a prior operator
`not_sent` resolution.

Legacy platform events without the required non-PII correlation tags are still
acknowledged as unsupported and cannot be recovered automatically. Alerting,
queue-age service levels, and retention/export policy for resolved cases remain
operational follow-ups.

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
webhook provisioning are not planned. Implemented readiness checks compare
read-only remote state with the expected local domain, endpoint, and event set.
They use provider `GET` operations only and never create, modify, or delete
provider resources.

### 8. Email Operations and case visibility

The organization-scoped read API provides:

- send and tracking capability separately;
- stored configuration checks and observed webhook evidence;
- cached live Resend readiness with explicit freshness;
- a last-24-hours summary of messages, attempts, webhook events, delivery
  outcomes, estimated opens, and clicks;
- stable cursor pagination for messages;
- sanitized per-message attempts and provider event milestones;
- a permission-gated reconciliation queue with audited no-send actions.

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

Live readiness uses a cache-and-job boundary:

1. organization and platform `GET` endpoints read the latest local snapshot and
   never call Resend;
2. an authorized `POST` coalesces duplicate requests and durably queues one
   read-only probe;
3. the worker checks the credential's domain list, required domain detail, and
   webhook list through admitted provider `GET` requests;
4. a configuration fingerprint fences the result, so a probe started against
   stale settings cannot overwrite current readiness.

The UI separates domain verification, sending capability, webhook endpoint,
delivery-event coverage, and estimated open/click-event coverage. It exposes
never-checked and stale states without claiming current readiness. Platform
invite readiness is advisory and does not disable invitation creation.

This is live configuration readiness, not a complete deliverability or
reputation monitor. It does not yet cover DMARC posture, custom tracking
subdomains, quota consumption, complaint/bounce trends, provider reputation,
or inbox-placement tests. Cache/message read endpoints still require only an
authenticated organization session; consider restricting recipient/subject
and provider diagnostics to an explicit email-operations role. Reconciliation
actions already require `OPS_MANAGE`, and starting a live organization check
requires `INTEGRATIONS_MANAGE`.

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

The production migration must be additive. Existing template IDs, stored
subject/body content, variables, history, and current send behavior must remain
valid byte-for-byte until an administrator explicitly publishes a new version.
Draft creation or editor adoption must not silently rewrite, re-render, archive,
or reassign existing user templates. Scheduled and queued sends must stay
pinned to the immutable content selected when they were created.

The review artifact at `docs/qa/template-studio-before-after.html` documents the
current editor and proposed staged capabilities. Its variants are complementary
feature/stage views, not mutually exclusive product choices, and the artifact
does not imply that the full Studio has been implemented.

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
| Provider admission | One slot every 200 ms at the official default 5 requests/second per resolved credential-or-team identity, with no local burst |
| Shared `429` cooldown | Send and read-only control-plane siblings on one resolved lane honor one bounded, monotonic cooldown |
| Idempotency | Automated producers reuse one payload-bound key; automatic sends stop at Resend's 24-hour safety boundary |
| Attempt budget | Default maximum of 5 provider attempts, with sanitized per-attempt evidence |
| Unknown provider outcomes | Safe retries reuse the original idempotency key; exhaustion becomes operator reconciliation rather than a false confirmed failure |
| Webhook deduplication | One provider event ID can affect engagement and campaign totals once per organization |
| Orphan acceptance | Signed unknown-message events are retained before `200` instead of being discarded during a send/commit race |
| Operator reconciliation | Exhausted orphan correlation and unknown delivery outcomes become scoped, audited cases with no-send resolution actions |
| Live readiness | Cached organization and platform views distinguish current domain, sending, webhook, delivery-event, and engagement-event state without mutating Resend |
| Queue priority | Transactional work is claimed before campaign/marketing work, with up to 10 full batches drained per worker tick |
| Campaign consistency | Recipient state is the aggregate source of truth; concurrent delivery/webhook writers are serialized by a stable lock order |
| Attachment integrity | Filename, MIME type, byte length, and SHA-256 must still match the queued manifest before every send |
| Operations visibility | A 24-hour organization summary plus message, attempt, and event timeline is available without exposing bodies or raw tracking metadata |

## Remaining work, in priority order

### P0 next product investment

1. Complete one production-safe `EmailTemplateStudio` with explicit
   draft/published/archived states, immutable published-version pinning,
   optimistic conflicts, unsaved-change protection, plaintext, preheader,
   mobile preview, typed variables, lint, and approval/publish controls.
2. Prove the template migration against production-shaped legacy rows. Existing
   stable IDs and rendered content must remain unchanged until explicit
   publish, and queued/scheduled messages must continue using their immutable
   snapshots.

### P1 operations and deliverability

1. Roll out and document one shared admission-group token per real Resend team,
   including coordinated rotation. Unset organizations intentionally remain on
   exact-credential lanes.
2. Extend live readiness with DMARC posture, custom tracking-subdomain state,
   quota visibility, recent complaint/bounce evidence, and last-test-send
   evidence without adding provider mutations.
3. Add queue-age alerts and service-level reporting for reconciliation cases,
   plus retention/export policy for resolved and dismissed cases.
4. Restrict Email Operations message and provider diagnostics to a dedicated
   permission and define retention/export/deletion policy for stored email
   bodies and raw webhook payloads.
5. Add purpose-specific sending subdomains. Resend tracking configuration is
   domain-level, so authentication/sensitive transactional links should not
   share a tracked domain with marketing mail.
6. Add suppression management backed by append-only evidence rather than only
   the current precedence-resolved row.

### P2 performance and reporting

1. Reuse a pooled HTTP client or supported SDK transport after preserving the
   current single-request/admission contract.
2. Add bounded refresh for active campaign screens so the UI converges while
   outbox and webhook work is in flight.
3. Split provider-result persistence from optional campaign/activity
   projections so an auxiliary projection fault cannot roll back a provider
   acceptance record.
4. Add deliverability trends by provider account and sending domain.
5. Add purpose-aware tracking controls and a clear click/open retention policy.

Resend OAuth and automatic remote webhook provisioning are intentionally
excluded from this roadmap. BYOK and guided manual webhook setup remain the
supported operating model.

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
- exact-credential fallback, domain-separated write-only group fingerprints,
  shared-team resolution across different keys, platform and organization
  configuration, and the absence of raw group tokens from storage and API
  responses;
- send, key-validation, and readiness wiring through the same admission
  identity while logical provider-account routes remain unchanged;
- bounded, monotonic shared `429` cooldowns for both send and read-only
  control-plane traffic;
- platform, invite, campaign, workflow, and test-send producer cutovers;
- webhook signature rejection, `svix-id` deduplication, orphan acceptance,
  unordered lifecycle events, concurrent engagement events, provider-ID
  conflicts, fast-webhook/send-response races, reconciliation resolution,
  retryable-failure and final-lease races both before and after verified
  acceptance, suppressions, and campaign aggregates;
- fenced recovery of stale/exhausted reconciliation jobs, scoped and sanitized
  case listing, permission/CSRF/version enforcement, audited retry/link/dismiss/
  confirm actions, cross-organization rejection, and the guarantee that
  operator actions do not send email;
- read-only Resend control-plane sanitization, admitted domain/webhook requests,
  configuration-fenced snapshots, stale and never-checked states, coalesced
  durable checks, cache-only `GET` routes, and platform-scoped worker jobs;
- organization scoping and sanitization of Email Operations APIs;
- Email Operations reconciliation and live-readiness UI states, case
  engagement, restricted-key onboarding, write-only group settings, and
  template history/rollback behavior;
- retry-stable test/campaign/shared-intake occurrences, partial campaign
  feedback, API-enforced sender-identity revalidation, campaign cancellation
  races, stale appointment occurrences, terminal template-load states, and
  one-click unsubscribe success/failure handling.

## Verification status for the current stack

This handoff does not reuse the earlier full-suite totals or browser-QA claims
for the new reconciliation, live-readiness, and shared-admission slices. Record
fresh consolidated counts only after the current stack completes its final
backend, frontend, migration, and rendered-browser gates.

The final gate should include:

- Alembic upgrade/current/check on a disposable database through
  `20260723_0270_add_resend_admission_group_identity`;
- focused reconciliation, readiness, admission-identity, settings, dispatch,
  control-plane, and UI tests followed by the complete backend and frontend
  suites;
- Ruff, ESLint, and TypeScript checks;
- rendered desktop and mobile QA for Email Operations reconciliation, live
  readiness, platform invite readiness, and the write-only admission-group
  setting, including loading, empty, stale, queued, error, and conflict states;
- console inspection and a final secret/PII exposure review.

Local QA must not send external email. Cache-only readiness reads and local job
queueing can be exercised without a worker or provider call. If a readiness
worker is exercised with provider responses, use controlled test doubles unless
separate credential authorization is supplied. The production readiness
implementation itself is read-only: it issues provider `GET` requests and never
creates, changes, or deletes Resend domains, webhooks, or other resources.

## Official references

- [Resend docs for agents](https://resend.com/docs/ai-onboarding)
- [Send email API](https://resend.com/docs/api-reference/emails/send-email)
- [API errors](https://resend.com/docs/api-reference/errors)
- [Idempotency keys: 24-hour retention](https://resend.com/docs/dashboard/emails/idempotency-keys)
- [Rate limit: 5 requests/second per team by default](https://resend.com/docs/api-reference/rate-limit)
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
