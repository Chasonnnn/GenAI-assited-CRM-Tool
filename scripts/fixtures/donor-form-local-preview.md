# EWI donor form preview

One platform template and one organization form use `scripts/fixtures/ewi-donor-pre-screening.json`. The first required question selects Egg donor or Sperm donor. All 19 fields appear on one questionnaire page, followed by review. Date of birth has no age eligibility filter. A PNG/JPEG profile photo is required.

Seven fields map to the donor record: donor type, name, email, phone, state, education, and profile photo. The published donor-type mapping determines each applicant's subtype. Other answers remain in the submission.

The seed script requires `ENV=dev`, database `crm_donor_preview` at `127.0.0.1:5549`, and API URL `http://127.0.0.1:8027`. It targets the synthetic organization created by `/dev/seed` and uses development login with CSRF-protected form APIs. Rerunning updates the shared template and form, retains their IDs, disables old separate preview links, and hides the old preview templates from that organization's library. Existing submissions remain stored.

```sh
cd apps/api
uv run python ../../scripts/preview_donor_forms.py
```

The website preview uses port 3027 and the CRM web application uses port 3037. Local environment files and development secrets are excluded from Git.

## Embedded preview

The compact `/embed/forms` renderer rejects file uploads. The development-only `/prototype/donor-intake/[slug]` route reuses the hosted CRM form with autosave, uploads, validation, review, and submission. It requires the local API and permits framing only from `http://127.0.0.1:3027`. Production frame protection remains unchanged.

The wrapper links to the single EWI privacy notice preview at `http://127.0.0.1:3027/prototype/privacy/`.

## Reusable consent field

The form-builder library includes an optional, unchecked Opt-in Consent checkbox. Authors can edit its label and description and add Markdown links to their privacy notice and terms. It records a form answer and does not enable SMS sending. Name and phone remain separate fields. The donor fixture does not automatically include this checkbox.

SMS remains unconfigured in the seeded preview. Tracking uses `internal_only`.
