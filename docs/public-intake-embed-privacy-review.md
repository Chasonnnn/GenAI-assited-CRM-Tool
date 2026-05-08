# Public Intake Embed Privacy Review

Public Intake Embed is a privacy-safe website intake and CRM routing surface. It is not designed or documented as a way to bypass advertising-platform review, data-source classification, or health/wellness restrictions.

## V1 Data Flow
1. A customer website loads the SurrogacyForce embed script.
2. The script creates a sandboxed iframe for `/embed/forms/{slug}`.
3. The iframe requests public form configuration from `/forms/public/embed/{slug}`.
4. The iframe creates a short-lived embed session for the allowed parent origin.
5. The applicant submits a lead-capture form.
6. SurrogacyForce stores CRM intake records and queues privacy-safe tracking metadata when enabled.

## Captured Internally
- Full name.
- Email and/or phone.
- Lead form answers.
- Allowlisted attribution:
  - `utm_source`
  - `utm_medium`
  - `utm_campaign`
  - `utm_term`
  - `utm_content`
  - `ad_id`
  - `adset_id`
  - `campaign_id`
  - `fbclid`
  - `fbc`
  - `fbp`
  - `referrer`
  - `landing_url`
- Consent text snapshot.
- Privacy policy URL snapshot.
- Hashed IP and user-agent for abuse controls and consent evidence.
- Published form/config/tracking hashes for historical interpretation.

## Not Sent To Meta By Default
- Form answers.
- Field labels.
- Free-text values.
- Pregnancy history.
- Medical details.
- BMI.
- Insurance details.
- Financial details.
- File data or file metadata.
- Qualification status.
- Disqualification reason.
- Compensation tier.
- Hashed email, phone, or name.
- Arbitrary URL parameters.

## Tracking Policy
`privacy_safe_lead` creates only a generic lead event payload in `TrackingEventLog`:
- `event_name = Lead`
- stable event id
- action source
- neutral embed source path
- generic content metadata
- allowlisted non-sensitive campaign fields when present

The feature does not inject Meta Pixel into the customer site and does not read or write customer-site cookies.

## Field Classification Rules
Lead-capture fields must have a sensitivity classification. In privacy-safe mode, publish/embed settings are blocked if the form contains:
- file upload fields
- sensitive health fields
- sensitive reproductive fields
- sensitive financial fields
- sensitive legal fields
- free-text-unclassified fields
- unclassified fields

## Customer-Facing Positioning
Use this wording:

> Public Intake Embed helps collect website leads, route them into SurrogacyForce, capture consent, and preserve first-party attribution. It does not guarantee that an advertising platform will classify the destination differently.

Avoid this wording:
- Meta bypass
- tracking workaround
- domain evasion
- medical flag workaround
- cloaking
- alternate review destination

## Pilot Privacy Gate
- [ ] Lead form contains contact-only fields.
- [ ] Consent text is present and snapshotted.
- [ ] `privacy_safe_lead` health check is ready.
- [ ] Tracking log payload has no PII or answers.
- [ ] postMessage payload has no PII or answers.
- [ ] Browser console has no accidental answer logging.

