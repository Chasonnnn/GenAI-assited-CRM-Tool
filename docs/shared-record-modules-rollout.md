# Shared Record Modules Rollout

## Change boundary

- Surrogates, intended parents, and donors share note persistence, activity rendering, task sections, document controls, subject authorization, and common email contact context.
- Intended parents and donors retain lighter detail layouts than surrogates. Domain fields, stage rules, matching behavior, and existing communication channels remain separate.
- `Donors (beta)` and `Tickets (beta)` navigation remains developer-only. Existing backend permission policies remain in effect.
- Donor SMS, donor matching relationships, donor appointment relationships, and intended-parent workflow subjects are outside this change.
- This change has no database migration, schema reset, destructive data conversion, or new job payload version.
- Local checks cannot establish uninterrupted production operation. Deployment, provider behavior, and mixed-revision behavior require deployed evidence.

## Compatibility

| Combination | Expected behavior | Deployment condition |
|---|---|---|
| Existing frontend with new API | Supported routes and request fields remain valid. Optional note author names and task creator metadata are additive. | Verify read-only and edit-role flows in the canary. |
| New frontend with existing API | The new donor ownership controls require `GET /donors/owner-options`. Existing API revisions do not provide that endpoint. | Deploy the API before enabling the new frontend. |
| New API with existing workers | Existing database rows and workflow/email payloads remain readable. Older workers retain their earlier note and donor-validation behavior. | Finish the worker rollout before declaring archive and note parity complete. |
| Existing API with new workers | Workers continue to consume existing job payloads and immutable email snapshots. | Verify legacy payloads and source-job preflight results. |
| Previous application image after rollback | Persisted notes, activity, attachments, and workflow/email rows remain readable. Existing enum values cover cancelled and reconciliation-required deliveries. | Roll back complete application images; shared helper callers and implementations must stay in the same image. |

The additive owner-options endpoint returns active users and queues from the authenticated organization and requires donor-edit permission. It precedes the dynamic donor-detail route.

Task lists, single-task operations, bulk completion, and attachment operations now enforce permissions for the actual linked record. Users with task access but without the linked module's view permission no longer see or mutate those tasks. Intended-parent attachment uploads and deletes require intended-parent edit permission; downloads retain view-only access. The generic note-deletion route accepts surrogate notes only; intended-parent and donor clients retain their own existing routes. Validate permission overrides before rollout.

Task editors load the full task before allowing edits. A failed detail request offers retry; list projections cannot overwrite existing descriptions with an empty value.

Shared note operations sanitize content and persist the note and activity together. Existing manually authored notes continue to emit their existing automation events after commit. Workflow-authored notes suppress a fresh recursive event. New activity rows use existing activity types and storage.

Existing intended-parent campaign preview, launch, and send paths use the intended-parent template builder. Shared contact fields now apply the same organization scope to user and queue owner labels for all three record types. User owner labels require active user and membership records. Surrogate form and appointment variables remain surrogate-specific.

Already queued emails keep their stored recipient, content, sender, and template snapshots. The shared template builder affects newly prepared messages; it does not rewrite previously approved content.

## Email delivery behavior

| State when the donor becomes unavailable | New behavior |
|---|---|
| Workflow has not started, or a failed execution is retried | Reject the unavailable subject before actions. |
| Workflow is waiting for approval | Fail the resumed execution before actions and clear its paused references. |
| Email source job has not entered the durable outbox | Record a skipped email without provider admission. |
| Personal Gmail email is being prepared | Check the subject again immediately before provider I/O. |
| Resend delivery is queued or leased, with no earlier attempt | Check the subject during preparation and immediately before provider I/O; cancel an unavailable subject through the existing lease fence. |
| Resend delivery has an earlier attempt | Stop further sends and require reconciliation when the subject becomes unavailable. Earlier provider acceptance may be unknown. |
| Provider has accepted the email | The email cannot be recalled. Preserve the provider result and reconciliation history. |

An unavailable donor includes an archived, missing, foreign-organization, or wrong-subtype donor. Source-job retries do not overwrite an existing delivery's outcome with a new skipped result. Previous attempts are treated conservatively because the persisted attempt history does not provide a single reliable flag proving that every earlier request was rejected before acceptance.

Legacy surrogate outbox rows remain eligible when the source Job is missing but `surrogate_id` survives. Donor emails do not populate that relationship. A missing source Job without a surrogate relationship leaves the subject unverified.

Checks immediately before network I/O reduce the exposure window; they do not make database changes and provider acceptance one atomic transaction. Do not report an in-flight or ambiguously accepted email as cancelled.

## Preflight

Record the target API, web, and worker image identifiers, current healthy revision identifiers, rollback images, database migration head, and active worker count. Confirm that the release artifact contains no migration or database-model changes.

The following count-only query must return no rows before rollout, or each affected delivery requires an explicit disposition. It does not expose recipients or message content.

```sql
SELECT d.status, count(*) AS unverified_workflow_deliveries
FROM email_deliveries AS d
JOIN email_logs AS e
  ON e.id = d.email_log_id
 AND e.organization_id = d.organization_id
LEFT JOIN jobs AS j
  ON j.id = e.source_id
 AND j.organization_id = d.organization_id
WHERE e.source_type = 'workflow_job'
  AND d.status IN ('pending', 'retry_scheduled', 'leased')
  AND j.id IS NULL
  AND e.surrogate_id IS NULL
GROUP BY d.status;
```

Do not infer donor identity from rendered message content or update these rows automatically. Reconciliation must preserve any earlier provider acceptance and idempotency identity.

Record baseline API errors, authorization-denial rates, workflow failures, worker backlog, delivery retries, and reconciliation counts. Keep raw record data and provider credentials out of operational logs.

## Staging and canary checks

1. Deploy the API revision with existing frontend traffic. Verify the additive donor owner-options route, existing record routes, and optional note author fields.
2. Exercise a synthetic surrogate, intended parent, egg donor, and sperm donor in one organization. Use a second synthetic organization for denied reads, writes, relationship changes, notes, attachments, and task links.
3. Verify existing owner and non-owner roles. Check view-only file downloads, signed and local downloads, denied uploads/deletes, and edit-only ownership controls. Preserve the existing surrogate owner restrictions.
4. Create and delete notes through each supported record flow. Confirm sanitization, author display, one activity entry per operation, durable history after deletion, and unchanged successful note responses when a post-commit automation fails.
5. Verify task loading, empty, populated, error, edit, completion, and permission states. Verify document upload, scan-pending, scan-failed, clean-file download, and deletion states. Confirm intended-parent and donor pages retain their compact composition.
6. Verify donor and surrogate workflow actions, review tasks, resumed approvals, retries, and note-trigger recursion limits. Archive a synthetic donor between approval creation and resolution; confirm that no action runs afterward.
7. Compare newly rendered contact, owner, branding, and unsubscribe variables across surrogate, intended-parent, and donor email templates. Preserve each domain's identifier and status labels. Confirm existing pending emails retain their immutable snapshots.
8. With approved non-production provider credentials, verify a donor archived before source-job processing, after outbox admission, and during delayed dispatch. Simulate an ambiguous earlier provider result and verify reconciliation without a second send. Verify a legacy surrogate source-job case and a normal intended-parent campaign.
9. Deploy the frontend only after the API revision serves the owner-options route. Verify developer-only beta navigation and direct-route permission behavior. Verify both old frontend/new API and new frontend/new API combinations during transition.
10. Roll workers through the same tested application artifact. Allow existing leases to finish or expire under their existing fencing rules. Do not delete jobs or clear lease tokens to accelerate replacement.
11. Compare canary errors, workflow outcomes, queue age, retries, and reconciliation counts with the baseline. Confirm the changed rendered states in a real browser before expanding traffic.

## Rollback

Stop traffic expansion when changed flows fail. Retain failed execution identifiers, delivery identifiers, revision identifiers, and sanitized error classes for diagnosis.

Restore the previous frontend before restoring an API revision that lacks the owner-options route. New API revisions can serve the previous frontend during this transition.

Restore API and worker images as complete units. Allow already running delivery attempts to complete under their existing lease fencing. Do not restore old database backups, remove new note/activity rows, reset idempotency keys, or replay terminal emails as part of application rollback.

Cancelled and reconciliation-required deliveries stay in their recorded state. Review their disposition individually; a rollback is not approval to resend. Old workers also restore the earlier donor archive-validation behavior, so record that limitation until the corrected worker revision is restored.

Verify the restored revision through synthetic record, task, attachment, note, and email-preview paths. A healthy process or successful HTTP response alone does not establish that the affected user flow works.

## Release evidence

Local validation, deployed canary results, provider integration results, traffic changes, and rollback verification are separate evidence. The release record must name which checks ran, their target revision, and any remaining gate.

Local results are recorded in [shared-record-modules-verification.md](/Users/chason/GenAI-assited-CRM-Tool/docs/shared-record-modules-verification.md).
