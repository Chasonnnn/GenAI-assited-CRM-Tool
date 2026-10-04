# Integration and security supplemental QA

Revision `65bca746e`; 2026-10-04. Synthetic admin session on the isolated local QA database. No real provider credentials, OAuth connections, message delivery, or authentication changes.

## Google Calendar and Meet

- Personal integrations shows Zoom/Gmail Not connected and synthetic Google Calendar Connected.
- Manage dialog shows account, absolute/relative last-sync time, Scheduling QA as booking destination, owner role, conflict/display checkboxes, and Meet availability.
- Destination menu shows `No booking calendar` and `Scheduling QA` labels. Selecting no calendar marks the form dirty; Cancel discards it and reopening restores Scheduling QA.
- Both Check conflicts and Show events can be unchecked and saved; full page reload preserves both unchecked values.
- Both toggles were restored and saved; reopening confirms checked values and disabled Save changes when clean.
- Sync now shows `Sync queued`; the old successful timestamp remains until the restricted synthetic calendar job runs. After job completion and reload, last sync updates to4:35 PM.
- Disconnect opens a confirmation describing the effect. Cancel preserves the connected integration.
- Google Tasks unavailable is shown separately from Calendar/Meet availability.

[Synced calendar management](integrations-calendar-synced.jpg).

## Organization integration readiness

| Surface | Observed state |
| --- | --- |
| AI Configuration | Disabled, consent required, Enable disabled, blank API key, Test disabled; Cancel works |
| Resend email configuration | Blank credentials/domain/sender; Test and Save disabled |
| Gmail email configuration | No eligible connected admin senders; Save disabled; Cancel works |
| Meta configuration | Not configured; dataset fields and stage mappings render with human labels; configuration/monitoring tabs work |
| Meta monitoring | Four automatic synthetic stage events correctly Skipped as Not a Meta lead; Retry disabled |
| Zapier card | One local fixture webhook Active; surrogate/donor reporting disabled; secret-bearing configuration was not opened |
| Messaging delivery | After fixture repair, launch gates show missing credentials/consent/approval/worker/route; SMS/MMS capabilities Unavailable; PHI control disabled |
| Messaging route setup | Operational Set up route expands service SID and sender fields without saving |
| Email Operations | Not checked/not configured; no messages/reconciliation cases; diagnostics expand to unavailable sending/tracking and no provider evidence |

Provider tests, OAuth connection, AI consent acceptance, and enabling delivery were not performed.

## Fixture issue, excluded from product findings

The communications fixture created TwilioSettings with only the operational route. Production `get_or_create_settings` creates operational and promotional routes together. Opening Messaging initially caused `TypeError: Cannot read properties of undefined (reading 'enabled')` in `initialRouteDraft` because the fixture lacked the promotional route.

The missing route was added only to the disposable database using standard defaults. Reloading Messaging then rendered normally. This is a fixture-induced error, not a confirmed application regression. The pre-repair screenshot is retained as diagnostic provenance: [fixture error](integrations-messaging-crash.jpg).

## Security and sessions

- Security shows Duo Unavailable and disables Set Up Duo in this credential-free environment.
- `/settings/sessions` resolves to General settings with Active Sessions, local device/browser/last-active information, Current marker, and revoke controls for other sessions.
- No session was revoked and no two-factor or account setting was changed.
- Console review shows the one fixture-induced Messaging error above; no additional warning/error occurred during subsequent integration/security checks.

## Approval review limits

Automatic approval review rejected clicking `Send Meta CRM Test Event` and `Test connection` for Twilio, citing possible external provider interaction and the no-external-sends restriction. Neither action executed or was retried through another path. Provider test controls remain untested; the rest of this pass uses local UI and synthetic Calendar transport.
