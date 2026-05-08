# Public Intake Embed

Public Intake Embed lets your agency place a SurrogacyForce lead form on your website. New leads flow into SurrogacyForce with consent, attribution, and CRM records.

It is not designed to bypass advertising-platform review or data-source classification.

## When To Use It
- You want website leads to appear in SurrogacyForce immediately.
- You want a short contact-first lead form.
- You want an iframe embed that is isolated from your website scripts and styling.
- You want first-party CRM attribution for website leads.

Use a deeper application form after the lead is created when you need medical, reproductive, financial, legal, or file-upload information.

## Create A Lead-Capture Form
1. Go to `Automation > Forms`.
2. Create or open a form.
3. Set `Form Purpose` to `Lead Capture`.
4. Include `Full Name`.
5. Include at least one of `Email` or `Phone`.
6. Keep the first form contact-only.
7. Publish the form.

Avoid these fields in the v1 lead form:
- medical history
- pregnancy history
- BMI
- insurance questions
- financial questions
- file uploads
- long free-text medical questions

## Enable Embed
1. Open the published form.
2. Open the share dialog.
3. Select the `Embed` tab.
4. Enable iframe embed.
5. Add exact allowed origins, for example:
   - `https://www.ewisurrogacy.com`
6. Choose `Privacy-safe Lead` unless your admin has approved another mode.
7. Add contact consent text.
8. Click `Save Embed Settings`.
9. Click `Check setup`.
10. Confirm the status is `Ready to embed`.

## Install The Snippet
Copy the snippet from the Embed tab:

```html
<div data-sf-form="PUBLIC_SLUG"></div>
<script async src="https://app.surrogacyforce.com/embed/forms.v1.js"></script>
```

Only use the current snippet shown in SurrogacyForce. The slug can change if a link is rotated.

## Wix
1. Add an Embed HTML block.
2. Paste the snippet.
3. Publish the page.
4. Test a submission.

## WordPress
1. Add a Custom HTML block.
2. Paste the snippet.
3. Publish or preview the page.
4. Test a submission.

## Webflow
1. Add an Embed element.
2. Paste the snippet.
3. Publish the site.
4. Test a submission.

## Test A Submission
1. Open the website page in a private/incognito window.
2. Submit a test lead with consent checked.
3. Confirm the thank-you state appears.
4. Confirm the lead appears in SurrogacyForce.
5. Confirm the source is website embed.
6. Confirm consent and attribution are present.

## What Is Tracked
SurrogacyForce stores the lead submission, consent snapshot, allowed attribution values, and CRM lead record.

Privacy-safe ad tracking does not send form answers, sensitive fields, uploaded files, qualification status, or hashed contact information to ad platforms by default.

## Known Limitations
- Custom domains are not part of v1.
- Native DOM embed is not part of v1.
- Full landing-page builder is not part of v1.
- Arbitrary customer pixels are not supported on embedded forms.
- Advertising-platform classification may still apply to your website or campaign destination.

