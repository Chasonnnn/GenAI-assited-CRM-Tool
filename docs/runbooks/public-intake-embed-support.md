# Public Intake Embed Support Runbook

Use this runbook when an agency has trouble embedding or submitting a Public Intake Embed form.

## Quick Triage
1. Open the form share dialog.
2. Go to the `Embed` tab.
3. Click `Check setup`.
4. Record whether the status is `Ready to embed`, `Needs attention`, or `Blocked`.

Do not request or paste applicant names, emails, phone numbers, answers, or screenshots containing applicant PII into support tickets unless the secure support process requires it.

## Where To Look
- `FormIntakeLink`: embed enabled, allowed origins, tracking mode, consent text.
- `PublishedIntakeVersion`: frozen form/config/tracking snapshot.
- `EmbedSession`: parent origin, expiry, consumed state, hashed IP/user-agent.
- `FormSubmission`: raw immutable submission record.
- `IntakeLead`: operational CRM lead.
- `LeadAttribution`: allowlisted attribution.
- `ConsentRecord`: consent text and privacy policy snapshots.
- `TrackingEventLog`: privacy-safe outbound tracking payload.
- Browser console: CSP/frame errors and postMessage errors.
- Response headers: `Content-Security-Policy`, `Cache-Control`, `X-Frame-Options`.

## Iframe Does Not Load
Likely causes:
- Embed is disabled.
- Allowed origin is missing or does not exactly match the website origin.
- Form is not published.
- Wrong slug.
- Dynamic frame policy lookup failed.

Checks:
```bash
curl -I "https://<web-base>/embed/forms/<slug>"
curl -sS "https://<api-base>/forms/public/embed/<slug>/frame-policy"
```

Expected embed document headers:
- no `X-Frame-Options`
- `Content-Security-Policy: frame-ancestors 'self' <allowed-origin>`
- `Cache-Control: no-store`

## Origin Mismatch
Allowed origins must be exact origins:
- Good: `https://www.ewisurrogacy.com`
- Bad: `https://www.ewisurrogacy.com/page`
- Bad: `https://*.ewisurrogacy.com`
- Bad: `https://www.ewisurrogacy.com.evil.com`

In local development, HTTP localhost origins may be used when dev mode is enabled.

## Session Errors
Symptoms:
- Submit returns 403.
- Browser shows expired or invalid session.

Likely causes:
- Session expired.
- Session was already consumed.
- Session belongs to a different intake link.
- Parent origin was not allowed.

Fix:
- Refresh the parent page.
- Confirm allowed origin.
- Confirm the iframe is using the current slug.

## Submission Succeeds But Lead Is Missing
Check:
- `FormSubmission.intake_lead_id`
- `IntakeLead.source = form_embed`
- duplicate email/phone behavior
- lead queue filters
- workflow errors after submission commit

The immutable `FormSubmission` is the source of truth. If it exists without a visible lead, inspect the lead creation and workflow logs using non-PII IDs only.

## Privacy-Safe Tracking Event Missing
Check:
- `FormIntakeLink.tracking_mode`
- setup health `Tracking policy`
- `TrackingEventLog` for the submission

No Meta event should be logged when tracking mode is `internal_only` or `disabled`.

## Rollback
Preferred rollback order:
1. Disable embed on the intake link.
2. Disable embed for the organization if an org-level flag exists.
3. Disable Public Intake Embed globally if a global flag exists.
4. Disable privacy-safe tracking only if submit should continue but outbound tracking should stop.

Rollback expectations:
- Existing hosted `/intake/{slug}` links continue working.
- Existing CRM leads and submissions remain intact.
- Existing embedded iframe should fail closed or show an unavailable state.
- Normal rollback should not require database migration rollback.

## Pilot Script
1. Create a test agency.
2. Create a `lead_capture` form.
3. Include full name and email or phone.
4. Add contact consent text.
5. Enable embed.
6. Add an allowed test origin.
7. Publish and copy the snippet.
8. Submit test leads:
   - valid email only
   - valid phone only
   - email and phone
   - duplicate email
   - duplicate phone
   - missing consent
   - expired session
   - disallowed origin
   - mobile viewport
9. Verify CRM, attribution, consent, tracking log, and setup health.

